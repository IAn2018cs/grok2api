"""Admin API Key management endpoints."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import verify_app_key
from app.services.api_key import api_key_manager

router = APIRouter()


class CreateRequest(BaseModel):
    note: str = ""
    expire_time: Optional[int] = None
    ip_whitelist: List[str] = []


class UpdateRequest(BaseModel):
    key: str
    note: Optional[str] = None
    expire_time: Optional[int] = None
    ip_whitelist: Optional[List[str]] = None
    status: Optional[str] = None


class DeleteRequest(BaseModel):
    key: str


@router.get("/apikeys", dependencies=[Depends(verify_app_key)])
async def list_apikeys():
    data = [k.model_dump() for k in api_key_manager.all()]
    return {"success": True, "data": data, "total": len(data)}


@router.get("/apikeys/stats", dependencies=[Depends(verify_app_key)])
async def apikey_stats():
    return {"success": True, "data": api_key_manager.stats()}


@router.post("/apikeys", dependencies=[Depends(verify_app_key)])
async def create_apikey(req: CreateRequest):
    info = await api_key_manager.create(
        note=req.note,
        expire_time=req.expire_time,
        ip_whitelist=req.ip_whitelist,
    )
    return {"success": True, "data": info.model_dump()}


@router.put("/apikeys", dependencies=[Depends(verify_app_key)])
async def update_apikey(req: UpdateRequest):
    ok = await api_key_manager.update(
        key=req.key,
        note=req.note,
        expire_time=req.expire_time,
        ip_whitelist=req.ip_whitelist,
        status=req.status,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return {"success": True}


@router.delete("/apikeys", dependencies=[Depends(verify_app_key)])
async def delete_apikey(req: DeleteRequest):
    ok = await api_key_manager.delete(req.key)
    if not ok:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return {"success": True}
