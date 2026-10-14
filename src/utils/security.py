#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用安全工具——加密原语。

本模块只放与业务无关的安全原语，供开放 API 认证等上层模块复用：
- SHA256 哈希
- HMAC-SHA256 签名计算
- Fernet 对称加解密（主密钥从 settings.AUTH_SECRET_KEY 派生）
- 常量时间字符串比对（防时序侧信道）
- 高熵随机密钥 / AppKey 生成
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet

from src.core.config import settings
from src.core.logger import logger


# ============================================================
# 随机密钥
# ============================================================
def generate_secret_key() -> str:
    """生成随机安全密钥（用于 AUTH_SECRET_KEY 初始化或密钥轮换）。"""
    return secrets.token_urlsafe(48)


def generate_app_key() -> str:
    """生成开放 API 应用 AppKey（高熵 urlsafe 串，带 gk_ 前缀便于识别）。"""
    return f"gk_{secrets.token_urlsafe(32)}"


# ============================================================
# SHA256
# ============================================================
def sha256_hex(text: str) -> str:
    """返回 text 的 SHA256 hex 摘要。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ============================================================
# 常量时间比对
# ============================================================
def constant_time_equals(a: str, b: str) -> bool:
    """常量时间字符串比对，防时序侧信道攻击。"""
    return hmac.compare_digest(a or "", b or "")


# ============================================================
# HMAC-SHA256
# ============================================================
def hmac_sha256_hex(key: str, message: str) -> str:
    """返回 HMAC-SHA256(key, message) 的 hex 摘要。"""
    return hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ============================================================
# Fernet 对称加解密
# ============================================================
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """惰性构造 Fernet 实例。

    主密钥从 settings.AUTH_SECRET_KEY 派生（加固定 domain 前缀后 SHA256）。
    注意：轮换 AUTH_SECRET_KEY 会导致已加密的密文无法解密，属于预期行为——
    轮换主密钥是大事，需要单独的重加密脚本。
    """
    global _fernet
    if _fernet is None:
        secret = settings.AUTH_SECRET_KEY
        if not secret:
            logger.warning(
                "AUTH_SECRET_KEY 未配置，使用内置开发密钥（生产环境必须配置，"
                "否则 AppKey 密文与签名主密钥可被破解）"
            )
            secret = "dev-only-secret-key-do-not-use-in-production"
        material = hashlib.sha256(f"guanhai-master-key::{secret}".encode()).digest()
        _fernet = Fernet(base64.urlsafe_b64encode(material))
    return _fernet


def encrypt_text(plaintext: str) -> str:
    """加密任意字符串，返回 urlsafe 串落库。"""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_text(ciphertext: str | None) -> str | None:
    """解密。密文为空或解密失败返回 None。"""
    if not ciphertext:
        return None
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        logger.warning("Fernet decrypt failed (ciphertext may be tampered)")
        return None


__all__ = [
    "generate_secret_key",
    "generate_app_key",
    "sha256_hex",
    "constant_time_equals",
    "hmac_sha256_hex",
    "encrypt_text",
    "decrypt_text",
]
