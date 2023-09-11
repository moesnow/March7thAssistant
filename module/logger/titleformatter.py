class TitleFormatter:
    @staticmethod
    def custom_len(s):
        length = 0
        for char in s:
            # 判断是否是中文字符和全角符号的Unicode范围
            if (ord(char) >= 0x4E00 and ord(char) <= 0x9FFF) or (ord(char) >= 0xFF00 and ord(char) <= 0xFFEF):
                length += 2
            else:
                length += 1
        return length

    @staticmethod
    def format_title(title, level=0):
        try:
            separator_length = 115
            title_lines = title.split('\n')
            separator = '+' + '-' * separator_length + '+'
            title_length = TitleFormatter.custom_len(title)
            half_separator_left = (separator_length - title_length) // 2
            half_separator_right = separator_length - title_length - half_separator_left

            if level == 0:
                formatted_title_lines = []

                for line in title_lines:
                    title_length_ = TitleFormatter.custom_len(line)
                    half_separator_left_ = (separator_length - title_length_) // 2
                    half_separator_right_ = separator_length - title_length_ - half_separator_left_

                    formatted_title_line = '|' + ' ' * half_separator_left_ + line + ' ' * half_separator_right_ + '|'
                    formatted_title_lines.append(formatted_title_line)

                print(separator)
                print('\n'.join(formatted_title_lines))
                print(separator)
            elif level == 1:
                formatted_title = '=' * half_separator_left + ' ' + title + ' ' + '=' * half_separator_right
                print(f"{formatted_title}")
            elif level == 2:
                formatted_title = '-' * half_separator_left + ' ' + title + ' ' + '-' * half_separator_right
                print(f"{formatted_title}")
        except:
            pass
