from module.logger import log
from module.ocr.ocr import OCR
import json

# 读取 OCR 替换配置
with open("./assets/config/ocr_replacements.json", 'r', encoding='utf-8') as file:
    replacements = json.load(file)
# 初始化 OCR 对象
ocr = OCR(log, replacements)
