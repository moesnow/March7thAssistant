"""Provider setup instructions from the desktop notification settings."""

TUTORIALS = {
    "wechatworkbot": """<h4>一、什么是企业微信机器人？</h4>
<p>企业微信机器人可以通过 Webhook 向企业微信群发送消息通知。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：创建群机器人</b></p>
<ol>
<li>打开企业微信电脑客户端</li>
<li>进入一个群聊，点击右上角「...」</li>
<li>点击「群机器人」→「添加」</li>
<li>设置机器人名称（如：游戏助手）</li>
<li>点击「添加」完成创建</li>
<li>复制 Webhook 地址中的 <b>key</b> 参数</li>
</ol>

<p><b>第 2 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「企业微信机器人」通知，开启开关</li>
<li>点击「机器人 Key」右侧的「修改」按钮，粘贴 key</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：Webhook 地址格式类似 <code>https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx</code>，其中 <code>xxx</code> 就是 key。</div>

<h4>三、常见问题</h4>

<p><b>Q：提示安全限制？</b></p>
<p>A：企业微信机器人可能有 IP 白名单限制，请在机器人设置中添加服务器 IP。</p>""",
    "qqbot": """<h4>一、什么是 QQ 官方机器人？</h4>
<p>QQ 官方机器人是 QQ 开放平台提供的官方能力，只需 <b>AppID + AppSecret</b> 两个字段即可主动推送消息，无需部署 NapCat / Lagrange 等第三方协议端（OneBot），无封号风险。</p>

<h4>二、前置准备</h4>
<ol>
<li>访问 <a href="https://q.qq.com/">QQ 开放平台</a>，注册并创建机器人</li>
<li>在「开发设置」中获取 <b>AppID</b> 与 <b>AppSecret</b></li>
</ol>

<h4>三、获取 openid / group_openid</h4>
<p>收件方标识 <code>openid</code> / <code>group_openid</code> 不是 QQ 号，也无法通过接口查询，只能在机器人收到事件时获取。推荐使用参数列表下方的「自动绑定收件标识」：</p>
<ul>
<li><b>绑定单聊</b>：点击后 60 秒内用 QQ 私聊机器人发送指定验证码，或直接添加机器人为好友</li>
<li><b>绑定群聊</b>：点击后 60 秒内在目标群中 @ 机器人发送指定验证码，或将机器人拉进目标群</li>
</ul>
<p>也可以手动填写：单聊对应 <code>C2C_MESSAGE_CREATE</code> / <code>FRIEND_ADD</code> 事件中的 openid，群聊对应 <code>GROUP_AT_MESSAGE_CREATE</code> / <code>GROUP_ADD_ROBOT</code> 事件中的 group_openid。</p>
<p>二者可只填一个，也可同时填写（同时推送）。</p>

<h4>四、配置到 March7thAssistant</h4>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「QQ 官方机器人」通知，开启开关</li>
<li>填写「机器人 AppID」「机器人 AppSecret」</li>
<li>点击「绑定单聊」或「绑定群聊」自动获取收件标识（也可手动填写）</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：推送截图会自动走官方分片上传并以图片消息发送，无需额外配置。</div>
<div class="warning">⚠️ <b>注意</b>：AppSecret 属于敏感凭证，请勿泄露给他人或发布到公开场合。</div>

<h4>五、常见问题</h4>

<p><b>Q：提示 40034105 主动消息发送失败？</b></p>
<p>A：一般是当月主动消息额度已用完或触发了发送频控，稍后再试即可；若持续出现，可到开放平台检查机器人状态与消息权限。</p>

<p><b>Q：提示 invalid appid or secret？</b></p>
<p>A：AppID 或 AppSecret 填写错误，请与开放平台「开发设置」中的内容核对。</p>

<p><b>Q：发送成功但 QQ 没收到？</b></p>
<p>A：请确认 openid / group_openid 是否正确，以及机器人是否已入群或与你建立过会话。</p>""",
    "smtp": """<h4>一、什么是 SMTP？</h4>
<p>SMTP 是电子邮件传输协议，通过配置 SMTP 可以将通知发送到你的邮箱。支持 QQ 邮箱、163 邮箱、Gmail 等主流邮箱服务。</p>

<h4>二、以 QQ 邮箱为例的配置步骤</h4>

<p><b>第 1 步：获取 QQ 邮箱授权码</b></p>
<ol>
<li>登录 <a href="https://mail.qq.com/">QQ 邮箱网页版</a></li>
<li>点击「设置」→「账户」</li>
<li>向下滚动找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」</li>
<li>开启「POP3/SMTP服务」或「IMAP/SMTP服务」</li>
<li>按照提示发送短信验证</li>
<li>验证成功后会获得一个 <b>授权码</b>（不是 QQ 密码！）</li>
<li>复制这个授权码</li>
</ol>

<p><b>第 2 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「SMTP」通知，开启开关</li>
<li>填写以下信息：
<ul>
<li><b>SMTP 服务器</b>：<code>smtp.qq.com</code></li>
<li><b>用户名/邮箱</b>：你的 QQ 邮箱地址（如 123456@qq.com）</li>
<li><b>密码/授权码</b>：刚才获取的授权码</li>
</ul>
</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<h4>三、其他常用邮箱配置</h4>

<table>
<tr><th>邮箱</th><th>SMTP 服务器</th><th>端口</th></tr>
<tr><td>QQ 邮箱</td><td>smtp.qq.com</td><td>465</td></tr>
<tr><td>163 邮箱</td><td>smtp.163.com</td><td>465</td></tr>
<tr><td>126 邮箱</td><td>smtp.126.com</td><td>465</td></tr>
<tr><td>Gmail</td><td>smtp.gmail.com</td><td>465</td></tr>
<tr><td>Outlook</td><td>smtp.office365.com</td><td>587</td></tr>
</table>

<div class="warning">⚠️ <b>注意</b>：大多数邮箱需要使用「授权码」而不是登录密码。163/126 邮箱也需要在设置中开启 SMTP 并获取授权码。</div>

<h4>四、常见问题</h4>

<p><b>Q：提示认证失败？</b></p>
<p>A：请确保使用的是授权码而不是邮箱密码。部分邮箱（如 163）可能需要开启「客户端授权密码」。</p>

<p><b>Q：发送成功但收不到邮件？</b></p>
<p>A：请检查垃圾邮件文件夹，或者确认收件人地址是否正确。</p>""",
    "lark": """<h4>一、什么是飞书机器人？</h4>
<p>飞书机器人可以通过 Webhook 向飞书群发送消息通知。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：创建飞书群</b></p>
<ol>
<li>打开飞书，创建一个群或使用已有群</li>
</ol>

<p><b>第 2 步：添加自定义机器人</b></p>
<ol>
<li>点击群右上角「...」→「设置」</li>
<li>点击「群机器人」→「添加机器人」</li>
<li>选择「自定义机器人」</li>
<li>设置机器人名称（如：游戏助手）</li>
<li>点击「添加」</li>
<li>复制 <b>Webhook 地址</b></li>
<li>如果设置了安全校验，记住关键词或签名密钥</li>
</ol>

<p><b>第 3 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「飞书」通知，开启开关</li>
<li>点击「Webhook 地址」右侧的「修改」按钮，粘贴地址</li>
<li>如果设置了关键词校验，填入「关键词」</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：Webhook 地址格式类似 <code>https://open.feishu.cn/open-apis/bot/v2/hook/xxx</code></div>""",
    "telegram": """<h4>一、什么是 Telegram？</h4>
<p>Telegram 是一款跨平台的即时通讯软件，支持手机和电脑。通过配置 Telegram Bot，可以让 March7thAssistant 自动向你发送任务完成通知。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：创建 Telegram Bot</b></p>
<ol>
<li>打开 Telegram，搜索 <b>@BotFather</b>（注意认准官方蓝色认证标志）</li>
<li>点击「开始」或发送 <code>/start</code></li>
<li>发送 <code>/newbot</code> 创建新机器人</li>
<li>按提示输入机器人的<b>名称</b>（如：我的通知机器人）</li>
<li>输入机器人的<b>用户名</b>（必须以 bot 结尾，如：my_notify_bot）</li>
<li>创建成功后，BotFather 会发送一条包含 <b>Token</b> 的消息</li>
<li>复制这个 Token（格式类似：<code>123456789:ABCdefGHIjklMNOpqrsTUVwxyz</code>）</li>
</ol>

<p><b>第 2 步：获取你的用户 ID</b></p>
<ol>
<li>在 Telegram 中搜索 <b>@userinfobot</b></li>
<li>点击「开始」或发送 <code>/start</code></li>
<li>机器人会回复你的用户信息，其中 <b>Id</b> 就是你的用户 ID（一串数字）</li>
<li>复制这个 ID</li>
</ol>

<p><b>第 3 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到 Telegram 通知，开启开关</li>
<li>点击「机器人令牌」右侧的「修改」按钮，粘贴第 1 步获取的 Token</li>
<li>点击「用户/群组 ID」右侧的「修改」按钮，粘贴第 2 步获取的用户 ID</li>
<li>点击下方的「发送消息」按钮测试是否配置成功</li>
</ol>

<div class="tip">💡 <b>提示</b>：如果你在中国大陆使用，可能需要配置代理才能访问 Telegram。</div>

<h4>三、常见问题</h4>

<p><b>Q：发送测试消息后没有收到通知？</b></p>
<p>A：请检查以下几点：</p>
<ul>
<li>是否已经给机器人发送过 /start（必须先启动机器人）</li>
<li>Token 是否复制完整（注意不要多复制空格）</li>
<li>用户 ID 是否正确</li>
<li>是否需要配置代理才能访问 Telegram</li>
</ul>

<p><b>Q：如何发送到群组？</b></p>
<p>A：将机器人添加到群组，然后将群组 ID（以 - 开头）填入「用户/群组 ID」即可。</p>

<h4>四、参考链接</h4>
<p><a href="https://core.telegram.org/bots#how-do-i-create-a-bot">Telegram Bot 官方文档</a></p>""",
    "dingtalk": """<h4>一、什么是钉钉机器人？</h4>
<p>钉钉机器人可以通过 Webhook 向钉钉群发送消息通知。适合团队协作场景。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：创建钉钉群</b></p>
<ol>
<li>打开钉钉，创建一个群或使用已有群</li>
<li>确保你有群管理权限</li>
</ol>

<p><b>第 2 步：添加自定义机器人</b></p>
<ol>
<li>点击群右上角「...」→「智能群助手」</li>
<li>点击「添加机器人」→「自定义（通过 Webhook 接入）」</li>
<li>设置机器人名称（如：游戏助手）</li>
<li>安全设置选择「自定义关键词」，填入关键词（如：通知）</li>
<li>点击「完成」后会显示 Webhook 地址</li>
<li>从 Webhook 地址中提取 Token（URL 最后的那段字符串）</li>
</ol>

<p><b>第 3 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「钉钉」通知，开启开关</li>
<li>点击「机器人令牌」右侧的「修改」按钮，粘贴提取的 Token</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="warning">⚠️ <b>注意</b>：如果设置了「加签」安全方式，需要同时填写「加签密钥」。建议使用「自定义关键词」方式更简单。</div>

<h4>三、常见问题</h4>

<p><b>Q：提示消息发送失败？</b></p>
<p>A：请检查关键词设置是否匹配，Token 是否正确。</p>""",
    "serverchan3": """<h4>一、什么是 Server酱³？</h4>
<p>Server酱³ 是 Server酱 的最新版本，通过专属 APP 接收推送通知，体验更好。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：下载 APP</b></p>
<ol>
<li>访问 <a href="https://sc3.ft07.com/">Server酱³ 官网</a></li>
<li>下载并安装 Server酱³ APP（支持 iOS 和 Android）</li>
<li>打开 APP 并注册登录</li>
</ol>

<p><b>第 2 步：获取 SendKey</b></p>
<ol>
<li>在 APP 中进入「设置」页面</li>
<li>找到「SendKey」并复制</li>
<li>或者在网页版登录后获取</li>
</ol>

<p><b>第 3 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「Server酱³」通知，开启开关</li>
<li>点击「SendKey」右侧的「修改」按钮，粘贴刚才获取的 SendKey</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：Server酱³ 的推送速度比 Turbo 版更快，建议优先使用。</div>

<h4>三、常见问题</h4>

<p><b>Q：APP 收不到通知？</b></p>
<p>A：请检查手机的通知权限设置，确保 Server酱³ APP 有通知权限。</p>

<h4>四、参考链接</h4>
<p><a href="https://sc3.ft07.com/">Server酱³ 官网</a></p>""",
    "onebot": """<h4>一、什么是 OneBot？</h4>
<p>OneBot 是一个聊天机器人应用接口标准，支持多种 QQ 机器人实现（如 Lagrange、NapCat 等）。通过配置 OneBot，可以让机器人向你或群组发送通知。</p>

<h4>二、前置准备</h4>
<p>你需要先部署一个 OneBot 服务端，常见选择：</p>
<ul>
<li><b>Lagrange.Core</b>（推荐，持续维护）</li>
<li><b>NapCatQQ</b>（基于 NTQQ 的实现）</li>
<li><b>OpenShamrock</b>（Android QQ 协议）</li>
</ul>

<h4>三、以 Lagrange 为例的配置步骤</h4>

<p><b>第 1 步：下载并部署 Lagrange</b></p>
<ol>
<li>访问 <a href="https://github.com/LagrangeDev/Lagrange.Core/releases">Lagrange Releases</a></li>
<li>下载对应系统的版本</li>
<li>解压并运行程序</li>
<li>使用 QQ 扫码登录</li>
</ol>

<p><b>第 2 步：配置 Lagrange</b></p>
<ol>
<li>编辑 Lagrange 的配置文件</li>
<li>在 Implementations 中添加 HTTP 服务端口（如 3000）</li>
<li>重启 Lagrange 使配置生效</li>
</ol>

<p><b>第 3 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「OneBot」通知，开启开关</li>
<li>填写以下信息：
<ul>
<li><b>服务地址</b>：<code>http://127.0.0.1:3000</code>（根据实际端口修改）</li>
<li><b>私聊用户 ID</b>：你的 QQ 号（用于私聊通知）</li>
<li>或 <b>群组 ID</b>：目标群号（用于群聊通知）</li>
</ul>
</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：QQ 号可以在 QQ 设置中查看，群号可以在群设置中查看。</div>

<h4>四、常见问题</h4>

<p><b>Q：连接失败？</b></p>
<p>A：请确保 OneBot 服务端正在运行，并且端口号填写正确。</p>

<p><b>Q：发送成功但 QQ 没收到？</b></p>
<p>A：检查用户 ID 或群组 ID 是否正确，以及机器人是否在该群中。</p>""",
    "serverchanturbo": """<h4>一、什么是 Server酱？</h4>
<p>Server酱（ServerChan）是一个将服务器消息推送到微信的服务。Turbo版是升级版，速度更快、更稳定。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：注册并登录</b></p>
<ol>
<li>访问 <a href="https://sct.ftqq.com/">Server酱 Turbo版官网</a></li>
<li>点击右上角「登录」，使用 GitHub 账号登录</li>
<li>登录后进入控制台</li>
</ol>

<p><b>第 2 步：获取 SendKey</b></p>
<ol>
<li>登录后，在首页可以看到你的 <b>SendKey</b></li>
<li>如果没有显示，点击「Key & API」查看</li>
<li>复制这个 SendKey</li>
</ol>

<p><b>第 3 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「Server酱·Turbo版」通知，开启开关</li>
<li>点击「SendKey」右侧的「修改」按钮，粘贴刚才获取的 SendKey</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<p><b>第 4 步：关注公众号接收消息</b></p>
<ol>
<li>微信搜索公众号「方糖」或扫描官网二维码</li>
<li>关注后即可在微信接收推送消息</li>
</ol>

<div class="tip">💡 <b>提示</b>：免费版每天有发送次数限制，如需更多次数可付费升级。</div>

<h4>三、常见问题</h4>

<p><b>Q：发送测试后微信没收到？</b></p>
<p>A：请确保已关注「方糖」公众号，并检查 SendKey 是否正确。</p>

<p><b>Q：提示发送失败？</b></p>
<p>A：可能是达到每日发送上限，请登录官网查看配额。</p>

<h4>四、参考链接</h4>
<p><a href="https://sct.ftqq.com/">Server酱 Turbo版官网</a></p>""",
    "bark": """<h4>一、什么是 Bark？</h4>
<p>Bark 是一款 iOS 端的推送通知工具，通过简单的 API 调用即可将消息推送到你的 iPhone 或 iPad 上。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：下载 Bark APP</b></p>
<ol>
<li>在 App Store 搜索「Bark」并下载安装</li>
<li>打开 APP，允许通知权限</li>
</ol>

<p><b>第 2 步：获取推送密钥</b></p>
<ol>
<li>打开 Bark APP</li>
<li>首页会显示你的 <b>推送密钥</b>（一串字母和数字）</li>
<li>点击「复制」按钮复制这个密钥</li>
</ol>

<p><b>第 3 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「Bark」通知，开启开关</li>
<li>点击「推送密钥」右侧的「修改」按钮，粘贴刚才复制的密钥</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：Bark 仅支持 iOS 设备。如果你使用的是 Android 手机，请选择其他推送方式。</div>

<h4>三、可选配置说明</h4>
<ul>
<li><b>分组名</b>：对通知进行分组显示</li>
<li><b>提示音</b>：自定义通知提示音（可在 Bark APP 中查看可用音效）</li>
<li><b>跳转链接</b>：点击通知后跳转的网址</li>
<li><b>服务地址</b>：如果你自建了 Bark 服务端，可以在此填写</li>
</ul>

<h4>四、常见问题</h4>

<p><b>Q：发送测试后 iPhone 没收到？</b></p>
<p>A：请检查：</p>
<ul>
<li>Bark APP 的通知权限是否开启</li>
<li>手机是否开启了勿扰模式</li>
<li>推送密钥是否复制正确</li>
</ul>

<h4>五、参考链接</h4>
<p><a href="https://bark.day/">Bark 官网</a></p>""",
    "wechatworkapp": """<h4>一、什么是企业微信应用？</h4>
<p>企业微信应用可以通过企业微信 API 向指定用户或全员发送应用消息。相比机器人方式，功能更强大。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：创建自建应用</b></p>
<ol>
<li>登录 <a href="https://work.weixin.qq.com/">企业微信管理后台</a></li>
<li>进入「应用管理」→「自建」</li>
<li>点击「创建应用」</li>
<li>填写应用名称和 Logo</li>
<li>设置可见范围（选择接收通知的人员）</li>
<li>创建完成后记录 <b>AgentId</b></li>
</ol>

<p><b>第 2 步：获取企业 ID 和应用密钥</b></p>
<ol>
<li>在管理后台「我的企业」→「企业信息」中获取 <b>企业 ID</b></li>
<li>在应用详情页获取 <b>Secret</b>（应用密钥）</li>
</ol>

<p><b>第 3 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「企业微信应用」通知，开启开关</li>
<li>依次填入：企业 ID、应用密钥、AgentId</li>
<li>接收用户填 <code>@all</code> 表示全员，或填指定用户 ID</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<h4>三、常见问题</h4>

<p><b>Q：提示 IP 不在白名单？</b></p>
<p>A：在应用设置中添加服务器的公网 IP 到白名单。如果无法获取公网 IP，可以使用「自定义 API 地址」通过反代绕过。</p>""",
    "pushplus": """<h4>一、什么是 Pushplus？</h4>
<p>Pushplus 是一个消息推送平台，支持将消息推送到微信、邮箱、短信等多种渠道。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：注册并登录</b></p>
<ol>
<li>访问 <a href="https://www.pushplus.plus/">Pushplus 官网</a></li>
<li>使用微信扫码登录</li>
<li>登录后进入控制台</li>
</ol>

<p><b>第 2 步：获取 Token</b></p>
<ol>
<li>在控制台首页可以看到你的 <b>Token</b></li>
<li>点击「复制」按钮复制这个 Token</li>
</ol>

<p><b>第 3 步：关注公众号</b></p>
<ol>
<li>微信搜索「pushplus推送加」公众号</li>
<li>关注公众号以接收推送消息</li>
</ol>

<p><b>第 4 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「Pushplus」通知，开启开关</li>
<li>点击「推送令牌」右侧的「修改」按钮，粘贴 Token</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：免费版每天有发送次数限制，可在官网查看详细配额。</div>

<h4>三、常见问题</h4>

<p><b>Q：微信收不到通知？</b></p>
<p>A：请确保已关注「pushplus推送加」公众号，并在公众号内绑定账号。</p>""",
    "discord": """<h4>一、什么是 Discord Webhook？</h4>
<p>Discord Webhook 可以让你的服务器频道自动接收消息通知，无需创建机器人。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：创建 Webhook</b></p>
<ol>
<li>打开 Discord，进入你的服务器</li>
<li>右键点击要接收通知的频道</li>
<li>选择「编辑频道」</li>
<li>点击左侧的「整合」</li>
<li>点击「Webhook」→「新建 Webhook」</li>
<li>设置 Webhook 名称和头像</li>
<li>点击「复制 Webhook 地址」</li>
</ol>

<p><b>第 2 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「Discord」通知，开启开关</li>
<li>点击「Webhook 地址」右侧的「修改」按钮，粘贴地址</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：Webhook 地址格式类似 <code>https://discord.com/api/webhooks/xxx/xxx</code></div>

<h4>三、可选配置</h4>
<ul>
<li><b>显示用户名</b>：自定义消息显示的用户名</li>
<li><b>头像地址</b>：自定义消息头像的图片 URL</li>
<li><b>消息颜色</b>：嵌入消息的侧边颜色（十六进制，如 0x3498db）</li>
</ul>""",
    "meow": """<h4>一、什么是 MeoW？</h4>
<p>MeoW 是一款专为 HarmonyOS NEXT 设备设计的推送服务。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：下载 MeoW APP</b></p>
<ol>
<li>在鸿蒙应用市场搜索「MeoW」并下载</li>
<li>打开 APP 并注册登录</li>
<li>记住你在 APP 中设置的昵称</li>
</ol>

<p><b>第 2 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「MeoW」通知，开启开关</li>
<li>点击「昵称」右侧的「修改」按钮，填入你的 MeoW 昵称</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：MeoW 仅支持 HarmonyOS NEXT 设备。其他设备请选择其他推送方式。</div>""",
    "gotify": """<h4>一、什么是 Gotify？</h4>
<p>Gotify 是一个自托管的推送通知服务器，适合有自己服务器的用户。你需要自己部署 Gotify 服务端。</p>

<h4>二、部署 Gotify 服务端（如果已有服务端可跳过）</h4>

<p><b>使用 Docker 部署（推荐）：</b></p>
<ol>
<li>确保服务器已安装 Docker</li>
<li>运行命令：<code>docker run -d --name gotify -p 8080:80 gotify/server</code></li>
<li>访问 <code>http://你的服务器IP:8080</code></li>
<li>默认管理员账号：admin / admin</li>
<li>登录后请立即修改密码</li>
</ol>

<h4>三、配置步骤</h4>

<p><b>第 1 步：创建应用</b></p>
<ol>
<li>登录 Gotify 管理界面</li>
<li>点击「Apps」标签</li>
<li>点击「Create Application」</li>
<li>填写应用名称（如：March7thAssistant）</li>
<li>创建后会显示 <b>Token</b>，复制它</li>
</ol>

<p><b>第 2 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「Gotify」通知，开启开关</li>
<li>填写以下信息：
<ul>
<li><b>服务地址</b>：你的 Gotify 服务器地址（如 http://192.168.1.100:8080）</li>
<li><b>访问令牌</b>：刚才创建的应用 Token</li>
</ul>
</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：Gotify 有 Android 客户端，可以在 Google Play 下载。iOS 用户可以使用 Web 推送。</div>""",
    "kook": """<h4>一、什么是 KOOK？</h4>
<p>KOOK（原开黑啦）是一款游戏语音社交软件，支持机器人推送通知。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：创建 KOOK 机器人</b></p>
<ol>
<li>访问 <a href="https://developer.kookapp.cn/">KOOK 开发者平台</a></li>
<li>登录你的 KOOK 账号</li>
<li>点击「新建应用」</li>
<li>填写应用名称，选择图标</li>
<li>在「机器人」页面开启「机器人」功能</li>
<li>复制 <b>Token</b>（在「机器人」页面）</li>
</ol>

<p><b>第 2 步：邀请机器人到服务器</b></p>
<ol>
<li>在应用详情页，点击「邀请链接」</li>
<li>选择你要添加机器人的服务器</li>
<li>完成授权</li>
</ol>

<p><b>第 3 步：获取目标 ID</b></p>
<ol>
<li>如果要私聊：在 KOOK 设置中获取你的用户 ID</li>
<li>如果要频道消息：右键点击频道 → 复制 ID（需开启开发者模式）</li>
</ol>

<p><b>第 4 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「KOOK」通知，开启开关</li>
<li>填写 Token 和目标 ID</li>
<li>聊天类型：1 为私聊，9 为频道</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>""",
    "qmsg": """<h4>一、什么是 Qmsg？</h4>
<p>Qmsg 酱是一个基于 QQ 的消息推送服务，可以把程序通知发送到指定 QQ 或群聊场景。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：注册并获取 Key</b></p>
<ol>
<li>访问 <a href="https://qmsg.zendee.cn/">Qmsg 酱官网</a></li>
<li>登录或注册账号后，进入控制台</li>
<li>创建或查看你的推送 Key，并复制保存</li>
</ol>

<p><b>第 2 步：确认接收目标</b></p>
<ol>
<li>默认情况下，消息会发送到该 Key 绑定的 QQ</li>
<li>如果需要发送给其他 QQ，可额外填写「QQ 号」参数</li>
<li>如需群发等其他能力，可按实际需要填写「发送模式」</li>
</ol>

<p><b>第 3 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「Qmsg」通知，开启开关</li>
<li>点击「推送密钥」右侧的「修改」按钮，粘贴获取的 Key</li>
<li>如有需要，填写「QQ 号」和「发送模式」</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：如果只给当前 Key 绑定的默认 QQ 发送消息，通常只需要填写 Key 即可。</div>

<h4>三、参考链接</h4>
<p><a href="https://qmsg.zendee.cn/api.html">Qmsg 酱接口文档</a></p>""",
    "matrix": """<h4>一、什么是 Matrix？</h4>
<p>Matrix 是一个开放的去中心化通讯协议，支持端到端加密。你可以使用 Element 等客户端来接收通知。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：注册 Matrix 账号</b></p>
<ol>
<li>访问 <a href="https://app.element.io/">Element Web</a> 或下载 Element 客户端</li>
<li>点击「创建账号」注册一个新账号</li>
<li>选择一个服务器（推荐 matrix.org）</li>
<li>完成注册并登录</li>
</ol>

<p><b>第 2 步：创建房间</b></p>
<ol>
<li>登录后，点击左侧的「+」创建新房间</li>
<li>设置房间名称（如：通知接收）</li>
<li>将房间设置为「私密」</li>
<li>创建完成后，点击房间名称 →「设置」→「高级」</li>
<li>复制「内部房间 ID」（格式类似：<code>!abc123:matrix.org</code>）</li>
</ol>

<p><b>第 3 步：获取 Access Token</b></p>
<ol>
<li>在 Element 中，点击右上角头像 →「所有设置」</li>
<li>点击「帮助 & 关于」</li>
<li>向下滚动找到「访问令牌」</li>
<li>点击「生成新令牌」并复制</li>
</ol>

<p><b>第 4 步：获取设备 ID</b></p>
<ol>
<li>在同一页面中，找到「会话 ID」或「设备 ID」</li>
<li>复制这个 ID（通常是 10 位大写字母或数字）</li>
</ol>

<p><b>第 5 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到 Matrix 通知，开启开关</li>
<li>依次填入服务器地址、设备 ID、用户 ID、访问令牌、房间 ID</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：用户 ID 格式为 <code>@username:server.org</code>，可以在「设置」→「常规」中查看。</div>

<h4>三、常见问题</h4>

<p><b>Q：提示认证失败？</b></p>
<p>A：Access Token 可能已过期，请重新生成一个。</p>

<p><b>Q：消息发送成功但收不到？</b></p>
<p>A：确保你已经加入了目标房间，并且房间 ID 格式正确（以 ! 开头）。</p>

<h4>四、参考链接</h4>
<p><a href="https://element.io/">Element 官网</a></p>""",
    "pushdeer": """<h4>一、什么是 Pushdeer？</h4>
<p>Pushdeer 是一个开源的推送服务，支持 iOS 和 Android。可以使用官方服务或自建服务。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：下载 Pushdeer APP</b></p>
<ol>
<li>iOS 用户在 App Store 搜索「Pushdeer」下载</li>
<li>Android 用户访问 <a href="https://github.com/easychen/pushdeer/releases">GitHub Releases</a> 下载</li>
<li>打开 APP 并登录</li>
</ol>

<p><b>第 2 步：获取 Token</b></p>
<ol>
<li>打开 Pushdeer APP</li>
<li>进入「Key」页面</li>
<li>点击「生成新 Key」或复制已有的 Key</li>
<li>这就是你的推送 Token</li>
</ol>

<p><b>第 3 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「Pushdeer」通知，开启开关</li>
<li>点击「推送令牌」右侧的「修改」按钮，粘贴 Token</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<div class="tip">💡 <b>提示</b>：如果使用自建服务，需要填写「服务地址」。</div>""",
    "gocqhttp": """<div class="warning">
<b>重要提示</b>：Go-cqhttp 项目已于 2023 年停止维护，不再推荐使用。建议改用 <b>OneBot</b> 配合 Lagrange 或 NapCat。
</div>

<h4>一、什么是 Go-cqhttp？</h4>
<p>Go-cqhttp 是一个基于 Mirai 的 QQ 机器人框架，曾经是最流行的 QQ 机器人方案之一。由于项目已停止维护，建议迁移到 OneBot 方案。</p>

<h4>二、如果仍在使用，配置步骤如下</h4>

<p><b>第 1 步：确保 Go-cqhttp 正在运行</b></p>
<ol>
<li>Go-cqhttp 服务端必须正在运行</li>
<li>已配置好 HTTP 服务端口</li>
</ol>

<p><b>第 2 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「Go-cqhttp」通知，开启开关</li>
<li>填写以下信息：
<ul>
<li><b>服务地址</b>：Go-cqhttp 的 HTTP 端点（如 http://127.0.0.1:5700）</li>
<li><b>消息类型</b>：private（私聊）或 group（群聊）</li>
<li><b>用户 ID</b>：私聊时填写 QQ 号</li>
<li><b>群组 ID</b>：群聊时填写群号</li>
</ul>
</li>
</ol>

<h4>三、建议迁移</h4>
<p>由于 Go-cqhttp 已停止维护，建议迁移到以下方案：</p>
<ul>
<li><b>Lagrange.Core</b>：持续维护，兼容性好</li>
<li><b>NapCatQQ</b>：基于新版 QQ 协议</li>
</ul>
<p>迁移后在本软件中选择「OneBot」推送方式即可。</p>""",
    "webhook": """<h4>一、什么是 Webhook？</h4>
<p>Webhook 是一种通用的 HTTP 回调方式，可以将通知发送到任何支持 HTTP 请求的服务。适合高级用户或需要对接自定义服务的场景。</p>

<h4>二、基本概念</h4>
<ul>
<li><b>接收地址</b>：你要发送通知的目标 URL</li>
<li><b>请求方法</b>：通常是 POST（创建数据）或 GET（获取数据）</li>
<li><b>请求头</b>：附加的 HTTP 头信息，用于认证等</li>
<li><b>请求体</b>：发送的数据内容</li>
</ul>

<h4>三、配置步骤</h4>

<p><b>第 1 步：准备接收端</b></p>
<p>你需要有一个能够接收 HTTP 请求的服务，例如：</p>
<ul>
<li>IFTTT Webhook</li>
<li>Zapier Webhook</li>
<li>自建服务器 API</li>
<li>其他支持 Webhook 的服务</li>
</ul>

<p><b>第 2 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「Webhook」通知，开启开关</li>
<li>填写以下信息：
<ul>
<li><b>接收地址</b>：你的 Webhook 接收 URL</li>
<li><b>请求方法</b>：默认 POST，通常不需要修改</li>
<li><b>请求头</b>：如需认证，填入 JSON 格式的请求头</li>
<li><b>请求体</b>：自定义发送的数据模板</li>
</ul>
</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<h4>四、占位符说明</h4>
<table>
<tr><th>占位符</th><th>说明</th></tr>
<tr><td><code>{title}</code></td><td>通知标题</td></tr>
<tr><td><code>{content}</code></td><td>通知内容</td></tr>
<tr><td><code>{image}</code></td><td>图片（Base64 编码）</td></tr>
</table>

<h4>五、示例配置</h4>
<p>请求头示例（JSON）：</p>
<p><code>{"Authorization": "Bearer your_token", "Content-Type": "application/json"}</code></p>

<p>请求体示例（JSON）：</p>
<p><code>{"title": "{title}", "message": "{content}"}</code></p>""",
    "custom": """<h4>一、什么是自定义通知？</h4>
<p>自定义通知允许你完全自定义 HTTP 请求，适合对接不被内置支持的服务或 API。</p>

<h4>二、配置步骤</h4>

<p><b>第 1 步：了解目标 API</b></p>
<p>首先需要了解你要对接的 API 的请求格式，包括：</p>
<ul>
<li>请求地址</li>
<li>请求方法（GET 或 POST）</li>
<li>数据格式（表单或 JSON）</li>
<li>是否需要认证</li>
</ul>

<p><b>第 2 步：配置到 March7thAssistant</b></p>
<ol>
<li>在本软件中，找到「消息推送」设置</li>
<li>开启「启用消息推送」总开关</li>
<li>找到「自定义通知」，开启开关</li>
<li>填写以下信息：
<ul>
<li><b>请求地址</b>：API 端点 URL</li>
<li><b>请求方法</b>：get 或 post</li>
<li><b>数据类型</b>：data（表单）或 json</li>
<li><b>数据模板</b>：请求体内容</li>
</ul>
</li>
<li>点击下方的「发送消息」按钮测试</li>
</ol>

<h4>三、占位符说明</h4>
<table>
<tr><th>占位符</th><th>说明</th></tr>
<tr><td><code>{message}</code></td><td>通知标题和内容的组合</td></tr>
<tr><td><code>{image}</code></td><td>图片（Base64 编码）</td></tr>
</table>

<h4>四、示例：对接 OneBot API</h4>
<p>请求地址：<code>http://127.0.0.1:3000/send_private_msg?user_id=123456</code></p>
<p>请求方法：<code>get</code></p>
<p>数据类型：<code>data</code></p>
<p>数据模板：<code>message={message}</code></p>""",
}
