# 深色头像

本目录的六张任务头像（March7th、JingYuan、Yanqing、Herta、SilverWolf、Bronya）均为已合成的静态 PNG：人物和淡纹保存在同一张图片中。浅色主题继续使用原来的带纹理 JPG；原始六张头像未覆盖。

静态图片由此前已确认的 Qt 绘制结果导出：对应浅色原图经过 Multiply 增强后，以 15% 不透明度铺在透明画布上，再覆盖人物。保留原图的色彩方向和明暗关系，纹理与浅色原图的大小、位置、裁切一致；半透明淡纹让卡片的 Mica 底色和悬停效果继续透出。运行时只通过普通 `QLabel` 加载整张 PNG，不再生成纹理或分层绘制，也不修改素材文件。

`app/common/theme_assets.py` 最多缓存 12 张内置深浅色头像，避免切换主题时重复解码。用户自选图片不进入内置缓存，重建卡片时重新读取。

普通深浅色模式的标题栏、任务栏和托盘均使用原版白底三月七 `assets/logo/March7th.ico`，切换主题不刷新图标。参见 [应用图标说明](../../../logo/README.md)。

素材以项目原始任务头像和 `assets/logo/March7th.ico` 为参考，使用 OpenAI 图像生成工具编辑。角色及原美术权利归原权利方所有；此处记录素材来源，不另行声明为项目代码许可证。

## 原始人物抠图提示词

以下提示词用于制作合成前的人物层；当前 PNG 已包含人物和淡纹。

```text
Use case: background-extraction. Edit target: the attached square task-card portrait. Remove ONLY the background: the white field and pale enlarged duplicate character line-art behind the main foreground character. Output a genuine transparent RGBA PNG, in the SAME square composition and SAME framing, character filling the canvas just as in the input. Preserve the main foreground character EXACTLY: pose, facial expression, eye colors, hair color and all fine hair strands, costume, accessories, lighting, cel shading, linework, proportions, crop, and existing artist signature on the foreground. This is precise background removal, no redesign or repainting. Do NOT remove any white hair, white skin, white clothing or white highlights from the foreground. Preserve semitransparent anti-aliased edges, no white matte/fringe, no black background, no shadow, no new text, no border, no decorative particles.
```
