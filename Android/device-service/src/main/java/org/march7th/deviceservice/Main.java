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

        if (!acquireInstanceLock(options.replace)) {
            System.err.println("error: another instance is running");
            System.exit(EXIT_ALREADY_RUNNING);
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
     * 用文件锁保证同一时间只有一个实例。锁文件里记着持有者的 pid。
     * 已有实例时默认把它结束掉再接手（它的虚拟屏随进程一起被系统回收）。
     */
    private static boolean acquireInstanceLock(boolean replace) {
        try {
            File file = new File(LOCK_FILE);
            RandomAccessFile handle = new RandomAccessFile(file, "rw");
            FileLock lock = handle.getChannel().tryLock();
            if (lock == null) {
                int owner = readPid(file);
                if (!replace || owner <= 0 || !PROCESS_NAME.equals(processName(owner))) {
                    handle.close();
                    return false;
                }
                Logger.i("replacing running instance pid " + owner);
                Process.killProcess(owner);
                long deadline = System.nanoTime() + 5_000_000_000L;
                while (lock == null && System.nanoTime() < deadline) {
                    Thread.sleep(100);
                    lock = handle.getChannel().tryLock();
                }
                if (lock == null) {
                    handle.close();
                    return false;
                }
            }
            handle.setLength(0);
            handle.write((Process.myPid() + "\n").getBytes(StandardCharsets.UTF_8));
            instanceLock = lock;
            return true;
        } catch (IOException e) {
            // 锁文件不可写（比如上一次是 root 建的）时不拦着启动，套接字名本身也是互斥的
            Logger.w("instance lock unavailable", e);
            return true;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }

    private static int readPid(File file) {
        try (FileInputStream in = new FileInputStream(file)) {
            byte[] buffer = new byte[32];
            int n = in.read(buffer);
            return n <= 0 ? -1 : Integer.parseInt(new String(buffer, 0, n, StandardCharsets.UTF_8).trim());
        } catch (IOException | NumberFormatException e) {
            return -1;
        }
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
