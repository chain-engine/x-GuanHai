#!/usr/bin/env python3
"""开放接口（网关）业务逻辑。

承载开放接口域（/api/v1 下受保护资源，供外部应用 / 第三方 Agent 调用）的核心逻辑：
1. 应用身份鉴权（authenticate）：AppId 查询 + GuanHai-1 签名校验（时间窗 + 重算签名）；
2. 签名 / 解签协议纯函数已下沉至 src/core/signature.py；
   FastAPI Request 由 API 层（api/open/dependencies.get_current_app）转换为
   OpenApiAuthContext 纯数据后传入，本层不依赖 Web 框架对象。

与开放平台门户（自然人登录）严格区分：本域只认机器身份（App）。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.constants import OPENAPI_CONTENT_TYPE
from src.core import signature
from src.core.config import settings
from src.core.exceptions import UnauthorizedError
from src.repositories.openapi_app_repository import OpenApiAppRepository
from src.schemas.openapi_app import OpenApiAuthContext, OpenApiCurrentApp
from src.utils import security
from src.utils.openapi import parse_scopes


class OpenGatewayService:
    """开放接口网关鉴权服务（每请求调用，仅做身份与签名校验，不触碰业务数据）。"""

    def __init__(self, repo: OpenApiAppRepository) -> None:
        self._repository = repo

    async def authenticate(self, ctx: OpenApiAuthContext) -> OpenApiCurrentApp:
        """解析开放接口应用身份。

        鉴权流程：
            1. 应用存在且启用（status=active）；
            2. GuanHai-1 签名校验：X-App-Date 时间窗 + Fernet 解密 secret 重算 HMAC；
            3. 常量时间比对通过后返回 OpenApiCurrentApp（含 scopes）。

        Args:
            ctx: API 层从 FastAPI Request 剥离的鉴权上下文（纯数据）
        """
        if not ctx.app_id:
            raise UnauthorizedError(message="缺少请求头 X-App-Id")
        app = self._repository.get_by_app_id(ctx.app_id)
        if app is None or app.status != "active":
            raise UnauthorizedError(message="App 无效或已停用")

        if not self._verify_hmac_signature(app_encrypted=app.app_key_encrypted, ctx=ctx):
            raise UnauthorizedError(message="应用鉴权失败")

        # 更新 last_used_at（失败不阻断主流程）
        try:
            self._repository.touch_last_used(app.app_id)
        except Exception:
            pass

        return OpenApiCurrentApp(
            app_id=app.app_id,
            name=app.name,
            scopes=parse_scopes(app.scopes),
            auth_mode=app.auth_mode or "hmac",
            rate_limit_per_minute=app.rate_limit_per_minute,
        )

    def _verify_hmac_signature(self, *, app_encrypted: str | None, ctx: OpenApiAuthContext) -> bool:
        """GuanHai-1 签名解签：时间窗 + 解密 secret + 调用 core.signature 重算比对。

        本方法只做鉴权编排；协议计算全部委托 src/core/signature.py。
        """
        # 1. 时间窗：X-App-Date 缺失或超窗一律拒绝
        if not ctx.date or not signature.is_request_date_valid(
            ctx.date, window_seconds=settings.OPENAPI_SIGNATURE_WINDOW_SECONDS
        ):
            return False
        # 2. 解密取回明文 secret
        secret = security.decrypt_text(app_encrypted)
        if not secret:
            return False
        # 3. 提取 Authorization 中的签名值
        # 格式：GuanHai-1 {app_id}:{signature}
        authorization = ctx.authorization
        if not authorization:
            return False
        parts = authorization.split(":", 1)
        if len(parts) != 2 or not parts[1]:
            return False
        # 4. 解签：重算签名并常量时间比对（协议 Content-Type 固定 application/json）
        return signature.verify_signature(
            app_key=secret,
            method=ctx.method,
            uri=ctx.uri,
            content_type=OPENAPI_CONTENT_TYPE,
            date=ctx.date,
            body=ctx.body,
            signature=parts[1].strip(),
        )


def build_gateway_service(session: Session) -> OpenGatewayService:
    """构建开放接口网关鉴权服务（组装 Repo；供 API 依赖工厂复用）。

    Repo 实例化收敛在 services 层，api 层只声明依赖、不直接接触数据访问层。
    """
    return OpenGatewayService(repo=OpenApiAppRepository(session=session))


async def authenticate_request(ctx: OpenApiAuthContext) -> OpenApiCurrentApp:
    """HTTP / MCP 双出口共用的请求级鉴权入口。

    会话获取、Repo 组装、事务（提交 / 回滚 / 关闭）全部收敛在 services 层，
    接入层（HTTP Depends / MCP 中间件）只需构造 OpenApiAuthContext 后调用，
    不接触数据库与会话。

    Args:
        ctx: 接入层剥离的鉴权上下文（纯数据）

    Returns:
        OpenApiCurrentApp: 鉴权通过的应用身份（含 scopes / 限流配置）

    Raises:
        UnauthorizedError: 应用不存在 / 停用 / 签名校验失败
    """
    from src.infras.database import get_session  # 延迟导入：避免组装期模块循环依赖

    session = get_session()
    try:
        gateway = build_gateway_service(session)
        current = await gateway.authenticate(ctx)
        session.commit()  # 落库 touch_last_used（best-effort，失败不阻断）
        return current
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["OpenGatewayService", "build_gateway_service", "authenticate_request"]
