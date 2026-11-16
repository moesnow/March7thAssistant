import time

from module.logger import log
from module.ocr import ocr
from tasks.power.policy import PowerError, parse_immersifier_stock


def read_number(auto, crop, parse, error, *, retries=6):
    for _ in range(retries):
        frame, _, _ = auto.take_screenshot(crop=crop)
        if frame.width < 250:
            frame = frame.resize((frame.width * 2, frame.height * 2))
        lines = ocr.recognize_multi_lines(frame) or []
        # 保留 OCR 框边界，避免把相邻控件的数字拼进同一个读数。
        text = "\n".join(text for _, (text, _) in sorted(lines, key=lambda line: line[0][0][0]))
        if (value := parse(text)) is not None:
            return value
        time.sleep(0.2)
    raise PowerError(error)


def read_immersifier_stock(auto, crop):
    try:
        stock = read_number(auto, crop, parse_immersifier_stock, "未能识别沉浸器库存", retries=3)
    except Exception as error:
        log.warning(f"沉浸器库存按 0 个安排挑战（{error}）")
        return 0
    log.info(f"沉浸器：{stock}/12")
    return stock
