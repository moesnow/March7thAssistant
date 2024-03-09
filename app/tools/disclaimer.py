from PyQt5.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition
from ..card.messagebox_custom import MessageBoxDisclaimer
from module.config import cfg
import markdown
import base64
import time
import sys
import os


def disclaimer(self):
    html_style = """
<style>
a {
    color: #f18cb9;
    font-weight: bold;
}
</style>
"""
    content = "LSDmraTnqIvluo/kuLrlhY3otLnlvIDmupDpobnnm67vvIzlpoLmnpzkvaDku5jkuobpkrHor7fnq4vliLvpgIDmrL7vvIHvvIHvvIEKCi0g5pys6aG555uu5bey57uP5Zug5YCS5Y2W6KGM5Li65Y+X5Yiw5Lil6YeN5aiB6IOB77yM6K+35biu5Yqp5oiR5Lus77yB77yB77yBCgotIOmXsumxvOWAkueLlzQwMDAr77yB5L2g5LuY57uZ5YCS54uX55qE5q+P5LiA5YiG6ZKx6YO95Lya6K6p5byA5rqQ6Ieq5Yqo5YyW5pu06Imw6Zq+77yM6K+36YCA5qy+5bm25Li+5oql5ZWG5a6277yB77yB77yBCgo8aDEgc3R5bGU9ImNvbG9yOiNmMThjYjkiPuazqOaEj++8mui9r+S7tuacquaOiOadg+S7u+S9leS6uuS7peS7u+S9leaWueW8j+i/m+ihjOWUruWNlu+8jDwvaDE+Cgo8aDEgc3R5bGU9ImNvbG9yOiNmMThjYjkiPuWmguWcqOmXsumxvOetieW3sui0reS5sO+8jOWPr+WHreatpOW8ueeql+aIquWbvuimgeaxgumAgOasvjwvaDE+CgrmnKzova/ku7blvIDmupDjgIHlhY3otLnvvIzku4XkvpvlrabkuaDkuqTmtYHkvb/nlKjjgILlvIDlj5HogIXlm6LpmJ/mi6XmnInmnKzpobnnm67nmoTmnIDnu4jop6Pph4rmnYPjgIIKCuS9v+eUqOacrOi9r+S7tuS6p+eUn+eahOaJgOaciemXrumimOS4juacrOmhueebruS4juW8gOWPkeiAheWboumYn+aXoOWFs+OAggoK6K+35rOo5oSP77yM5qC55o2uTWlIb1lv55qEIFvltKnlnY865pif56m56ZOB6YGT55qE5YWs5bmz5ri45oiP5a6j6KiAXShodHRwczovL3NyLm1paG95by5jb20vbmV3cy8xMTEyNDY/bmF2PW5ld3MmdHlwZT1ub3RpY2UpOgoKICAgICLkuKXnpoHkvb/nlKjlpJbmjILjgIHliqDpgJ/lmajjgIHohJrmnKzmiJblhbbku5bnoLTlnY/muLjmiI/lhazlubPmgKfnmoTnrKzkuInmlrnlt6XlhbfjgIIiCiAgICAi5LiA57uP5Y+R546w77yM57Gz5ZOI5ri477yI5LiL5Lqm56ew4oCc5oiR5Lus4oCd77yJ5bCG6KeG6L+d6KeE5Lil6YeN56iL5bqm5Y+K6L+d6KeE5qyh5pWw77yM6YeH5Y+W5omj6Zmk6L+d6KeE5pS255uK44CB5Ya757uT5ri45oiP6LSm5Y+344CB5rC45LmF5bCB56aB5ri45oiP6LSm5Y+3562J5o6q5pa944CCIg=="
    try:
        w = MessageBoxDisclaimer(base64.b64decode("5YWN6LSj5aOw5piO").decode("utf-8"), html_style + markdown.markdown(base64.b64decode(content).decode("utf-8")), self.window())
        while True:
            start_time = time.time()
            result = w.exec()
            if result:
                sys.exit(0)
            time_used = time.time() - start_time
            if time_used > 10:
                break
            else:
                InfoBar.error(
                    title=base64.b64decode("6ZiF6K+75pe26Ze05aSq55+t5LqG77yM5aSa5YGc55WZ5LiA5Lya5ZCnKO+8vuKIgO+8vuKXjyk=").decode("utf-8"),
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self.window()
                )
        if not result:
            cfg.set_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8"), True)
            path = os.path.join(os.environ[base64.b64decode("UHJvZ3JhbURhdGE=").decode("utf-8")], base64.b64decode("TWFyY2g3dGhBc3Npc3RhbnQvZGlzY2xhaW1lcg==").decode("utf-8"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'a').close()
        else:
            sys.exit(0)
    except Exception:
        sys.exit(0)
