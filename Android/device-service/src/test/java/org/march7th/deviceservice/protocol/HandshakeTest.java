package org.march7th.deviceservice.protocol;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.json.JSONObject;
import org.junit.Test;

public class HandshakeTest {
    private static final String TOKEN = "s3cret-token_0123456789";

    private static JSONObject hello(Object token, Object protocol) throws Exception {
        JSONObject hello = new JSONObject().put("id", 1).put("cmd", "hello");
        if (token != null) {
            hello.put("token", token);
        }
        if (protocol != null) {
            hello.put("protocol", protocol);
        }
        return hello;
    }

    @Test
    public void acceptsMatchingTokenAndProtocol() throws Exception {
        assertEquals(Handshake.Result.OK, new Handshake(TOKEN).check(hello(TOKEN, Protocol.VERSION)));
    }

    @Test
    public void rejectsMissingOrWrongToken() throws Exception {
        Handshake handshake = new Handshake(TOKEN);
        assertEquals(Handshake.Result.UNAUTHORIZED, handshake.check(hello(null, Protocol.VERSION)));
        assertEquals(Handshake.Result.UNAUTHORIZED, handshake.check(hello("", Protocol.VERSION)));
        assertEquals(Handshake.Result.UNAUTHORIZED, handshake.check(hello(TOKEN + "x", Protocol.VERSION)));
        assertEquals(Handshake.Result.UNAUTHORIZED, handshake.check(hello(TOKEN.substring(1), Protocol.VERSION)));
        assertEquals(Handshake.Result.UNAUTHORIZED, handshake.check(hello(TOKEN.toUpperCase(), Protocol.VERSION)));
        assertEquals(Handshake.Result.UNAUTHORIZED, handshake.check(hello(12345, Protocol.VERSION)));
        assertEquals(Handshake.Result.UNAUTHORIZED, handshake.check(hello(JSONObject.NULL, Protocol.VERSION)));
    }

    @Test
    public void rejectsOtherProtocolVersions() throws Exception {
        Handshake handshake = new Handshake(TOKEN);
        assertEquals(Handshake.Result.PROTOCOL_MISMATCH, handshake.check(hello(TOKEN, Protocol.VERSION + 1)));
        assertEquals(Handshake.Result.PROTOCOL_MISMATCH, handshake.check(hello(TOKEN, 0)));
        assertEquals(Handshake.Result.PROTOCOL_MISMATCH, handshake.check(hello(TOKEN, null)));
        assertEquals(Handshake.Result.PROTOCOL_MISMATCH, handshake.check(hello(TOKEN, "1")));
    }

    @Test
    public void wrongTokenWinsOverWrongProtocol() throws Exception {
        // 令牌不对的连接不该知道服务用的是哪个协议版本
        assertEquals(Handshake.Result.UNAUTHORIZED, new Handshake(TOKEN).check(hello("wrong-token-0123456789", 999)));
    }

    @Test
    public void firstMessageMustBeHello() throws Exception {
        Handshake handshake = new Handshake(TOKEN);
        JSONObject status = new JSONObject().put("cmd", "status").put("token", TOKEN).put("protocol", Protocol.VERSION);
        assertEquals(Handshake.Result.BAD_REQUEST, handshake.check(status));
        assertEquals(Handshake.Result.BAD_REQUEST, handshake.check(new JSONObject()));
        assertEquals(Handshake.Result.BAD_REQUEST, handshake.check(null));
    }

    @Test
    public void tokenFormat() {
        assertTrue(Handshake.isValidToken("abcdefghijklmnop"));
        assertTrue(Handshake.isValidToken("A-Z_a-z_0-9_____"));
        assertFalse(Handshake.isValidToken(null));
        assertFalse(Handshake.isValidToken("short"));
        assertFalse(Handshake.isValidToken("abcdefghijklmno"));
        assertFalse(Handshake.isValidToken("has space in token"));
        assertFalse(Handshake.isValidToken("has$dollar$in$token"));
        assertFalse(Handshake.isValidToken(new String(new char[129]).replace('\0', 'a')));
    }

    @Test
    public void refusesToStartWithAWeakToken() {
        try {
            new Handshake("short");
            fail();
        } catch (IllegalArgumentException expected) {
            // 令牌太短
        }
    }
}
