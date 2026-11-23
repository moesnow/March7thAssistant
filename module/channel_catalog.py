"""Notification form definitions. Labels and descriptions are source msgids."""
from dataclasses import dataclass

from module.channel_tutorials import TUTORIALS


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str
    description: str = ""
    required: bool = False
    secret: bool = False
    choices: tuple[str, ...] = ()
    placeholder: str = ""


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    icon: str
    description: str
    fields: tuple[Field, ...]

    @property
    def enable_key(self):
        return f"notify_{self.id}_enable"

    @property
    def tutorial(self):
        return TUTORIALS.get(self.id, "")


CHANNELS = (
    Channel('winotify', 'Windows', 'BrandIcon.WINDOWS', 'Windows 原生通知', (
    )),
    Channel('wechatworkbot', '企业微信机器人', 'BrandIcon.WECOM', '企业微信机器人消息推送', (
        Field('notify_wechatworkbot_key', '机器人 Key', 'secret', '', secret=True),
        Field('notify_wechatworkbot_webhook_url', 'Webhook 地址', 'secret', '可选参数，企业微信机器人 Webhook URL', secret=True),
    )),
    Channel('qqbot', 'QQ 官方机器人', 'BrandIcon.QQ', 'QQ 开放平台官方机器人推送', (
        Field('notify_qqbot_appid', '机器人 AppID', 'text', 'QQ 开放平台的机器人 AppID', required=True),
        Field('notify_qqbot_client_secret', '机器人 AppSecret', 'secret', 'QQ 开放平台的机器人 AppSecret', required=True, secret=True),
        Field('notify_qqbot_openid', '单聊用户 openid', 'text', '可选参数，单聊消息的接收用户 openid'),
        Field('notify_qqbot_group_openid', '群聊 group_openid', 'text', '可选参数，群聊消息的接收群 group_openid'),
    )),
    Channel('smtp', 'SMTP', 'FIF.MAIL', '常用于邮箱提醒', (
        Field('notify_smtp_host', 'SMTP 服务器', 'text', '', required=True),
        Field('notify_smtp_user', '用户名/邮箱', 'text', ''),
        Field('notify_smtp_password', '密码/授权码', 'secret', '部分邮箱需要填写授权码（如 QQ 邮箱）', secret=True),
        Field('notify_smtp_From', '发件人', 'text', '可选参数，发件人邮箱，默认使用 user'),
        Field('notify_smtp_To', '收件人', 'text', '可选参数，收件人邮箱，默认使用 user'),
        Field('notify_smtp_port', '端口', 'number', '可选参数，端口，默认 465', placeholder='465'),
        Field('notify_smtp_ssl', '启用 SSL', 'switch', '可选参数，是否启用 SSL'),
        Field('notify_smtp_starttls', '启用 STARTTLS', 'switch', '可选参数，是否启用 STARTTLS'),
        Field('notify_smtp_ssl_unverified', '跳过证书验证', 'switch', '可选参数，是否跳过 SSL 证书验证'),
        Field('notify_smtp_plain_text', '纯文本模式', 'switch', '可选参数，是否以纯文本格式发送邮件（适用于 Outlook 等邮箱）'),
    )),
    Channel('lark', '飞书', 'BrandIcon.LARK', '飞书机器人推送', (
        Field('notify_lark_webhook', 'Webhook 地址', 'secret', '', required=True, secret=True),
        Field('notify_lark_content', '消息内容', 'text', ''),
        Field('notify_lark_keyword', '关键词', 'text', '可选参数，关键词安全校验内容'),
        Field('notify_lark_sign', '签名', 'secret', '可选参数，签名安全校验参数', secret=True),
        Field('notify_lark_imageenable', '启用图片', 'switch', '是否发送图片'),
        Field('notify_lark_appid', '应用 AppId', 'text', '发送图片时必填：飞书应用 AppId'),
        Field('notify_lark_secret', '应用 Secret', 'secret', '发送图片时必填：飞书应用 Secret', secret=True),
    )),
    Channel('telegram', 'Telegram', 'BrandIcon.TELEGRAM', '通常需要可访问 Telegram 网络', (
        Field('notify_telegram_token', '机器人令牌', 'secret', '获取方式：创建 Bot → @BotFather → /newbot → 获取 Token', required=True, secret=True),
        Field('notify_telegram_userid', '用户/群组 ID', 'text', '接收通知的用户 ID 或群组 ID（以 - 开头）', required=True),
        Field('notify_telegram_api_url', '自定义 API 地址', 'text', '可选参数，自定义 Telegram API 地址，例如 api.telegram.org', placeholder='api.telegram.org'),
        Field('notify_telegram_proxies', '代理配置', 'secret', '可选参数，例如 127.0.0.1:10808 或 socks5://127.0.0.1:1080，不填则使用系统 PAC 代理', secret=True),
        Field('notify_telegram_thread_id', '话题 ID', 'text', '可选参数，开启 Topics 功能的群组需要填写对应的话题 ID'),
    )),
    Channel('dingtalk', '钉钉', 'BrandIcon.DINGTALK', '钉钉机器人推送', (
        Field('notify_dingtalk_token', '机器人令牌', 'secret', '', required=True, secret=True),
        Field('notify_dingtalk_secret', '加签密钥', 'secret', '可选参数，安全加签密钥', secret=True),
    )),
    Channel('serverchan3', 'Server酱³', 'UiIcon.SEND_COPY', 'Server酱³ APP 推送', (
        Field('notify_serverchan3_sendkey', 'SendKey', 'secret', '在 https://sc3.ft07.com/ 获取的 SendKey', required=True, secret=True),
    )),
    Channel('onebot', 'OneBot', 'FIF.ROBOT', '适用于 OneBot 协议', (
        Field('notify_onebot_endpoint', '服务地址', 'text', 'OneBot 服务端点地址，例如 http://127.0.0.1:3000', required=True, placeholder='http://127.0.0.1:3000'),
        Field('notify_onebot_token', '访问令牌', 'secret', '可选参数，Access Token', secret=True),
        Field('notify_onebot_user_id', '私聊用户 ID', 'text', '可选参数，私聊接收用户 ID'),
        Field('notify_onebot_group_id', '群组 ID', 'text', '可选参数，群聊接收群组 ID'),
    )),
    Channel('serverchanturbo', 'Server酱·Turbo版', 'UiIcon.SEND', '微信推送，适合轻量通知', (
        Field('notify_serverchanturbo_sctkey', 'SendKey', 'secret', '在 https://sct.ftqq.com/ 获取的 SendKey', required=True, secret=True),
        Field('notify_serverchanturbo_channel', '发送通道', 'text', '可选参数'),
        Field('notify_serverchanturbo_openid', '接收人 OpenID', 'text', '可选参数'),
    )),
    Channel('bark', 'Bark', 'UiIcon.MEGAPHONE', '适合 iOS 设备推送', (
        Field('notify_bark_key', '推送密钥', 'secret', '在 Bark APP 中获取的唯一标识符', required=True, secret=True),
        Field('notify_bark_group', '分组名', 'text', '可选参数，Bark 通知的分组名'),
        Field('notify_bark_icon', '图标地址', 'text', '可选参数，通知图标的 URL'),
        Field('notify_bark_isarchive', '归档', 'text', '可选参数：1 归档，0 不归档'),
        Field('notify_bark_sound', '提示音', 'text', '可选参数，自定义提示音名称'),
        Field('notify_bark_url', '跳转链接', 'text', '可选参数，通知点击后跳转的 URL'),
        Field('notify_bark_base_url', '服务地址', 'text', '可选参数，自定义 Bark 服务的 URL'),
        Field('notify_bark_copy', '复制内容', 'text', '可选参数，通知点击后复制内容'),
        Field('notify_bark_autocopy', '自动复制', 'text', '可选参数，是否自动复制'),
        Field('notify_bark_cipherkey', '加密密钥', 'secret', '可选参数，推送加密密钥，需在 Bark APP 中配置相同的密钥', secret=True),
        Field('notify_bark_ciphermethod', '加密算法', 'choice', '可选参数，支持 cbc 或 ecb，需与 Bark APP 中配置的算法一致', choices=('cbc', 'ecb')),
    )),
    Channel('wechatworkapp', '企业微信应用', 'BrandIcon.WECOM', '企业微信应用消息推送', (
        Field('notify_wechatworkapp_corpid', '企业 ID', 'text', '', required=True),
        Field('notify_wechatworkapp_corpsecret', '应用密钥', 'secret', '', required=True, secret=True),
        Field('notify_wechatworkapp_agentid', '应用 AgentId', 'text', '', required=True),
        Field('notify_wechatworkapp_touser', '接收用户', 'text', '可选参数，接收用户，@all 表示全员', required=True),
        Field('notify_wechatworkapp_base_url', '自定义 API 地址', 'text', '可选参数，自定义企业微信 API 地址，用于反向代理绕过可信 IP 限制'),
    )),
    Channel('pushplus', 'Pushplus', 'UiIcon.MEGAPHONE_CIRCLE', 'Pushplus 通知服务', (
        Field('notify_pushplus_token', '推送令牌', 'secret', '', required=True, secret=True),
        Field('notify_pushplus_channel', '推送渠道', 'text', '可选参数'),
        Field('notify_pushplus_webhook', 'Webhook 地址', 'secret', '可选参数，Webhook URL', secret=True),
        Field('notify_pushplus_callbackUrl', '回调地址', 'secret', '可选参数，回调 URL', secret=True),
    )),
    Channel('discord', 'Discord', 'BrandIcon.DISCORD', 'Discord Webhook 推送', (
        Field('notify_discord_webhook', 'Webhook 地址', 'secret', '', required=True, secret=True),
        Field('notify_discord_username', '显示用户名', 'text', '可选参数，显示用户名'),
        Field('notify_discord_avatar_url', '头像地址', 'text', '可选参数，头像 URL'),
        Field('notify_discord_color', '消息颜色', 'text', '可选参数，嵌入消息颜色，十六进制颜色值（如：0x3498db）'),
    )),
    Channel('meow', 'MeoW', 'UiIcon.SOUND_WAVE', '适合 鸿蒙NEXT 设备推送', (
        Field('notify_meow_nickname', '昵称', 'text', '', required=True),
    )),
    Channel('gotify', 'Gotify', 'UiIcon.SERVER', 'Gotify 私有通知服务', (
        Field('notify_gotify_url', '服务地址', 'text', 'Gotify 服务器 URL，例如 https://gotify.example.com', required=True),
        Field('notify_gotify_token', '访问令牌', 'secret', 'Gotify 应用的 Access Token', required=True, secret=True),
        Field('notify_gotify_priority', '优先级', 'number', '可选参数，通知优先级，范围 1-10，越高优先级越高。1-3:仅图标，4-7:图标 + 声音，8-10:图标 + 声音 + 震动'),
    )),
    Channel('kook', 'KOOK', 'UiIcon.MIC', 'KOOK 机器人推送', (
        Field('notify_kook_token', '机器人令牌', 'secret', 'KOOK 机器人的 Token', required=True, secret=True),
        Field('notify_kook_target_id', '目标 ID', 'text', '接收消息的用户 ID 或频道 ID', required=True),
        Field('notify_kook_chat_type', '聊天类型', 'choice', '可选参数，1 为私聊，9 为频道', choices=('1', '9')),
    )),
    Channel('qmsg', 'Qmsg', 'UiIcon.PEOPLE_CHAT', 'Qmsg 酱 QQ 推送', (
        Field('notify_qmsg_key', '推送密钥', 'secret', 'Qmsg 酱分配的 Key', required=True, secret=True),
        Field('notify_qmsg_qq', 'QQ 号', 'text', '可选参数，指定接收通知的 QQ 号，不填则发送到该 Key 绑定的默认 QQ'),
        Field('notify_qmsg_mode', '发送模式', 'choice', '可选参数，例如 send（默认）或 group', choices=('send', 'group')),
    )),
    Channel('matrix', 'Matrix', 'BrandIcon.MATRIX', '适用于 Matrix 协议', (
        Field('notify_matrix_homeserver', '服务器地址', 'text', '服务器地址，例如 https://matrix.org', required=True),
        Field('notify_matrix_device_id', '设备 ID', 'text', '设备 ID，通常是 10 位大写字母或数字', required=True),
        Field('notify_matrix_user_id', '用户 ID', 'text', '用户 ID，例如 @user:matrix.org', required=True),
        Field('notify_matrix_access_token', '访问令牌', 'secret', '登录后分配的 Access Token', required=True, secret=True),
        Field('notify_matrix_room_id', '房间 ID', 'text', '目标房间 ID，例如 !xxx:matrix.org', required=True),
        Field('notify_matrix_proxy', '代理配置', 'secret', '可选参数，例如 127.0.0.1:10808 或 socks5://127.0.0.1:1080，不填则使用系统 PAC 代理', secret=True),
        Field('notify_matrix_separately_text_media', '文字与图片分开发送', 'switch', '是否分开发送文字和图片，避免部分客户端不显示文字'),
    )),
    Channel('pushdeer', 'Pushdeer', 'UiIcon.MEGAPHONE_LOUD', 'Pushdeer 通知服务', (
        Field('notify_pushdeer_token', '推送令牌', 'secret', 'Pushdeer Token', required=True, secret=True),
        Field('notify_pushdeer_url', '服务地址', 'text', '可选参数，自定义 Pushdeer 服务地址'),
    )),
    Channel('gocqhttp', 'Go-cqhttp', 'FIF.ROBOT', 'Go-cqhttp 项目已停止维护', (
        Field('notify_gocqhttp_endpoint', '服务地址', 'text', '', required=True),
        Field('notify_gocqhttp_message_type', '消息类型', 'choice', '消息类型：private 或 group', choices=('private', 'group')),
        Field('notify_gocqhttp_token', '访问令牌', 'secret', '可选参数，Access Token', secret=True),
        Field('notify_gocqhttp_user_id', '私聊用户 ID', 'text', '可选参数，私聊接收用户 ID'),
        Field('notify_gocqhttp_group_id', '群组 ID', 'text', '可选参数，群聊接收群组 ID'),
    )),
    Channel('webhook', 'Webhook', 'UiIcon.PLUG', '可自定义请求方法、请求头和请求体', (
        Field('notify_webhook_url', '接收地址', 'secret', '', required=True, secret=True),
        Field('notify_webhook_method', '请求方法', 'choice', '可选参数，HTTP 方法，默认 POST', choices=('GET', 'POST', 'PUT', 'PATCH', 'DELETE')),
        Field('notify_webhook_headers', '请求头', 'multiline', '可选参数，请求头 JSON 格式字符串，如：{"Authorization": "Bearer token"}', secret=True, placeholder='{"Content-Type": "application/json"}'),
        Field('notify_webhook_body', '请求体', 'multiline', '可选参数，请求体模板 JSON 格式字符串，支持 {title}/{content}/{image} 占位符', secret=True),
    )),
    Channel('custom', '自定义通知', 'FIF.CODE', '自定义 HTTP 请求推送', (
        Field('notify_custom_url', '请求地址', 'secret', '请求地址，OneBot 可填写 send_msg 接口 URL', required=True, secret=True),
        Field('notify_custom_method', '请求方法', 'choice', '请求方法，通常 get 或 post', choices=('get', 'post', 'put', 'patch', 'delete')),
        Field('notify_custom_datatype', '数据类型', 'choice', '数据类型，通常为 data 或 json', choices=('json', 'data')),
        Field('notify_custom_image', '图片模板', 'multiline', '可选参数，图片消息模板，{image} 会替换为 Base64', secret=True),
        Field('notify_custom_data', '数据模板', 'multiline', '请求体模板，{message} 会替换为标题和内容', secret=True),
    )),
)
CHANNEL_BY_ID = {channel.id: channel for channel in CHANNELS}
