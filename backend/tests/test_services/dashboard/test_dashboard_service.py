import pytest

from app.services.dashboard_service import DashboardService


class FakeHealthyDb:
    async def execute(self, _stmt):
        return object()


class FakeBrokenDb:
    async def execute(self, _stmt):
        raise RuntimeError("db down")


def test_dashboard_format_duration():
    assert DashboardService.format_duration(0) == "0:00"
    assert DashboardService.format_duration(65) == "1:05"
    assert DashboardService.format_duration(3661) == "1:01:01"


def test_dashboard_percentage_helpers():
    assert DashboardService._percentage_trend(12, 10) == 20.0
    assert DashboardService._percentage_trend(12, 0) == 0
    assert DashboardService._completion_rate(3, 4) == 75.0
    assert DashboardService._completion_rate(3, 0) == 0


@pytest.mark.asyncio
async def test_dashboard_check_database_reports_health():
    assert await DashboardService(FakeHealthyDb()).check_database() == {
        "status": "healthy",
        "message": "连接正常",
    }


@pytest.mark.asyncio
async def test_dashboard_check_database_reports_error():
    assert await DashboardService(FakeBrokenDb()).check_database() == {
        "status": "error",
        "message": "数据库不可达",
    }
