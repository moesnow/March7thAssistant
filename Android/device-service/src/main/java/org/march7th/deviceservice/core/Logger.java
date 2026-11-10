package org.march7th.deviceservice.core;

import android.util.Log;

import org.march7th.deviceservice.protocol.Protocol;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** 统一的日志出口：logcat 用同一个 tag，同时带时间戳写到标准输出，方便把输出重定向成日志文件。 */
public final class Logger {
    private static final SimpleDateFormat FORMAT = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US);

    private Logger() {
    }

    public static void i(String message) {
        Log.i(Protocol.LOG_TAG, message);
        print('I', message, null);
    }

    public static void w(String message) {
        Log.w(Protocol.LOG_TAG, message);
        print('W', message, null);
    }

    public static void w(String message, Throwable error) {
        Log.w(Protocol.LOG_TAG, message, error);
        print('W', message, error);
    }

    public static void e(String message, Throwable error) {
        Log.e(Protocol.LOG_TAG, message, error);
        print('E', message, error);
    }

    private static synchronized void print(char level, String message, Throwable error) {
        System.out.println(FORMAT.format(new Date()) + ' ' + level + ' ' + message
                + (error == null ? "" : " :: " + describe(error)));
        System.out.flush();
    }

    /** 反射调用的异常外面包着一层 InvocationTargetException，这里取真正的原因。 */
    public static String describe(Throwable error) {
        Throwable cause = error;
        while (cause.getCause() != null && cause instanceof java.lang.reflect.InvocationTargetException) {
            cause = cause.getCause();
        }
        return cause.getClass().getSimpleName() + ": " + cause.getMessage();
    }
}
