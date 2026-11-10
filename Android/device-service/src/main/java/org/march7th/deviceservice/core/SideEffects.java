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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 会留在系统里的两处改动：实体面板的电源状态，以及游戏的 PLAY_AUDIO AppOps。
 *
 * 服务正常退出时在这里恢复。进程被强杀时没有机会执行任何代码，所以第一次产生改动时会另起一个
 * {@link Cleanup} 子进程，父进程一消失它就把记下来的改动恢复掉。
 */
final class SideEffects {
    private static final String OP = "PLAY_AUDIO";
    private static final Pattern MODE = Pattern.compile(OP + ":\\s*(\\w+)");
    private static final long COMMAND_TIMEOUT_MS = 5000;
    private static final long KEEP_AWAKE_INTERVAL_MS = 5000;
    private static final long CLEANUP_ACK_TIMEOUT_MS = 2000;

    private final String cleanupJarPath;
    private boolean panelOff;
    private boolean panelRestorePending;
    private Thread keepAwake;
    /** 包名到静音前的 AppOps 模式。 */
    private final Map<String, String> muted = new LinkedHashMap<>();
    private Process cleanup;
    private OutputStream cleanupInput;
    private BufferedReader cleanupOutput;
    private boolean cleanupUnavailable;
    private boolean closed;

    SideEffects(String cleanupJarPath) {
        this.cleanupJarPath = cleanupJarPath;
    }

    synchronized boolean panelOff() {
        return panelOff;
    }

    synchronized List<String> mutedPackages() {
        return new ArrayList<>(muted.keySet());
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
        if (panelOff) {
            keepAwake = new Thread(this::keepAwakeLoop, "m7a-keep-awake");
            keepAwake.setDaemon(true);
            keepAwake.start();
        } else {
            panelRestorePending = false;
            forgetCleanup("panel 0");
            if (keepAwake != null) {
                keepAwake.interrupt();
                keepAwake = null;
            }
        }
        Logger.i("panel power " + (on ? "restored" : "off, keeping the system awake"));
    }

    private void keepAwakeLoop() {
        boolean warned = false;
        while (!Thread.currentThread().isInterrupted()) {
            try {
                SystemApis.userActivity();
            } catch (ReflectiveOperationException | RuntimeException e) {
                if (!warned) {
                    warned = true;
                    Logger.w("cannot reset the screen-off timer", e);
                }
            }
            try {
                Thread.sleep(KEEP_AWAKE_INTERVAL_MS);
            } catch (InterruptedException e) {
                return;
            }
        }
    }

    /** 读某个包当前的 PLAY_AUDIO 模式，没有单独设置过时返回 default。 */
    static String audioMode(String packageName) throws IOException, InterruptedException {
        Shell.Result result = Shell.run(COMMAND_TIMEOUT_MS, "cmd", "appops", "get", packageName, OP);
        if (!result.ok()) {
            throw new IOException("appops get failed: " + result);
        }
        Matcher matcher = MODE.matcher(result.stdout);
        return matcher.find() ? matcher.group(1) : "default";
    }

    static void setAudioMode(String packageName, String mode) throws IOException, InterruptedException {
        Shell.Result result = Shell.run(COMMAND_TIMEOUT_MS, "cmd", "appops", "set", packageName, OP, mode);
        if (!result.ok() || !result.stderr.trim().isEmpty()) {
            throw new IOException("appops set failed: " + result);
        }
    }

    /**
     * 按包名静音或恢复。
     *
     * @return 静音前的模式
     */
    synchronized String mute(String packageName, boolean on) throws CommandException, InterruptedException {
        requireOpen();
        try {
            if (on) {
                String original = muted.get(packageName);
                if (original == null) {
                    original = audioMode(packageName);
                    if ("ignore".equals(original)) {
                        // 本来就是静音，不归我们恢复
                        return original;
                    }
                }
                registerCleanup("mute " + packageName + " " + original);
                muted.put(packageName, original);
                try {
                    setAudioMode(packageName, "ignore");
                    String now = audioMode(packageName);
                    if (!"ignore".equals(now)) {
                        throw new IOException("PLAY_AUDIO stayed at " + now);
                    }
                } catch (IOException | InterruptedException error) {
                    try {
                        restoreAudio(packageName);
                    } catch (IOException | InterruptedException restoreError) {
                        if (restoreError instanceof InterruptedException) {
                            Thread.currentThread().interrupt();
                        }
                        Logger.w("cannot roll back PLAY_AUDIO of " + packageName, restoreError);
                    }
                    throw error;
                }
                return original;
            }
            String original = muted.get(packageName);
            if (original != null) {
                restoreAudio(packageName);
            }
            return original == null ? audioMode(packageName) : original;
        } catch (IOException e) {
            throw new CommandException(Protocol.E_UNSUPPORTED, e.getMessage());
        }
    }

    private void restoreAudio(String packageName) throws IOException, InterruptedException {
        String original = muted.get(packageName);
        setAudioMode(packageName, original);
        muted.remove(packageName);
        forgetCleanup("unmute " + packageName);
        Logger.i("PLAY_AUDIO of " + packageName + " restored to " + original);
    }

    /** 恢复全部改动，服务退出时调用。 */
    synchronized void restoreAll() {
        if (closed) {
            return;
        }
        try {
            setPanel(true);
        } catch (CommandException e) {
            Logger.w("cannot restore the panel: " + e.getMessage());
        }
        for (String packageName : new ArrayList<>(muted.keySet())) {
            try {
                restoreAudio(packageName);
            } catch (IOException e) {
                Logger.w("cannot restore PLAY_AUDIO of " + packageName, e);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
        closed = true;
        if (cleanupInput != null) {
            // UserService 关闭核心后进程可能还活着，主动断管，让子进程兜底恢复失败的记录。
            try {
                cleanupInput.close();
            } catch (IOException ignored) {
                // 子进程已经退出
            }
            cleanupInput = null;
            cleanupOutput = null;
            cleanup = null;
        }
    }

    private void requireOpen() throws CommandException {
        if (closed) {
            throw new CommandException(Protocol.E_INTERNAL, "service is closing");
        }
    }

    private void registerCleanup(String line) throws CommandException {
        try {
            exchangeCleanup(line);
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
            exchangeCleanup(line);
        } catch (IOException | RuntimeException e) {
            markCleanupUnavailable(e);
        }
    }

    private void markCleanupUnavailable(Exception error) {
        // 保留旧进程和管道。它可能仍持有已登记的记录，不能杀掉或另起进程覆盖它。
        if (!cleanupUnavailable) {
            Logger.w("cleanup process unavailable", error);
            cleanupUnavailable = true;
        }
    }

    private void exchangeCleanup(String line) throws IOException {
        if (cleanupUnavailable) {
            throw new IOException("cleanup channel is unavailable");
        }
        if (line.length() > 1024) {
            throw new IOException("cleanup record is too long");
        }
        if (cleanup == null) {
            startCleanup();
        }
        OutputStream input = cleanupInput;
        BufferedReader output = cleanupOutput;
        FutureTask<String> exchange = new FutureTask<>(() -> {
            input.write((line + "\n").getBytes(StandardCharsets.UTF_8));
            input.flush();
            return output.readLine();
        });
        Thread worker = new Thread(exchange, "m7a-cleanup-ack");
        worker.setDaemon(true);
        worker.start();
        try {
            String reply = exchange.get(CLEANUP_ACK_TIMEOUT_MS, TimeUnit.MILLISECONDS);
            if (!("M7A_CLEANUP_OK " + line).equals(reply) || !cleanup.isAlive()) {
                throw new IOException("cleanup did not acknowledge the record");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("cleanup acknowledgement interrupted", e);
        } catch (ExecutionException | TimeoutException e) {
            throw new IOException("cleanup acknowledgement failed", e);
        }
    }

    private void startCleanup() throws IOException {
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
        ProcessBuilder builder = new ProcessBuilder(command);
        builder.environment().put("CLASSPATH", classpath);
        builder.redirectError(new File("/dev/null"));
        cleanup = builder.start();
        cleanupInput = cleanup.getOutputStream();
        cleanupOutput = new BufferedReader(new InputStreamReader(cleanup.getInputStream(), StandardCharsets.UTF_8));
    }
}
