package org.march7th.deviceservice.core;

import org.march7th.deviceservice.protocol.Protocol;

import java.lang.reflect.Method;

/** 选择 Android 输入接口。指定 UID 的调用失败时不会重试普通注入。 */
final class InputDispatch {
    private final Object manager;
    private final Method untargeted;
    private final Method targeted;

    InputDispatch(Object manager, Class<?> eventType, int sdk) throws NoSuchMethodException {
        this.manager = manager;
        Class<?> type = manager.getClass();
        untargeted = type.getMethod("injectInputEvent", eventType, int.class);
        Method method = null;
        // Android 13 的系统服务可能在目标不匹配时退回普通注入。
        if (sdk >= 34) {
            try {
                method = type.getMethod("injectInputEvent", eventType, int.class, int.class);
            } catch (NoSuchMethodException ignored) {
                // 厂商系统也可能没有提供此接口。
            }
        }
        targeted = method;
    }

    boolean supportsTargetUid() {
        return targeted != null;
    }

    boolean inject(Object event, int mode, Integer targetUid)
            throws ReflectiveOperationException, CommandException {
        if (targetUid == null) {
            return (Boolean) untargeted.invoke(manager, event, mode);
        }
        if (!supportsTargetUid() || targetUid < 0) {
            throw new CommandException(Protocol.E_UNSUPPORTED, "strict target UID injection is unavailable");
        }
        return (Boolean) targeted.invoke(manager, event, mode, targetUid);
    }
}
