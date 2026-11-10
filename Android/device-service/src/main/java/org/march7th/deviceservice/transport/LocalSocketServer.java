package org.march7th.deviceservice.transport;

import android.net.Credentials;
import android.net.LocalServerSocket;
import android.net.LocalSocket;

import org.json.JSONException;
import org.json.JSONObject;
import org.march7th.deviceservice.core.DeviceService;
import org.march7th.deviceservice.core.Logger;
import org.march7th.deviceservice.protocol.Handshake;
import org.march7th.deviceservice.protocol.Message;
import org.march7th.deviceservice.protocol.MessageCodec;
import org.march7th.deviceservice.protocol.Protocol;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 桌面 ADB 模式用的传输：监听抽象命名空间里的 Unix 套接字，桌面端用
 * {@code adb forward tcp:<端口> localabstract:<名字>} 连进来。
 *
 * 这一层只管连接、握手和收发帧，命令全部交给 {@link DeviceService}。
 * 换成别的传输（Binder、带令牌的本机回环）时不需要改核心。
 */
public final class LocalSocketServer {
    private final String name;
    private final Handshake handshake;
    private final DeviceService service;
    private final Set<Integer> allowedUids;
    private final long idleTimeoutMs;
    private final Runnable onStopped;
    private final AtomicInteger connections = new AtomicInteger();
    private final Object idleLock = new Object();
    private LocalServerSocket server;
    private Thread acceptThread;
    private Thread idleThread;
    private long idleSince;
    private volatile boolean stopping;

    /**
     * @param allowedUids   允许连接的对端 uid（adb forward 过来的连接是 shell）
     * @param idleTimeoutMs 没有任何已鉴权连接超过这么久就停止服务；0 表示不限
     * @param onStopped     服务停止时回调一次（空闲超时或收到 shutdown）
     */
    public LocalSocketServer(String name, Handshake handshake, DeviceService service, Set<Integer> allowedUids,
                             long idleTimeoutMs, Runnable onStopped) {
        this.name = name;
        this.handshake = handshake;
        this.service = service;
        this.allowedUids = allowedUids;
        this.idleTimeoutMs = idleTimeoutMs;
        this.onStopped = onStopped;
    }

    /** 绑定并开始接受连接。名字已被占用时抛 IOException。 */
    public void start() throws IOException {
        server = new LocalServerSocket(name);
        idleSince = System.nanoTime();
        acceptThread = new Thread(this::acceptLoop, "m7a-accept");
        acceptThread.start();
        if (idleTimeoutMs > 0) {
            idleThread = new Thread(this::idleLoop, "m7a-idle");
            idleThread.setDaemon(true);
            idleThread.start();
        }
    }

    /** 停止接受连接并触发 onStopped。可以重复调用，只生效一次。 */
    public void stop(String reason) {
        synchronized (idleLock) {
            if (stopping) {
                return;
            }
            stopping = true;
        }
        Logger.i("transport stopping: " + reason);
        // LocalServerSocket.close() 不一定能唤醒阻塞中的 accept()，先自己连一下把它叫醒
        try {
            LocalSocket wake = new LocalSocket();
            wake.connect(new android.net.LocalSocketAddress(name));
            wake.close();
        } catch (IOException ignored) {
            // 已经不在监听
        }
        try {
            server.close();
        } catch (IOException ignored) {
            // 正在关闭
        }
        onStopped.run();
    }

    private void acceptLoop() {
        while (!stopping) {
            LocalSocket socket;
            try {
                socket = server.accept();
            } catch (IOException e) {
                if (!stopping) {
                    Logger.w("accept failed", e);
                    stop("accept failed");
                }
                return;
            }
            if (stopping) {
                closeQuietly(socket);
                return;
            }
            Thread thread = new Thread(() -> serve(socket), "m7a-client");
            thread.setDaemon(true);
            thread.start();
        }
    }

    private void idleLoop() {
        while (!stopping) {
            try {
                Thread.sleep(500);
            } catch (InterruptedException e) {
                return;
            }
            boolean expired;
            synchronized (idleLock) {
                expired = connections.get() == 0 && (System.nanoTime() - idleSince) / 1_000_000L >= idleTimeoutMs;
            }
            if (expired) {
                stop("no client for " + idleTimeoutMs + " ms");
                return;
            }
        }
    }

    private void serve(LocalSocket socket) {
        DeviceService.Session session = null;
        boolean counted = false;
        try {
            Credentials peer = socket.getPeerCredentials();
            if (!allowedUids.contains(peer.getUid())) {
                Logger.w("rejected connection from uid " + peer.getUid());
                return;
            }
            InputStream in = new BufferedInputStream(socket.getInputStream(), 8192);
            OutputStream out = new BufferedOutputStream(socket.getOutputStream(), 65536);
            Object writeLock = new Object();

            socket.setSoTimeout(Protocol.HANDSHAKE_TIMEOUT_MS);
            Message hello = MessageCodec.read(in, Protocol.MAX_HANDSHAKE_HEADER_BYTES, 0);
            if (hello == null) {
                return;
            }
            Handshake.Result result = handshake.check(hello.header);
            if (result == Handshake.Result.PROTOCOL_MISMATCH) {
                // 令牌是对的，告诉对方该用哪个版本，然后断开
                JSONObject error = Message.error(hello.header, Protocol.E_PROTOCOL_MISMATCH,
                        "this service speaks protocol " + Protocol.VERSION);
                try {
                    error.put("protocol", Protocol.VERSION);
                    error.put("version", Protocol.SERVICE_VERSION);
                } catch (JSONException ignored) {
                    // 不影响断开
                }
                MessageCodec.write(out, new Message(error));
                Logger.w("rejected uid " + peer.getUid() + ": protocol mismatch");
                return;
            }
            if (result != Handshake.Result.OK) {
                // 令牌不对：什么都不回，直接断开
                Logger.w("rejected uid " + peer.getUid() + ": " + result);
                return;
            }
            socket.setSoTimeout(0);

            session = service.openSession(event -> {
                synchronized (writeLock) {
                    try {
                        MessageCodec.write(out, new Message(event));
                    } catch (IOException e) {
                        closeQuietly(socket);
                    }
                }
            }, hello.header.optBoolean("events", false));
            synchronized (idleLock) {
                connections.incrementAndGet();
                counted = true;
            }
            Logger.i("session " + session.id + " connected from uid " + peer.getUid());
            Message response = service.handle(session, hello);
            synchronized (writeLock) {
                MessageCodec.write(out, response);
            }

            while (!stopping) {
                Message request = MessageCodec.read(in, Protocol.MAX_HEADER_BYTES, Protocol.MAX_REQUEST_PAYLOAD_BYTES);
                if (request == null) {
                    break;
                }
                response = service.handle(session, request);
                synchronized (writeLock) {
                    MessageCodec.write(out, response);
                }
                if (service.shutdownRequested()) {
                    stop("shutdown command");
                    break;
                }
            }
        } catch (IOException e) {
            if (!stopping) {
                Logger.i("connection closed: " + Logger.describe(e));
            }
        } catch (RuntimeException e) {
            Logger.e("connection handler failed", e);
        } finally {
            if (session != null) {
                service.closeSession(session);
                Logger.i("session " + session.id + " disconnected");
            }
            if (counted) {
                synchronized (idleLock) {
                    if (connections.decrementAndGet() == 0) {
                        idleSince = System.nanoTime();
                    }
                }
            }
            closeQuietly(socket);
        }
    }

    private static void closeQuietly(LocalSocket socket) {
        try {
            socket.shutdownInput();
        } catch (IOException ignored) {
            // 已经关闭
        }
        try {
            socket.shutdownOutput();
        } catch (IOException ignored) {
            // 已经关闭
        }
        try {
            socket.close();
        } catch (IOException ignored) {
            // 已经关闭
        }
    }
}
