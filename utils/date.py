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
    def calculate_future_time(input_data):
        current_time = datetime.now()

        # 如果输入是整数（表示秒数）
        if isinstance(input_data, int):
            future_time = current_time + timedelta(seconds=input_data)
        # 如果输入是字符串（格式如 "HH:MM"）
        elif isinstance(input_data, str):
            try:
                # 提取时分并构造当天的目标时间
                input_time = datetime.strptime(input_data, "%H:%M").time()
                future_time = datetime.combine(current_time.date(), input_time)
                # 如果目标时间已经过了今天，则认为是明天的时间
                if future_time <= current_time:
                    future_time += timedelta(days=1)
            except ValueError:
                return "输入的时间格式不合法，应为 'HH:MM'"
        else:
            return "输入数据类型不支持，请输入秒数或时间字符串"

        # 判断并返回对应的时间描述
        if future_time.date() == current_time.date():
            return f"今天{future_time.hour}时{future_time.minute}分"
        elif future_time.date() == current_time.date() + timedelta(days=1):
            return f"明天{future_time.hour}时{future_time.minute}分"
        elif future_time.date() == current_time.date() + timedelta(days=2):
            return f"后天{future_time.hour}时{future_time.minute}分"
        else:
            return "输入秒数或时间超出范围"

    @staticmethod
    def time_to_seconds(time_str):
        try:
            # 获取当前时间
            current_time = datetime.now()

            # 将输入时间字符串解析为时间对象
            target_time = datetime.strptime(time_str, "%H:%M").time()

            # 构造当天的目标时间
            target_datetime = datetime.combine(current_time.date(), target_time)

            # 如果目标时间已经过了今天，则调整为明天的时间
            if target_datetime <= current_time:
                target_datetime += timedelta(days=1)

            # 计算剩余秒数
            remaining_seconds = int((target_datetime - current_time).total_seconds())

            return remaining_seconds
        except ValueError:
            return "输入的时间格式不合法，应为 'HH:MM'"
