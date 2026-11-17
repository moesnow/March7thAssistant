# 深色头像

本目录的六张任务头像（March7th、JingYuan、Yanqing、Herta、SilverWolf、Bronya）是原始任务头像的透明人物 PNG 版本。浅色主题继续使用原来的带纹理 JPG；原始六张头像未覆盖。

深色纹理由 `app/common/theme_assets.py` 参考对应的浅色原图生成，通过 Qt Multiply 混合增强原有淡纹颜色；`app/components/portrait_label.py` 再以 4% 不透明度叠在卡片底色上，最后覆盖正常人物。内置头像及其纹理最多缓存 12 组，避免主题切换时重复解码或混合整排图片。保留原图的色彩方向和明暗关系，不反转亮度，避免把浅色皮肤变成深色；卡片的 Mica 与悬停色仍可透出。纹理与浅色原图共用完整图像矩形，大小、位置、裁切完全一致，不再另行缩放或偏移人物副本。原始文件不重写；用户自选图片不进入内置缓存，重建卡片时重新读取。

普通深浅色模式的标题栏、任务栏和托盘均使用原版白底三月七 `assets/logo/March7th.ico`，切换主题不刷新图标。参见 [应用图标说明](../../../logo/README.md)。

素材以项目原始任务头像和 `assets/logo/March7th.ico` 为参考，使用 OpenAI 图像生成工具编辑。角色及原美术权利归原权利方所有；此处记录素材来源，不另行声明为项目代码许可证。

## 任务头像统一编辑提示词

```text
Use case: background-extraction. Edit target: the attached square task-card portrait. Remove ONLY the background: the white field and pale enlarged duplicate character line-art behind the main foreground character. Output a genuine transparent RGBA PNG, in the SAME square composition and SAME framing, character filling the canvas just as in the input. Preserve the main foreground character EXACTLY: pose, facial expression, eye colors, hair color and all fine hair strands, costume, accessories, lighting, cel shading, linework, proportions, crop, and existing artist signature on the foreground. This is precise background removal, no redesign or repainting. Do NOT remove any white hair, white skin, white clothing or white highlights from the foreground. Preserve semitransparent anti-aliased edges, no white matte/fringe, no black background, no shadow, no new text, no border, no decorative particles.
```
