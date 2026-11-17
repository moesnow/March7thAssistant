# 应用图标

点击主窗口左上角 LOGO 可切换深浅色主题，悬停提示为“切换主题”。侧边栏不再显示主题按钮，默认窗口高度恢复为 640；已有窗口尺寸记忆仍按用户设置读取。连续三次点击 LOGO 的彩蛋触发方式见 [交互约定](../app/images/evernight/README.md#交互约定)。

| 图标组 | 使用时机 | 左上角标题栏 | 任务栏、托盘及原生窗口 |
|---|---|---|---|
| 三月七 | 浅色模式 | 原版 [March7th.ico](March7th.ico) | 同一原版图标 |
| 三月七（夜晚） | 普通深色模式，或首次彩蛋动画尚未到中点 | [march7th-night/titlebar.png](march7th-night/titlebar.png)，闭眼、黑灰色装饰底 | [march7th-night/icon.png](march7th-night/icon.png)，闭眼、白色装饰底 |
| 长夜月 | 彩蛋激活后的深色模式 | [evernight/titlebar.png](evernight/titlebar.png)，豆豆眼、黑灰色装饰底 | [evernight/icon.png](evernight/icon.png)，豆豆眼、白色装饰底 |

原版 `March7th.ico` 保持不变。两组新图保留圆角底板和原图风格的花朵、星星装饰；只有圆角外部透明。黑灰底与深色软件底色保留对比。除已确认的闭眼白底三月七版本外，其余三张新图额外去除了最外圈描边，保留内部装饰线。

PNG 保存生成素材，运行时使用同名 ICO。ICO 通过 Qt 缩放并封装 16、20、24、32、40、48、64、128、256 像素图层，减少小尺寸图标的加载开销；不在运行时生成或修改文件。应用先设置白底原生图标，再设置自绘标题栏的黑灰底图标。三组图标切换沿用现有任务栏标识刷新逻辑。

素材使用内置 OpenAI image_gen 编辑。三月七（夜晚）参考项目原版 `March7th.ico`，长夜月参考此前的豆豆眼彩蛋图标；角色和原美术的权利归原权利方所有，不重新声明为项目代码许可证。长夜月的角色参考来源见 [彩蛋素材说明](../app/images/evernight/README.md)。

## 生成与修订提示词

### 三月七（夜晚）：白底系统图标

```text
Use case: precise-object-edit. Asset type: a small Windows application icon, one square image. Edit the provided original March 7th bean-eyed app logo. Change ONLY the two open solid navy oval bean eyes into two gently curved CLOSED navy eyelids, peaceful sleepy expression, no eyelashes, no pupils. Preserve EXACTLY the original tilted head, pink hair, blush, tiny body, blue-white outfit, camera, hand pose, head-to-body proportions, framing and flat soft pastel chibi style. Retain the original WHITE/light cream rounded-square background tile, thin blue-gray rounded border, and the original pastel pink flowers and blue stars in their original size and positions. Character must stay the same scale and location inside this tile. Full rounded-square tile nearly fills canvas with only the same tiny clear margin as original; transparent only OUTSIDE rounded corners, interior background opaque white. Do not add a new sleeping cap, moon, bed, Z text or anything else. No text. Do not remove the decorative background. Output one finished icon only, not a sheet or mockup.
```

### 长夜月：白底系统图标

```text
Use case: compositing. Asset type: one square Windows app icon. Image 1 is the EXACT edit target: preserve this bean-eyed Evernight chibi character with unchanged facial features, two solid oval open eyes, hairstyle, flower ornament, black-violet clothing, colors, pose and flat pastel drawing. Image 2 supplies ONLY the background tile and visual spacing. Add behind the image 1 character the SAME opaque WHITE/light cream rounded-square app-icon tile as image 2, with thin blue-gray rounded edge, small pastel pink flowers and blue star decorations like image 2. Position the character within the tile at the same scale and comfortable inset as March 7th in image 2; retain all hair tips and ornament inside tile. Full rounded-square tile nearly fills canvas with tiny clear margin, transparent only OUTSIDE its rounded corners, interior white and opaque. The chibi remains bean-eyed and has exactly the same design as image 1; no redesign, no big anime eyes, no new accessories, no additional hands. No text, mockup, drop shadow or duplicate icons. One finished icon.
```

### 两组黑灰底标题栏图标

分别使用对应白底图作为编辑输入：

```text
Use case: precise-object-edit. Asset type: one square dark-titlebar application icon. Change ONLY the BACKGROUND TILE of this exact icon. Replace the white/cream field behind the character with opaque dark charcoal gray, approximately #4A4B54, with a very gentle #42434B to #54545E variation. It must be visibly lighter than an app title bar of #202024, NOT black. Retain the same rounded-square shape, tiny transparent outside corner margins, and a fine muted silver-gray rim. Retain the existing background flowers, dots, stars and curved stripe at EXACTLY the same sizes and positions, but soften their pastel pink/blue hues into muted dusty pink/blue-gray against charcoal so they are readable and restrained. Preserve the character EXACTLY: all skin and hair colors and brightness, all facial expression and eye shapes (closed eyes stay closed; open oval bean eyes stay open), head/body proportions, pose, outline, costume, camera if present, accessories, location and scale. Do not recolor, dim, redraw, crop, resize or move any part of the character. Only the tile field, tile rim and decorative background marks change color. Same square composition, flat pastel chibi illustration, no new objects, no text, no glowing effects, no background outside rounded tile. Transparent ONLY outside the rounded corners; interior tile opaque. One finished icon, no mockup or sheet.
```

### 去除三张新图的最外圈描边

保留闭眼白底三月七；仅对另外三张新图应用：

```text
Use case: precise-object-edit. Remove ONLY the thin outline/rim that traces the very outer perimeter of this rounded-square application icon. The user does NOT want the gray/blue/silver enclosing stroke. Keep the SAME rounded-square silhouette and SAME canvas/framing, with actual transparency outside the rounded corners. Fill the former rim area with the immediately adjacent tile background color so the tile ends cleanly at its own rounded edge, with normal antialiasing but NO enclosing stroke, NO border, NO rim, NO glow, NO shadow, NO white halo. Preserve EVERYTHING ELSE exactly: character design, facial expression, all open/closed eye shapes, pose, hair, clothes, object details, scale, position, all colors; preserve the tile's existing white or charcoal background and every internal decorative flower, star, dot and curved stripe at its exact position. The interior curved decorative stripe is NOT the outer border: keep it. Do not alter the character outlines or hair outlines. One icon only, transparent outside the rounded tile, opaque inside.
```

### 长夜月白底图的边缘清理

```text
Use case: background-extraction with strict identity preservation. Clean ONLY the alpha edge of this existing rounded-square app icon. The tile is white/cream and MUST remain an opaque white rounded-square behind the unchanged Evernight chibi and pastel decorations. There are unwanted scattered white speckles / ragged white patches OUTSIDE the smoothly rounded square, especially upper left/right and lower corners. Remove ALL those external white speckles and ragged patches to true transparency. Make the outside edge a single clean smooth rounded-square edge with subtle 1-pixel antialiasing and NO enclosing stroke or border. Retain exactly the same size and location of the existing tile; do not crop, zoom, redraw or move anything inside it. No gray rim, no black outline, no white glow, no shadow, no feathered halo. Preserve character, facial expression, all colors and inner background decorations pixel-faithfully. One isolated icon with genuinely transparent corners and a completely clean outside silhouette.
```
