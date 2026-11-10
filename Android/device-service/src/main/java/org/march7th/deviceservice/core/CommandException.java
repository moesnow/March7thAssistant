package org.march7th.deviceservice.core;

import org.json.JSONObject;

/** 命令执行失败，对应响应里的 error.code 和 error.message。 */
public final class CommandException extends Exception {
    private static final long serialVersionUID = 1L;

    public final String code;
    /** 附加到 error 对象里的字段，可以为 null。 */
    public final transient JSONObject details;

    public CommandException(String code, String message) {
        this(code, message, null);
    }

    public CommandException(String code, String message, JSONObject details) {
        super(message);
        this.code = code;
        this.details = details;
    }
}
