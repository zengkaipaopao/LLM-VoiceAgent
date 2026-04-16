"""
Dashboard API Endpoints
提供仪表盘统计数据 - 预约管理中心
"""
import asyncio
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.models.appointment import Appointment
from app.models.call import Call
from app.schemas.base import ResponseBase
from app.utils.datetime_utils import now_tokyo_naive

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stats", response_model=ResponseBase[dict])
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """获取Dashboard统计数据 - 固定最近7天，天粒度。"""
    # Use Tokyo local time semantics in dashboard windows.
    now = now_tokyo_naive()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today_start - timedelta(days=7)

    total_calls = int(await db.scalar(select(func.count(Call.id))) or 0)

    today_calls = int(
        await db.scalar(select(func.count(Call.id)).where(Call.created_at >= today_start)) or 0
    )

    avg_duration_seconds = await db.scalar(select(func.avg(Call.duration_seconds))) or 0
    avg_duration = _format_duration(int(avg_duration_seconds))

    total_duration_seconds = await db.scalar(select(func.sum(Call.duration_seconds))) or 0
    total_duration = _format_duration(int(total_duration_seconds))

    yesterday_start = today_start - timedelta(days=1)
    yesterday_calls = int(
        await db.scalar(
            select(func.count(Call.id)).where(
                and_(
                    Call.created_at >= yesterday_start,
                    Call.created_at < today_start,
                )
            )
        )
        or 0
    )

    calls_trend = 0
    if yesterday_calls > 0:
        calls_trend = round(((today_calls - yesterday_calls) / yesterday_calls) * 100, 1)

    total_appointments = int(await db.scalar(select(func.count(Appointment.id))) or 0)

    today_appointments = int(
        await db.scalar(select(func.count(Appointment.id)).where(Appointment.created_at >= today_start))
        or 0
    )

    pending_appointments = int(
        await db.scalar(
            select(func.count(Appointment.id)).where(Appointment.is_handled.is_(False))
        )
        or 0
    )

    new_today = int(
        await db.scalar(
            select(func.count(Appointment.id)).where(
                and_(
                    Appointment.operation == "create",
                    Appointment.created_at >= today_start,
                )
            )
        )
        or 0
    )

    cancelled_appointments = int(
        await db.scalar(
            select(func.count(Appointment.id)).where(Appointment.operation == "delete")
        )
        or 0
    )

    rescheduled_appointments = int(
        await db.scalar(
            select(func.count(Appointment.id)).where(Appointment.operation == "update")
        )
        or 0
    )

    completed_appointments = int(
        await db.scalar(
            select(func.count(Appointment.id)).where(Appointment.is_handled.is_(True))
        )
        or 0
    )

    completion_rate = 0
    if total_appointments > 0:
        completion_rate = round((completed_appointments / total_appointments) * 100, 1)

    yesterday_appointments = int(
        await db.scalar(
            select(func.count(Appointment.id)).where(
                and_(
                    Appointment.created_at >= yesterday_start,
                    Appointment.created_at < today_start,
                )
            )
        )
        or 0
    )

    appointments_trend = 0
    if yesterday_appointments > 0:
        appointments_trend = round(
            ((today_appointments - yesterday_appointments) / yesterday_appointments) * 100,
            1,
        )

    trend_data = await _generate_daily_trend(db, week_ago, now)

    system_status = {
        "database": await _check_database(db),
        "redis": await _check_redis(),
        "ai_service": _check_ai_service(),
    }

    return ResponseBase(
        success=True,
        data={
            "calls": {
                "total": total_calls,
                "today": today_calls,
                "avg_duration": avg_duration,
                "total_duration": total_duration,
                "trend": calls_trend,
            },
            "appointments": {
                "total": total_appointments,
                "today": today_appointments,
                "pending": pending_appointments,
                "new_today": new_today,
                "cancelled": cancelled_appointments,
                "rescheduled": rescheduled_appointments,
                "completed": completed_appointments,
                "completion_rate": completion_rate,
                "trend": appointments_trend,
            },
            "trend": trend_data,
            "system_status": system_status,
        },
    )


def _format_duration(seconds: int) -> str:
    """格式化时长为 HH:MM:SS 或 MM:SS。"""
    if seconds == 0:
        return "0:00"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


async def _generate_daily_trend(db: AsyncSession, start_time: datetime, end_time: datetime) -> list:
    """生成每日通话趋势数据（最近7天）。"""
    truncated_day = func.date_trunc(text("'day'"), Call.created_at)
    stmt = (
        select(
            truncated_day.label("day"),
            func.count(Call.id).label("count"),
        )
        .where(and_(Call.created_at >= start_time, Call.created_at <= end_time))
        .group_by(truncated_day)
        .order_by(truncated_day)
    )
    result = await db.execute(stmt)
    trend_rows = result.all()

    data_dict = {row.day.date().isoformat(): row.count for row in trend_rows}

    trend_data = []
    current = start_time
    while current <= end_time:
        date_str = current.date().isoformat()
        value = data_dict.get(date_str, 0)
        trend_data.append({"date": date_str, "value": value, "group": "通话数"})
        current += timedelta(days=1)

    return trend_data


async def _check_database(db: AsyncSession) -> dict:
    """检查数据库连接状态。"""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "message": "连接正常"}
    except Exception:
        logger.exception("Database health probe failed.")
        return {"status": "error", "message": "数据库不可达"}


async def _check_redis() -> dict:
    redis_url = (settings.redis_url or "").strip()
    if not redis_url:
        return {"status": "unknown", "message": "REDIS_URL not configured"}

    parsed = urlparse(redis_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 6379

    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.5)
        writer.close()
        await writer.wait_closed()
        return {"status": "healthy", "message": "连接正常"}
    except Exception:
        return {"status": "error", "message": "Redis不可达"}


def _check_ai_service() -> dict:
    if settings.google_genai_backend_enabled:
        return {"status": "healthy", "message": f"配置有效 ({settings.google_genai_backend_mode})"}
    return {"status": "error", "message": "Gemini后端未配置"}
