package org.march7th.deviceservice.core;

import org.march7th.deviceservice.Cleanup;
import org.march7th.deviceservice.protocol.Protocol;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * 管理实体面板的电源状态和游戏静音。
 *
 * 服务正常退出时在这里恢复。进程被强杀时没有机会执行任何代码，所以第一次产生改动时会另起一个
 * {@link Cleanup} 子进程，父进程一消失它就把记下来的改动恢复掉。
 */
final class SideEffects {
    private static final long KEEP_AWAKE_INTERVAL_MS = 5000;
    // PowerManager.USER_ACTIVITY_FLAG_NO_CHANGE_LIGHTS 是隐藏常量。
    private static final int USER_ACTIVITY_FLAG_NO_CHANGE_LIGHTS = 1;
    private static final long CLEANUP_ACK_TIMEOUT_MS = 2000;
    private static final long CLEANUP_MUTE_TIMEOUT_MS = 5000;

    private final String cleanupJarPath;
    private boolean panelOff;
    private boolean panelRestorePending;
    private boolean keepAwakeRequested;
    private Thread keepAwake;
    private final Set<String> muted = new LinkedHashSet<>();
    private CleanupChannel cleanup;
    private boolean cleanupUnavailable;
    private boolean closed;

    SideEffects(String cleanupJarPath) {
        this.cleanupJarPath = cleanupJarPath;
    }

    synchronized boolean panelOff() {
        return panelOff;
    }

    synchronized List<String> mutedPackages() {
        return new ArrayList<>(muted);
    }

    /**
     * 开关实体面板。关闭期间系统保持唤醒：每隔几秒重置一次息屏计时，
     * 因为系统一旦休眠，虚拟屏里的游戏就收不到触摸了。
     */
    synchronized void setPanel(boolean on) throws CommandException {
        requireOpen();
        if (on ? !panelRestorePending : panelOff) {
            return;
        }
        if (!on) {
            // 先让子进程记下来，再动面板，这样任何时候被杀都能恢复
            registerCleanup("panel 1");
            panelRestorePending = true;
        }
        try {
            SystemApis.setPanelPower(on);
        } catch (ReflectiveOperationException | RuntimeException e) {
            if (!on) {
                // 有多个物理面板时，系统调用可能在部分面板已经关掉之后失败。
                try {
                    setPanel(true);
                } catch (CommandException restoreError) {
                    Logger.w("cannot roll back panel power: " + restoreError.getMessage());
                }
            }
            throw new CommandException(Protocol.E_UNSUPPORTED, "cannot switch the panel: " + Logger.describe(e));
        }
        panelOff = !on;
        if (on) {
            panelRestorePending = false;
            forgetCleanup("panel 0");
        }
        updateKeepAwake();
        Logger.i("panel power " + (on ? "restored" : "off, keeping the system awake"));
    }

    synchronized void setKeepAwake(boolean on) throws CommandException {
        requireOpen();
        keepAwakeRequested = on;
        updateKeepAwake();
    }

    private void updateKeepAwake() {
        if (panelOff || keepAwakeRequested) {
            if (keepAwake == null) {
                keepAwake = new Thread(this::keepAwakeLoop, "m7a-keep-awake");
                keepAwake.setDaemon(true);
                keepAwake.start();
            }
        } else {
            stopKeepAwake();
        }
    }

    private void stopKeepAwake() {
        if (keepAwake != null) {
            keepAwake.interrupt();
            keepAwake = null;
        }
    }

    static int userActivityFlags(boolean panelOff) {
        return panelOff ? 0 : USER_ACTIVITY_FLAG_NO_CHANGE_LIGHTS;
    }

    private void keepAwakeLoop() {
        Thread worker = Thread.currentThread();
        boolean warned = false;
        while (true) {
            synchronized (this) {
                if (worker != keepAwake) {
                    return;
                }
                try {
                    SystemApis.userActivity(userActivityFlags(panelOff));
                } catch (ReflectiveOperationException | RuntimeException e) {
                    if (!warned) {
                        warned = true;
                        Logger.w("cannot reset the screen-off timer", e);
                    }
                }
            }
            try {
                Thread.sleep(KEEP_AWAKE_INTERVAL_MS);
            } catch (InterruptedException e) {
                return;
            }
        }
    }

    /** 按包名静音或恢复，返回操作前的 AppOps 模式。 */
    synchronized String mute(String packageName, boolean on) throws CommandException {
        requireOpen();
        try {
            String original = exchangeCleanup((on ? "mute " : "restore_audio ") + packageName, CLEANUP_MUTE_TIMEOUT_MS);
            if (on && !"ignore".equals(original)) {
                muted.add(packageName);
            } else {
                muted.remove(packageName);
            }
            return original;
        } catch (IOException | RuntimeException error) {
            markCleanupUnavailable(error);
            // 在途音频操作由同一个子进程做完，再按 EOF 恢复。
            closeCleanupInput();
            throw new CommandException(Protocol.E_CLEANUP_UNAVAILABLE, error.getMessage());
        }
    }

    synchronized void restoreAll() {
        if (closed) {
            return;
        }
        try {
            setPanel(true);
        } catch (CommandException error) {
            Logger.w("cannot restore the panel: " + error.getMessage());
        } finally {
            closed = true;
            stopKeepAwake();
            closeCleanupInput();
            if (cleanup != null) {
                try {
                    cleanup.process.waitFor(CLEANUP_MUTE_TIMEOUT_MS, TimeUnit.MILLISECONDS);
                } catch (InterruptedException error) {
                    Thread.currentThread().interrupt();
                }
            }
            cleanup = null;
        }
    }

    private void closeCleanupInput() {
        if (cleanup != null) {
            cleanup.close();
        }
    }

    private void requireOpen() throws CommandException {
        if (closed) {
            throw new CommandException(Protocol.E_INTERNAL, "service is closing");
        }
    }

    private void registerCleanup(String line) throws CommandException {
        try {
            exchangeCleanup(line, CLEANUP_ACK_TIMEOUT_MS);
        } catch (IOException | RuntimeException e) {
            markCleanupUnavailable(e);
            throw new CommandException(Protocol.E_CLEANUP_UNAVAILABLE, "cannot register cleanup: " + e.getMessage());
        }
    }

    /** 设备已经恢复，撤销子进程里的记录失败不影响恢复结果。 */
    private void forgetCleanup(String line) {
        if (cleanup == null || cleanupUnavailable) {
            return;
        }
        try {
            exchangeCleanup(line, CLEANUP_ACK_TIMEOUT_MS);
        } catch (CommandException | IOException | RuntimeException e) {
            markCleanupUnavailable(e);
        }
    }

    private void markCleanupUnavailable(Exception error) {
        if (!cleanupUnavailable) {
            Logger.w("cleanup process unavailable", error);
            cleanupUnavailable = true;
        }
    }

    private String exchangeCleanup(String line, long timeoutMs) throws IOException, CommandException {
        if (cleanupUnavailable) {
            throw new IOException("cleanup channel is unavailable");
        }
        if (cleanup == null) {
            cleanup = startCleanup();
        }
        return cleanup.exchange(line, timeoutMs);
    }

    private CleanupChannel startCleanup() throws IOException {
        String classpath = cleanupJarPath == null ? System.getenv("CLASSPATH") : cleanupJarPath;
        if (classpath == null || classpath.trim().isEmpty()) {
            throw new IOException("no cleanup jar path");
        }
        List<String> command = new ArrayList<>();
        // 新开一个会话，adb 会话结束时的 SIGHUP 不会把它一起带走
        if (new File("/system/bin/setsid").exists()) {
            command.add("/system/bin/setsid");
        }
        command.add("app_process");
        command.add("/");
        command.add(Cleanup.class.getName());
        command.add(Cleanup.HANDOFF_VERSION);
        ProcessBuilder builder = new ProcessBuilder(command);
        builder.environment().put("CLASSPATH", classpath);
        builder.redirectError(new File("/dev/null"));
        return new CleanupChannel(builder.start());
    }

    private static final class CleanupChannel implements AutoCloseable {
        private final Process process;
        private final OutputStream input;
        private final BufferedReader output;
        private boolean ready;

        CleanupChannel(Process process) {
            this.process = process;
            input = process.getOutputStream();
            output = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8));
        }

        String exchange(String line, long timeoutMs) throws IOException, CommandException {
            if (line.length() > 1024) {
                throw new IOException("cleanup record is too long");
            }
            boolean waitForReady = !ready;
            FutureTask<String> exchange = new FutureTask<>(() -> {
                // 持锁前不发送任何恢复记录。迟启动的孤儿子进程只会读到 EOF。
                if (waitForReady && !Cleanup.READY.equals(output.readLine())) {
                    throw new IOException("cleanup did not acquire the handoff lock");
                }
                input.write((line + "\n").getBytes(StandardCharsets.UTF_8));
                input.flush();
                return output.readLine();
            });
            Thread worker = new Thread(exchange, "m7a-cleanup-ack");
            worker.setDaemon(true);
            worker.start();
            try {
                String reply = exchange.get(timeoutMs, TimeUnit.MILLISECONDS);
                String success = Cleanup.OK + line;
                String failure = Cleanup.FAILED + line + " ";
                if (success.equals(reply)) {
                    ready = true;
                    return "";
                }
                if (reply != null && reply.startsWith(success + " ")) {
                    ready = true;
                    return reply.substring(success.length() + 1);
                }
                if (reply != null && reply.startsWith(failure)) {
                    ready = true;
                    throw new CommandException(Protocol.E_UNSUPPORTED, reply.substring(failure.length()));
                }
                throw new IOException("cleanup did not acknowledge the record");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IOException("cleanup acknowledgement interrupted", e);
            } catch (ExecutionException | TimeoutException e) {
                throw new IOException("cleanup acknowledgement failed", e);
            }
        }

        @Override
        public void close() {
            try {
                input.close();
            } catch (IOException ignored) {
                // 子进程已经退出
            }
        }
    }
}
