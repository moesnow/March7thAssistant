# 深色头像与透明角标

本目录的六张任务头像（March7th、JingYuan、Yanqing、Herta、SilverWolf、Bronya）是原始任务头像的透明人物 PNG 版本。浅色主题继续使用原来的带纹理 JPG；原始六张头像未覆盖。

深色纹理由 `app/common/theme_assets.py` 参考对应的浅色原图生成，通过 Qt Multiply 混合增强原有淡纹颜色；`app/components/portrait_label.py` 再以 4% 不透明度叠在卡片底色上，最后覆盖正常人物。内置头像及其纹理最多缓存 12 组，避免主题切换时重复解码或混合整排图片。保留原图的色彩方向和明暗关系，不反转亮度，避免把浅色皮肤变成深色；卡片的 Mica 与悬停色仍可透出。纹理与浅色原图共用完整图像矩形，大小、位置、裁切完全一致，不再另行缩放或偏移人物副本。原始文件不重写；用户自选图片不进入内置缓存，重建卡片时重新读取。

`March7th-icon.png` 是原豆豆眼应用角标的透明版本，只用于普通深色的标题栏、托盘与任务栏。角标不再复用任务头像。配套 ICO 用 Qt 从 PNG 编译 16、20、24、32、40、48、64、128、256 像素尺寸，保留 alpha。

素材以项目原始任务头像和 `assets/logo/March7th.ico` 为参考，使用 OpenAI 图像生成工具编辑。角色及原美术权利归原权利方所有；此处记录素材来源，不另行声明为项目代码许可证。

## 任务头像统一编辑提示词

```text
Use case: background-extraction. Edit target: the attached square task-card portrait. Remove ONLY the background: the white field and pale enlarged duplicate character line-art behind the main foreground character. Output a genuine transparent RGBA PNG, in the SAME square composition and SAME framing, character filling the canvas just as in the input. Preserve the main foreground character EXACTLY: pose, facial expression, eye colors, hair color and all fine hair strands, costume, accessories, lighting, cel shading, linework, proportions, crop, and existing artist signature on the foreground. This is precise background removal, no redesign or repainting. Do NOT remove any white hair, white skin, white clothing or white highlights from the foreground. Preserve semitransparent anti-aliased edges, no white matte/fringe, no black background, no shadow, no new text, no border, no decorative particles.
```

## March7th 豆豆眼角标提示词

```text
Use case: background-extraction. Input image is the edit target, the application's original bean-eyed March 7th chibi icon. Remove only the pale rounded-square tile and every background flower/star/frame, leaving a clean transparent-background cutout of the EXACT original chibi character and her camera. Preserve the very simple solid navy oval bean eyes (NO irises, NO highlights in eyes), short round pink hair, round pink cheek blush, no nose, tiny or absent mouth, tilted oversized round head, tiny blue-white clothed body, camera held at lower right, soft flat pastel cel shading. Do not redraw her as a detailed anime portrait. Maintain the same character framing and orientation, compact square app-icon silhouette, with a small clear transparent margin around the entire character. True RGBA alpha, no white or black tile, no circle or rounded rectangle, no border, no shadow, no text.
```

## Windows 任务栏同步

窗口、QApplication 默认图标及托盘使用同一份独立角标；Windows 窗口属性另外设置 RelaunchIconResource，最后写入由安装路径和当前图标内容生成的 AppUserModelID。Windows 11 会缓存同一分组的图标，仅重写同一个标识并不足以刷新实际任务栏；深浅两种图标各有一个稳定标识，让系统在图标变化时重新建立运行按钮，切回原图标也恢复原标识。主窗口本身不重建。这只更新当前窗口的属性，不修改快捷方式、系统图标缓存或其他安装目录。已固定的快捷方式仍绑定固定时的标识，当前运行按钮可能与它分组显示。

- [Microsoft: AppUserModel.ID 与刷新顺序](https://learn.microsoft.com/en-us/windows/win32/properties/props-system-appusermodel-id)
- [Microsoft: RelaunchIconResource](https://learn.microsoft.com/en-us/windows/win32/properties/props-system-appusermodel-relaunchiconresource)
