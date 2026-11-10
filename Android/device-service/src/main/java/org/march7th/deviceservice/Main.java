package org.march7th.deviceservice;

import android.os.Looper;
import android.os.Process;

import org.march7th.deviceservice.core.DeviceService;
import org.march7th.deviceservice.core.Logger;
import org.march7th.deviceservice.protocol.Handshake;
import org.march7th.deviceservice.protocol.Protocol;
import org.march7th.deviceservice.transport.LocalSocketServer;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.lang.reflect.Method;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;

/**
 * 桌面 ADB 模式的入口：
 *
 * <pre>
 * CLASSPATH=/data/local/tmp/m7a-device-service.jar app_process / org.march7th.deviceservice.Main \
 *     --token &lt;随机令牌&gt; --socket &lt;名字&gt;
 * </pre>
 *
 * 这里只解析参数、保证单实例、把传输层和核心接起来。命令的实现都在 {@link DeviceService}。
 */
public final class Main {
    static final String PROCESS_NAME = "m7a-device-service";
    private static final String LOCK_FILE = "/data/local/tmp/m7a-device-service.lock";
    private static final long HANDOFF_TIMEOUT_NS = 5_000_000_000L;

    private static final int EXIT_USAGE = 2;
    private static final int EXIT_ALREADY_RUNNING = 3;
    private static final int EXIT_BIND_FAILED = 4;
    private static final int EXIT_INIT_FAILED = 5;

    // 进程存活期间一直持有，退出时由系统释放
    @SuppressWarnings("unused")
    private static FileLock instanceLock;

    private Main() {
    }

    private static final class Options {
        String token;
        String socket = Protocol.DEFAULT_SOCKET_NAME;
        long idleTimeoutMs = 30_000;
        boolean replace = true;
        final Set<Integer> allowedUids = new HashSet<>();
    }

    @SuppressWarnings("deprecation") // prepareMainLooper：app_process 进程没有别人替我们准备主 Looper
    public static void main(String[] args) {
        Options options;
        try {
            options = parse(args);
        } catch (IllegalArgumentException e) {
            System.err.println("error: " + e.getMessage());
            System.err.println(usage());
            System.exit(EXIT_USAGE);
            return;
        }
        if (options == null) {
            return;
        }
        // 改名的同时会清空 /proc/<pid>/cmdline 里的参数，令牌不再留在进程列表里
        setProcessName();
        Looper.prepareMainLooper();
        Thread.setDefaultUncaughtExceptionHandler((thread, error) -> {
            Logger.e("uncaught exception in " + thread.getName(), error);
            Runtime.getRuntime().halt(1);
        });

        try {
            if (!acquireInstanceLock(options.replace)) {
                System.err.println("error: another instance or its cleanup is still running");
                System.exit(EXIT_ALREADY_RUNNING);
                return;
            }
        } catch (IOException e) {
            Logger.e("cannot verify instance handoff", e);
            System.exit(EXIT_INIT_FAILED);
            return;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            System.exit(EXIT_ALREADY_RUNNING);
            return;
        }

        DeviceService service;
        try {
            service = new DeviceService();
        } catch (ReflectiveOperationException | RuntimeException e) {
            Logger.e("cannot initialise the service", e);
            System.exit(EXIT_INIT_FAILED);
            return;
        }
        Runtime.getRuntime().addShutdownHook(new Thread(service::close, "m7a-shutdown-hook"));

        options.allowedUids.add(0);
        options.allowedUids.add(Process.SHELL_UID);
        options.allowedUids.add(Process.myUid());
        LocalSocketServer server = new LocalSocketServer(options.socket, new Handshake(options.token), service,
                options.allowedUids, options.idleTimeoutMs, () -> {
            Thread exit = new Thread(() -> {
                // 清理卡住时也要保证进程退出：进程一消失，系统会回收虚拟屏
                Thread guard = new Thread(() -> {
                    try {
                        Thread.sleep(8000);
                    } catch (InterruptedException e) {
                        return;
                    }
                    Runtime.getRuntime().halt(0);
                }, "m7a-exit-guard");
                guard.setDaemon(true);
                guard.start();
                service.close();
                System.exit(0);
            }, "m7a-exit");
            exit.start();
        });
        try {
            server.start();
        } catch (IOException e) {
            Logger.e("cannot listen on localabstract:" + options.socket, e);
            System.exit(EXIT_BIND_FAILED);
            return;
        }
        Logger.i("listening on localabstract:" + options.socket + " idle-timeout=" + options.idleTimeoutMs + "ms");
        // 启动方靠这一行判断服务已经就绪
        System.out.println("M7A_DEVICE_SERVICE_READY protocol=" + Protocol.VERSION + " version=" + Protocol.SERVICE_VERSION
                + " socket=" + options.socket + " pid=" + Process.myPid());
        System.out.flush();
        Looper.loop();
    }

    private static Options parse(String[] args) {
        Options options = new Options();
        for (int i = 0; i < args.length; i++) {
            String arg = args[i];
            switch (arg) {
                case "--help":
                    System.out.println(usage());
                    return null;
                case "--version":
                    System.out.println(Protocol.SERVICE_VERSION + " protocol=" + Protocol.VERSION);
                    return null;
                case "--no-replace":
                    options.replace = false;
                    break;
                case "--token":
                    options.token = value(args, ++i, arg);
                    break;
                case "--socket":
                    options.socket = value(args, ++i, arg);
                    break;
                case "--idle-timeout":
                    options.idleTimeoutMs = Math.round(Double.parseDouble(value(args, ++i, arg)) * 1000);
                    break;
                case "--allow-uid":
                    options.allowedUids.add(Integer.parseInt(value(args, ++i, arg)));
                    break;
                default:
                    throw new IllegalArgumentException("unknown option " + arg);
            }
        }
        if (!Handshake.isValidToken(options.token)) {
            throw new IllegalArgumentException("--token must be 16-128 characters of [A-Za-z0-9_-]");
        }
        if (!options.socket.matches("[A-Za-z0-9_.-]{1,64}")) {
            throw new IllegalArgumentException("--socket must be 1-64 characters of [A-Za-z0-9_.-]");
        }
        if (options.idleTimeoutMs < 0) {
            throw new IllegalArgumentException("--idle-timeout must not be negative");
        }
        return options;
    }

    private static String value(String[] args, int index, String name) {
        if (index >= args.length) {
            throw new IllegalArgumentException(name + " needs a value");
        }
        return args[index];
    }

    private static String usage() {
        return "usage: app_process / " + Main.class.getName() + " --token <token> [--socket <name>]\n"
                + "           [--idle-timeout <seconds>] [--allow-uid <uid>]... [--no-replace]\n"
                + "  --token         shared secret, 16-128 characters of [A-Za-z0-9_-]\n"
                + "  --socket        abstract socket name (default " + Protocol.DEFAULT_SOCKET_NAME + ")\n"
                + "  --idle-timeout  exit after this many seconds without a client; 0 = never (default 30)\n"
                + "  --allow-uid     extra peer uid allowed to connect (root, shell and own uid always are)\n"
                + "  --no-replace    exit with code 3 instead of replacing a running instance";
    }

    private static void setProcessName() {
        try {
            Method setArgV0 = Process.class.getMethod("setArgV0", String.class);
            setArgV0.invoke(null, PROCESS_NAME);
        } catch (ReflectiveOperationException | RuntimeException e) {
            System.err.println("warning: cannot rename the process: " + e);
        }
    }

    /**
     * 实例锁阻止多个主进程并发工作。主进程退出后，还要等持有善后锁的子进程完成在途写入和恢复。
     */
    private static boolean acquireInstanceLock(boolean replace) throws IOException, InterruptedException {
        RandomAccessFile handle = new RandomAccessFile(LOCK_FILE, "rw");
        boolean retained = false;
        try {
            FileLock lock = handle.getChannel().tryLock();
            String[] owner = readOwner(handle);
            boolean guarded = owner.length == 2 && Cleanup.HANDOFF_VERSION.equals(owner[1]);
            if (lock == null) {
                int pid = readPid(owner[0]);
                if (!replace || pid <= 0 || !PROCESS_NAME.equals(processName(pid))) {
                    return false;
                }
                if (!guarded) {
                    Logger.w("previous instance does not support safe replacement; shut it down first");
                    return false;
                }
                Logger.i("replacing running instance pid " + pid);
                Process.killProcess(pid);
                long deadline = System.nanoTime() + HANDOFF_TIMEOUT_NS;
                while (lock == null && CleanupHandoff.pauseUntil(deadline)) {
                    lock = handle.getChannel().tryLock();
                }
                if (lock == null) {
                    return false;
                }
            }
            long deadline = System.nanoTime() + (replace ? HANDOFF_TIMEOUT_NS : 0);
            // 老版本退出后也可能留有善后进程。只有旧锁记录才需要检查这些没有持锁的进程。
            if (!guarded && readPid(owner[0]) > 0) {
                while (legacyCleanupRunning()) {
                    if (!CleanupHandoff.pauseUntil(deadline)) {
                        Logger.w("previous legacy cleanup is still running");
                        return false;
                    }
                }
            }
            if (!CleanupHandoff.awaitIdle(CleanupHandoff.LOCK_PATH, deadline)) {
                Logger.w("previous cleanup is still running");
                return false;
            }
            handle.setLength(0);
            handle.seek(0);
            handle.write((Process.myPid() + "\n" + Cleanup.HANDOFF_VERSION + "\n").getBytes(StandardCharsets.UTF_8));
            instanceLock = lock;
            retained = true;
            return true;
        } finally {
            if (!retained) {
                handle.close();
            }
        }
    }

    private static String[] readOwner(RandomAccessFile handle) throws IOException {
        byte[] buffer = new byte[64];
        handle.seek(0);
        int n = handle.read(buffer);
        return n <= 0 ? new String[] {""} : new String(buffer, 0, n, StandardCharsets.UTF_8).trim().split("\n");
    }

    private static int readPid(String value) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    private static boolean legacyCleanupRunning() throws IOException {
        File[] processes = new File("/proc").listFiles(file -> file.getName().matches("[0-9]+"));
        if (processes == null) {
            throw new IOException("cannot list processes to check legacy cleanup");
        }
        for (File process : processes) {
            try (FileInputStream in = new FileInputStream(new File(process, "cmdline"))) {
                byte[] buffer = new byte[1024];
                int n = in.read(buffer);
                if (n <= 0) {
                    continue;
                }
                String[] arguments = new String(buffer, 0, n, StandardCharsets.UTF_8).split("\u0000");
                for (int i = 1; i < arguments.length; i++) {
                    if (Cleanup.class.getName().equals(arguments[i])) {
                        if (i + 1 == arguments.length || !Cleanup.HANDOFF_VERSION.equals(arguments[i + 1])) {
                            return true;
                        }
                        break;
                    }
                }
            } catch (IOException ignored) {
                // 进程可能已退出，也可能属于其他 uid。
            }
        }
        return false;
    }

    private static String processName(int pid) {
        try (FileInputStream in = new FileInputStream("/proc/" + pid + "/cmdline")) {
            byte[] buffer = new byte[256];
            int n = in.read(buffer);
            int end = 0;
            while (end < n && buffer[end] != 0) {
                end++;
            }
            return new String(buffer, 0, end, StandardCharsets.UTF_8);
        } catch (IOException e) {
            return null;
        }
    }
}
