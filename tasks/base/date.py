from datetime import datetime, timedelta


class Date:
    @staticmethod
    def is_next_4_am(timestamp):
        dt_object = datetime.fromtimestamp(timestamp)
        current_time = datetime.now()
        if dt_object.hour < 4:
            next_4am = dt_object.replace(
                hour=4, minute=0, second=0, microsecond=0)
        else:
            next_4am = dt_object.replace(
                hour=4, minute=0, second=0, microsecond=0) + timedelta(days=1)
        if current_time >= next_4am:
            return True
        return False

    @staticmethod
    def is_next_mon_4_am(timestamp):
        dt_object = datetime.fromtimestamp(timestamp)
        current_time = datetime.now()
        if dt_object.weekday() == 0 and dt_object.hour < 4:
            next_monday_4am = dt_object.replace(
                hour=4, minute=0, second=0, microsecond=0)
        else:
            days_until_next_monday = (
                7 - dt_object.weekday()) % 7 if dt_object.weekday() != 0 else 7
            next_monday_4am = dt_object.replace(
                hour=4, minute=0, second=0, microsecond=0) + timedelta(days=days_until_next_monday)
        if current_time >= next_monday_4am:
            return True
        return False

    @staticmethod
    def get_time_next_4am():
        now = datetime.now()
        next_4am = now.replace(hour=4, minute=0, second=0, microsecond=0)

        if now >= next_4am:
            next_4am += timedelta(days=1)

        time_until_next_4am = next_4am - now
        return int(time_until_next_4am.total_seconds())

    @staticmethod
    def calculate_future_time(seconds):
        current_time = datetime.now()
        future_time = current_time + timedelta(seconds=seconds)
        if future_time.date() == current_time.date():
            return f"今天{future_time.hour}时{future_time.minute}分"
        elif future_time.date() == current_time.date() + timedelta(days=1):
            return f"明天{future_time.hour}时{future_time.minute}分"
        else:
            return "输入秒数不合法"
