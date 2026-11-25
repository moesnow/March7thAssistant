# 长夜月彩蛋素材

本目录提供长夜月主题彩蛋素材；运行时不联网加载，不改变原有三月七素材。

- Q 版长夜月位于 `assets/app/images/mascot/evernight/`，说明见 [Q 版形象说明](../mascot/README.md)。
- 长夜月应用图标位于 `assets/logo/evernight/icon.ico`：左上角、任务栏与托盘统一使用紫色装饰底，说明见 [应用图标说明](../../../logo/README.md)。
- `evey-floating.png`：使用内置 image_gen 根据官方立绘和游戏内红色形态参考生成的透明同人素材。Qt 驱动约 5.2 秒的淡入、漂移、上下浮动、摆动和淡出。无边框、无战斗场景、无音轨；临时工具窗口不添加任务栏入口，不抢焦点，鼠标穿透，可按 Esc 或切回普通主题结束。
- `evey-decoration-wide.png`（1 号）、`evey-decoration-folded.png`（2 号）、`evey-decoration-upright.png`（3 号）：使用内置 image_gen 新绘制并经用户认可的鲜红色水母图片。2 号位于顶部最小化/最大化/关闭按钮区域的底层，1 号衬在主题选择框背后，3 号衬在侧边栏“设置”按钮背后，始终保留原有齿轮和文字。图片适度超出下拉框和设置按钮边缘，不占用布局空间，主题设置条保持 70 逻辑像素高；首次解锁时与问候区背景一起在动画中点显示，装饰不拦截鼠标，切回普通主题后隐藏。伞帽严格为四片彼此贴合或搭接的叶状薄膜，触手为有宽度和扭转层次的半透明丝带。参考用户提供的四叶结构截图及原动画素材的材质，新绘姿态与构图；没有裁切或直接复用 `evey-floating.png`。

角色、原始美术和游戏画面属于《崩坏：星穹铁道》及其权利方；这里记录来源，不把第三方素材重新声明为本项目代码的许可证。

## 来源

- [官方角色页面（Evernight）](https://hsr.hoyoverse.com/en-us/character?charIndex=12&worldIndex=11)
- [BWiki 长夜月资料与技能演示](https://wiki.biligame.com/sr/长夜月)
- [BWiki 聊天表情](https://wiki.biligame.com/sr/聊天表情)
- 角色立绘参考：https://patchwiki.biligame.com/images/sr/9/9b/7s6sqw32vxisniguc9zygumm16e9lgf.png
- Q 版身份参考：https://patchwiki.biligame.com/images/sr/e/e3/2ri3630o2lnvfwlgo6flizdzsx7gwhq.png
- 红色形态的参考片段：https://patchwiki.biligame.com/images/sr/5/58/19hie4xnqhmivv44w83yt9pf0jtxl8l.gif

## 交互约定

在 5 秒内点击主窗口左上角 LOGO 五次，总览问候区显示「别晃啦！」提示，小人临时切换为眼花姿势。提示持续 5 秒，期间再点击五次即可解锁并保存「长夜」主题。切换设置、系统主题变化均不计入点击。

首次解锁播放忆灵悬浮动画，在中点切换问候区的背景和小人、窗口及托盘图标、强调色和三处装饰。切换背景时文字和按钮保持清晰。按 Esc 可提前完成切换；切回普通主题时恢复原有外观和用户自选背景。以后选择长夜会立即生效，重启后仍可使用已解锁的选项。程序在解锁时检查图标和装饰，关键素材损坏时保留原主题。

## evey-floating.png 生成提示词

```text
Use case: stylized-concept.
Asset type: a single transparent PNG character sprite for a desktop splash animation.
Create Evey (忆灵「长夜」), Evernight's memosprite from Honkai: Star Rail, in its CRIMSON RED enhanced form, isolated in midair. Reference 1 contains the memosprite's official pale lavender/white anatomy to the right of Evernight; use only that non-human flower/jellyfish creature as the silhouette reference. Reference 2 shows its enhanced red form in the left half of the game screen; use only that red creature for the color and identity reference.
Full creature: elegant flower-like jellyfish bell made of pointed, overlapping translucent petals, the distinctive central four-petal flower motif and brilliant crimson core, several slender long curling ribbon-like tendrils flowing downward and to the left. Three-quarter side view, floating gently, a graceful diagonal silhouette. Delicate inner vein lines and controlled red/pink emissive edges; deep crimson translucent body with rose highlights. Match the polished 2D anime game illustration quality used in the companion app, with clear readable silhouette at roughly 320 pixels tall.
This is NOT an attack scene. No enemies, no damage numbers, no energy beam, no explosion, no human character. No face or cartoon eyes. No text, logos, buttons, frames, background scene, ground, cast shadow, or checkerboard. Genuine alpha-transparent background; gentle glow contained close to the creature. Keep the entire body, glow and every tentacle comfortably inside the canvas with generous transparent padding. One complete sprite only, not a sheet, not multiple poses.
```
