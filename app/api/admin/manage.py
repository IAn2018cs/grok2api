"""管理接口 - Token管理和系统配置"""

import secrets
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.core.config import setting
from app.core.logger import logger
from app.services.grok.token import token_manager
from app.models.grok_models import TokenType


router = APIRouter(tags=["管理"])

# 常量
STATIC_DIR = Path(__file__).parents[2] / "template"
TEMP_DIR = Path(__file__).parents[3] / "data" / "temp"
IMAGE_CACHE_DIR = TEMP_DIR / "image"
VIDEO_CACHE_DIR = TEMP_DIR / "video"
SESSION_EXPIRE_HOURS = 24
BYTES_PER_KB = 1024
BYTES_PER_MB = 1024 * 1024

# 会话存储
_sessions: Dict[str, datetime] = {}


# === 请求/响应模型 ===

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str


class AddTokensRequest(BaseModel):
    tokens: List[str]
    token_type: str
    proxy_url: Optional[str] = None
    cache_proxy_url: Optional[str] = None
    cf_clearance: Optional[str] = None


class DeleteTokensRequest(BaseModel):
    tokens: List[str]
    token_type: str


class TokenInfo(BaseModel):
    token: str
    token_type: str
    created_time: Optional[int] = None
    remaining_queries: int
    heavy_remaining_queries: int
    status: str
    tags: List[str] = []
    note: str = ""
    proxy_url: Optional[str] = None
    cache_proxy_url: Optional[str] = None
    cf_clearance: Optional[str] = None


class TokenListResponse(BaseModel):
    success: bool
    data: List[TokenInfo]
    total: int


class UpdateSettingsRequest(BaseModel):
    global_config: Optional[Dict[str, Any]] = None
    grok_config: Optional[Dict[str, Any]] = None


class UpdateTokenTagsRequest(BaseModel):
    token: str
    token_type: str
    tags: List[str]


class UpdateTokenNoteRequest(BaseModel):
    token: str
    token_type: str
    note: str


class UpdateTokenProxyRequest(BaseModel):
    token: str
    token_type: str
    proxy_url: Optional[str] = None
    cache_proxy_url: Optional[str] = None
    cf_clearance: Optional[str] = None


class TestTokenRequest(BaseModel):
    token: str
    token_type: str


class CreateAPIKeyRequest(BaseModel):
    note: str = ""
    expire_time: Optional[int] = None
    ip_whitelist: Optional[List[str]] = None


class UpdateAPIKeyRequest(BaseModel):
    key: str
    note: Optional[str] = None
    expire_time: Optional[int] = None
    ip_whitelist: Optional[List[str]] = None
    status: Optional[str] = None


class DeleteAPIKeyRequest(BaseModel):
    key: str


# === 辅助函数 ===

def validate_token_type(token_type_str: str) -> TokenType:
    """验证Token类型"""
    if token_type_str not in ["sso", "ssoSuper"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "无效的Token类型", "code": "INVALID_TYPE"}
        )
    return TokenType.NORMAL if token_type_str == "sso" else TokenType.SUPER


def parse_created_time(created_time) -> Optional[int]:
    """解析创建时间"""
    if isinstance(created_time, str):
        return int(created_time) if created_time else None
    elif isinstance(created_time, int):
        return created_time
    return None


def calculate_token_stats(tokens: Dict[str, Any], token_type: str) -> Dict[str, int]:
    """计算Token统计"""
    total = len(tokens)
    expired = sum(1 for t in tokens.values() if t.get("status") == "expired")

    if token_type == "normal":
        unused = sum(1 for t in tokens.values()
                    if t.get("status") != "expired" and t.get("remainingQueries", -1) == -1)
        limited = sum(1 for t in tokens.values()
                     if t.get("status") != "expired" and t.get("remainingQueries", -1) == 0)
        active = sum(1 for t in tokens.values()
                    if t.get("status") != "expired" and t.get("remainingQueries", -1) > 0)
    else:
        unused = sum(1 for t in tokens.values()
                    if t.get("status") != "expired" and
                    t.get("remainingQueries", -1) == -1 and t.get("heavyremainingQueries", -1) == -1)
        limited = sum(1 for t in tokens.values()
                     if t.get("status") != "expired" and
                     (t.get("remainingQueries", -1) == 0 or t.get("heavyremainingQueries", -1) == 0))
        active = sum(1 for t in tokens.values()
                    if t.get("status") != "expired" and
                    (t.get("remainingQueries", -1) > 0 or t.get("heavyremainingQueries", -1) > 0))

    return {"total": total, "unused": unused, "limited": limited, "expired": expired, "active": active}


def verify_admin_session(authorization: Optional[str] = Header(None)) -> bool:
    """验证管理员会话"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": "未授权访问", "code": "UNAUTHORIZED"})
    
    token = authorization[7:]
    
    if token not in _sessions:
        raise HTTPException(status_code=401, detail={"error": "会话无效", "code": "SESSION_INVALID"})
    
    if datetime.now() > _sessions[token]:
        del _sessions[token]
        raise HTTPException(status_code=401, detail={"error": "会话已过期", "code": "SESSION_EXPIRED"})
    
    return True


def get_token_status(token_data: Dict[str, Any], token_type: str) -> str:
    """获取Token状态"""
    if token_data.get("status") == "expired":
        return "失效"
    
    remaining = token_data.get("remainingQueries", -1)
    heavy_remaining = token_data.get("heavyremainingQueries", -1)
    
    relevant = max(remaining, heavy_remaining) if token_type == "ssoSuper" else remaining
    
    if relevant == -1:
        return "未使用"
    elif relevant == 0:
        return "限流中"
    else:
        return "正常"


def _calculate_dir_size(directory: Path) -> int:
    """计算目录大小"""
    total = 0
    for file_path in directory.iterdir():
        if file_path.is_file():
            try:
                total += file_path.stat().st_size
            except Exception as e:
                logger.warning(f"[Admin] 无法获取文件大小: {file_path.name}, {e}")
    return total


def _format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    size_mb = size_bytes / BYTES_PER_MB
    if size_mb < 1:
        return f"{size_bytes / BYTES_PER_KB:.1f} KB"
    return f"{size_mb:.1f} MB"


# === 页面路由 ===

@router.get("/login", response_class=HTMLResponse)
async def login_page():
    """登录页面"""
    login_html = STATIC_DIR / "login.html"
    if login_html.exists():
        return login_html.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="登录页面不存在")


@router.get("/manage", response_class=HTMLResponse)
async def manage_page():
    """管理页面"""
    admin_html = STATIC_DIR / "admin.html"
    if admin_html.exists():
        return admin_html.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="管理页面不存在")


# === API端点 ===

@router.post("/api/login", response_model=LoginResponse)
async def admin_login(request: LoginRequest) -> LoginResponse:
    """管理员登录"""
    try:
        logger.debug(f"[Admin] 登录尝试: {request.username}")

        expected_user = setting.global_config.get("admin_username", "")
        expected_pass = setting.global_config.get("admin_password", "")

        if request.username != expected_user or request.password != expected_pass:
            logger.warning(f"[Admin] 登录失败: {request.username}")
            return LoginResponse(success=False, message="用户名或密码错误")

        session_token = secrets.token_urlsafe(32)
        _sessions[session_token] = datetime.now() + timedelta(hours=SESSION_EXPIRE_HOURS)

        logger.debug(f"[Admin] 登录成功: {request.username}")
        return LoginResponse(success=True, token=session_token, message="登录成功")

    except Exception as e:
        logger.error(f"[Admin] 登录异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"登录失败: {e}", "code": "LOGIN_ERROR"})


@router.post("/api/logout")
async def admin_logout(_: bool = Depends(verify_admin_session), authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """管理员登出"""
    try:
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:]
            if token in _sessions:
                del _sessions[token]
                logger.debug("[Admin] 登出成功")
                return {"success": True, "message": "登出成功"}

        logger.warning("[Admin] 登出失败: 无效会话")
        return {"success": False, "message": "无效的会话"}

    except Exception as e:
        logger.error(f"[Admin] 登出异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"登出失败: {e}", "code": "LOGOUT_ERROR"})


@router.get("/api/tokens", response_model=TokenListResponse)
async def list_tokens(_: bool = Depends(verify_admin_session)) -> TokenListResponse:
    """获取Token列表"""
    try:
        logger.debug("[Admin] 获取Token列表")

        all_tokens = token_manager.get_tokens()
        token_list: List[TokenInfo] = []

        # 普通Token
        for token, data in all_tokens.get(TokenType.NORMAL.value, {}).items():
            token_list.append(TokenInfo(
                token=token,
                token_type="sso",
                created_time=parse_created_time(data.get("createdTime")),
                remaining_queries=data.get("remainingQueries", -1),
                heavy_remaining_queries=data.get("heavyremainingQueries", -1),
                status=get_token_status(data, "sso"),
                tags=data.get("tags", []),
                note=data.get("note", ""),
                proxy_url=data.get("proxy_url", ""),
                cache_proxy_url=data.get("cache_proxy_url", ""),
                cf_clearance=data.get("cf_clearance", "")
            ))

        # Super Token
        for token, data in all_tokens.get(TokenType.SUPER.value, {}).items():
            token_list.append(TokenInfo(
                token=token,
                token_type="ssoSuper",
                created_time=parse_created_time(data.get("createdTime")),
                remaining_queries=data.get("remainingQueries", -1),
                heavy_remaining_queries=data.get("heavyremainingQueries", -1),
                status=get_token_status(data, "ssoSuper"),
                tags=data.get("tags", []),
                note=data.get("note", ""),
                proxy_url=data.get("proxy_url", ""),
                cache_proxy_url=data.get("cache_proxy_url", ""),
                cf_clearance=data.get("cf_clearance", "")
            ))

        logger.debug(f"[Admin] Token列表获取成功: {len(token_list)}个")
        return TokenListResponse(success=True, data=token_list, total=len(token_list))

    except Exception as e:
        logger.error(f"[Admin] 获取Token列表异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"获取失败: {e}", "code": "LIST_ERROR"})


@router.post("/api/tokens/add")
async def add_tokens(request: AddTokensRequest, _: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """批量添加Token"""
    try:
        logger.debug(f"[Admin] 添加Token: {request.token_type}, {len(request.tokens)}个")

        token_type = validate_token_type(request.token_type)
        await token_manager.add_token(
            request.tokens,
            token_type,
            proxy_url=request.proxy_url,
            cache_proxy_url=request.cache_proxy_url,
            cf_clearance=request.cf_clearance
        )

        logger.debug(f"[Admin] Token添加成功: {len(request.tokens)}个")
        return {"success": True, "message": f"成功添加 {len(request.tokens)} 个Token", "count": len(request.tokens)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin] Token添加异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"添加失败: {e}", "code": "ADD_ERROR"})


@router.post("/api/tokens/delete")
async def delete_tokens(request: DeleteTokensRequest, _: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """批量删除Token"""
    try:
        logger.debug(f"[Admin] 删除Token: {request.token_type}, {len(request.tokens)}个")

        token_type = validate_token_type(request.token_type)
        await token_manager.delete_token(request.tokens, token_type)

        logger.debug(f"[Admin] Token删除成功: {len(request.tokens)}个")
        return {"success": True, "message": f"成功删除 {len(request.tokens)} 个Token", "count": len(request.tokens)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin] Token删除异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"删除失败: {e}", "code": "DELETE_ERROR"})


@router.get("/api/settings")
async def get_settings(_: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """获取配置"""
    try:
        logger.debug("[Admin] 获取配置")
        return {"success": True, "data": {"global": setting.global_config, "grok": setting.grok_config}}
    except Exception as e:
        logger.error(f"[Admin] 获取配置失败: {e}")
        raise HTTPException(status_code=500, detail={"error": f"获取失败: {e}", "code": "GET_SETTINGS_ERROR"})


@router.post("/api/settings")
async def update_settings(request: UpdateSettingsRequest, _: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """更新配置"""
    try:
        logger.debug("[Admin] 更新配置")
        await setting.save(global_config=request.global_config, grok_config=request.grok_config)
        logger.debug("[Admin] 配置更新成功")
        return {"success": True, "message": "配置更新成功"}
    except Exception as e:
        logger.error(f"[Admin] 更新配置失败: {e}")
        raise HTTPException(status_code=500, detail={"error": f"更新失败: {e}", "code": "UPDATE_SETTINGS_ERROR"})


@router.get("/api/cache/size")
async def get_cache_size(_: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """获取缓存大小"""
    try:
        logger.debug("[Admin] 获取缓存大小")

        image_size = _calculate_dir_size(IMAGE_CACHE_DIR) if IMAGE_CACHE_DIR.exists() else 0
        video_size = _calculate_dir_size(VIDEO_CACHE_DIR) if VIDEO_CACHE_DIR.exists() else 0
        total_size = image_size + video_size

        logger.debug(f"[Admin] 缓存大小: 图片{_format_size(image_size)}, 视频{_format_size(video_size)}")
        
        return {
            "success": True,
            "data": {
                "image_size": _format_size(image_size),
                "video_size": _format_size(video_size),
                "total_size": _format_size(total_size),
                "image_size_bytes": image_size,
                "video_size_bytes": video_size,
                "total_size_bytes": total_size
            }
        }

    except Exception as e:
        logger.error(f"[Admin] 获取缓存大小异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"获取失败: {e}", "code": "CACHE_SIZE_ERROR"})


@router.post("/api/cache/clear")
async def clear_cache(_: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """清理所有缓存"""
    try:
        logger.debug("[Admin] 清理缓存")

        image_count = 0
        video_count = 0

        # 清理图片
        if IMAGE_CACHE_DIR.exists():
            for file_path in IMAGE_CACHE_DIR.iterdir():
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        image_count += 1
                    except Exception as e:
                        logger.error(f"[Admin] 删除失败: {file_path.name}, {e}")

        # 清理视频
        if VIDEO_CACHE_DIR.exists():
            for file_path in VIDEO_CACHE_DIR.iterdir():
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        video_count += 1
                    except Exception as e:
                        logger.error(f"[Admin] 删除失败: {file_path.name}, {e}")

        total = image_count + video_count
        logger.debug(f"[Admin] 缓存清理完成: 图片{image_count}, 视频{video_count}")

        return {
            "success": True,
            "message": f"成功清理缓存，删除图片 {image_count} 个，视频 {video_count} 个，共 {total} 个文件",
            "data": {"deleted_count": total, "image_count": image_count, "video_count": video_count}
        }

    except Exception as e:
        logger.error(f"[Admin] 清理缓存异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"清理失败: {e}", "code": "CACHE_CLEAR_ERROR"})


@router.post("/api/cache/clear/images")
async def clear_image_cache(_: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """清理图片缓存"""
    try:
        logger.debug("[Admin] 清理图片缓存")

        count = 0
        if IMAGE_CACHE_DIR.exists():
            for file_path in IMAGE_CACHE_DIR.iterdir():
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        count += 1
                    except Exception as e:
                        logger.error(f"[Admin] 删除失败: {file_path.name}, {e}")

        logger.debug(f"[Admin] 图片缓存清理完成: {count}个")
        return {"success": True, "message": f"成功清理图片缓存，删除 {count} 个文件", "data": {"deleted_count": count, "type": "images"}}

    except Exception as e:
        logger.error(f"[Admin] 清理图片缓存异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"清理失败: {e}", "code": "IMAGE_CACHE_CLEAR_ERROR"})


@router.post("/api/cache/clear/videos")
async def clear_video_cache(_: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """清理视频缓存"""
    try:
        logger.debug("[Admin] 清理视频缓存")

        count = 0
        if VIDEO_CACHE_DIR.exists():
            for file_path in VIDEO_CACHE_DIR.iterdir():
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        count += 1
                    except Exception as e:
                        logger.error(f"[Admin] 删除失败: {file_path.name}, {e}")

        logger.debug(f"[Admin] 视频缓存清理完成: {count}个")
        return {"success": True, "message": f"成功清理视频缓存，删除 {count} 个文件", "data": {"deleted_count": count, "type": "videos"}}

    except Exception as e:
        logger.error(f"[Admin] 清理视频缓存异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"清理失败: {e}", "code": "VIDEO_CACHE_CLEAR_ERROR"})


@router.get("/api/stats")
async def get_stats(_: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """获取统计信息"""
    try:
        logger.debug("[Admin] 开始获取统计信息")

        all_tokens = token_manager.get_tokens()
        normal_stats = calculate_token_stats(all_tokens.get(TokenType.NORMAL.value, {}), "normal")
        super_stats = calculate_token_stats(all_tokens.get(TokenType.SUPER.value, {}), "super")
        total = normal_stats["total"] + super_stats["total"]

        logger.debug(f"[Admin] 统计信息获取成功 - 普通Token: {normal_stats['total']}, Super Token: {super_stats['total']}, 总计: {total}")
        return {"success": True, "data": {"normal": normal_stats, "super": super_stats, "total": total}}

    except Exception as e:
        logger.error(f"[Admin] 获取统计信息异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"获取失败: {e}", "code": "STATS_ERROR"})


@router.get("/api/storage/mode")
async def get_storage_mode(_: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """获取存储模式"""
    try:
        logger.debug("[Admin] 获取存储模式")
        import os
        mode = os.getenv("STORAGE_MODE", "file").upper()
        return {"success": True, "data": {"mode": mode}}
    except Exception as e:
        logger.error(f"[Admin] 获取存储模式异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"获取失败: {e}", "code": "STORAGE_MODE_ERROR"})


@router.post("/api/tokens/tags")
async def update_token_tags(request: UpdateTokenTagsRequest, _: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """更新Token标签"""
    try:
        logger.debug(f"[Admin] 更新Token标签: {request.token[:10]}..., {request.tags}")

        token_type = validate_token_type(request.token_type)
        await token_manager.update_token_tags(request.token, token_type, request.tags)

        logger.debug(f"[Admin] Token标签更新成功: {request.token[:10]}...")
        return {"success": True, "message": "标签更新成功", "tags": request.tags}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin] Token标签更新异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"更新失败: {e}", "code": "UPDATE_TAGS_ERROR"})


@router.get("/api/tokens/tags/all")
async def get_all_tags(_: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """获取所有标签"""
    try:
        logger.debug("[Admin] 获取所有标签")

        all_tokens = token_manager.get_tokens()
        tags_set = set()

        for token_type_data in all_tokens.values():
            for token_data in token_type_data.values():
                tags = token_data.get("tags", [])
                if isinstance(tags, list):
                    tags_set.update(tags)

        tags_list = sorted(list(tags_set))
        logger.debug(f"[Admin] 标签获取成功: {len(tags_list)}个")
        return {"success": True, "data": tags_list}

    except Exception as e:
        logger.error(f"[Admin] 获取标签异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"获取失败: {e}", "code": "GET_TAGS_ERROR"})


@router.post("/api/tokens/note")
async def update_token_note(request: UpdateTokenNoteRequest, _: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """更新Token备注"""
    try:
        logger.debug(f"[Admin] 更新Token备注: {request.token[:10]}...")

        token_type = validate_token_type(request.token_type)
        await token_manager.update_token_note(request.token, token_type, request.note)

        logger.debug(f"[Admin] Token备注更新成功: {request.token[:10]}...")
        return {"success": True, "message": "备注更新成功", "note": request.note}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin] Token备注更新异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"更新失败: {e}", "code": "UPDATE_NOTE_ERROR"})


@router.post("/api/tokens/proxy")
async def update_token_proxy(request: UpdateTokenProxyRequest, _: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """更新Token代理配置"""
    try:
        logger.debug(f"[Admin] 更新Token代理配置: {request.token[:10]}...")

        token_type = validate_token_type(request.token_type)
        await token_manager.update_token_proxy(
            request.token,
            token_type,
            proxy_url=request.proxy_url,
            cache_proxy_url=request.cache_proxy_url,
            cf_clearance=request.cf_clearance
        )

        logger.debug(f"[Admin] Token代理配置更新成功: {request.token[:10]}...")
        return {
            "success": True,
            "message": "代理配置更新成功",
            "proxy_url": request.proxy_url or "",
            "cache_proxy_url": request.cache_proxy_url or "",
            "cf_clearance": request.cf_clearance or ""
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin] Token代理配置更新异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"更新失败: {e}", "code": "UPDATE_PROXY_ERROR"})


@router.post("/api/tokens/test")
async def test_token(request: TestTokenRequest, _: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """测试Token可用性"""
    try:
        logger.debug(f"[Admin] 测试Token: {request.token[:10]}...")

        token_type = validate_token_type(request.token_type)
        auth_token = f"sso-rw={request.token};sso={request.token}"

        result = await token_manager.check_limits(auth_token, "grok-4-fast")

        if result:
            logger.debug(f"[Admin] Token测试成功: {request.token[:10]}...")
            return {
                "success": True,
                "message": "Token有效",
                "data": {
                    "valid": True,
                    "remaining_queries": result.get("remainingTokens", -1),
                    "limit": result.get("limit", -1)
                }
            }
        else:
            logger.warning(f"[Admin] Token测试失败: {request.token[:10]}...")

            all_tokens = token_manager.get_tokens()
            token_data = all_tokens.get(token_type.value, {}).get(request.token)

            if token_data:
                if token_data.get("status") == "expired":
                    return {"success": False, "message": "Token已失效", "data": {"valid": False, "error_type": "expired", "error_code": 401}}
                elif token_data.get("remainingQueries") == 0:
                    return {"success": False, "message": "Token已被限流", "data": {"valid": False, "error_type": "limited", "error_code": "other"}}
                else:
                    return {"success": False, "message": "服务器被block或网络错误", "data": {"valid": False, "error_type": "blocked", "error_code": 403}}
            else:
                return {"success": False, "message": "Token数据异常", "data": {"valid": False, "error_type": "unknown", "error_code": "data_error"}}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin] Token测试异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"测试失败: {e}", "code": "TEST_TOKEN_ERROR"})


# === API Key 管理接口 ===

@router.get("/api/api-keys")
async def get_api_keys(_: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """获取所有 API Key 列表"""
    try:
        from app.services.api_key import api_key_manager

        api_keys = api_key_manager.get_all_api_keys()

        # 转换为字典格式
        data = []
        for api_key_info in api_keys:
            data.append({
                "key": api_key_info.key,
                "note": api_key_info.note,
                "expire_time": api_key_info.expire_time,
                "ip_whitelist": api_key_info.ip_whitelist,
                "created_time": api_key_info.created_time,
                "last_used_time": api_key_info.last_used_time,
                "status": api_key_info.status
            })

        logger.debug(f"[Admin] 获取API Key列表: {len(data)}个")
        return {
            "success": True,
            "data": data,
            "total": len(data)
        }

    except Exception as e:
        logger.error(f"[Admin] 获取API Key列表异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"获取失败: {e}", "code": "GET_API_KEYS_ERROR"})


@router.post("/api/api-keys/create")
async def create_api_key(request: CreateAPIKeyRequest, _: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """创建新的 API Key"""
    try:
        from app.services.api_key import api_key_manager

        # 创建 API Key
        api_key_info = await api_key_manager.create_api_key(
            note=request.note,
            expire_time=request.expire_time,
            ip_whitelist=request.ip_whitelist
        )

        logger.info(f"[Admin] 创建API Key: {api_key_info.key[:20]}..., 备注: {request.note}")

        return {
            "success": True,
            "message": "API Key 创建成功",
            "data": {
                "key": api_key_info.key,
                "note": api_key_info.note,
                "expire_time": api_key_info.expire_time,
                "ip_whitelist": api_key_info.ip_whitelist,
                "created_time": api_key_info.created_time,
                "status": api_key_info.status
            }
        }

    except Exception as e:
        logger.error(f"[Admin] 创建API Key异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"创建失败: {e}", "code": "CREATE_API_KEY_ERROR"})


@router.put("/api/api-keys/update")
async def update_api_key(request: UpdateAPIKeyRequest, _: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """更新 API Key"""
    try:
        from app.services.api_key import api_key_manager

        # 更新 API Key
        success = await api_key_manager.update_api_key(
            key=request.key,
            note=request.note,
            expire_time=request.expire_time,
            ip_whitelist=request.ip_whitelist,
            status=request.status
        )

        if not success:
            raise HTTPException(status_code=404, detail={"error": "API Key 不存在", "code": "API_KEY_NOT_FOUND"})

        logger.info(f"[Admin] 更新API Key: {request.key[:20]}...")

        return {
            "success": True,
            "message": "API Key 更新成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin] 更新API Key异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"更新失败: {e}", "code": "UPDATE_API_KEY_ERROR"})


@router.delete("/api/api-keys/delete")
async def delete_api_key(request: DeleteAPIKeyRequest, _: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """删除 API Key"""
    try:
        from app.services.api_key import api_key_manager

        # 删除 API Key
        success = await api_key_manager.delete_api_key(request.key)

        if not success:
            raise HTTPException(status_code=404, detail={"error": "API Key 不存在", "code": "API_KEY_NOT_FOUND"})

        logger.info(f"[Admin] 删除API Key: {request.key[:20]}...")

        return {
            "success": True,
            "message": "API Key 删除成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin] 删除API Key异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"删除失败: {e}", "code": "DELETE_API_KEY_ERROR"})


@router.get("/api/api-keys/stats")
async def get_api_keys_stats(_: bool = Depends(verify_admin_session)) -> Dict[str, Any]:
    """获取 API Key 统计信息"""
    try:
        from app.services.api_key import api_key_manager

        stats = api_key_manager.get_statistics()

        logger.debug(f"[Admin] 获取API Key统计: {stats}")

        return {
            "success": True,
            "data": stats
        }

    except Exception as e:
        logger.error(f"[Admin] 获取API Key统计异常: {e}")
        raise HTTPException(status_code=500, detail={"error": f"获取失败: {e}", "code": "GET_API_KEYS_STATS_ERROR"})
