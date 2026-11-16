package org.march7th.deviceservice;

import android.util.Log;

import org.march7th.deviceservice.core.GameAudio;
import org.march7th.deviceservice.core.Logger;
import org.march7th.deviceservice.protocol.Protocol;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
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
 * mute 包名             先持久化再尝试静音
 * restore_audio 包名    恢复该包的音频，验证成功后移除记录
 * </pre>
 * 音频命令的成功回复附带原模式，失败回复附带原因。
 */
public final class Cleanup {
    public static final String HANDOFF_VERSION = "cleanup-lock-v1";
    public static final String READY = "M7A_CLEANUP_READY";
    public static final String OK = "M7A_CLEANUP_OK ";
    public static final String FAILED = "M7A_CLEANUP_FAILED ";

    interface AudioCommand {
        String run(String packageName, boolean on) throws IOException, InterruptedException;
    }

    interface AudioRestore {
        void run() throws IOException, InterruptedException;
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
                    GameAudio audio = new GameAudio();
                    run(commands, replies, Cleanup::restorePanel, audio::setMuted, audio::restorePending,
                            (message, error) -> Log.e(Protocol.LOG_TAG, message, error));
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
                    AudioCommand audio, AudioRestore restoreAudio, BiConsumer<String, Exception> reportFailure) {
        boolean panelOff = false;
        try (BufferedReader reader = commands) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] parts = line.trim().split(" ");
                String reply = OK + line;
                if (parts.length == 2 && "panel".equals(parts[0]) && ("0".equals(parts[1]) || "1".equals(parts[1]))) {
                    panelOff = "1".equals(parts[1]);
                } else if (parts.length == 2 && ("mute".equals(parts[0]) || "restore_audio".equals(parts[0]))) {
                    try {
                        reply += " " + audio.run(parts[1], "mute".equals(parts[0]));
                    } catch (IOException | InterruptedException | RuntimeException error) {
                        reportFailure.accept("cleanup: " + line, error);
                        String detail = Logger.describe(error).replace('\r', ' ').replace('\n', ' ');
                        reply = FAILED + line + " " + detail;
                    }
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
            try {
                restoreAudio.run();
            } catch (IOException | InterruptedException | RuntimeException error) {
                reportFailure.accept("cleanup: game audio recovery is still pending", error);
            }
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
