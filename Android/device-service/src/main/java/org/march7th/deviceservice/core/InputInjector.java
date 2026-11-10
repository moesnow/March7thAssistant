package org.march7th.deviceservice.core;

import android.os.Build;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.KeyCharacterMap;
import android.view.KeyEvent;
import android.view.MotionEvent;

import org.march7th.deviceservice.protocol.Protocol;
import org.march7th.deviceservice.protocol.TouchPath;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 在服务进程里直接注入触摸和按键，事件带目标 displayId。
 *
 * 用 InputManager.injectInputEvent 的“等待结果”模式：返回时事件已经派发给目标窗口，
 * 找不到可触摸的窗口时会如实返回失败。
 */
final class InputInjector {
    static final int MAX_POINTERS = 10;
    /** 滑动时相邻两次移动的间隔，约等于触摸屏的上报间隔。 */
    private static final int MOVE_INTERVAL_MS = 10;
    private static final int MODE_WAIT_FOR_RESULT = 1;

    private static final class Pointer {
        int id;
        float x;
        float y;
        int owner;
    }

    /** 一块屏上当前按着的触点。 */
    private static final class Touches {
        final List<Pointer> pointers = new ArrayList<>();
        long downTime;

        int indexOf(int id) {
            for (int i = 0; i < pointers.size(); i++) {
                if (pointers.get(i).id == id) {
                    return i;
                }
            }
            return -1;
        }
    }

    private final Object inputManager;
    private final Method injectMethod;
    private final Method setDisplayIdMethod;
    private final Map<Integer, Touches> displays = new HashMap<>();

    InputInjector() throws ReflectiveOperationException {
        inputManager = findInputManager();
        injectMethod = inputManager.getClass().getMethod("injectInputEvent", InputEvent.class, int.class);
        setDisplayIdMethod = InputEvent.class.getMethod("setDisplayId", int.class);
    }

    /**
     * Android 10 到 13：InputManager.getInstance()。
     * Android 14 起 getInstance() 依赖 Application，改从 Context 取，再退到 InputManagerGlobal（未在实机验证）。
     */
    private static Object findInputManager() throws ReflectiveOperationException {
        Class<?> inputManager = Class.forName("android.hardware.input.InputManager");
        if (Build.VERSION.SDK_INT < 34) {
            return inputManager.getMethod("getInstance").invoke(null);
        }
        ShellContext context = ShellContext.get();
        if (context.hasBase()) {
            Object manager = context.getSystemService("input");
            if (manager != null) {
                return manager;
            }
        }
        return Class.forName("android.hardware.input.InputManagerGlobal").getMethod("getInstance").invoke(null);
    }

    private boolean inject(InputEvent event, int displayId) throws CommandException {
        try {
            setDisplayIdMethod.invoke(event, displayId);
            return (Boolean) injectMethod.invoke(inputManager, event, MODE_WAIT_FOR_RESULT);
        } catch (InvocationTargetException e) {
            Throwable cause = e.getCause();
            if (cause instanceof SecurityException) {
                // MIUI 上没开“USB 调试（安全设置）”时 shell 不能注入
                throw new CommandException(Protocol.E_INJECT_DENIED, String.valueOf(cause.getMessage()));
            }
            throw new CommandException(Protocol.E_INJECT_FAILED, Logger.describe(e));
        } catch (ReflectiveOperationException e) {
            throw new CommandException(Protocol.E_INTERNAL, Logger.describe(e));
        }
    }

    /**
     * 按下、移动或抬起一个触点。
     *
     * @param action MotionEvent.ACTION_DOWN、ACTION_MOVE 或 ACTION_UP
     * @return 事件是否派发到了窗口。按下失败会直接抛异常；移动和抬起失败只返回 false，触点状态照常更新。
     */
    boolean touch(int displayId, int action, int pointerId, float x, float y, int owner) throws CommandException {
        synchronized (this) {
            Touches touches = displays.get(displayId);
            if (touches == null) {
                touches = new Touches();
                displays.put(displayId, touches);
            }
            int index = touches.indexOf(pointerId);
            long now = SystemClock.uptimeMillis();
            int eventAction;
            if (action == MotionEvent.ACTION_DOWN) {
                if (index >= 0) {
                    throw new CommandException(Protocol.E_BAD_REQUEST, "pointer " + pointerId + " is already down");
                }
                if (touches.pointers.size() >= MAX_POINTERS) {
                    throw new CommandException(Protocol.E_BAD_REQUEST, "too many pointers");
                }
                Pointer pointer = new Pointer();
                pointer.id = pointerId;
                pointer.x = x;
                pointer.y = y;
                pointer.owner = owner;
                touches.pointers.add(pointer);
                index = touches.pointers.size() - 1;
                if (index == 0) {
                    touches.downTime = now;
                    eventAction = MotionEvent.ACTION_DOWN;
                } else {
                    eventAction = MotionEvent.ACTION_POINTER_DOWN | (index << MotionEvent.ACTION_POINTER_INDEX_SHIFT);
                }
            } else {
                if (index < 0) {
                    throw new CommandException(Protocol.E_BAD_REQUEST, "pointer " + pointerId + " is not down");
                }
                Pointer pointer = touches.pointers.get(index);
                if (!Float.isNaN(x) && !Float.isNaN(y)) {
                    pointer.x = x;
                    pointer.y = y;
                }
                if (action == MotionEvent.ACTION_MOVE) {
                    eventAction = MotionEvent.ACTION_MOVE;
                } else if (touches.pointers.size() == 1) {
                    eventAction = MotionEvent.ACTION_UP;
                } else {
                    eventAction = MotionEvent.ACTION_POINTER_UP | (index << MotionEvent.ACTION_POINTER_INDEX_SHIFT);
                }
            }
            MotionEvent event = buildEvent(touches, eventAction, index, now);
            boolean delivered;
            try {
                delivered = inject(event, displayId);
            } catch (CommandException e) {
                if (action != MotionEvent.ACTION_MOVE) {
                    touches.pointers.remove(index);
                }
                throw e;
            } finally {
                event.recycle();
            }
            if (action == MotionEvent.ACTION_UP) {
                touches.pointers.remove(index);
            } else if (action == MotionEvent.ACTION_DOWN && !delivered) {
                touches.pointers.remove(index);
                throw new CommandException(Protocol.E_INJECT_FAILED,
                        "no window accepted the touch on display " + displayId);
            }
            return delivered;
        }
    }

    private static MotionEvent buildEvent(Touches touches, int action, int actionIndex, long now) {
        int count = touches.pointers.size();
        MotionEvent.PointerProperties[] properties = new MotionEvent.PointerProperties[count];
        MotionEvent.PointerCoords[] coords = new MotionEvent.PointerCoords[count];
        boolean lifting = (action & MotionEvent.ACTION_MASK) == MotionEvent.ACTION_UP
                || (action & MotionEvent.ACTION_MASK) == MotionEvent.ACTION_POINTER_UP;
        for (int i = 0; i < count; i++) {
            Pointer pointer = touches.pointers.get(i);
            properties[i] = new MotionEvent.PointerProperties();
            properties[i].id = pointer.id;
            properties[i].toolType = MotionEvent.TOOL_TYPE_FINGER;
            coords[i] = new MotionEvent.PointerCoords();
            coords[i].x = pointer.x;
            coords[i].y = pointer.y;
            coords[i].pressure = lifting && i == actionIndex ? 0f : 1f;
            coords[i].size = 1f;
        }
        return MotionEvent.obtain(touches.downTime, now, action, count, properties, coords,
                0, 0, 1f, 1f, 0, 0, InputDevice.SOURCE_TOUCHSCREEN, 0);
    }

    /** 点按：按下，保持 durationMs，抬起。 */
    boolean tap(int displayId, int pointerId, float x, float y, long durationMs, int owner)
            throws CommandException, InterruptedException {
        touch(displayId, MotionEvent.ACTION_DOWN, pointerId, x, y, owner);
        try {
            if (durationMs > 0) {
                Thread.sleep(durationMs);
            }
        } catch (InterruptedException e) {
            liftQuietly(displayId, pointerId, x, y, owner);
            throw e;
        }
        return liftQuietly(displayId, pointerId, x, y, owner);
    }

    /** 滑动：在起点按下，沿折线匀速移动 durationMs，在终点抬起；两端可以各停留一段时间。 */
    boolean swipe(int displayId, int pointerId, TouchPath path, long durationMs, long holdStartMs, long holdEndMs, int owner)
            throws CommandException, InterruptedException {
        float[] start = path.at(0);
        float[] end = path.at(1);
        touch(displayId, MotionEvent.ACTION_DOWN, pointerId, start[0], start[1], owner);
        float[] last = start;
        try {
            if (holdStartMs > 0) {
                Thread.sleep(holdStartMs);
            }
            long begin = SystemClock.uptimeMillis();
            while (true) {
                long elapsed = SystemClock.uptimeMillis() - begin;
                if (elapsed >= durationMs) {
                    break;
                }
                last = path.at((double) elapsed / durationMs);
                touch(displayId, MotionEvent.ACTION_MOVE, pointerId, last[0], last[1], owner);
                Thread.sleep(Math.max(1, Math.min(MOVE_INTERVAL_MS, durationMs - elapsed)));
            }
            last = end;
            touch(displayId, MotionEvent.ACTION_MOVE, pointerId, end[0], end[1], owner);
            if (holdEndMs > 0) {
                Thread.sleep(holdEndMs);
            }
        } catch (CommandException | InterruptedException | RuntimeException e) {
            liftQuietly(displayId, pointerId, last[0], last[1], owner);
            throw e;
        }
        return liftQuietly(displayId, pointerId, end[0], end[1], owner);
    }

    /** 抬起触点。即使前面的步骤失败也要保证不留下按着的触点。 */
    private boolean liftQuietly(int displayId, int pointerId, float x, float y, int owner) {
        try {
            return touch(displayId, MotionEvent.ACTION_UP, pointerId, x, y, owner);
        } catch (CommandException e) {
            Logger.w("cannot lift pointer " + pointerId + " on display " + displayId + ": " + e.getMessage());
            return false;
        }
    }

    /**
     * 让一块屏成为焦点屏：注入一次按下，紧接着取消。系统在按下时把焦点切过去，取消的手势不算点击。
     *
     * MuMu（Android 12）上，星铁在没有焦点的虚拟屏里不渲染，setFocusedTask 也切不动显示器焦点，只有触摸可以。
     * 这块屏上已经有触点按着时说明焦点已经在这里，直接返回。
     */
    boolean focus(int displayId, float x, float y) throws CommandException {
        synchronized (this) {
            Touches touches = displays.get(displayId);
            if (touches != null && !touches.pointers.isEmpty()) {
                return true;
            }
            Touches poke = new Touches();
            Pointer pointer = new Pointer();
            pointer.x = x;
            pointer.y = y;
            poke.pointers.add(pointer);
            poke.downTime = SystemClock.uptimeMillis();
            MotionEvent down = buildEvent(poke, MotionEvent.ACTION_DOWN, 0, poke.downTime);
            MotionEvent cancel = buildEvent(poke, MotionEvent.ACTION_CANCEL, 0, SystemClock.uptimeMillis());
            try {
                boolean delivered = inject(down, displayId);
                inject(cancel, displayId);
                return delivered;
            } finally {
                down.recycle();
                cancel.recycle();
            }
        }
    }

    /** 按一下按键：按下后立即抬起。 */
    boolean key(int displayId, int keyCode) throws CommandException {
        long now = SystemClock.uptimeMillis();
        boolean delivered = true;
        for (int action : new int[] {KeyEvent.ACTION_DOWN, KeyEvent.ACTION_UP}) {
            KeyEvent event = new KeyEvent(now, SystemClock.uptimeMillis(), action, keyCode, 0, 0,
                    KeyCharacterMap.VIRTUAL_KEYBOARD, 0, 0, InputDevice.SOURCE_KEYBOARD);
            delivered &= inject(event, displayId);
        }
        return delivered;
    }

    /**
     * 抬起还按着的触点。
     *
     * @param owner     只处理这个会话按下的触点；-1 表示全部
     * @param displayId 只处理这块屏；-1 表示全部
     */
    void releaseAll(int owner, int displayId) {
        List<int[]> pending = new ArrayList<>();
        List<float[]> positions = new ArrayList<>();
        synchronized (this) {
            for (Map.Entry<Integer, Touches> entry : displays.entrySet()) {
                if (displayId >= 0 && entry.getKey() != displayId) {
                    continue;
                }
                for (Pointer pointer : entry.getValue().pointers) {
                    if (owner < 0 || pointer.owner == owner) {
                        pending.add(new int[] {entry.getKey(), pointer.id, pointer.owner});
                        positions.add(new float[] {pointer.x, pointer.y});
                    }
                }
            }
        }
        for (int i = 0; i < pending.size(); i++) {
            int[] item = pending.get(i);
            float[] position = positions.get(i);
            liftQuietly(item[0], item[1], position[0], position[1], item[2]);
        }
    }

    /** 忘掉一块屏上的触点状态，屏被释放后调用。 */
    synchronized void forgetDisplay(int displayId) {
        displays.remove(displayId);
    }
}
