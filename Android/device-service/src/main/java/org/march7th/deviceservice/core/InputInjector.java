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
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Objects;

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
        final Integer targetUid;
        long downTime;

        Touches(Integer targetUid) {
            this.targetUid = targetUid;
        }

        int indexOf(int id) {
            for (int i = 0; i < pointers.size(); i++) {
                if (pointers.get(i).id == id) {
                    return i;
                }
            }
            return -1;
        }
    }

    private final InputDispatch dispatch;
    private final Method setDisplayIdMethod;
    private final Map<Integer, Touches> displays = new HashMap<>();
    private boolean closed;

    InputInjector() throws ReflectiveOperationException {
        dispatch = new InputDispatch(findInputManager(), InputEvent.class, Build.VERSION.SDK_INT);
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

    boolean supportsTargetUid() {
        return dispatch.supportsTargetUid();
    }

    private boolean inject(InputEvent event, int displayId, Integer targetUid) throws CommandException {
        try {
            setDisplayIdMethod.invoke(event, displayId);
            return dispatch.inject(event, MODE_WAIT_FOR_RESULT, targetUid);
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
     * @param targetUid 按下时指定目标。移动、抬起和取消沿用手势开始时的 UID。
     * @return 事件是否派发到了窗口。移动或抬起失败时取消该屏上的手势。
     */
    boolean touch(int displayId, int action, int pointerId, float x, float y, int owner, Integer targetUid)
            throws CommandException {
        synchronized (this) {
            requireOpen();
            Touches touches = displays.get(displayId);
            int index = touches == null ? -1 : touches.indexOf(pointerId);
            long now = SystemClock.uptimeMillis();
            int eventAction;
            if (action == MotionEvent.ACTION_DOWN) {
                if (index >= 0) {
                    throw new CommandException(Protocol.E_BAD_REQUEST, "pointer " + pointerId + " is already down");
                }
                if (touches == null) {
                    touches = new Touches(targetUid);
                    displays.put(displayId, touches);
                } else if (!Objects.equals(touches.targetUid, targetUid)) {
                    throw new CommandException(Protocol.E_BAD_REQUEST, "the gesture already has a different target UID");
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
                if (index < 0 || touches.pointers.get(index).owner != owner) {
                    throw new CommandException(Protocol.E_BAD_REQUEST, "pointer " + pointerId + " is not down in this session");
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
            boolean delivered;
            try {
                MotionEvent event = buildEvent(touches, eventAction, index, now);
                try {
                    delivered = inject(event, displayId, touches.targetUid);
                } finally {
                    event.recycle();
                }
            } catch (CommandException | RuntimeException e) {
                if (action == MotionEvent.ACTION_DOWN) {
                    removePointer(displayId, touches, index);
                } else {
                    cancelDisplay(displayId, touches);
                }
                throw e;
            }
            if (!delivered) {
                if (action == MotionEvent.ACTION_DOWN) {
                    removePointer(displayId, touches, index);
                    throw new CommandException(Protocol.E_INJECT_FAILED,
                            "no window accepted the touch on display " + displayId);
                }
                cancelDisplay(displayId, touches);
            } else if (action == MotionEvent.ACTION_UP) {
                removePointer(displayId, touches, index);
            }
            return delivered;
        }
    }

    private void removePointer(int displayId, Touches touches, int index) {
        touches.pointers.remove(index);
        if (touches.pointers.isEmpty()) {
            displays.remove(displayId);
        }
    }

    private void requireOpen() throws CommandException {
        if (closed) {
            throw new CommandException(Protocol.E_INTERNAL, "service is closing");
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
    boolean tap(int displayId, int pointerId, float x, float y, long durationMs, int owner, Integer targetUid)
            throws CommandException, InterruptedException {
        touch(displayId, MotionEvent.ACTION_DOWN, pointerId, x, y, owner, targetUid);
        try {
            if (durationMs > 0) {
                Thread.sleep(durationMs);
            }
        } catch (InterruptedException e) {
            cancelPointerGesture(displayId, pointerId, owner);
            throw e;
        }
        return touch(displayId, MotionEvent.ACTION_UP, pointerId, x, y, owner, null);
    }

    /** 滑动：在起点按下，沿折线匀速移动 durationMs，在终点抬起；两端可以各停留一段时间。 */
    boolean swipe(int displayId, int pointerId, TouchPath path, long durationMs, long holdStartMs, long holdEndMs,
                  int owner, Integer targetUid) throws CommandException, InterruptedException {
        float[] start = path.at(0);
        float[] end = path.at(1);
        touch(displayId, MotionEvent.ACTION_DOWN, pointerId, start[0], start[1], owner, targetUid);
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
                float[] point = path.at((double) elapsed / durationMs);
                if (!touch(displayId, MotionEvent.ACTION_MOVE, pointerId, point[0], point[1], owner, null)) {
                    return false;
                }
                Thread.sleep(Math.max(1, Math.min(MOVE_INTERVAL_MS, durationMs - elapsed)));
            }
            if (!touch(displayId, MotionEvent.ACTION_MOVE, pointerId, end[0], end[1], owner, null)) {
                return false;
            }
            if (holdEndMs > 0) {
                Thread.sleep(holdEndMs);
            }
        } catch (CommandException | InterruptedException | RuntimeException e) {
            cancelPointerGesture(displayId, pointerId, owner);
            throw e;
        }
        return touch(displayId, MotionEvent.ACTION_UP, pointerId, end[0], end[1], owner, null);
    }

    private synchronized void cancelPointerGesture(int displayId, int pointerId, int owner) {
        Touches touches = displays.get(displayId);
        int index = touches == null ? -1 : touches.indexOf(pointerId);
        if (index >= 0 && touches.pointers.get(index).owner == owner) {
            cancelDisplay(displayId, touches);
        }
    }

    private void cancelDisplay(int displayId, Touches touches) {
        displays.remove(displayId);
        sendCancel(displayId, touches);
    }

    private void sendCancel(int displayId, Touches touches) {
        try {
            MotionEvent cancel = buildEvent(touches, MotionEvent.ACTION_CANCEL, 0, SystemClock.uptimeMillis());
            try {
                inject(cancel, displayId, touches.targetUid);
            } finally {
                cancel.recycle();
            }
        } catch (CommandException | RuntimeException e) {
            Logger.w("cannot cancel gesture on display " + displayId, e);
        }
    }

    /**
     * 让一块屏成为焦点屏：注入一次按下，紧接着取消。系统在按下时把焦点切过去，取消的手势不算点击。
     *
     * MuMu（Android 12）上，星铁在没有焦点的虚拟屏里不渲染，setFocusedTask 也切不动显示器焦点，只有触摸可以。
     * 这块屏上已经有触点按着时说明焦点已经在这里，直接返回。
     */
    boolean focus(int displayId, float x, float y, Integer targetUid) throws CommandException {
        synchronized (this) {
            requireOpen();
            Touches touches = displays.get(displayId);
            if (touches != null && !touches.pointers.isEmpty()) {
                return true;
            }
            Touches poke = new Touches(targetUid);
            Pointer pointer = new Pointer();
            pointer.x = x;
            pointer.y = y;
            poke.pointers.add(pointer);
            poke.downTime = SystemClock.uptimeMillis();
            MotionEvent down = buildEvent(poke, MotionEvent.ACTION_DOWN, 0, poke.downTime);
            MotionEvent cancel = buildEvent(poke, MotionEvent.ACTION_CANCEL, 0, SystemClock.uptimeMillis());
            try {
                boolean delivered = inject(down, displayId, poke.targetUid);
                inject(cancel, displayId, poke.targetUid);
                return delivered;
            } finally {
                down.recycle();
                cancel.recycle();
            }
        }
    }

    /** 按一下按键：按下后立即抬起。 */
    synchronized boolean key(int displayId, int keyCode, Integer targetUid) throws CommandException {
        requireOpen();
        long now = SystemClock.uptimeMillis();
        boolean delivered = true;
        for (int action : new int[] {KeyEvent.ACTION_DOWN, KeyEvent.ACTION_UP}) {
            KeyEvent event = new KeyEvent(now, SystemClock.uptimeMillis(), action, keyCode, 0, 0,
                    KeyCharacterMap.VIRTUAL_KEYBOARD, 0, 0, InputDevice.SOURCE_KEYBOARD);
            delivered &= inject(event, displayId, targetUid);
        }
        return delivered;
    }

    /**
     * 取消整块屏上的手势。命中指定会话的任一个触点时，其余会话的触点也随同取消。
     *
     * @param owner     只处理这个会话按下的触点；-1 表示全部
     * @param displayId 只处理这块屏；-1 表示全部
     */
    synchronized void cancelAll(int owner, int displayId) {
        Iterator<Map.Entry<Integer, Touches>> iterator = displays.entrySet().iterator();
        while (iterator.hasNext()) {
            Map.Entry<Integer, Touches> entry = iterator.next();
            int id = entry.getKey();
            if (displayId >= 0 && id != displayId) {
                continue;
            }
            Touches touches = entry.getValue();
            if (owner < 0 || touches.pointers.stream().anyMatch(pointer -> pointer.owner == owner)) {
                iterator.remove();
                sendCancel(id, touches);
            }
        }
    }

    synchronized void close() {
        closed = true;
        cancelAll(-1, -1);
    }
}
