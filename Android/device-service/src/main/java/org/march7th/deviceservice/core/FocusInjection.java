package org.march7th.deviceservice.core;

import org.json.JSONException;
import org.json.JSONObject;

/** DOWN/CANCEL 的派发回执，不能用来证明窗口获得焦点或恢复渲染。 */
final class FocusInjection {
    interface Event {
        boolean send() throws CommandException;
    }

    static final class Result {
        Boolean downAccepted;
        Boolean cancelAccepted;
        Exception downError;
        Exception cancelError;
        String skipped;
        Integer downDisplayId;
        Integer cancelDisplayId;

        boolean delivered() throws CommandException {
            // 保留原模拟器路径对已有手势的返回约定。
            if ("active_gesture".equals(skipped)) return true;
            Exception error = downError != null ? downError : cancelError;
            if (error instanceof CommandException) throw (CommandException) error;
            if (error instanceof RuntimeException) throw (RuntimeException) error;
            return Boolean.TRUE.equals(downAccepted);
        }

        JSONObject describe() throws JSONException {
            JSONObject out = new JSONObject();
            out.put("attempted", skipped == null);
            out.put("skipped", skipped == null ? JSONObject.NULL : skipped);
            out.put("down_accepted", downAccepted == null ? JSONObject.NULL : downAccepted);
            out.put("cancel_accepted", cancelAccepted == null ? JSONObject.NULL : cancelAccepted);
            out.put("down_display_id", downDisplayId == null ? JSONObject.NULL : downDisplayId);
            out.put("cancel_display_id", cancelDisplayId == null ? JSONObject.NULL : cancelDisplayId);
            if (downError != null) out.put("down_error", error(downError));
            if (cancelError != null) out.put("cancel_error", error(cancelError));
            out.put("focus_verification", "requires_window_observation");
            return out;
        }

        private static String error(Exception error) {
            return (error instanceof CommandException ? ((CommandException) error).code : error.getClass().getSimpleName())
                    + ": " + error.getMessage();
        }
    }

    static Result skipped(String reason) {
        Result result = new Result();
        result.skipped = reason;
        return result;
    }

    static Result send(Event down, Event cancel) {
        Result result = new Result();
        try {
            result.downAccepted = down.send();
        } catch (CommandException | RuntimeException e) {
            result.downError = e;
        } finally {
            // DOWN 超时或抛异常也可能已经送达；始终尝试清理，且分别保留两个回执。
            try {
                result.cancelAccepted = cancel.send();
            } catch (CommandException | RuntimeException e) {
                result.cancelError = e;
            }
        }
        return result;
    }
}
