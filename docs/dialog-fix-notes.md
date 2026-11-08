# 对话框（弹窗）修复经验记录

> 记录 2026-09「按键设置弹窗」与「发现新版本 更新弹窗」一组修复中踩掉的坑、根因与验证方法。
> 适用于本仓库所有基于 qfluentwidgets `MaskDialogBase` 的自定义弹窗（`app/card/messagebox_custom.py` 家族、
> `app/sub_interfaces/hotkey_interface.py` 等）。
>
> 相关提交：`a06b8fce` `1eb0eec3` `09da6ef7` `b0282c6d` `0bf5e23f` `f6d0f546` `9569ba20` `20302847`

## 一、结论速查表

| 现象 | 根因 | 修法 |
|---|---|---|
| 内容一长，底部按钮被裁、点不到 | 遮罩窗口尺寸**跟随父窗口**而非屏幕，内容按屏幕高度做预算必然溢出 | 高度预算 = 父窗口高度 − 非滚动部分（chrome） |
| 弹窗塌成一小条、只显示一行 | `QScrollArea` 的 `sizeHint` 远小于实际内容，弹窗按**最小尺寸**收缩 | 以内容真实尺寸为滚动区最小尺寸撑开弹窗，超高部分内部滚动 |
| 卡片/按钮被横向裁切 | 纵向滚动条出现后视口变窄，而横向滚动条被禁用 | 滚动区最小宽度 = 内容下限 + 滚动条占位（约 20px） |
| 开关动画时外框渐变、内容瞬间闪现/消失 | 基类把 `QGraphicsOpacityEffect` **整窗**挂载，无法正确栅格化 QScrollArea 视口内容 | 拆分到遮罩/外壳/滚动内容分别挂效果、同一动画组同步驱动（`SplitFadeDialogMixin`） |
| 滚动区底色与外框割裂（深色下尤其明显） | 内容容器以调色板色自填底（**固定 #1e1e1e**，与主题无关），半透明子部件被染脏 | 容器 `setAutoFillBackground(False)` + 视口透明 |
| 视口透明后卡片颜色也变了 | 无选择器的 `background: transparent` **样式级联**到全部后代 | 视口样式规则用 `objectName` 限定选择器，只作用于自身 |
| 弹窗高度算不准、按钮仍然溢出 | 卡片 `sizeHint` 谎报（如 34px，实际 70px） | 先入布局 `activate()`，取布局后的**真实高度**再算 chrome |
| 点取消后弹窗迟迟不关闭 | 逐项 `set_value` 恢复配置 = 14 次带 fsync 的全量落盘（约 1.1s） | 无改动零落盘；有改动 `cfg.set_values` 批量一次落盘 |
| 测试窗口堆积到进程退出才统一关闭 | `deleteLater` 是延迟删除，`processEvents` 驱动的测试流程一直处理不到 | `tests/conftest.py` 自动收尾：用例结束立即隐藏并销毁可见顶层窗口 |

## 二、尺寸与滚动

### 1. 预算按父窗口算，不按屏幕算

`MaskDialogBase` 的窗口几何是 `setGeometry(0, 0, parent.width(), parent.height())`——
遮罩铺满**父窗口**，内容框居中其中。主窗口比屏幕矮时，按屏幕高度做的预算必然被父窗口下沿裁掉。

```python
from app.common.scroll_dialog import available_host_size
host_width, host_height = available_host_size(parent)   # 父窗口尺寸（无父窗口才退化为屏幕）
```

### 2. 滚动区必须以内容尺寸为最小尺寸

`QScrollArea.sizeHint()` 不等于内容尺寸（实测内容 476×533、滚动区只报 476×360、最小高度接近 0），
弹窗按最小尺寸收缩时会塌成一条。修法见 `build_scroll_area()`：

- `scroll.setMinimumHeight(min(内容高, 上限))`：内容少时紧凑，超高时撑到上限内部滚动
- `scroll.setMaximumHeight(上限)`，上限 = `host_height - chrome`
- `scroll.setMinimumWidth(min(内容宽 + 20, host_width - 120))`：给纵向滚动条留占位

### 3. chrome 要算全，高度要用真值

chrome = 文本布局上下边距 + 标题 + **全部固定部分**（如更新卡片）+ 按钮区 + 间距 + 余量（24px）。
注意 `PrimaryPushSettingCard` 这类自定义卡片的 `sizeHint` 会谎报（34 vs 实际 70），
先把卡片加进布局并 `self.textLayout.activate()`，再取 `card.height()` 真值。

### 4. 只滚可变内容，操作入口固定

更新弹窗的设计原则：**只滚动更新日志**（变量），「开源渠道 / Mirror酱 立即更新」两张操作卡片
和底部按钮固定在滚动区外，任何时候可见可点。凡是"操作入口"都不该被滚走。

## 三、开关动画

1. **`windowOpacity` 对 `WA_TranslucentBackground` 无边框窗无效**（实测设 0.3 无任何变化）。
2. **整窗挂 `QGraphicsOpacityEffect` 会漏栅格化 QScrollArea 视口内容**：
   背景淡了但文字/图标不参与，动画收尾 `setGraphicsEffect(None)` 触发整体重绘时内容"闪现"。
   对照实验：普通 MessageBox 均匀淡、拆分挂效果均匀淡、整窗挂 + 滚动区必坏。
3. 修法：`SplitFadeDialogMixin`（`app/common/scroll_dialog.py`）——对 **windowMask、widget（外壳）、
   滚动内容容器**分别挂效果，`QParallelAnimationGroup` 同步驱动；动画收尾统一清理并恢复
   内容框投影（`setShadowEffect()`）；淡出中忽略重复关闭请求、淡入中可直接转入淡出。

```python
class MyDialog(SplitFadeDialogMixin, MessageBox):
    def __init__(self, title, content, parent=None):
        super().__init__(title, content, parent)
        ...
        self._scroll = build_scroll_area(container, host_width, host_height, chrome)
        # 之后无需额外代码：showEvent/done 的分体动画由 mixin 接管
```

## 四、背景底色

- 滚动区内容容器会以调色板色自填底（**#1e1e1e，与主题无关**）：浅色下面板 `#ffffff` 色差高达 225，
  深色下面板 `#2b2b2b` 色差 13（肉眼可见的割裂带）；半透明卡片还会被这块底色染脏。
- 修法（两件事都要做）：
  1. `container.setAutoFillBackground(False)`
  2. `scroll.viewport().setStyleSheet("#<objectName> { background: transparent; }")`——
     **必须用 objectName 限定选择器**，无选择器规则会级联到所有后代，把卡片自身配色改掉。
- 验证方式：逐像素取色，与"真正原始结构"（卡片直接贴面板、无滚动区）对照，
  浅/深两套主题下应**完全一致**（见 `tests/test_app/test_hotkey_interface.py::TestHotkeyScrollBackground`）。

## 五、配置写盘放大（顺带修掉的取消卡顿）

- `Config.set_value` 每次调用会保存**两遍**（`_load_config` 默认 `save=True` 又存一次），
  而 `save_config` 带 `fsync`（单次实测约 40ms）。逐项恢复 7 项配置 = 14 次落盘 ≈ 1.1 秒。
- 修法：对话框取消恢复时**比对备份，未改动的不写**；需要写时用 `Config.set_values` 批量一次落盘
  （实测：直接取消 1085ms → 0.5ms；改一项取消 → 95ms）。

## 六、验证方法论（这套流程救了至少三次）

1. **探针先行、像素说话**：不要靠目测和推理，写 `temp/probe_*.py` 采样渲染结果。
2. **`QWidget.grab()` 会绕过图形效果**直接渲染部件树——验证透明度动画必须全屏抓取
   （`QScreen.grabWindow(0)`）再裁剪，抓的是合成器结果。
3. **坐标会说谎**：本环境中 `geometry()` 报 (0,0) 而窗口真实位置是 (484,198)，
   `mapToGlobal` 反而是对的；重要结论用 Win32 `GetWindowRect` 做独立旁证。
4. **采样点避开文字**：LCD 次像素抗锯齿在字形边缘产生彩边（#660066、#bfffbf 这类假色），
   会让"底色不一致"误报/漏报。取纯色块内部或文字旁的空白区。
5. **截图加水印**：并行读图/多方案抓图容易串图，保存前用 QPainter 画上方案名。
6. **ground truth 用复刻对照**：判断"和以前一样"的唯一可靠标准，是把改动前的原始结构
   重建出来逐像素对比，而不是凭印象。

## 七、测试护栏清单

- **数值断言**：底色色差 ≤ 2；按钮底边 ≤ 窗口高（用布局算术 `widget.y + buttonGroup.y + height`，
  **不用 `mapToGlobal`**——它会被窗口实际摆放位置干扰）。
- **长动画钉状态**：`_start_fade(0.5, 0.5, 5000, None)` 再断言效果挂载位置，避免时间敏感。
- **主题参数化**：浅/深两套都测，用 `qconfig.theme` 保存恢复。
- **计时断言留余量**：等动画 0.6s（动画 200ms）、关闭断言 2s（实际约 120ms）。
- **窗口自动收尾**：`tests/conftest.py` 的 autouse fixture，用例结束立即隐藏销毁顶层窗口
  （`deleteLater` 在 `processEvents` 驱动的测试里可能永远处理不到）。
- **平台门禁**：真开窗口的用例 `pytestmark = skipif(sys.platform != "win32"...)`，
  非 Windows 的 CI 腿要么跳过、要么只跑纯逻辑；相关用例已通过 `QT_QPA_PLATFORM=offscreen` 无头冒烟。

## 八、已知同族风险（后续工作）

- `app/card/messagebox_custom.py` 家族的其他弹窗（`MessageBoxHtml`、`MessageBoxDisclaimer`、
  `MessageBoxInstance` 等）内容超长时同样存在按钮被裁风险，修法照抄本页 + `scroll_dialog` 组件即可。
- 全局 `time.sleep`（500+ 处）与硬编码资源路径是另一族问题，与弹窗无关，见仓库 issue 讨论。
