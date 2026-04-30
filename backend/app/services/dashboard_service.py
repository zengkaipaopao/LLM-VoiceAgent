import asyncio
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.call import Call
from app.utils.datetime_utils import now_tokyo_naive

logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_stats(self) -> dict:
        """Return dashboard stats using Tokyo-local day windows."""
        now = now_tokyo_naive()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today_start - timedelta(days=7)
        yesterday_start = today_start - timedelta(days=1)

        total_calls = int(await self.db.scalar(select(func.count(Call.id))) or 0)
        today_calls = int(
            await self.db.scalar(select(func.count(Call.id)).where(Call.created_at >= today_start))
            or 0
        )
        yesterday_calls = int(
            await self.db.scalar(
                select(func.count(Call.id)).where(
                    and_(
                        Call.created_at >= yesterday_start,
                        Call.created_at < today_start,
                    )
                )
            )
            or 0
        )

        avg_duration_seconds = await self.db.scalar(select(func.avg(Call.duration_seconds))) or 0
        total_duration_seconds = await self.db.scalar(select(func.sum(Call.duration_seconds))) or 0

        total_appointments = int(
            await self.db.scalar(select(func.count(Appointment.id))) or 0
        )
        today_appointments = int(
            await self.db.scalar(
                select(func.count(Appointment.id)).where(Appointment.created_at >= today_start)
            )
            or 0
        )
        yesterday_appointments = int(
            await self.db.scalar(
                select(func.count(Appointment.id)).where(
                    and_(
                        Appointment.created_at >= yesterday_start,
                        Appointment.created_at < today_start,
                    )
                )
            )
            or 0
        )
        pending_appointments = int(
            await self.db.scalar(
                select(func.count(Appointment.id)).where(Appointment.is_handled.is_(False))
            )
            or 0
        )
        new_today = int(
            await self.db.scalar(
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
            await self.db.scalar(
                select(func.count(Appointment.id)).where(Appointment.operation == "delete")
            )
            or 0
        )
        rescheduled_appointments = int(
            await self.db.scalar(
                select(func.count(Appointment.id)).where(Appointment.operation == "update")
            )
            or 0
        )
        completed_appointments = int(
            await self.db.scalar(
                select(func.count(Appointment.id)).where(Appointment.is_handled.is_(True))
            )
            or 0
        )

        return {
            "calls": {
                "total": total_calls,
                "today": today_calls,
                "avg_duration": self.format_duration(int(avg_duration_seconds)),
                "total_duration": self.format_duration(int(total_duration_seconds)),
                "trend": self._percentage_trend(today_calls, yesterday_calls),
            },
            "appointments": {
                "total": total_appointments,
                "today": today_appointments,
                "pending": pending_appointments,
                "new_today": new_today,
                "cancelled": cancelled_appointments,
                "rescheduled": rescheduled_appointments,
                "completed": completed_appointments,
                "completion_rate": self._completion_rate(
                    completed_appointments,
                    total_appointments,
                ),
                "trend": self._percentage_trend(today_appointments, yesterday_appointments),
            },
            "trend": await self.generate_daily_trend(week_ago, now),
            "system_status": {
                "database": await self.check_database(),
                "redis": await self.check_redis(),
                "ai_service": self.check_ai_service(),
            },
        }

    async def generate_daily_trend(self, start_time: datetime, end_time: datetime) -> list:
        """Generate daily call trend data for the requested window."""
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
        result = await self.db.execute(stmt)
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

    async def check_database(self) -> dict:
        try:
            await self.db.execute(text("SELECT 1"))
            return {"status": "healthy", "message": "连接正常"}
        except Exception:
            logger.exception("Database health probe failed.")
            return {"status": "error", "message": "数据库不可达"}

    @staticmethod
    async def check_redis() -> dict:
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

    @staticmethod
    def check_ai_service() -> dict:
        if settings.google_genai_backend_enabled:
            return {"status": "healthy", "message": f"配置有效 ({settings.google_genai_backend_mode})"}
        return {"status": "error", "message": "Gemini后端未配置"}

    @staticmethod
    def format_duration(seconds: int) -> str:
        if seconds == 0:
            return "0:00"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    @staticmethod
    def _percentage_trend(today_value: int, yesterday_value: int) -> float | int:
        if yesterday_value <= 0:
            return 0
        return round(((today_value - yesterday_value) / yesterday_value) * 100, 1)

    @staticmethod
    def _completion_rate(completed: int, total: int) -> float | int:
        if total <= 0:
            return 0
        return round((completed / total) * 100, 1)
