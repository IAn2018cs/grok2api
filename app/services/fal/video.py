"""fal 视频生成服务 - 通过 fal API 生成视频"""

import os
import base64
import asyncio
from typing import Dict, Any

import fal_client
from curl_cffi.requests import AsyncSession

from app.core.logger import logger


# fal 模型 ID
FAL_MODEL_ID = "xai/grok-imagine-video/image-to-video"

# 图片下载超时
DOWNLOAD_TIMEOUT = 30

# 默认 MIME 类型
DEFAULT_MIME = "image/jpeg"


async def _ensure_base64_image(image_url: str) -> str:
    """确保图片为 Base64 data URI 格式

    Args:
        image_url: 图片 URL（HTTP/HTTPS）或已有的 data URI

    Returns:
        Base64 data URI 格式的字符串
    """
    # 已经是 data URI，直接返回
    if image_url.startswith("data:image/"):
        return image_url

    # HTTP/HTTPS URL，下载并转为 Base64
    logger.info(f"[Fal] 下载图片并转换为 Base64: {image_url[:80]}...")
    try:
        async with AsyncSession() as session:
            response = await session.get(image_url, timeout=DOWNLOAD_TIMEOUT)
            response.raise_for_status()

            content_type = response.headers.get("content-type", DEFAULT_MIME)
            if not content_type.startswith("image/"):
                content_type = DEFAULT_MIME

            b64_data = base64.b64encode(response.content).decode()
            data_uri = f"data:{content_type};base64,{b64_data}"
            logger.info(f"[Fal] 图片转换完成，大小: {len(response.content)} bytes")
            return data_uri
    except Exception as e:
        logger.error(f"[Fal] 图片下载失败: {e}")
        raise RuntimeError(f"图片下载失败: {e}") from e


def _sync_subscribe(prompt: str, image_url: str) -> Dict[str, Any]:
    """同步调用 fal_client.subscribe（在线程池中执行）"""
    def on_queue_update(update):
        if isinstance(update, fal_client.InProgress):
            for log_entry in update.logs:
                logger.info(f"[Fal] 队列进度: {log_entry['message']}")

    result = fal_client.subscribe(
        FAL_MODEL_ID,
        arguments={
            "prompt": prompt,
            "image_url": image_url,
        },
        with_logs=True,
        on_queue_update=on_queue_update,
    )
    return result


async def generate_video(image_url: str, prompt: str) -> Dict[str, Any]:
    """通过 fal API 生成视频

    Args:
        image_url: 输入图片的 URL 或 Base64 data URI
        prompt: 视频生成提示词

    Returns:
        fal API 响应，格式: {"video": {"url": "...", "duration": ..., ...}}

    Raises:
        RuntimeError: 当 FAL_KEY 未配置或 API 调用失败时
    """
    # 检查 FAL_KEY
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("未配置 FAL_KEY 环境变量，无法使用 fal 视频生成服务")

    logger.info(f"[Fal] 开始视频生成 - 提示词: {prompt[:50]}...")

    # 转换图片为 Base64 data URI
    base64_image = await _ensure_base64_image(image_url)

    # 调用 fal API（同步 subscribe 通过线程池异步执行）
    logger.info("[Fal] 提交视频生成请求到 fal API...")
    try:
        result = await asyncio.to_thread(_sync_subscribe, prompt, base64_image)
    except Exception as e:
        logger.error(f"[Fal] fal API 调用失败: {e}")
        raise RuntimeError(f"fal 视频生成失败: {e}") from e

    # 验证响应
    video_info = result.get("video", {})
    video_url = video_info.get("url")
    if not video_url:
        logger.error(f"[Fal] 响应中未找到视频 URL: {result}")
        raise RuntimeError("fal 视频生成失败：响应中未包含视频 URL")

    logger.info(f"[Fal] 视频生成成功: {video_url}")
    return result
