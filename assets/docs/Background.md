# 后台运行

> 远程本地多用户桌面（是一台电脑，不需要两台电脑）

 * 模拟器运行拥有卡顿，性能消耗大等诸多缺点
 * 我们推荐您使用 Windows 自带的远程桌面服务进行该程序
 * 在电脑上直接运行的性能消耗要小于模拟器
 * Windows 开启远程桌面多用户教程：
   * [详细教程 by_Rin](https://www.bilibili.com/read/cv24286313/)（⭐推荐⭐）
   * [RDPWrap 方法](https://blog.sena.moe/win10-multiple-RDP/)
   * [修改文件方法](https://www.wyr.me/post/701)
 * [详细教程 by_Rin](https://www.bilibili.com/read/cv24286313/) 中所有相关文件：[下载链接](https://github.com/CHNZYX/asu_version_latest/releases/download/RDP/LocalRemoteDesktop1.191_by_lin.zip)
   * 备用链接
     * [百度网盘](https://pan.baidu.com/s/13aoll4n1gmKlPT9WwNYeEw?pwd=jbha) 提取码：jbha
     * [GitHub镜像](https://github.kotori.top/https://github.com/CHNZYX/asu_version_latest/releases/download/RDP/LocalRemoteDesktop1.191_by_lin.zip)



## 对于 Windows 11 用户

在 [详细教程 by_Rin](https://www.bilibili.com/read/cv24286313/) 中提到的 `SuperRDP` 软件可能已无法使用，建议改用 [TermsrvPatcher](https://github.com/fabianosrc/TermsrvPatcher)。如果你在国内使用，可以通过备用链接下载：[蓝奏云](https://wwsj.lanzout.com/i4V8u2np8dna)。

**注意：** 此方法仅实现了[详细教程 by_Rin](https://www.bilibili.com/read/cv24286313/)中`4. 多用户同时登陆补丁`的功能，其余步骤请继续按照原教程进行。

**使用方法：**

1. 使用 `git clone` 克隆仓库，或直接下载压缩包。
2. 下载完成后，解压压缩包，找到 `TermsrvPatcher.ps1` 文件，右键点击选择“运行”，脚本将自动完成所有操作。

此外，如果你希望手动修改文件，可以参考博客文章：[修改文件方法](https://www.wyr.me/post/701)。不过需要注意的是，该博客中的部分操作在 Windows 11 上可能不适用，具体如下：

- **在 Windows 11 中需搜索的字符串（正则）：**
   `39 81 3C 06 00 00 0F (?:[0-9A-F]{2} ){4}00`（实际操作中，仅需搜索`39 81 3C 06 00 00 0F`即可，剩下的两个16进制数符合正则表达式再进行修改）
- **替换为的字符串：**
   `8B 81 38 06 00 00 39 81 3C 06 00 00 75`

