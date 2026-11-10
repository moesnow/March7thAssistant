package org.march7th.deviceservice.protocol;

import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * 握手校验：连接上的第一条消息必须是带令牌和协议版本的 hello。
 *
 * 先校验令牌，再校验协议版本：令牌不对的连接拿不到任何关于服务的信息。
 */
public final class Handshake {
    public enum Result {
        OK,
        /** 第一条消息不是合法的 hello。 */
        BAD_REQUEST,
        /** 令牌缺失或不匹配。 */
        UNAUTHORIZED,
        /** 令牌正确，但协议版本不一致。 */
        PROTOCOL_MISMATCH,
    }

    private final byte[] token;

    public Handshake(String token) {
        if (!isValidToken(token)) {
            throw new IllegalArgumentException("token must be 16-128 characters of [A-Za-z0-9_-]");
        }
        this.token = token.getBytes(StandardCharsets.UTF_8);
    }

    /** 令牌要求 16 到 128 个字符，只含字母、数字、下划线和连字符。 */
    public static boolean isValidToken(String token) {
        if (token == null || token.length() < 16 || token.length() > 128) {
            return false;
        }
        for (int i = 0; i < token.length(); i++) {
            char c = token.charAt(i);
            boolean ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c == '-';
            if (!ok) {
                return false;
            }
        }
        return true;
    }

    public Result check(JSONObject hello) {
        if (hello == null || !"hello".equals(hello.optString("cmd", null))) {
            return Result.BAD_REQUEST;
        }
        Object candidate = hello.opt("token");
        if (!(candidate instanceof String) || !matches((String) candidate)) {
            return Result.UNAUTHORIZED;
        }
        Object protocol = hello.opt("protocol");
        if (!(protocol instanceof Integer) || (Integer) protocol != Protocol.VERSION) {
            return Result.PROTOCOL_MISMATCH;
        }
        return Result.OK;
    }

    /** 比较耗时不随第一个不同字符的位置变化。 */
    public boolean matches(String candidate) {
        if (candidate == null) {
            return false;
        }
        return MessageDigest.isEqual(token, candidate.getBytes(StandardCharsets.UTF_8));
    }
}
