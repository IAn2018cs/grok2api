"""OpenAI 请求-响应模型定义"""

from fastapi import HTTPException
from typing import Optional, List, Union, Dict, Any
from pydantic import BaseModel, Field, field_validator

from app.models.grok_models import Models


class OpenAIChatRequest(BaseModel):
    """OpenAI聊天请求"""

    model: str = Field(..., description="模型名称", min_length=1)
    messages: List[Dict[str, Any]] = Field(..., description="消息列表", min_length=1)
    stream: bool = Field(False, description="流式响应")
    temperature: Optional[float] = Field(0.7, ge=0, le=2, description="采样温度")
    max_tokens: Optional[int] = Field(None, ge=1, le=100000, description="最大Token数")
    top_p: Optional[float] = Field(1.0, ge=0, le=1, description="采样参数")

    @classmethod
    @field_validator('messages')
    def validate_messages(cls, v):
        """验证消息格式"""
        if not v:
            raise HTTPException(status_code=400, detail="消息列表不能为空")

        for msg in v:
            if not isinstance(msg, dict):
                raise HTTPException(status_code=400, detail="每个消息必须是字典")
            if 'role' not in msg:
                raise HTTPException(status_code=400, detail="消息缺少 'role' 字段")
            if 'content' not in msg:
                raise HTTPException(status_code=400, detail="消息缺少 'content' 字段")
            if msg['role'] not in ['system', 'user', 'assistant']:
                raise HTTPException(
                    status_code=400,
                    detail=f"无效角色 '{msg['role']}', 必须是 system/user/assistant"
                )

        return v

    @classmethod
    @field_validator('model')
    def validate_model(cls, v):
        """验证模型名称"""
        if not Models.is_valid_model(v):
            supported = Models.get_all_model_names()
            raise HTTPException(
                status_code=400,
                detail=f"不支持的模型 '{v}', 支持: {', '.join(supported)}"
            )
        return v


class OpenAIChatCompletionMessage(BaseModel):
    """聊天完成消息"""
    role: str = Field(..., description="角色")
    content: str = Field(..., description="内容")
    reference_id: Optional[str] = Field(default=None, description="参考ID")
    annotations: Optional[List[str]] = Field(default=None, description="注释")


class OpenAIChatCompletionChoice(BaseModel):
    """聊天完成选项"""
    index: int = Field(..., description="索引")
    message: OpenAIChatCompletionMessage = Field(..., description="消息")
    logprobs: Optional[float] = Field(default=None, description="对数概率")
    finish_reason: str = Field(default="stop", description="完成原因")


class OpenAIChatCompletionResponse(BaseModel):
    """聊天完成响应"""
    id: str = Field(..., description="响应ID")
    object: str = Field("chat.completion", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="模型")
    choices: List[OpenAIChatCompletionChoice] = Field(..., description="选项")
    usage: Optional[Dict[str, Any]] = Field(None, description="令牌使用")


class OpenAIChatCompletionChunkMessage(BaseModel):
    """流式消息片段"""
    role: str = Field(..., description="角色")
    content: str = Field(..., description="内容")


class OpenAIChatCompletionChunkChoice(BaseModel):
    """流式选项"""
    index: int = Field(..., description="索引")
    delta: Optional[Union[Dict[str, Any], OpenAIChatCompletionChunkMessage]] = Field(
        None, description="Delta数据"
    )
    finish_reason: Optional[str] = Field(None, description="完成原因")


class OpenAIChatCompletionChunkResponse(BaseModel):
    """流式聊天响应"""
    id: str = Field(..., description="响应ID")
    object: str = Field(default="chat.completion.chunk", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="模型")
    system_fingerprint: Optional[str] = Field(default=None, description="系统指纹")
    choices: List[OpenAIChatCompletionChunkChoice] = Field(..., description="选项")


class VideoGenerationRequest(BaseModel):
    """视频生成请求"""
    image_url: str = Field(..., description="输入图片的URL（支持http/https或base64）")
    prompt: str = Field(..., description="视频生成提示词", min_length=1)
    model: str = Field("grok-imagine-0.9", description="使用的视频生成模型")

    @classmethod
    @field_validator('image_url')
    def validate_image_url(cls, v):
        """验证图片URL格式"""
        if not v:
            raise HTTPException(status_code=400, detail="图片URL不能为空")
        if not (v.startswith(('http://', 'https://', 'data:image/'))):
            raise HTTPException(
                status_code=400,
                detail="图片URL必须是http/https链接或base64格式（data:image/...）"
            )
        return v

    @classmethod
    @field_validator('model')
    def validate_video_model(cls, v):
        """验证是否为视频生成模型"""
        if not Models.is_valid_model(v):
            raise HTTPException(
                status_code=400,
                detail=f"不支持的模型 '{v}'"
            )

        model_info = Models.get_model_info(v)
        if not model_info.get("is_video_model", False):
            raise HTTPException(
                status_code=400,
                detail=f"模型 '{v}' 不是视频生成模型，请使用 grok-imagine-0.9"
            )
        return v


class VideoGenerationResponse(BaseModel):
    """视频生成响应"""
    id: str = Field(..., description="任务ID")
    model: str = Field(..., description="使用的模型")
    created: int = Field(..., description="创建时间戳")
    video_url: Optional[str] = Field(None, description="生成的视频URL")
    status: str = Field("completed", description="生成状态")
    prompt: str = Field(..., description="使用的提示词")