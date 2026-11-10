package org.march7th.deviceservice.protocol;

import java.util.ArrayList;
import java.util.List;

/**
 * 一个任务栈（Android 10、11 叫 stack，Android 12 起叫 root task）的快照。
 */
public final class StackEntry {
    /** 回迁时传给系统的 ID：Android 10、11 是栈 ID，Android 12 起是 root task ID。 */
    public final int stackId;
    public final int displayId;
    public final boolean visible;
    /** 栈顶 Activity，形如 包名/类名；没有时为 null。 */
    public final String topActivity;
    public final List<Integer> taskIds = new ArrayList<>();
    /** 各任务的根 Activity，形如 包名/类名，与 taskIds 一一对应。 */
    public final List<String> taskNames = new ArrayList<>();

    public StackEntry(int stackId, int displayId, boolean visible, String topActivity) {
        this.stackId = stackId;
        this.displayId = displayId;
        this.visible = visible;
        this.topActivity = topActivity;
    }

    /** 这个栈里是否有属于指定包的任务。 */
    public boolean belongsTo(String packageName) {
        String prefix = packageName + "/";
        for (String name : taskNames) {
            if (name != null && name.startsWith(prefix)) {
                return true;
            }
        }
        return topActivity != null && topActivity.startsWith(prefix);
    }

    /** 属于指定包的第一个任务的 ID，没有时为 -1。 */
    public int taskIdOf(String packageName) {
        String prefix = packageName + "/";
        for (int i = 0; i < taskNames.size(); i++) {
            String name = taskNames.get(i);
            if (name != null && name.startsWith(prefix)) {
                return taskIds.get(i);
            }
        }
        return taskIds.isEmpty() ? -1 : taskIds.get(0);
    }

    /** 栈顶 Activity 的类名，没有时为 null。 */
    public String topActivityClass() {
        if (topActivity == null) {
            return null;
        }
        int slash = topActivity.indexOf('/');
        if (slash < 0) {
            return topActivity;
        }
        String cls = topActivity.substring(slash + 1);
        return cls.startsWith(".") ? topActivity.substring(0, slash) + cls : cls;
    }

    @Override
    public String toString() {
        return "StackEntry{id=" + stackId + " display=" + displayId + " visible=" + visible
                + " top=" + topActivity + " tasks=" + taskIds + " " + taskNames + "}";
    }
}
