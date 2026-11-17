# 长夜月彩蛋素材

本目录提供长夜月主题彩蛋素材；运行时不联网加载，不改变原有三月七素材。

- `banner.png`：使用内置 image_gen 生成的同人插画，参照项目原有 `../bg37.jpg` 的画风/横幅构图，以及长夜月官方宣传立绘的角色设计。人物头顶接近上边缘，短横幅中可见腰腹部，保留左上标题空间；构图修订提示词见下文。
- `avatar.png`：使用内置 image_gen 生成的同人 Q 版头像，参照项目原有 `../March7th.jpg` 的画风、头身比和背景，以及长夜月官方表情的角色设计。保留为原图；深色界面使用 `../dark/Evernight.png` 透明版本，由界面叠加淡纹。
- 豆豆眼长夜月应用图标位于 `assets/logo/evernight/`：任务栏与托盘使用白色装饰底，左上角使用黑灰色装饰底；两组图标与生成说明见 [应用图标说明](../../../logo/README.md)。
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

在 5 秒内连续点击主窗口左上角 LOGO 3 次立即解锁并开始动画，仅本次运行有效。前两次点击不改变主题；第 3 次点击时若当前为浅色，自动选择并保存“深色”，已是深色则直接播放。主题选项位于“设置 → 程序 → 界面主题”，默认为跟随系统。首次触发时，先保留三月七封面、完整运行头像和角标，播放一次「长夜」悬浮动画；播放到一半（约 2.6 秒）时，三处图片及中英文标题、托盘和任务栏同步切换为长夜月，剩余动画继续播放并淡出。之后的深浅色切换立即显示长夜月或还原用户自己的三月七背景和卡片图标，不再重复动画。若主窗口隐藏，待恢复显示后播放。解锁后的额外 LOGO 点击不重复播放，也不强制改变用户后来选择的主题。按 Esc 可跳过动画并完成替换；中途切回浅色则结束动画并显示三月七。隐藏/关闭主窗口或播完都会释放动画。设置中的主题选择和系统主题事件均不计入三次点击。普通深浅色切换保留原版白底三月七，不刷新任务栏或托盘图标；只有彩蛋角色实际出现或还原时才同步图标。默认整排任务头像在普通深色模式下也使用透明底和人物淡纹，浅色恢复原图；用户自选图片不重写。

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

#### 构图对齐修订

2026-11-17 构图对齐修订：以原有长夜月封面为编辑底图、`../bg37.jpg` 为构图参考，分两次通过内置 image_gen 上移人物，使头顶接近上边缘，并让腰腹部进入应用当前显示的顶部约 80% 区域。成图保持 1863×844；应用裁切逻辑与预加载方式不变。

首次调整提示词：

```text
Use case: precise-object-edit / composition alignment.
Asset type: a wide 2.20:1 home-page banner for a desktop app.
Image 1 is the EDIT TARGET: the existing Evernight illustration. Image 2 is ONLY a framing reference: the application's original March 7th banner. Preserve Evernight's exact character identity and the style, clothing, pose, expression, face angle, color palette and detailed anime linework of image 1.
Primary request: Reposition Evernight UPWARD so changing from image 2 to image 1 no longer makes the character visually jump down, and so her clothed waist/abdomen is visible in the short banner viewport. Translate her entire coherent head/body/arms upward by about 8-10 percent of the full canvas height. Use only a very slight scale adjustment if needed; her face should remain approximately the same apparent size and same center-right horizontal position as March 7th's in image 2. Top of the actual HAIR crown should nearly touch the top edge (0-2 percent gap), like March 7th. The head ornament may reach the top edge; do not cut off her face, eyes or chin. Keep the same relaxed chin-side gloved hand and outstretched right hand as the target.
Critical layout constraint: the app displays only the TOP 80 percent of this wide image at the user's current window size. In that top-80-percent region, the full face must be high near the top, the shoulders/chest must sit higher, and a meaningful portion of the CLOTHED ABDOMEN/corset waist and belt chains must already be visible. Position her corset waist around 65-72 percent of the FULL image height, not at its bottom edge. Preserve normal anatomy and head-to-body proportions; do not stretch or squeeze her torso. Continue the lower outfit naturally into the bottom 20 percent that the app may crop away. Do not expose skin or redesign her outfit.
Background: keep the existing dark lavender night setting, mirror/moon, candle, floating photo panels, pale ribbons, flowers and butterflies from image 1, filling any area revealed by moving the character. Keep the upper-left title area quiet and dark. Do not add large objects in that area. No change to overall lighting, outfit design or expression; not a new character illustration.
Output one finished opaque landscape banner, SAME roughly 2.20:1 aspect ratio as both inputs. No text, no lettering, no title baked into the artwork, no watermark, no UI, no borders, no duplicate characters. Do not copy March 7th's blue outfit, camera or face into Evernight.
```

小幅上移修订提示词：

```text
Use case: precise-object-edit.
Image 1 is the exact edit target: the recently reframed Evernight banner. Image 2 is only the original March 7th layout reference.
Make ONE very small composition correction to image 1: move the whole Evernight character (head, hair, coherent torso, and both arms together) straight UP by about 4 percent of the full canvas height (about 34 pixels on this 1863x844 reference), keeping her size and horizontal position unchanged. Do not change her face, identity, anatomy, expression, head tilt, costume details, hand pose, linework, colors, or lighting. Do not zoom or shrink the person.
The crown of her actual pink HAIR, not just the ornament, should now reach almost the top edge, with only a 0-1 percent gap. A little of the uppermost ornament can extend beyond the top edge naturally, similar to the cropped hair crown in image 2. Keep all eyes and face clearly inside. Her clothed corset ABDOMEN and more of the silver WAIST CHAIN must be comfortably visible within the TOP 80 percent of the canvas, since the app crops away the bottom 20 percent in its short viewport. This small upward translation is the only desired composition change.
Keep the background of image 1 virtually unchanged: same mirror/moon, candle, night purple palette, flowers, butterfly, floating photo frames and ribbons. Seamlessly fill only the regions uncovered by the small upward move. The left title area remains quiet, dark and empty.
Output one opaque 1863x844 (or the same 2.20:1 landscape aspect ratio) image, no text, UI, border, watermark, duplicate people or redesign. Do not copy March 7th's camera or blue clothing.
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
