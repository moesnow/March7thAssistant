package org.march7th.deviceservice.protocol;

/** 协议常量。字段含义见 PROTOCOL.md。 */
public final class Protocol {
    /** 协议版本。出现不兼容改动时加一，握手要求两端完全相等。 */
    public static final int VERSION = 1;
    /** 服务自身的版本，只用于判断设备上的 jar 是否需要重新推送。 */
    public static final String SERVICE_VERSION = "0.1.0";

    public static final String LOG_TAG = "M7ADevice";
    public static final String DEFAULT_SOCKET_NAME = "m7a-device-service";

    /** 握手完成前只接受很小的消息，避免未鉴权的连接占用内存。 */
    public static final int MAX_HANDSHAKE_HEADER_BYTES = 4096;
    public static final int MAX_HEADER_BYTES = 1 << 20;
    public static final int MAX_REQUEST_PAYLOAD_BYTES = 1 << 20;
    public static final int MAX_RESPONSE_PAYLOAD_BYTES = 64 << 20;

    public static final int HANDSHAKE_TIMEOUT_MS = 5000;

    // 错误码
    public static final String E_BAD_REQUEST = "bad_request";
    public static final String E_UNKNOWN_COMMAND = "unknown_command";
    public static final String E_UNAUTHORIZED = "unauthorized";
    public static final String E_PROTOCOL_MISMATCH = "protocol_mismatch";
    public static final String E_NO_DISPLAY = "no_display";
    public static final String E_DISPLAY_EXISTS = "display_exists";
    public static final String E_DISPLAY_FAILED = "display_failed";
    public static final String E_FORBIDDEN_DISPLAY = "forbidden_display";
    public static final String E_TIMEOUT = "timeout";
    public static final String E_INJECT_FAILED = "inject_failed";
    public static final String E_INJECT_DENIED = "inject_denied";
    public static final String E_DEVICE_ASLEEP = "device_asleep";
    public static final String E_KEYGUARD_LOCKED = "keyguard_locked";
    public static final String E_GAME_NOT_ON_DISPLAY = "game_not_on_display";
    public static final String E_LAUNCH_FAILED = "launch_failed";
    public static final String E_UNSUPPORTED = "unsupported";
    public static final String E_INTERNAL = "internal";

    private Protocol() {
    }
}
