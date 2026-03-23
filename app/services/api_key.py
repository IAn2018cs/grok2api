"""API Key 管理模块 - 支持多 API Key 管理"""

import os
import secrets
import string
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

import orjson
import aiofiles
from pydantic import BaseModel

from app.core.logger import logger

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent.parent.parent / "data")).expanduser()
API_KEY_FILE = DATA_DIR / "api_keys.json"


class APIKeyInfo(BaseModel):
    key: str
    note: str = ""
    expire_time: Optional[int] = None
    ip_whitelist: List[str] = []
    created_time: int
    last_used_time: Optional[int] = None
    status: str = "active"  # active, disabled, expired


class APIKeyManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.api_keys: Dict[str, APIKeyInfo] = {}
            self._initialized = True

    async def load(self):
        try:
            if not API_KEY_FILE.exists():
                self.api_keys = {}
                return
            async with aiofiles.open(API_KEY_FILE, "rb") as f:
                content = await f.read()
            data = orjson.loads(content)
            self.api_keys = {}
            for key, value in data.items():
                try:
                    self.api_keys[key] = APIKeyInfo(**value)
                except Exception as e:
                    logger.error(f"[APIKey] 解析失败: {key[:20]}, {e}")
            logger.info(f"[APIKey] 已加载 {len(self.api_keys)} 个 API Key")
        except Exception as e:
            logger.error(f"[APIKey] 加载失败: {e}")
            self.api_keys = {}

    async def save(self):
        try:
            data = {key: info.model_dump() for key, info in self.api_keys.items()}
            API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = API_KEY_FILE.with_suffix(".tmp")
            async with aiofiles.open(tmp, "wb") as f:
                await f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))
            os.replace(tmp, API_KEY_FILE)
        except Exception as e:
            logger.error(f"[APIKey] 保存失败: {e}")

    @staticmethod
    def generate_key() -> str:
        alphabet = string.ascii_letters + string.digits
        return "sk-" + "".join(secrets.choice(alphabet) for _ in range(45))

    async def create(self, note: str = "", expire_time: Optional[int] = None,
                     ip_whitelist: Optional[List[str]] = None) -> APIKeyInfo:
        while True:
            key = self.generate_key()
            if key not in self.api_keys:
                break
        info = APIKeyInfo(
            key=key,
            note=note,
            expire_time=expire_time,
            ip_whitelist=ip_whitelist or [],
            created_time=int(datetime.now().timestamp() * 1000),
        )
        self.api_keys[key] = info
        await self.save()
        logger.info(f"[APIKey] 创建: {key[:20]}...")
        return info

    async def delete(self, key: str) -> bool:
        if key not in self.api_keys:
            return False
        del self.api_keys[key]
        await self.save()
        return True

    async def update(self, key: str, note: Optional[str] = None, expire_time: Optional[int] = None,
                     ip_whitelist: Optional[List[str]] = None, status: Optional[str] = None) -> bool:
        if key not in self.api_keys:
            return False
        info = self.api_keys[key]
        if note is not None:
            info.note = note
        if expire_time is not None:
            info.expire_time = expire_time
        if ip_whitelist is not None:
            info.ip_whitelist = ip_whitelist
        if status is not None:
            info.status = status
        await self.save()
        return True

    def verify(self, key: str, client_ip: Optional[str] = None) -> tuple[bool, str]:
        if key not in self.api_keys:
            return False, "API Key 不存在"
        info = self.api_keys[key]
        if info.status == "disabled":
            return False, "API Key 已被禁用"
        if info.status == "expired":
            return False, "API Key 已过期"
        if info.expire_time is not None:
            if int(datetime.now().timestamp() * 1000) > info.expire_time:
                info.status = "expired"
                import asyncio
                asyncio.create_task(self.save())
                return False, "API Key 已过期"
        if info.ip_whitelist and client_ip:
            if not self._check_ip(client_ip, info.ip_whitelist):
                return False, f"IP {client_ip} 不在白名单"
        info.last_used_time = int(datetime.now().timestamp() * 1000)
        import asyncio
        asyncio.create_task(self.save())
        return True, ""

    @staticmethod
    def _check_ip(client_ip: str, whitelist: List[str]) -> bool:
        import ipaddress
        try:
            ip = ipaddress.ip_address(client_ip)
            for pattern in whitelist:
                try:
                    if "/" in pattern:
                        if ip in ipaddress.ip_network(pattern, strict=False):
                            return True
                    elif ip == ipaddress.ip_address(pattern):
                        return True
                except ValueError:
                    continue
            return False
        except ValueError:
            return False

    def all(self) -> List[APIKeyInfo]:
        return list(self.api_keys.values())

    def stats(self) -> Dict[str, Any]:
        vals = self.api_keys.values()
        return {
            "total": len(self.api_keys),
            "active": sum(1 for k in vals if k.status == "active"),
            "disabled": sum(1 for k in vals if k.status == "disabled"),
            "expired": sum(1 for k in vals if k.status == "expired"),
        }


api_key_manager = APIKeyManager()
