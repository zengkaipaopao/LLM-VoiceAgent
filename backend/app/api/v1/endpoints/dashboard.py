"""
Dashboard API Endpoints
提供仪表盘统计数据 - 预约管理中心
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.appointment import Appointment
from app.models.call import Call
from app.schemas.base import ResponseBase
from app.utils.datetime_utils import now_tokyo_naive

router = APIRouter()


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
        "redis": {"status": "healthy", "message": "连接正常"},
        "ai_service": {"status": "healthy", "message": "服务正常"},
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
    except Exception as e:
        return {"status": "error", "message": str(e)}
