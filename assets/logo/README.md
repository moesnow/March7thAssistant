# 应用图标

主题选项位于“设置 → 程序 → 界面主题”，提供“跟随系统 / 浅色 / 深色”，默认跟随系统；选择即时生效并保存。普通深浅色模式的左上角、任务栏及托盘均使用项目原版白底三月七图标，切换主题不会刷新系统图标。

每次点击左上角 LOGO 都会轻轻晃动。5 秒内连续点击 5 次，主页显示粉色提示“别晃啦！本姑娘头好晕( ꩜ ᯅ ꩜;)”，提示缓缓上移并渐隐，5 秒后完全消失；从提示出现起的 5 秒内再点击 5 次，才解锁并播放彩蛋。超时则收起提示、重新计数。提示阶段不改变主题；解锁时临时添加并选择“长夜”主题，使用深色外观但不改写已保存的主题偏好。重启后恢复原先的跟随系统、浅色或深色，“长夜”选项随之隐藏。解锁后的点击仍有晃动，但不重复播放，也不改变用户后来选择的主题。详见 [交互约定](../app/images/evernight/README.md#交互约定)。

| 图标组 | 使用时机 | 左上角标题栏 | 任务栏、托盘及原生窗口 |
|---|---|---|---|
| 三月七 | 普通深浅色模式，或首次彩蛋动画尚未到中点 | 原版 [March7th.ico](March7th.ico) | 同一原版图标 |
| 长夜月 | 选择“长夜”且首次动画已到中点 | [evernight/icon.ico](evernight/icon.ico)，豆豆眼、白色装饰底 | 同一白底长夜月图标 |

粉色提示与长夜悬浮效果由 Qt 代码渲染；动画与素材说明见 [彩蛋素材说明](../app/images/evernight/README.md)。

“长夜”主题的窗口控制区、主题选择框和侧边栏“设置”背后分别衬有 2 号、1 号、3 号新绘忆灵图片，下拉框和设置按钮周围允许图片适度越界，保留原有图标、文字、布局和点击区域，选择普通主题后隐藏；这些静态装饰与首次悬浮动画使用不同素材。

LOGO 使用居中的 48×48 点击热区，图标本身的尺寸和位置保持不变；热区内连点和双击不会触发标题栏最大化。

原版 `March7th.ico` 保持不变，不制作深色或闭眼变体。仅当彩蛋角色出现或还原时同步更新图标及 Windows 任务栏标识。

仓库仅保留运行时使用的 ICO；生成用的 PNG 源稿不随应用分发。ICO 通过 Qt 缩放并封装 16、20、24、32、40、48、64、128、256 像素图层；不在运行时生成或修改文件。

长夜月素材使用内置 OpenAI image_gen 编辑，参考此前的豆豆眼彩蛋图标；角色和原美术的权利归原权利方所有，不重新声明为项目代码许可证。角色参考来源见 [彩蛋素材说明](../app/images/evernight/README.md)。

## 生成与修订提示词

### 长夜月：白底图标

```text
Use case: compositing. Asset type: one square Windows app icon. Image 1 is the EXACT edit target: preserve this bean-eyed Evernight chibi character with unchanged facial features, two solid oval open eyes, hairstyle, flower ornament, black-violet clothing, colors, pose and flat pastel drawing. Image 2 supplies ONLY the background tile and visual spacing. Add behind the image 1 character the SAME opaque WHITE/light cream rounded-square app-icon tile as image 2, with thin blue-gray rounded edge, small pastel pink flowers and blue star decorations like image 2. Position the character within the tile at the same scale and comfortable inset as March 7th in image 2; retain all hair tips and ornament inside tile. Full rounded-square tile nearly fills canvas with tiny clear margin, transparent only OUTSIDE its rounded corners, interior white and opaque. The chibi remains bean-eyed and has exactly the same design as image 1; no redesign, no big anime eyes, no new accessories, no additional hands. No text, mockup, drop shadow or duplicate icons. One finished icon.
```

### 去除长夜月图标的最外圈描边

对长夜月白底图应用：

```text
Use case: precise-object-edit. Remove ONLY the thin outline/rim that traces the very outer perimeter of this rounded-square application icon. The user does NOT want the gray/blue/silver enclosing stroke. Keep the SAME rounded-square silhouette and SAME canvas/framing, with actual transparency outside the rounded corners. Fill the former rim area with the immediately adjacent tile background color so the tile ends cleanly at its own rounded edge, with normal antialiasing but NO enclosing stroke, NO border, NO rim, NO glow, NO shadow, NO white halo. Preserve EVERYTHING ELSE exactly: character design, facial expression, all open/closed eye shapes, pose, hair, clothes, object details, scale, position, all colors; preserve the tile's existing white or charcoal background and every internal decorative flower, star, dot and curved stripe at its exact position. The interior curved decorative stripe is NOT the outer border: keep it. Do not alter the character outlines or hair outlines. One icon only, transparent outside the rounded tile, opaque inside.
```

### 长夜月白底图的边缘清理

```text
Use case: background-extraction with strict identity preservation. Clean ONLY the alpha edge of this existing rounded-square app icon. The tile is white/cream and MUST remain an opaque white rounded-square behind the unchanged Evernight chibi and pastel decorations. There are unwanted scattered white speckles / ragged white patches OUTSIDE the smoothly rounded square, especially upper left/right and lower corners. Remove ALL those external white speckles and ragged patches to true transparency. Make the outside edge a single clean smooth rounded-square edge with subtle 1-pixel antialiasing and NO enclosing stroke or border. Retain exactly the same size and location of the existing tile; do not crop, zoom, redraw or move anything inside it. No gray rim, no black outline, no white glow, no shadow, no feathered halo. Preserve character, facial expression, all colors and inner background decorations pixel-faithfully. One isolated icon with genuinely transparent corners and a completely clean outside silhouette.
```
