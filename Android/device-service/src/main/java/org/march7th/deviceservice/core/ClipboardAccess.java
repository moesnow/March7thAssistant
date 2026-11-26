package org.march7th.deviceservice.core;

import java.lang.reflect.Method;

/** 兼容 Android 10 起剪贴板服务的包名、用户和设备参数，不依赖 Application Context。 */
final class ClipboardAccess {
    private final Object manager;
    private final Method setter;
    private final Object[] arguments;

    ClipboardAccess(Object manager, Class<?> clipType, String packageName, int userId) throws NoSuchMethodException {
        this.manager = manager;
        Class<?>[][] signatures = {
                {clipType, String.class, int.class},
                {clipType, String.class, String.class, int.class},
                {clipType, String.class, String.class, int.class, int.class},
                {clipType, String.class, String.class, int.class, int.class, boolean.class},
        };
        Method found = null;
        for (Class<?>[] signature : signatures) {
            try {
                found = manager.getClass().getMethod("setPrimaryClip", signature);
                break;
            } catch (NoSuchMethodException ignored) {
                // 系统版本和部分 ROM 使用不同的 Binder 参数。
            }
        }
        if (found == null) {
            throw new NoSuchMethodException("clipboard.setPrimaryClip");
        }
        setter = found;
        switch (setter.getParameterCount()) {
            case 3:
                arguments = new Object[]{null, packageName, userId};
                break;
            case 4:
                arguments = new Object[]{null, packageName, null, userId};
                break;
            case 5:
                arguments = new Object[]{null, packageName, null, userId, 0};
                break;
            default:
                arguments = new Object[]{null, packageName, null, userId, 0, true};
                break;
        }
    }

    synchronized void set(Object clip) throws ReflectiveOperationException {
        arguments[0] = clip;
        try {
            setter.invoke(manager, arguments);
        } finally {
            arguments[0] = null;
        }
    }
}
