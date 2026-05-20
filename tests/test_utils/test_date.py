from datetime import datetime, timedelta
from unittest.mock import patch
from utils.date import Date


class TestDate:
    def test_is_next_x_am_already_passed(self):
        # 时间戳是昨天凌晨3点，当前时间已过今天凌晨4点
        yesterday_3am = datetime.now().replace(hour=3, minute=0, second=0) - timedelta(days=1)
        timestamp = yesterday_3am.timestamp()
        assert Date.is_next_x_am(timestamp, hour=4) is True

    def test_is_next_x_am_not_passed(self):
        # 时间戳是今天凌晨3点，当前时间还没到今天凌晨4点
        today_3am = datetime.now().replace(hour=3, minute=0, second=0)
        with patch('utils.date.datetime') as mock_dt:
            mock_dt.now.return_value = today_3am
            mock_dt.fromtimestamp = datetime.fromtimestamp
            assert Date.is_next_x_am(today_3am.timestamp(), hour=4) is False

    def test_is_next_mon_x_am_passed(self):
        # 上周一的时间戳
        last_week = datetime.now() - timedelta(weeks=1)
        timestamp = last_week.timestamp()
        assert Date.is_next_mon_x_am(timestamp, hour=4) is True

    def test_is_next_month_x_am_passed(self):
        # 上个月的时间戳
        last_month = datetime.now() - timedelta(days=32)
        timestamp = last_month.timestamp()
        assert Date.is_next_month_x_am(timestamp, hour=4) is True

    def test_is_next_2weeks_mon_x_am_passed(self):
        # 两周前的时间戳
        two_weeks_ago = datetime.now() - timedelta(weeks=2)
        timestamp = two_weeks_ago.timestamp()
        assert Date.is_next_2weeks_mon_x_am(timestamp, hour=4) is True

    def test_get_time_next_x_am(self):
        result = Date.get_time_next_x_am(hour=4)
        assert isinstance(result, int)
        assert 0 < result <= 86400  # 应该在 0 到 24小时之间

    def test_calculate_future_time_seconds(self):
        result = Date.calculate_future_time(3600)  # 1小时后
        assert "时" in result and "分" in result

    def test_calculate_future_time_hhmm(self):
        result = Date.calculate_future_time("23:59")
        assert "时" in result and "分" in result

    def test_calculate_future_time_invalid_format(self):
        result = Date.calculate_future_time("invalid")
        assert "不合法" in result

    def test_calculate_future_time_unsupported_type(self):
        result = Date.calculate_future_time(3.14)
        assert "不支持" in result

    def test_time_to_seconds_valid(self):
        result = Date.time_to_seconds("23:59")
        assert isinstance(result, int)
        assert result > 0

    def test_time_to_seconds_invalid(self):
        result = Date.time_to_seconds("invalid")
        assert "不合法" in result
