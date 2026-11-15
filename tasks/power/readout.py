import time

from module.ocr import ocr
from tasks.power.policy import PowerError, normalize, parse_power


def read_number(auto, crop, parse, error, *, retries=6, sep=""):
    for _ in range(retries):
        frame, _, _ = auto.take_screenshot(crop=crop)
        if frame.width < 250:
            frame = frame.resize((frame.width * 2, frame.height * 2))
        lines = ocr.recognize_multi_lines(frame) or []
        text = sep.join(text for _, (text, _) in sorted(lines, key=lambda line: line[0][0][0]))
        if (value := parse(text)) is not None:
            return value
        time.sleep(0.2)
    raise PowerError(error)


def parse_power_lines(text):
    """解析开拓力区域多框 OCR 结果，忽略左侧被裁切的后备开拓力余数（如 ['5', '25/300']）。"""
    parts = [part for part in text.splitlines() if part.strip()]
    for start in range(len(parts)):
        if (value := parse_power(" ".join(parts[start:]))) is not None:
            if start == 0 or all(normalize(item).isdecimal() for item in parts[:start]):
                return value
    return None


def read_power(auto, crop, error="未能确认当前开拓力", *, retries=6):
    return read_number(auto, crop, parse_power_lines, error, retries=retries, sep="\n")
