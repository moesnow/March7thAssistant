package org.march7th.deviceservice.core;

import java.io.IOException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 服务和善后子进程共用的 PLAY_AUDIO 操作。 */
public final class AudioAppOps {
    private static final String OP = "PLAY_AUDIO";
    private static final Pattern MODE = Pattern.compile(OP + ":\\s*(\\w+)");
    private static final long COMMAND_TIMEOUT_MS = 5000;

    private AudioAppOps() {
    }

    static String mode(String packageName) throws IOException, InterruptedException {
        Shell.Result result = Shell.run(COMMAND_TIMEOUT_MS, "cmd", "appops", "get", packageName, OP);
        if (!result.ok()) {
            throw new IOException("appops get failed: " + result);
        }
        Matcher matcher = MODE.matcher(result.stdout);
        return matcher.find() ? matcher.group(1) : "default";
    }

    static void setMode(String packageName, String mode) throws IOException, InterruptedException {
        setMode(packageName, mode, COMMAND_TIMEOUT_MS);
    }

    /** 善后子进程等写入实际完成，随后才处理下一条命令或 EOF 恢复。 */
    public static void setModeAndWait(String packageName, String mode) throws IOException, InterruptedException {
        setMode(packageName, mode, 0);
    }

    private static void setMode(String packageName, String mode, long timeoutMs) throws IOException, InterruptedException {
        Shell.Result result = Shell.run(timeoutMs, "cmd", "appops", "set", packageName, OP, mode);
        if (!result.ok() || !result.stderr.trim().isEmpty()) {
            throw new IOException("appops set failed: " + result);
        }
    }
}
