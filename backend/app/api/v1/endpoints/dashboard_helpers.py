"""
Helper function for dashboard trend data generation
"""
from sqlalchemy import func, and_, cast, String
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models.call import Call


def _generate_trend_data(db: Session, start_time: datetime, end_time: datetime, granularity: str):
    """
    根据粒度生成趋势数据（优化版本 - 使用单次GROUP BY查询）
    
    Args:
        db: 数据库session
        start_time: 开始时间
        end_time: 结束时间
        granularity: 粒度 (minute/hour/day/week/month/year)
    
    Returns:
        List of trend data points
    """
    # 计算时间跨度和预期数据点数量
    time_span = end_time - start_time
    
    # 根据粒度确定时间间隔和最大数据点限制
    if granularity == 'hour':
        delta = timedelta(hours=1)
        date_format = "%Y-%m-%d %H:00"
        max_points = 720  # 最多30天的小时数据
        if time_span > timedelta(days=30):
            granularity = 'day'
            delta = timedelta(days=1)
            date_format = "%Y-%m-%d"
    elif granularity == 'day':
        delta = timedelta(days=1)
        date_format = "%Y-%m-%d"
        max_points = 366
    elif granularity == 'week':
        delta = timedelta(weeks=1)
        date_format = "%Y-W%W"
        max_points = 104  # 2年
    elif granularity == 'month':
        delta = timedelta(days=30)
        date_format = "%Y-%m"
        max_points = 60  # 5年
    elif granularity == 'year':
        delta = timedelta(days=365)
        date_format = "%Y"
        max_points = 10
    else:
        delta = timedelta(days=1)
        date_format = "%Y-%m-%d"
        max_points = 366
    
    # 使用PostgreSQL的date_trunc进行高效分组查询
    # 定义分组粒度映射
    trunc_mapping = {
        'hour': 'hour',
        'day': 'day',
        'week': 'week',
        'month': 'month',
        'year': 'year'
    }
    
    trunc_type = trunc_mapping.get(granularity, 'day')
    
    # 执行单次GROUP BY查询
    results = db.query(
        func.date_trunc(trunc_type, Call.created_at).label('time_bucket'),
        func.count(Call.id).label('call_count')
    ).filter(
        and_(
            Call.created_at >= start_time,
            Call.created_at <= end_time
        )
    ).group_by('time_bucket').order_by('time_bucket').all()
    
    # 创建结果字典以便快速查找
    # 注意：去除时区信息用于匹配
    results_dict = {}
    for result in results:
        # 将时区aware的datetime转为naive（去掉tzinfo），只保留UTC时间
        if result.time_bucket:
            key = result.time_bucket.replace(tzinfo=None)
            results_dict[key] = result.call_count
    
    # 生成完整的时间序列（包括0值数据点）
    trend_data = []
    current = start_time
    point_count = 0
    
    while current < end_time and point_count < max_points:
        # 对齐到粒度边界
        if granularity == 'hour':
            bucket_time = current.replace(minute=0, second=0, microsecond=0, tzinfo=None)
        elif granularity == 'day':
            bucket_time = current.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        elif granularity == 'week':
            # 周的开始（周一）
            days_since_monday = current.weekday()
            bucket_time = (current - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None
            )
        elif granularity == 'month':
            bucket_time = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        elif granularity == 'year':
            bucket_time = current.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        else:
            bucket_time = current.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        
        # 从结果字典中获取该时间段的数据
        call_count = results_dict.get(bucket_time, 0)
        
        # 格式化时间字符串用于显示（使用带时区的原始时间）
        display_time = current.replace(second=0, microsecond=0) if granularity == 'minute' else bucket_time
        
        trend_data.append({
            "date": display_time.strftime(date_format) if isinstance(display_time, datetime) else bucket_time.strftime(date_format),
            "value": call_count,
            "group": "通话数"
        })
        
        # 移动到下一个时间点（使用带时区的时间计算）
        if granularity == 'minute':
            current = current + delta
        elif granularity == 'hour':
            current = current.replace(microsecond=0, second=0, minute=0) + delta
        elif granularity == 'day':
            current = current.replace(microsecond=0, second=0, minute=0, hour=0) + delta
        elif granularity in ['week', 'month', 'year']:
            # 对于week/month/year，从bucket开始计算
            current = current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current
            temp_bucket = bucket_time.replace(tzinfo=timezone.utc)
            current = temp_bucket + delta
        else:
            current = current + delta
            
        point_count += 1
    
    return trend_data
