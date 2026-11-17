import time

from module.logger import log
from module.ocr import ocr
from tasks.power.policy import PowerError, parse_immersifier_stock


def read_number(auto, crop, parse, error, *, retries=6, single_line=False):
    """读取 crop 中的数字。

    single_line=True 表示 crop 只含一行文字：先跳过文本检测直接识别，
    解析失败再退回完整 OCR，兼顾速度与排版变化时的可靠性。
    """
    for _ in range(retries):
        frame, _, _ = auto.take_screenshot(crop=crop)
        if frame.width < 250:
            frame = frame.resize((frame.width * 2, frame.height * 2))
        lines = ocr.recognize_multi_lines(frame, recognition_only=single_line) or []
        # 保留 OCR 框边界，避免把相邻控件的数字拼进同一个读数。
        text = "\n".join(text for _, (text, _) in sorted(lines, key=lambda line: line[0][0][0]))
        if (value := parse(text)) is not None:
            return value
        if single_line:
            # 快路径没读出来时回退到完整检测：兼容多行 crop 与排版变化。
            lines = ocr.recognize_multi_lines(frame) or []
            text = "\n".join(text for _, (text, _) in sorted(lines, key=lambda line: line[0][0][0]))
            if (value := parse(text)) is not None:
                return value
        time.sleep(0.2)
    raise PowerError(error)


def read_immersifier_stock(auto, crop):
    try:
        stock = read_number(auto, crop, parse_immersifier_stock, "未能识别沉浸器库存", retries=3,
                            single_line=True)
    except Exception as error:
        log.warning(f"沉浸器库存按 0 个安排挑战（{error}）")
        return 0
    log.info(f"沉浸器：{stock}/12")
    return stock
