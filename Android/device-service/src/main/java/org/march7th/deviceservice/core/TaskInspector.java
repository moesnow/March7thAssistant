package org.march7th.deviceservice.core;

import org.march7th.deviceservice.protocol.StackEntry;
import org.march7th.deviceservice.protocol.StackListParser;

import java.util.List;

/**
 * 查任务栈、移动任务栈。优先走隐藏 API（一次 Binder 调用），失败后改为解析命令输出。
 */
final class TaskInspector {
    static final String AUTO = "auto";
    static final String HIDDEN = "hidden";
    static final String SHELL = "shell";

    private static final long COMMAND_TIMEOUT_MS = 5000;

    private final String mode;
    private boolean hiddenBroken;

    TaskInspector(String mode) {
        if (!AUTO.equals(mode) && !HIDDEN.equals(mode) && !SHELL.equals(mode)) {
            throw new IllegalArgumentException("inspector must be auto, hidden or shell");
        }
        this.mode = mode;
    }

    /** 当前实际在用的方式：hidden 或 shell。 */
    synchronized String activeMode() {
        return useHidden() ? HIDDEN : SHELL;
    }

    private boolean useHidden() {
        return HIDDEN.equals(mode) || (AUTO.equals(mode) && !hiddenBroken);
    }

    private synchronized void markHiddenBroken(Throwable error) {
        if (!hiddenBroken) {
            hiddenBroken = true;
            Logger.w("hidden task API failed, falling back to shell commands", error);
        }
    }

    List<StackEntry> stacks() throws Exception {
        boolean hidden;
        synchronized (this) {
            hidden = useHidden();
        }
        if (hidden) {
            try {
                return SystemApis.stacks();
            } catch (ReflectiveOperationException | RuntimeException e) {
                if (HIDDEN.equals(mode)) {
                    throw e;
                }
                markHiddenBroken(e);
            }
        }
        Shell.Result result = Shell.run(COMMAND_TIMEOUT_MS, "cmd", "activity", "stack", "list");
        if (!result.ok()) {
            throw new IllegalStateException("stack list failed: " + result);
        }
        return StackListParser.parse(result.stdout);
    }

    void move(int stackId, int displayId) throws Exception {
        boolean hidden;
        synchronized (this) {
            hidden = useHidden();
        }
        if (hidden) {
            try {
                SystemApis.moveStackToDisplay(stackId, displayId);
                return;
            } catch (ReflectiveOperationException | RuntimeException e) {
                if (HIDDEN.equals(mode)) {
                    throw e;
                }
                markHiddenBroken(e);
            }
        }
        Shell.Result result = Shell.run(COMMAND_TIMEOUT_MS, "cmd", "activity", "display", "move-stack",
                Integer.toString(stackId), Integer.toString(displayId));
        if (!result.ok() || result.stdout.contains("Error") || result.stderr.contains("Exception")) {
            throw new IllegalStateException("move-stack failed: " + result);
        }
    }
}
