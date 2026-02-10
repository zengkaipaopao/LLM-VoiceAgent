"""
Dashboard API Endpoints
提供仪表盘统计数据
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timezone, timedelta
from typing import List

from app.api.deps import get_db
from app.models.call import Call, CallStatus
from app.models.appointment import Appointment
from app.api.v1.endpoints.dashboard_helpers import _generate_trend_data

router = APIRouter()


@router.get("/stats")
def get_dashboard_stats(
    start_date: str = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    granularity: str = Query("day", regex="^(hour|day|week|month|year)$", description="数据粒度"),
    db: Session = Depends(get_db)
):
    """
    获取Dashboard统计数据
    
    Args:
        start_date: 开始日期（可选，默认为今天0点）
        end_date: 结束日期（可选，默认为当前时间）
        granularity: 数据粒度（minute/hour/day/week/month/year）
        
    Returns:
        - 通话统计
        - 预约统计
        - 通话趋势数据（按粒度聚合）
        - AI效率分布
        - 系统状态
    """
    now = datetime.now(timezone.utc)
    
    # 解析时间范围
    if start_date:
        start_time = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    else:
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if end_date:
        end_time = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
    else:
        end_time = now
    
    # 昨日同时间（用于计算趋势）
    time_diff = end_time - start_time
    yesterday_start = start_time - time_diff
    yesterday_end = start_time
    
    # ==================== 通话统计 ====================
    period_calls = db.query(func.count(Call.id)).filter(
        and_(
            Call.created_at >= start_time,
            Call.created_at <= end_time
        )
    ).scalar() or 0
    
    previous_calls = db.query(func.count(Call.id)).filter(
        and_(
            Call.created_at >= yesterday_start,
            Call.created_at < yesterday_end
        )
    ).scalar() or 0
    
    # 计算趋势
    calls_trend = 0
    if previous_calls > 0:
        calls_trend = round(((period_calls - previous_calls) / previous_calls) * 100, 1)
    
    # 成功率
    completed_calls = db.query(func.count(Call.id)).filter(
        and_(
            Call.created_at >= start_time,
            Call.created_at <= end_time,
            Call.status == CallStatus.COMPLETED.value
        )
    ).scalar() or 0
    
    success_rate = 0
    if period_calls > 0:
        success_rate = round((completed_calls / period_calls) * 100, 1)
    
    # AI处理统计
    ai_handled = db.query(func.count(Call.id)).filter(
        and_(
            Call.created_at >= start_time,
            Call.created_at <= end_time,
            Call.handler_type == "ai"
        )
    ).scalar() or 0
    
    ai_percent = 0
    if period_calls > 0:
        ai_percent = round((ai_handled / period_calls) * 100, 1)
    
    # 平均时长
    avg_duration = db.query(func.avg(Call.duration_seconds)).filter(
        and_(
            Call.created_at >= start_time,
            Call.created_at <= end_time,
            Call.duration_seconds.isnot(None)
        )
    ).scalar() or 0
    
    avg_duration = int(avg_duration) if avg_duration else 0
    
    # ==================== 预约统计 ====================
    period_appointments = db.query(func.count(Appointment.id)).filter(
        and_(
            Appointment.created_at >= start_time,
            Appointment.created_at <= end_time
        )
    ).scalar() or 0
    
    new_appointments = db.query(func.count(Appointment.id)).filter(
        and_(
            Appointment.created_at >= start_time,
            Appointment.created_at <= end_time,
            Appointment.operation == 'create'
        )
    ).scalar() or 0
    
    cancelled_appointments = db.query(func.count(Appointment.id)).filter(
        and_(
            Appointment.created_at >= start_time,
            Appointment.created_at <= end_time,
            Appointment.operation == 'delete'
        )
    ).scalar() or 0
    
    rescheduled_appointments = db.query(func.count(Appointment.id)).filter(
        and_(
            Appointment.created_at >= start_time,
            Appointment.created_at <= end_time,
            Appointment.operation == 'update'
        )
    ).scalar() or 0
    
    # ==================== 趋势数据（按粒度聚合） ====================
    trend_data = _generate_trend_data(db, start_time, end_time, granularity)
    
    # ==================== AI效率分布 ====================
    # 只统计已接通的通话（排除no_answer等）
    ai_handled_count = db.query(func.count(Call.id)).filter(
        and_(
            Call.created_at >= start_time,
            Call.created_at <= end_time,
            Call.handler_type == "ai",
            Call.is_answered == True
        )
    ).scalar() or 0
    
    transferred_count = db.query(func.count(Call.id)).filter(
        and_(
            Call.created_at >= start_time,
            Call.handler_type == "transferred",
            Call.is_answered == True
        )
    ).scalar() or 0
    
    efficiency_data = [
        {"group": "AI处理", "value": ai_handled_count},
        {"group": "转人工", "value": transferred_count},
    ]
    
    # ==================== 系统状态 ====================
    # TODO: 实现真实的系统健康检查
    system_status = {
        "postgres": "online",
        "redis": "online",
        "llm_api": "online"
    }
    
    return {
        "calls": {
            "total": period_calls,
            "trend": calls_trend,
            "success_rate": success_rate,
            "ai_handled": ai_handled,
            "ai_percent": ai_percent,
            "avg_duration": avg_duration,
        },
        "appointments": {
            "total": period_appointments,
            "new": new_appointments,
            "cancelled": cancelled_appointments,
            "rescheduled": rescheduled_appointments,
        },
        "trend": trend_data,
        "efficiency": efficiency_data,
        "system_status": system_status,
    }
