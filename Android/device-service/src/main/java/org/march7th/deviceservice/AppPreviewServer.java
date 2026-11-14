package org.march7th.deviceservice;

import android.os.SystemClock;

import org.json.JSONException;
import org.json.JSONObject;
import org.march7th.deviceservice.core.DeviceService;
import org.march7th.deviceservice.core.Logger;
import org.march7th.deviceservice.protocol.Handshake;
import org.march7th.deviceservice.protocol.Message;
import org.march7th.deviceservice.protocol.MessageCodec;
import org.march7th.deviceservice.protocol.Protocol;

import java.io.Closeable;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;

/** 预览独立于任务命令串行连接，只允许经本轮令牌鉴权后读取虚拟屏缩略图。 */
final class AppPreviewServer implements Closeable {
    private final DeviceService service;
    private final Handshake handshake;
    private final ServerSocket listener;
    private Socket peer;
    /** 同一轮切换页面或重连，仍沿用同一个采样上限。只在预览线程上读写。 */
    private long nextSample;

    private AppPreviewServer(DeviceService service, Handshake handshake, ServerSocket listener) {
        this.service = service;
        this.handshake = handshake;
        this.listener = listener;
    }

    static AppPreviewServer open(DeviceService service, Handshake handshake) {
        try {
            ServerSocket listener = new ServerSocket(0, 1, InetAddress.getByAddress(new byte[]{127, 0, 0, 1}));
            AppPreviewServer preview = new AppPreviewServer(service, handshake, listener);
            new Thread(preview::serve, "m7a-app-preview").start();
            return preview;
        } catch (IOException error) {
            Logger.w("cannot start game preview", error);
            return null;
        }
    }

    int port() {
        return listener.getLocalPort();
    }

    private void serve() {
        while (!listener.isClosed()) {
            try (Socket socket = listener.accept()) {
                synchronized (this) {
                    if (listener.isClosed()) return;
                    peer = socket;
                }
                serveConnection(socket);
            } catch (IOException ignored) {
                // 收起预览、连接超时或任务结束时都会断开。
            } catch (RuntimeException | JSONException error) {
                Logger.w("game preview unavailable", error);
            } finally {
                synchronized (this) {
                    peer = null;
                }
            }
        }
    }

    private void serveConnection(Socket socket) throws IOException, JSONException {
        socket.setSoTimeout(2000);
        socket.setTcpNoDelay(true);
        InputStream in = socket.getInputStream();
        OutputStream out = socket.getOutputStream();
        // 对端如果停止读取，内核只需缓冲一张缩略图；关停任务时关闭 socket 会解除写等待。
        socket.setSendBufferSize(Protocol.PREVIEW_MAX_BYTES);
        Message hello = MessageCodec.read(in, Protocol.MAX_HANDSHAKE_HEADER_BYTES, 0);
        if (hello == null || handshake.check(hello.header) != Handshake.Result.OK) {
            return;
        }
        MessageCodec.write(out, new Message(Message.ok(hello.header)));

        byte[] pixels = new byte[Protocol.PREVIEW_MAX_BYTES];
        Message request;
        while ((request = MessageCodec.read(in, Protocol.MAX_HANDSHAKE_HEADER_BYTES, 0)) != null) {
            JSONObject header = request.header;
            if (!"preview_frame".equals(header.optString("cmd"))) {
                return;
            }
            long now = SystemClock.uptimeMillis();
            if (now < nextSample) {
                MessageCodec.write(out, new Message(Message.ok(header)));
                continue;
            }
            nextSample = now + Protocol.PREVIEW_INTERVAL_MS;
            MessageCodec.write(out, service.previewFrame(header, pixels));
        }
    }

    @Override
    public synchronized void close() {
        try {
            listener.close();
        } catch (IOException ignored) {
            // 已关闭。
        }
        if (peer != null) {
            try {
                peer.close();
            } catch (IOException ignored) {
                // 已断开。
            }
        }
    }
}
