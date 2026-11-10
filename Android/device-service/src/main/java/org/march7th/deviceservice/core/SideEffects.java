package org.march7th.deviceservice.core;

import org.march7th.deviceservice.Cleanup;
import org.march7th.deviceservice.protocol.Protocol;

import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
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

    private boolean panelOff;
    private Thread keepAwake;
    /** 包名到静音前的 AppOps 模式。 */
    private final Map<String, String> muted = new LinkedHashMap<>();
    private Process cleanup;
    private OutputStream cleanupInput;

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
        if (on != panelOff) {
            return;
        }
        if (!on) {
            // 先让子进程记下来，再动面板，这样任何时候被杀都能恢复
            tellCleanup("panel 1");
        }
        try {
            SystemApis.setPanelPower(on);
        } catch (ReflectiveOperationException | RuntimeException e) {
            if (!on) {
                tellCleanup("panel 0");
            }
            throw new CommandException(Protocol.E_UNSUPPORTED, "cannot switch the panel: " + Logger.describe(e));
        }
        panelOff = !on;
        if (panelOff) {
            keepAwake = new Thread(this::keepAwakeLoop, "m7a-keep-awake");
            keepAwake.setDaemon(true);
            keepAwake.start();
        } else {
            tellCleanup("panel 0");
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
        try {
            if (on) {
                String original = muted.get(packageName);
                if (original == null) {
                    original = audioMode(packageName);
                    if ("ignore".equals(original)) {
                        // 本来就是静音，不归我们恢复
                        return original;
                    }
                    tellCleanup("mute " + packageName + " " + original);
                    muted.put(packageName, original);
                }
                setAudioMode(packageName, "ignore");
                String now = audioMode(packageName);
                if (!"ignore".equals(now)) {
                    restoreAudio(packageName);
                    throw new CommandException(Protocol.E_UNSUPPORTED, "PLAY_AUDIO stayed at " + now);
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
        tellCleanup("unmute " + packageName);
        Logger.i("PLAY_AUDIO of " + packageName + " restored to " + original);
    }

    /** 恢复全部改动，服务退出时调用。 */
    synchronized void restoreAll() {
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
        if (cleanupInput != null && muted.isEmpty() && !panelOff) {
            try {
                cleanupInput.close();
            } catch (IOException ignored) {
                // 子进程已经退出
            }
            cleanupInput = null;
            cleanup = null;
        }
    }

    private void tellCleanup(String line) {
        try {
            if (cleanup == null) {
                startCleanup();
            }
            cleanupInput.write((line + "\n").getBytes(StandardCharsets.UTF_8));
            cleanupInput.flush();
        } catch (IOException e) {
            Logger.w("cleanup process unavailable; a hard kill will not restore the device", e);
            cleanup = null;
            cleanupInput = null;
        }
    }

    private void startCleanup() throws IOException {
        String classpath = System.getenv("CLASSPATH");
        if (classpath == null) {
            throw new IOException("CLASSPATH is not set");
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
        builder.redirectErrorStream(true);
        builder.redirectOutput(new File("/dev/null"));
        cleanup = builder.start();
        cleanupInput = cleanup.getOutputStream();
    }
}
