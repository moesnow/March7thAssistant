package org.march7th.deviceservice.protocol;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 解析 {@code cmd activity stack list} 的输出。隐藏 API 用不了时，看门狗靠它取任务状态。
 *
 * Android 10、11 的一段形如：
 * <pre>
 * Stack id=79 bounds=[0,0][1080,2340] displayId=0 userId=0
 *  configuration={...}
 *   taskId=122: 包名/根Activity bounds=[...] userId=0 visible=true topActivity=ComponentInfo{包名/栈顶Activity}
 * </pre>
 * Android 12 起首行改为 {@code RootTask id=...}，其余相同。任务没有运行中的 Activity 时没有 topActivity 字段。
 */
public final class StackListParser {
    private static final Pattern STACK = Pattern.compile("^(?:Stack|RootTask) id=(\\d+) .*\\bdisplayId=(-?\\d+)");
    private static final Pattern TASK = Pattern.compile(
            "^\\s+taskId=(\\d+): (\\S+) .*\\bvisible=(true|false)(?: topActivity=ComponentInfo\\{([^}]+)\\})?");

    private StackListParser() {
    }

    public static List<StackEntry> parse(String output) {
        List<StackEntry> result = new ArrayList<>();
        int stackId = -1;
        int displayId = -1;
        boolean open = false;
        List<int[]> taskIds = new ArrayList<>();
        List<String> taskNames = new ArrayList<>();
        boolean visible = false;
        String top = null;
        for (String line : output.split("\n")) {
            if (line.endsWith("\r")) {
                line = line.substring(0, line.length() - 1);
            }
            Matcher stack = STACK.matcher(line);
            if (stack.find()) {
                if (open) {
                    result.add(build(stackId, displayId, visible, top, taskIds, taskNames));
                }
                stackId = Integer.parseInt(stack.group(1));
                displayId = Integer.parseInt(stack.group(2));
                open = true;
                taskIds = new ArrayList<>();
                taskNames = new ArrayList<>();
                visible = false;
                top = null;
                continue;
            }
            if (!open) {
                continue;
            }
            Matcher task = TASK.matcher(line);
            if (task.find()) {
                taskIds.add(new int[] {Integer.parseInt(task.group(1))});
                taskNames.add(task.group(2));
                // 同一个栈里的任务按从上到下列出，第一个带 topActivity 的就是栈顶。
                if (top == null && task.group(4) != null) {
                    top = task.group(4);
                    visible = "true".equals(task.group(3));
                }
            }
        }
        if (open) {
            result.add(build(stackId, displayId, visible, top, taskIds, taskNames));
        }
        return result;
    }

    private static StackEntry build(int stackId, int displayId, boolean visible, String top,
                                    List<int[]> taskIds, List<String> taskNames) {
        StackEntry entry = new StackEntry(stackId, displayId, visible, top);
        for (int i = 0; i < taskIds.size(); i++) {
            entry.taskIds.add(taskIds.get(i)[0]);
            entry.taskNames.add(taskNames.get(i));
        }
        return entry;
    }
}
