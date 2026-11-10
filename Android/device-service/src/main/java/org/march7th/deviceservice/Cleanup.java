package org.march7th.deviceservice;

import android.util.Log;

import org.march7th.deviceservice.protocol.Protocol;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 善后子进程，做法参照 scrcpy（Apache-2.0）的 CleanUp。
 *
 * 服务从标准输入告诉它目前有哪些改动需要恢复。标准输入一断开（服务退出或被强杀），它就把还没恢复的
 * 改动恢复掉然后退出。它不依赖服务进程里的任何状态。
 *
 * <pre>
 * panel 1               面板已关，需要恢复
 * panel 0               面板已恢复
 * mute 包名 原模式       已静音，需要恢复成原模式
 * unmute 包名           已恢复
 * </pre>
 */
public final class Cleanup {
    private Cleanup() {
    }

    public static void main(String[] args) {
        boolean panelOff = false;
        Map<String, String> muted = new LinkedHashMap<>();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] parts = line.trim().split(" ");
                if (parts.length == 2 && "panel".equals(parts[0])) {
                    panelOff = "1".equals(parts[1]);
                } else if (parts.length == 3 && "mute".equals(parts[0])) {
                    muted.put(parts[1], parts[2]);
                } else if (parts.length == 2 && "unmute".equals(parts[0])) {
                    muted.remove(parts[1]);
                }
            }
        } catch (IOException e) {
            // 管道异常和正常断开一样处理
        }
        if (panelOff) {
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
        for (Map.Entry<String, String> entry : muted.entrySet()) {
            try {
                Process process = new ProcessBuilder("cmd", "appops", "set", entry.getKey(), "PLAY_AUDIO", entry.getValue())
                        .redirectErrorStream(true).start();
                process.getOutputStream().close();
                process.waitFor(5, TimeUnit.SECONDS);
                Log.i(Protocol.LOG_TAG, "cleanup: PLAY_AUDIO of " + entry.getKey() + " restored to " + entry.getValue());
            } catch (Throwable error) {
                Log.e(Protocol.LOG_TAG, "cleanup: cannot restore PLAY_AUDIO of " + entry.getKey(), error);
            }
        }
        System.exit(0);
    }
}
