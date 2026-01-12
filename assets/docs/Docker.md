# Docker 部署教程

本教程介绍如何使用 Docker 部署 March7th Assistant（云崩铁模式）。

> **注意**：
> - Docker 部署仅支持**云游戏模式**，不支持本地游戏客户端。
> - 目前仅支持 **linux/amd64** 架构，暂不支持 ARM64（如 Apple Silicon Mac、树莓派等），后续可能会适配。

## 前置要求

- 已安装 [Docker](https://docs.docker.com/get-docker/)
- 已安装 [Docker Compose](https://docs.docker.com/compose/install/)（通常已包含在 Docker Desktop 中）
- 有效的米哈游账号（用于云崩铁登录）
- **x86_64 (amd64) 架构**的 Linux 主机或虚拟机

## 方式一：使用预编译镜像（推荐）

预编译镜像托管在 [GitHub Container Registry](https://ghcr.io/moesnow/march7thassistant)，开箱即用。

### 1. 创建项目目录

```bash
mkdir march7thassistant && cd march7thassistant
```

### 2. 下载配置文件

```bash
curl -o config.yaml https://m7a.top/assets/config/config.example.yaml
```

### 3. 下载 docker-compose.yml

```bash
curl -o docker-compose.yml https://m7a.top/docker-compose.yml
```

下载后，编辑 `docker-compose.yml`，将 `build: .` 注释掉，取消 `image:` 行的注释：

```yaml
services:
  march7thassistant:
    container_name: m7a
    # build: .
    image: ghcr.io/moesnow/march7thassistant:latest
    # image: ghcr.nju.edu.cn/moesnow/march7thassistant:latest
    # ...
```

> **中国大陆用户**：如果从 GitHub Container Registry 下载镜像速度较慢，可以使用南京大学镜像源：
> ```yaml
> image: ghcr.nju.edu.cn/moesnow/march7thassistant:latest
> ```

### 4. 首次启动（登录云游戏账号）

```bash
docker compose up -d
```

首次运行时，程序会自动切换到**二维码登录**模式。

二维码图片会保存在 `./logs/qrcode_login.png`，使用手机**米游社 APP** 扫描完成登录。

查看日志也可以获取二维码内容：

```bash
docker compose logs -f
```

日志中会显示二维码内容（网址），也可以使用在线工具（如 [草料二维码](https://cli.im/)）将网址生成二维码后扫码登录。

### 5. 查看日志

```bash
docker compose logs -f
```

## 方式二：手动构建镜像

如果需要自定义或使用最新代码，可以手动构建镜像。

### 1. 克隆仓库

```bash
git clone https://github.com/moesnow/March7thAssistant.git
cd March7thAssistant
```

### 2. 创建配置文件

```bash
cp assets/config/config.example.yaml config.yaml
```

### 3. 构建镜像

```bash
docker compose build
```

> **注意**：构建过程会自动下载 OCR 模型和浏览器，可能需要几分钟。
>
> **中国大陆用户**：如果下载缓慢，可以编辑 `Dockerfile`，取消国内镜像源相关行的注释来加速：
> - 取消 apt 源镜像注释：`sed -i 's/deb.debian.org/mirrors.cloud.tencent.com/g' ...`
> - 取消 pip 镜像注释：`-i https://mirrors.cloud.tencent.com/pypi/simple/`
> - 启用浏览器镜像下载：将 `ENV MARCH7TH_BROWSER_DOWNLOAD_USE_MIRROR=false` 改为 `true`

### 4. 启动并登录

启动和登录流程与方式一相同，参见 [首次启动](#4-首次启动登录云游戏账号)。

## 默认任务执行行为

Docker 部署时已预配置为**自动循环运行模式**，无需手动操作：

- **每天凌晨 4:00** 自动执行完整运行
- 任务完成后**自动循环等待**下一个执行时间
- 容器会持续运行，不会自动退出

如需修改可通过编辑配置文件或环境变量进行调整（见下方环境变量配置）。

## 环境变量配置

Docker 部署支持通过环境变量覆盖配置文件中的设置，环境变量优先级高于配置文件。

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `MARCH7TH_CLOUD_GAME_ENABLE` | 启用云游戏模式 | `true` |
| `MARCH7TH_BROWSER_HEADLESS_ENABLE` | 启用无头浏览器模式 | `true` |
| `MARCH7TH_BROWSER_HEADLESS_RESTART_ON_NOT_LOGGED_IN` | 未登录时是否重启浏览器 | `false` |
| `MARCH7TH_BROWSER_DOWNLOAD_USE_MIRROR` | 使用镜像下载浏览器 | `false` |
| `MARCH7TH_AFTER_FINISH` | 任务完成后操作 | `Loop` |
| `MARCH7TH_LOG_LEVEL` | 日志等级 | - |

示例：

```yaml
services:
  march7thassistant:
    # ...
    environment:
      - MARCH7TH_LOG_LEVEL=DEBUG
```

## 数据持久化

通过 volumes 挂载以下目录实现数据持久化：

| 路径 | 说明 |
|-----|------|
| `./config.yaml` | 配置文件 |
| `./logs` | 日志目录 |
| `./3rdparty/WebBrowser/UserProfile` | 浏览器数据（登录状态） |

## 常见问题

### Q: 如何更新到最新版本？

```bash
docker compose pull
docker compose up -d
```

### Q: 登录状态丢失怎么办？

重启容器后查看日志，重新扫描二维码登录：

```bash
docker compose restart
docker compose logs -f
```

### Q: 如何查看容器状态？

```bash
docker compose ps
```

### Q: 如何停止容器？

```bash
docker compose down
```

### Q: 报错 "session not created: probably user data directory is already in use"？

如果遇到类似以下错误：

```
Message: session not created: probably user data directory is already in use, 
please specify a unique value for --user-data-dir argument
```

这通常是浏览器用户数据目录被占用导致的，可能原因包括：
- 上一次 Chrome 异常退出，锁文件未清理
- 文件权限问题

解决方法：

1. 尝试多重启几次

2. 尝试删除浏览器数据目录后重试：

```bash
rm -rf ./3rdparty/WebBrowser/UserProfile
docker compose restart
```

### Q: 报错 "Message: tab crashed" 或 shm 相关错误？

如果遇到类似 `Message: tab crashed` 的错误，通常是共享内存（shm）不足导致的。

确保 `docker-compose.yml` 中设置了 `shm_size`：

```yaml
services:
  march7thassistant:
    # ...
    shm_size: 1g
```

如果仍然出错，可以尝试增大该值，例如 `shm_size: 2g`。