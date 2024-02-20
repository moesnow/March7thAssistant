from datetime import datetime, timedelta


class Date:
    @staticmethod
    def is_next_x_am(timestamp, hour=4):
        dt_object = datetime.fromtimestamp(timestamp)
        current_time = datetime.now()

        if dt_object.hour < hour:
            next_x_am = dt_object.replace(hour=hour, minute=0, second=0, microsecond=0)
        else:
            next_x_am = dt_object.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=1)

        if current_time >= next_x_am:
            return True

        return False

    @staticmethod
    def is_next_mon_x_am(timestamp, hour=4):
        dt_object = datetime.fromtimestamp(timestamp)
        current_time = datetime.now()

        if dt_object.weekday() == 0 and dt_object.hour < hour:
            next_monday_x_am = dt_object.replace(hour=hour, minute=0, second=0, microsecond=0)
        else:
            days_until_next_monday = (7 - dt_object.weekday()) % 7 if dt_object.weekday() != 0 else 7
            next_monday_x_am = dt_object.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days_until_next_monday)

        if current_time >= next_monday_x_am:
            return True

        return False

    @staticmethod
    def get_time_next_x_am(hour=4):
        now = datetime.now()
        next_x_am = now.replace(hour=hour, minute=0, second=0, microsecond=0)

        if now >= next_x_am:
            next_x_am += timedelta(days=1)

        time_until_next_x_am = next_x_am - now

        return int(time_until_next_x_am.total_seconds())

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
