# 长夜月彩蛋素材

本目录提供长夜月主题彩蛋素材；运行时不联网加载，不改变原有三月七素材。

- `banner.png`：使用内置 image_gen 生成的同人插画，参照项目原有 `../bg37.jpg` 的画风/横幅构图，以及长夜月官方宣传立绘的角色设计。保留左上标题空间。
- `avatar.png`：使用内置 image_gen 生成的同人 Q 版头像，参照项目原有 `../March7th.jpg` 的画风、头身比和背景，以及长夜月官方表情的角色设计。保留为原图；深色界面使用 `../dark/Evernight.png` 透明版本，由界面叠加淡纹。
- `icon.png` / `icon.ico`：独立的豆豆眼长夜月小角标，匹配原三月七角标的简洁头身比例，透明背景。标题栏、系统托盘及 Windows 任务栏共用；提示词与 ICO 打包说明见 [深色素材说明](../dark/README.md)。
- `evey-floating.png`：使用内置 image_gen 根据官方立绘和游戏内红色形态参考生成的透明同人素材。Qt 驱动约 5.2 秒的淡入、漂移、上下浮动、摆动和淡出。无边框、无战斗场景、无音轨；临时工具窗口不添加任务栏入口，不抢焦点，鼠标穿透，可按 Esc 或切回浅色结束。

角色、原始美术和游戏画面属于《崩坏：星穹铁道》及其权利方；这里记录来源，不把第三方素材重新声明为本项目代码的许可证。

## 来源

- [官方角色页面（Evernight）](https://hsr.hoyoverse.com/en-us/character?charIndex=12&worldIndex=11)
- [BWiki 长夜月资料与技能演示](https://wiki.biligame.com/sr/长夜月)
- [BWiki 聊天表情](https://wiki.biligame.com/sr/聊天表情)
- 角色立绘参考：https://patchwiki.biligame.com/images/sr/9/9b/7s6sqw32vxisniguc9zygumm16e9lgf.png
- Q 版身份参考：https://patchwiki.biligame.com/images/sr/e/e3/2ri3630o2lnvfwlgo6flizdzsx7gwhq.png
- 红色形态的参考片段：https://patchwiki.biligame.com/images/sr/5/58/19hie4xnqhmivv44w83yt9pf0jtxl8l.gif

## 交互约定

5 秒内手动切换主题 3 次解锁，仅本次运行有效。首次显示解锁后的深色界面时，先保留三月七封面、完整运行头像和角标，播放一次「长夜」悬浮动画；播放到一半（约 2.6 秒）时，三处图片及中英文标题、托盘和任务栏同步切换为长夜月，剩余动画继续播放并淡出。之后的深浅色切换立即显示长夜月或还原用户自己的三月七背景和卡片图标，不再重复动画。如果第 3 次切换落在浅色或窗口隐藏，动画等到深色主窗口显示后才开始。按 Esc 可跳过动画并完成替换；中途切回浅色则结束动画并显示三月七。隐藏/关闭主窗口或播完都会释放动画。系统主题事件不计入三次点击。默认整排任务头像在普通深色模式下也使用透明底和人物淡纹，浅色恢复原图；用户自选图片不重写。

## 生成提示词

### banner.png

```text
Use case: illustration-story.
Asset type: wide home-page banner for a desktop Honkai: Star Rail fan assistant.
Create a finished 2560x1160 horizontal anime illustration of Evernight (长夜月) from Honkai: Star Rail, matching the crisp linework, detailed cel shading, polished game illustration quality and close-up composition of reference image 1 (the existing March 7th app banner). Image 1 is STYLE AND LAYOUT reference only; image 2 is the exact CHARACTER IDENTITY reference.
Show Evernight prominently from waist up at center-right, pale pink/lilac hair, crimson red eyes, the same purple-black flower ornament, black/lavender gothic outfit with the red and silver details from image 2. Calm, confident, slightly playful smile; elegant outstretched gloved hand. Preserve her actual design, do not give her March 7th's blue outfit or camera.
Background: a richly illustrated dreamlike nighttime memory scene with mirrors, floating photograph-like panels, pale lilac flowing ribbons and subtle red petals, cohesive with the visual density of image 1. Keep the upper-left quarter dark and quieter so the app can overlay two lines of large white title text. Her full head and eyes must remain inside the upper 60 percent, with a generous margin above her hair, so top-aligned crops still show her face.
Palette: lavender, muted midnight plum and pale pink with small crimson accents. Still colorful and readable, no gloomy horror. Two-dimensional anime game art, not 3D, not photorealistic, not a chibi.
No text, no lettering, no logo, no watermark, no user interface, no border, no extra characters.
```

### avatar.png

```text
Use case: illustration-story.
Asset type: square chibi character illustration for a desktop app task card and a small application icon.
Reference image 1 is the exact STYLE, COMPOSITION and DETAIL reference: the existing March 7th card portrait. Reference image 2 supplies the identity of Evernight (长夜月), not its simpler sticker rendering.
Create Evernight from Honkai: Star Rail in the same polished detailed 2D chibi anime style as image 1: large expressive red eyes, pale pink/lilac hair, recognizable dark purple flower ornament at the side of her head, black/lavender gothic outfit with silver trim and red jewel. Large head, upper torso, one small gloved hand held near her face, a playful confident gentle smile. Preserve the character's official design.
Match the soft clean colored linework, pastel hair highlights, detailed cel shading, head-to-body ratio, square close-up framing and bright pale patterned background of image 1. A faint larger silhouette of the same Evernight portrait may decorate the near-white lilac background as in image 1. Subject fills most of square but keep flower and hair tips inside frame. The face must remain readable at 24x24 pixels. 1024x1024 square.
No text, no letters, no exclamation marks, no speech bubbles, no UI, no watermark. This is a finished illustration, not a sticker sheet.
```

## evey-floating.png 生成提示词

```text
Use case: stylized-concept.
Asset type: a single transparent PNG character sprite for a desktop splash animation.
Create Evey (忆灵「长夜」), Evernight's memosprite from Honkai: Star Rail, in its CRIMSON RED enhanced form, isolated in midair. Reference 1 contains the memosprite's official pale lavender/white anatomy to the right of Evernight; use only that non-human flower/jellyfish creature as the silhouette reference. Reference 2 shows its enhanced red form in the left half of the game screen; use only that red creature for the color and identity reference.
Full creature: elegant flower-like jellyfish bell made of pointed, overlapping translucent petals, the distinctive central four-petal flower motif and brilliant crimson core, several slender long curling ribbon-like tendrils flowing downward and to the left. Three-quarter side view, floating gently, a graceful diagonal silhouette. Delicate inner vein lines and controlled red/pink emissive edges; deep crimson translucent body with rose highlights. Match the polished 2D anime game illustration quality used in the companion app, with clear readable silhouette at roughly 320 pixels tall.
This is NOT an attack scene. No enemies, no damage numbers, no energy beam, no explosion, no human character. No face or cartoon eyes. No text, logos, buttons, frames, background scene, ground, cast shadow, or checkerboard. Genuine alpha-transparent background; gentle glow contained close to the creature. Keep the entire body, glow and every tentacle comfortably inside the canvas with generous transparent padding. One complete sprite only, not a sheet, not multiple poses.
```
