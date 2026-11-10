package org.march7th.deviceservice.protocol;

import java.io.IOException;

/** 对端发来的数据不符合帧格式。收到后应当直接断开。 */
public final class ProtocolException extends IOException {
    private static final long serialVersionUID = 1L;

    public ProtocolException(String message) {
        super(message);
    }

    public ProtocolException(String message, Throwable cause) {
        super(message, cause);
    }
}
