package org.march7th.deviceservice.protocol;

import org.json.JSONException;
import org.json.JSONObject;

/** 一条消息：JSON 头加可选的二进制负载。 */
public final class Message {
    private static final byte[] EMPTY = new byte[0];

    public final JSONObject header;
    public final byte[] payload;
    public final int payloadOffset;
    public final int payloadLength;

    public Message(JSONObject header) {
        this(header, EMPTY, 0, 0);
    }

    public Message(JSONObject header, byte[] payload) {
        this(header, payload, 0, payload.length);
    }

    public Message(JSONObject header, byte[] payload, int payloadOffset, int payloadLength) {
        if (header == null || payload == null) {
            throw new NullPointerException();
        }
        if (payloadOffset < 0 || payloadLength < 0 || payloadOffset > payload.length - payloadLength) {
            throw new IndexOutOfBoundsException();
        }
        this.header = header;
        this.payload = payload;
        this.payloadOffset = payloadOffset;
        this.payloadLength = payloadLength;
    }

    /** 成功响应，带上请求的 id。 */
    public static JSONObject ok(JSONObject request) {
        JSONObject header = new JSONObject();
        try {
            copyId(request, header);
            header.put("ok", true);
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        return header;
    }

    /** 失败响应。 */
    public static JSONObject error(JSONObject request, String code, String message) {
        JSONObject header = new JSONObject();
        try {
            copyId(request, header);
            header.put("ok", false);
            JSONObject error = new JSONObject();
            error.put("code", code);
            error.put("message", message == null ? "" : message);
            header.put("error", error);
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        return header;
    }

    private static void copyId(JSONObject request, JSONObject header) throws JSONException {
        if (request != null && request.has("id")) {
            header.put("id", request.get("id"));
        }
    }
}
