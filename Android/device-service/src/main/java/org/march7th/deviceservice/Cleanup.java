package org.march7th.deviceservice;

import android.util.Log;

import org.march7th.deviceservice.core.AudioAppOps;
import org.march7th.deviceservice.protocol.Protocol;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.function.BiConsumer;

/**
 * 善后子进程，做法参照 scrcpy（Apache-2.0）的 CleanUp。
 *
 * 服务从标准输入告诉它目前有哪些改动需要恢复。标准输入一断开（服务退出或被强杀），它就把还没恢复的
 * 改动恢复掉然后退出。它不依赖服务进程里的任何状态。
 *
 * <pre>
 * panel 1               面板即将关闭，需要恢复
 * panel 0               面板已恢复
 * mute 包名 原模式       登记原模式
 * apply_mute 包名       串行执行静音，写入完成后应答
 * restore_audio 包名 原模式  恢复并撤销登记，也可由独立的备用恢复进程执行
 * unmute 包名           已恢复，撤销登记
 * </pre>
 * 每条成功处理的命令回一行 M7A_CLEANUP_OK 和原记录。AppOps 写入失败回 M7A_CLEANUP_FAILED。
 */
public final class Cleanup {
    public static final String HANDOFF_VERSION = "cleanup-lock-v1";
    public static final String READY = "M7A_CLEANUP_READY";

    interface AudioSetter {
        void setMode(String packageName, String mode) throws IOException, InterruptedException;
    }

    private Cleanup() {
    }

    public static void main(String[] args) {
        try {
            CleanupHandoff.runWorker(CleanupHandoff.LOCK_PATH, () -> {
                BufferedReader commands = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
                PrintWriter replies = new PrintWriter(System.out, true);
                replies.println(READY);
                if (!replies.checkError()) {
                    run(commands, replies, Cleanup::restorePanel, (packageName, mode) -> {
                        AudioAppOps.setModeAndWait(packageName, mode);
                        Log.i(Protocol.LOG_TAG, "cleanup: PLAY_AUDIO of " + packageName + " set to " + mode);
                    }, (message, error) -> Log.e(Protocol.LOG_TAG, message, error));
                }
            });
        } catch (IOException e) {
            Log.e(Protocol.LOG_TAG, "cleanup: cannot hold handoff lock", e);
            System.exit(1);
            return;
        }
        System.exit(0);
    }

    static void run(BufferedReader commands, PrintWriter replies, Runnable restorePanel,
                    AudioSetter audio, BiConsumer<String, Exception> reportFailure) {
        boolean panelOff = false;
        Map<String, String> muted = new LinkedHashMap<>();
        try (BufferedReader reader = commands) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] parts = line.trim().split(" ");
                String reply = "M7A_CLEANUP_OK " + line;
                if (parts.length == 2 && "panel".equals(parts[0]) && ("0".equals(parts[1]) || "1".equals(parts[1]))) {
                    panelOff = "1".equals(parts[1]);
                } else if (parts.length == 3 && "mute".equals(parts[0])) {
                    muted.put(parts[1], parts[2]);
                } else if (parts.length == 2 && "apply_mute".equals(parts[0]) && muted.containsKey(parts[1])) {
                    if (!writeAudio(audio, reportFailure, parts[1], "ignore")) {
                        reply = "M7A_CLEANUP_FAILED " + line;
                    }
                } else if (parts.length == 3 && "restore_audio".equals(parts[0])) {
                    if (writeAudio(audio, reportFailure, parts[1], parts[2])) {
                        muted.remove(parts[1]);
                    } else {
                        reply = "M7A_CLEANUP_FAILED " + line;
                    }
                } else if (parts.length == 2 && "unmute".equals(parts[0])) {
                    muted.remove(parts[1]);
                } else {
                    reply = "M7A_CLEANUP_ERROR";
                }
                replies.println(reply);
                if (replies.checkError()) {
                    break;
                }
            }
        } catch (IOException e) {
            // 管道异常和正常断开一样处理
        } finally {
            if (panelOff) {
                restorePanel.run();
            }
            for (Map.Entry<String, String> entry : muted.entrySet()) {
                writeAudio(audio, reportFailure, entry.getKey(), entry.getValue());
            }
        }
    }

    private static boolean writeAudio(AudioSetter audio, BiConsumer<String, Exception> reportFailure,
                                      String packageName, String mode) {
        try {
            audio.setMode(packageName, mode);
            return true;
        } catch (IOException | InterruptedException | RuntimeException error) {
            reportFailure.accept("cleanup: cannot set PLAY_AUDIO of " + packageName + " to " + mode, error);
            return false;
        }
    }

    private static void restorePanel() {
        try {
            Class<?> apis = Class.forName("org.march7th.deviceservice.core.SystemApis");
            Method setPanelPower = apis.getDeclaredMethod("setPanelPower", boolean.class);
            setPanelPower.setAccessible(true);
            setPanelPower.invoke(null, true);
            Log.i(Protocol.LOG_TAG, "cleanup: panel restored");
        } catch (Throwable error) {
            Log.e(Protocol.LOG_TAG, "cleanup: cannot restore the panel", error);
        }
    }
}
