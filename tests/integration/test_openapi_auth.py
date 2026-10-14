"""
开放 API 认证鉴权测试

覆盖：GuanHai-1 签名协议 / 网关 authenticate / 管理面 CRUD /
FastAPI 集成全链路（签名请求 → 401/403/200）。
"""

import json
from datetime import UTC, datetime, timedelta
from email.utils import formatdate

import httpx
import pytest
from fastapi import Depends, FastAPI

from src.constants.scopes import OpenApiScopeCode
from src.core import signature
from src.core.config import settings
from src.core.exceptions import UnauthorizedError, ValidationError
from src.http_server.dependencies import require_app_scope
from src.infras.database import get_session
from src.repositories.openapi_app_repository import OpenApiAppRepository
from src.schemas.openapi_app import OpenApiAppCreateRequest, OpenApiAuthContext
from src.services.gateway_service import OpenGatewayService
from src.services.openapi_app_service import OpenApiAppService
from src.utils import security

# ──────────────────────────────────────────────────────────
# 夹具
# ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def openapi_enabled():
    """开启鉴权（conftest 默认关闭以保护既有测试）。"""
    settings.openapi.enabled = True
    yield
    settings.openapi.enabled = False


@pytest.fixture(scope="module")
def admin_service(openapi_enabled):
    """管理面服务 + 会话（数据库由 conftest session fixture 初始化）。"""
    session = get_session()
    svc = OpenApiAppService(repo=OpenApiAppRepository(session=session))
    yield svc, session
    session.close()


def _signed_headers(
    app_id: str,
    app_key: str,
    method: str,
    uri: str,
    body: bytes = b"",
    *,
    date: str | None = None,
) -> dict[str, str]:
    """生成 GuanHai-1 签名请求头（与服务端协议同源）。"""
    date = date or formatdate(timeval=None, localtime=False, usegmt=True)
    sig = signature.sign(
        app_key=app_key,
        method=method,
        uri=uri,
        content_type="application/json",
        date=date,
        body=body,
    )
    return {
        "X-App-Id": app_id,
        "X-App-Date": date,
        "X-App-Authorization": f"GuanHai-1 {app_id}:{sig}",
    }


# ──────────────────────────────────────────────────────────
# 签名协议单元测试
# ──────────────────────────────────────────────────────────


class TestSignatureProtocol:
    def test_build_signing_string_structure(self):
        s = signature.build_signing_string(
            method="GET",
            uri="/api/v1/rag/stats",
            content_type="application/json",
            date="Mon, 13 Oct 2026 00:00:00 GMT",
            body=b"",
        )
        # Ver + METHOD + URI + Content-Type + Date + (空 body → 空摘要)
        assert s == (
            "GuanHai-1GET/api/v1/rag/statsapplication/json" "Mon, 13 Oct 2026 00:00:00 GMT"
        )

    def test_build_signing_string_with_body(self):
        body = b'{"query":"hi"}'
        s = signature.build_signing_string(
            method="POST",
            uri="/api/v1/rag/query",
            content_type="application/json",
            date="Mon, 13 Oct 2026 00:00:00 GMT",
            body=body,
        )
        assert s.endswith(security.sha256_hex(body.decode("utf-8")))

    def test_sign_verify_roundtrip(self):
        date = "Mon, 13 Oct 2026 00:00:00 GMT"
        body = b'{"query":"hi"}'
        sig = signature.sign(
            app_key="gk_secret",
            method="POST",
            uri="/api/v1/rag/query",
            content_type="application/json",
            date=date,
            body=body,
        )
        assert signature.verify_signature(
            app_key="gk_secret",
            method="POST",
            uri="/api/v1/rag/query",
            content_type="application/json",
            date=date,
            body=body,
            signature=sig,
        )
        # 错误 key 必然失败
        assert not signature.verify_signature(
            app_key="gk_wrong",
            method="POST",
            uri="/api/v1/rag/query",
            content_type="application/json",
            date=date,
            body=body,
            signature=sig,
        )

    def test_request_date_window(self):
        now = formatdate(timeval=None, localtime=False, usegmt=True)
        assert signature.is_request_date_valid(now)
        old = formatdate(
            timeval=(datetime.now(UTC) - timedelta(seconds=3600)).timestamp(),
            localtime=False,
            usegmt=True,
        )
        assert not signature.is_request_date_valid(old)
        assert not signature.is_request_date_valid("not-a-date")
        assert not signature.is_request_date_valid("")


# ──────────────────────────────────────────────────────────
# 管理面测试
# ──────────────────────────────────────────────────────────


class TestAdminService:
    def test_create_app_stores_hash_not_plaintext(self, admin_service):
        svc, session = admin_service
        created = svc.create_app(OpenApiAppCreateRequest(name="测试应用", scopes=["rag:read"]))
        session.commit()
        entity = OpenApiAppRepository(session=session).get_by_app_id(created.app_id)
        assert entity is not None
        # 不存明文：哈希 + Fernet 密文，且密文可解密回原文
        assert entity.app_key_hash == security.sha256_hex(created.app_key)
        assert entity.app_key_hash != created.app_key
        assert entity.app_key_encrypted is not None
        assert security.decrypt_text(entity.app_key_encrypted) == created.app_key

    def test_create_app_rejects_invalid_scope(self, admin_service):
        svc, session = admin_service
        with pytest.raises(ValidationError):
            svc.create_app(OpenApiAppCreateRequest(name="坏scope", scopes=["nope:read"]))

    def test_revoke_enable_flow(self, admin_service):
        svc, session = admin_service
        created = svc.create_app(OpenApiAppCreateRequest(name="启停测试", scopes=["rag:read"]))
        session.commit()
        revoked = svc.revoke_app(created.app_id)
        session.commit()
        assert revoked.status == "disabled"
        enabled = svc.enable_app(created.app_id)
        session.commit()
        assert enabled.status == "active"

    def test_list_apps_pagination(self, admin_service):
        svc, session = admin_service
        result = svc.list_apps(page=1, page_size=5)
        assert result.total >= 1
        assert len(result.items) == min(5, result.total)
        # 列表项不应包含任何密钥字段
        item = result.items[0]
        assert not hasattr(item, "app_key")


# ──────────────────────────────────────────────────────────
# 网关 authenticate 测试
# ──────────────────────────────────────────────────────────


class TestGatewayAuthenticate:
    async def test_authenticate_ok(self, admin_service):
        svc, session = admin_service
        created = svc.create_app(
            OpenApiAppCreateRequest(name="网关成功", scopes=["rag:read", "document:read"])
        )
        session.commit()
        date = formatdate(timeval=None, localtime=False, usegmt=True)
        uri = "/api/v1/rag/query"
        body = b'{"query":"hi"}'
        ctx = OpenApiAuthContext(
            app_id=created.app_id,
            authorization=f"GuanHai-1 {created.app_id}:{signature.sign(app_key=created.app_key, method='POST', uri=uri, content_type='application/json', date=date, body=body)}",
            date=date,
            method="POST",
            uri=uri,
            body=body,
        )
        gateway = OpenGatewayService(repo=OpenApiAppRepository(session=session))
        current = await gateway.authenticate(ctx)
        assert current.app_id == created.app_id
        assert current.scopes == ["rag:read", "document:read"]

    async def test_authenticate_wrong_key(self, admin_service):
        svc, session = admin_service
        created = svc.create_app(OpenApiAppCreateRequest(name="网关错key", scopes=["rag:read"]))
        session.commit()
        date = formatdate(timeval=None, localtime=False, usegmt=True)
        uri = "/api/v1/rag/stats"
        body = b""
        ctx = OpenApiAuthContext(
            app_id=created.app_id,
            authorization=f"GuanHai-1 {created.app_id}:{signature.sign(app_key='gk_wrong', method='GET', uri=uri, content_type='application/json', date=date, body=body)}",
            date=date,
            method="GET",
            uri=uri,
            body=body,
        )
        gateway = OpenGatewayService(repo=OpenApiAppRepository(session=session))
        with pytest.raises(UnauthorizedError):
            await gateway.authenticate(ctx)

    async def test_authenticate_disabled_app(self, admin_service):
        svc, session = admin_service
        created = svc.create_app(OpenApiAppCreateRequest(name="网关停用", scopes=["rag:read"]))
        session.commit()
        svc.revoke_app(created.app_id)
        session.commit()
        date = formatdate(timeval=None, localtime=False, usegmt=True)
        uri = "/api/v1/rag/stats"
        body = b""
        ctx = OpenApiAuthContext(
            app_id=created.app_id,
            authorization=f"GuanHai-1 {created.app_id}:{signature.sign(app_key=created.app_key, method='GET', uri=uri, content_type='application/json', date=date, body=body)}",
            date=date,
            method="GET",
            uri=uri,
            body=body,
        )
        gateway = OpenGatewayService(repo=OpenApiAppRepository(session=session))
        with pytest.raises(UnauthorizedError):
            await gateway.authenticate(ctx)

    async def test_authenticate_stale_date(self, admin_service):
        svc, session = admin_service
        created = svc.create_app(OpenApiAppCreateRequest(name="网关过期", scopes=["rag:read"]))
        session.commit()
        stale = formatdate(
            timeval=(datetime.now(UTC) - timedelta(seconds=3600)).timestamp(),
            localtime=False,
            usegmt=True,
        )
        uri = "/api/v1/rag/stats"
        body = b""
        ctx = OpenApiAuthContext(
            app_id=created.app_id,
            authorization=f"GuanHai-1 {created.app_id}:{signature.sign(app_key=created.app_key, method='GET', uri=uri, content_type='application/json', date=stale, body=body)}",
            date=stale,
            method="GET",
            uri=uri,
            body=body,
        )
        gateway = OpenGatewayService(repo=OpenApiAppRepository(session=session))
        with pytest.raises(UnauthorizedError):
            await gateway.authenticate(ctx)


# ──────────────────────────────────────────────────────────
# FastAPI 集成测试（签名请求全链路）
# ──────────────────────────────────────────────────────────


@pytest.fixture
def openapi_test_app(openapi_enabled):
    """最小 FastAPI 应用：apps 管理路由 + rag:read 保护路由。"""
    from fastapi.responses import JSONResponse

    from src.core.exceptions import AppException
    from src.http_server.v1.openapi_app import router as app_router
    from src.services.audit_service import AuditService

    app = FastAPI(title="openapi-auth-test")
    app.state.audit_service = AuditService()
    app.include_router(app_router, prefix="/api/v1")

    @app.exception_handler(AppException)
    async def app_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.code,
            content={"code": exc.code, "message": exc.message, "detail": exc.detail},
        )

    @app.get(
        "/api/v1/test/rag",
        dependencies=[Depends(require_app_scope(OpenApiScopeCode.RAG_READ.mark))],
    )
    async def test_rag():
        return {"ok": True}

    return app


class TestFastAPIIntegration:
    async def test_full_flow(self, openapi_test_app, admin_service):
        svc, session = admin_service
        # 准备：admin 应用（仅 admin scope）
        admin = svc.create_app(OpenApiAppCreateRequest(name="集成-admin", scopes=["admin"]))
        session.commit()

        create_body = json.dumps(
            {"name": "集成-rag", "scopes": ["rag:read"]}, ensure_ascii=False
        ).encode()
        transport = httpx.ASGITransport(app=openapi_test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. 无签名 → 401
            r = await client.post(
                "/api/v1/apps", content=create_body, headers={"Content-Type": "application/json"}
            )
            assert r.status_code == 401

            # 2. 签名错误 → 401
            bad_headers = _signed_headers(
                admin.app_id, "gk_wrong", "POST", "/api/v1/apps", create_body
            )
            bad_headers["Content-Type"] = "application/json"
            r = await client.post("/api/v1/apps", content=create_body, headers=bad_headers)
            assert r.status_code == 401

            # 3. admin 签名创建 rag 应用 → 201（明文 key 返回一次）
            ok_headers = _signed_headers(
                admin.app_id, admin.app_key, "POST", "/api/v1/apps", create_body
            )
            ok_headers["Content-Type"] = "application/json"
            r = await client.post("/api/v1/apps", content=create_body, headers=ok_headers)
            assert r.status_code == 201, r.text
            data = r.json()["data"]
            rag_app_id, rag_app_key = data["app_id"], data["app_key"]

            # 4. rag 应用（rag:read）访问受保护路由 → 200
            r = await client.get(
                "/api/v1/test/rag",
                headers=_signed_headers(rag_app_id, rag_app_key, "GET", "/api/v1/test/rag"),
            )
            assert r.status_code == 200, r.text
            assert r.json()["ok"] is True

            # 5. rag 应用无 admin scope 访问管理面 → 403
            r = await client.post(
                "/api/v1/apps",
                content=create_body,
                headers={
                    **_signed_headers(rag_app_id, rag_app_key, "POST", "/api/v1/apps", create_body),
                    "Content-Type": "application/json",
                },
            )
            assert r.status_code == 403

            # 6. 吊销后即使签名正确 → 401
            svc.revoke_app(rag_app_id)
            session.commit()
            r = await client.get(
                "/api/v1/test/rag",
                headers=_signed_headers(rag_app_id, rag_app_key, "GET", "/api/v1/test/rag"),
            )
            assert r.status_code == 401
