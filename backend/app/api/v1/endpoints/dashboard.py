"""
Dashboard API Endpoints
提供仪表盘统计数据 - 预约管理中心
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case
from datetime import datetime, timezone, timedelta

from app.api.deps import get_db
from app.models.call import Call, CallStatus
from app.models.appointment import Appointment

router = APIRouter()


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    获取Dashboard统计数据 - 固定最近7天，天粒度
    
    Returns:
        - 通话统计：总数、今日、平均时长、总时长
        - 预约统计：总数、今日、待处理、新增、取消、变更、完成、处理率
        - 通话趋势：最近7天趋势数据
        - 系统状态
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today_start - timedelta(days=7)
    
    # ==================== 通话统计 ====================
    # 总通话数
    total_calls = db.query(func.count(Call.id)).scalar() or 0
    
    # 今日通话数
    today_calls = db.query(func.count(Call.id)).filter(
        Call.created_at >= today_start
    ).scalar() or 0
    
    # 平均通话时长
    avg_duration_seconds = db.query(func.avg(Call.duration_seconds)).scalar() or 0
    avg_duration = _format_duration(int(avg_duration_seconds))
    
    # 总通话时长
    total_duration_seconds = db.query(func.sum(Call.duration_seconds)).scalar() or 0
    total_duration = _format_duration(int(total_duration_seconds))
    
    # 计算趋势（与昨天同期比较）
    yesterday_start = today_start - timedelta(days=1)
    yesterday_calls = db.query(func.count(Call.id)).filter(
        and_(
            Call.created_at >= yesterday_start,
            Call.created_at < today_start
        )
    ).scalar() or 0
    
    calls_trend = 0
    if yesterday_calls > 0:
        calls_trend = round(((today_calls - yesterday_calls) / yesterday_calls) * 100, 1)
    
    # ==================== 预约统计 ====================
    # 总预约数
    total_appointments = db.query(func.count(Appointment.id)).scalar() or 0
    
    # 今日预约数
    today_appointments = db.query(func.count(Appointment.id)).filter(
        Appointment.created_at >= today_start
    ).scalar() or 0
    
    # 待处理预约（is_handled = False）
    pending_appointments = db.query(func.count(Appointment.id)).filter(
        Appointment.is_handled.is_(False)
    ).scalar() or 0
    
    # 今日新增预约（operation = 'create' AND today）
    new_today = db.query(func.count(Appointment.id)).filter(
        and_(
            Appointment.operation == 'create',
            Appointment.created_at >= today_start
        )
    ).scalar() or 0
    
    # 已取消（operation = 'delete'）
    cancelled_appointments = db.query(func.count(Appointment.id)).filter(
        Appointment.operation == 'delete'
    ).scalar() or 0
    
    # 已变更（operation = 'update'）
    rescheduled_appointments = db.query(func.count(Appointment.id)).filter(
        Appointment.operation == 'update'
    ).scalar() or 0
    
    # 已完成（is_handled = True）
    completed_appointments = db.query(func.count(Appointment.id)).filter(
        Appointment.is_handled.is_(True)
    ).scalar() or 0
    
    # 处理率（已完成 / 总数 * 100）
    completion_rate = 0
    if total_appointments > 0:
        completion_rate = round((completed_appointments / total_appointments) * 100, 1)
    
    # 预约趋势
    appointments_trend = 0
    yesterday_appointments = db.query(func.count(Appointment.id)).filter(
        and_(
            Appointment.created_at >= yesterday_start,
            Appointment.created_at < today_start
        )
    ).scalar() or 0
    
    if yesterday_appointments > 0:
        appointments_trend = round(((today_appointments - yesterday_appointments) / yesterday_appointments) * 100, 1)
    
    # ==================== 通话趋势数据（最近7天，天粒度）====================
    trend_data = _generate_daily_trend(db, week_ago, now)
    
    # ==================== 系统状态 ====================
    system_status = {
        "database": _check_database(db),
        "redis": {"status": "healthy", "message": "连接正常"},  # TODO: 实际检查Redis
        "ai_service": {"status": "healthy", "message": "服务正常"}  # TODO: 实际检查AI服务
    }
    
    return {
        "calls": {
            "total": total_calls,
            "today": today_calls,
            "avg_duration": avg_duration,
            "total_duration": total_duration,
            "trend": calls_trend
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
            "trend": appointments_trend
        },
        "trend": trend_data,
        "system_status": system_status
    }


def _format_duration(seconds: int) -> str:
    """格式化时长为 HH:MM:SS 或 MM:SS"""
    if seconds == 0:
        return "0:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def _generate_daily_trend(db: Session, start_time: datetime, end_time: datetime) -> list:
    """
    生成每日通话趋势数据（最近7天）
    """
    from sqlalchemy import func, cast, Date
    
    # 使用PostgreSQL的date_trunc按天分组
    trend_query = db.query(
        func.date_trunc('day', Call.created_at).label('day'),
        func.count(Call.id).label('count')
    ).filter(
        and_(
            Call.created_at >= start_time,
            Call.created_at <= end_time
        )
    ).group_by(
        func.date_trunc('day', Call.created_at)
    ).order_by('day').all()
    
    # 转换为字典以便快速查找
    data_dict = {
        row.day.date().isoformat(): row.count 
        for row in trend_query
    }
    
    # 填充所有日期（包括没有数据的日期）
    trend_data = []
    current = start_time
    while current <= end_time:
        date_str = current.date().isoformat()
        value = data_dict.get(date_str, 0)
        trend_data.append({
            "date": date_str,
            "value": value,
            "group": "通话数"
        })
        current += timedelta(days=1)
    
    return trend_data


def _check_database(db: Session) -> dict:
    """检查数据库连接状态"""
    try:
        db.execute("SELECT 1")
        return {"status": "healthy", "message": "连接正常"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
