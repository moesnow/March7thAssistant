package org.march7th.deviceservice;

import android.os.Handler;
import android.os.Looper;
import android.os.Process;

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
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** APK 专用的单会话传输。首个连接通过 S1 握手后关闭监听，断线即善后并退出。 */
public final class AppServer {
    public static final String BUSY = "service_busy";
    private static final long START_TIMEOUT_NS = TimeUnit.SECONDS.toNanos(12);

    private final ServerSocket listener;
    private final DeviceService service;
    private final Handshake handshake;
    private final AtomicBoolean stopping = new AtomicBoolean();
    private volatile Socket peer;
    private volatile boolean authenticated;

    private AppServer(ServerSocket listener, DeviceService service, Handshake handshake) {
        this.listener = listener;
        this.service = service;
        this.handshake = handshake;
    }

    /** 在特权进程的 Looper 线程调用。一个进程只服务一轮任务。 */
    public static AppServer start(String apkPath, String token)
            throws IOException, InterruptedException, ReflectiveOperationException {
        Handshake handshake = new Handshake(token);
        if (!Main.acquireInstanceLock(false)) {
            throw new IOException(BUSY);
        }
        ServerSocket listener = new ServerSocket();
        try {
            listener.bind(new InetSocketAddress(InetAddress.getByAddress(new byte[]{127, 0, 0, 1}), 0), 4);
            listener.setSoTimeout(1000);
            // 安装后的 base.apk 同时提供 Cleanup 所需的 DEX。
            DeviceService service = new DeviceService(apkPath);
            AppServer server = new AppServer(listener, service, handshake);
            new Thread(server::serve, "m7a-app-loopback").start();
            new Handler(Looper.myLooper()).postDelayed(() -> {
                if (!server.authenticated) {
                    server.stop();
                }
            }, TimeUnit.NANOSECONDS.toMillis(START_TIMEOUT_NS));
            return server;
        } catch (IOException | RuntimeException | ReflectiveOperationException error) {
            listener.close();
            throw error;
        }
    }

    public int port() {
        return listener.getLocalPort();
    }

    /** Binder 死亡和 Root 管道 EOF 都走这里。中断收发，等待正在处理的命令结束。 */
    public void stop() {
        if (!stopping.compareAndSet(false, true)) {
            return;
        }
        Thread guard = new Thread(() -> {
            try {
                Thread.sleep(8000);
                Runtime.getRuntime().halt(0);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }, "m7a-app-exit-guard");
        guard.setDaemon(true);
        guard.start();
        try {
            listener.close();
        } catch (IOException ignored) {
            // 监听可能已在鉴权后关闭。
        }
        Socket socket = peer;
        if (socket != null) {
            try {
                socket.close();
            } catch (IOException ignored) {
                // 连接可能已断开。
            }
        }
    }

    private void serve() {
        long deadline = System.nanoTime() + START_TIMEOUT_NS;
        try {
            while (!stopping.get() && System.nanoTime() < deadline) {
                try (Socket socket = listener.accept()) {
                    peer = socket;
                    if (stopping.get() || serveConnection(socket)) {
                        break;
                    }
                } catch (SocketTimeoutException ignored) {
                    // 没连上或未完成握手，仍受启动期限限制。
                } catch (IOException error) {
                    if (!stopping.get() && listener.isClosed()) {
                        Logger.i("APK session disconnected: " + Logger.describe(error));
                        break;
                    }
                } finally {
                    peer = null;
                }
            }
        } finally {
            stop();
            service.close();
            System.exit(0);
        }
    }

    private boolean serveConnection(Socket socket) throws IOException {
        socket.setTcpNoDelay(true);
        socket.setSoTimeout(1000);
        InputStream in = new BufferedInputStream(socket.getInputStream(), 8192);
        OutputStream out = new BufferedOutputStream(socket.getOutputStream(), 65536);
        Message hello = MessageCodec.read(in, Protocol.MAX_HANDSHAKE_HEADER_BYTES, 0);
        if (hello == null) {
            return false;
        }
        Handshake.Result result = handshake.check(hello.header);
        if (result == Handshake.Result.PROTOCOL_MISMATCH) {
            JSONObject error = Message.error(hello.header, Protocol.E_PROTOCOL_MISMATCH,
                    "this service speaks protocol " + Protocol.VERSION);
            try {
                error.put("protocol", Protocol.VERSION);
            } catch (JSONException ignored) {
                // 错误响应仍可发送。
            }
            MessageCodec.write(out, new Message(error));
        }
        if (result != Handshake.Result.OK) {
            return false;
        }
        authenticated = true;
        listener.close();
        socket.setSoTimeout(0);
        DeviceService.Session session = service.openSession(event -> { }, false);
        try {
            MessageCodec.write(out, service.handle(session, hello));
            while (!stopping.get() && !service.shutdownRequested()) {
                Message request = MessageCodec.read(in, Protocol.MAX_HEADER_BYTES, Protocol.MAX_REQUEST_PAYLOAD_BYTES);
                if (request == null) {
                    break;
                }
                MessageCodec.write(out, service.handle(session, request));
            }
            return true;
        } finally {
            service.closeSession(session);
        }
    }

    /** 已获授权的 su 入口。令牌走 stdin，关闭管道时结束租约。 */
    @SuppressWarnings("deprecation")
    public static void main(String[] args) {
        if (Process.myUid() != Process.SHELL_UID || args.length != 1) {
            System.exit(2);
        }
        Looper.prepareMainLooper();
        BufferedReader owner = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        try {
            AppServer server = start(args[0], owner.readLine());
            System.out.println("M7A_APP_PORT " + server.port());
            System.out.flush();
            new Thread(() -> {
                try {
                    while (owner.read() != -1) {
                        // 管道保持打开即表示应用进程仍持有租约。
                    }
                } catch (IOException ignored) {
                    // 视为租约结束。
                } finally {
                    server.stop();
                }
            }, "m7a-app-owner").start();
            Looper.loop();
        } catch (Exception error) {
            if (BUSY.equals(error.getMessage())) {
                System.out.println("M7A_APP_BUSY");
            }
            Logger.e("cannot start Root service", error);
            System.exit(3);
        }
    }
}
