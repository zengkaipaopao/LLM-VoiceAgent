"""
Dashboard API Endpoints
提供仪表盘统计数据 - 预约管理中心
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.base import ResponseBase
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/stats", response_model=ResponseBase[dict])
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """获取Dashboard统计数据 - 固定最近7天，天粒度。"""
    return ResponseBase(success=True, data=await DashboardService(db).get_stats())
