package org.march7th.deviceservice.core;

import org.json.JSONObject;
import org.junit.Test;
import java.util.ArrayList;
import java.util.List;
import static org.junit.Assert.*;

public class FocusInjectionTest {
    @Test
    public void keepsDownAndCancelReceiptsSeparateWithoutClaimingFocus() throws Exception {
        for (boolean down : new boolean[]{true, false}) {
            for (boolean cancel : new boolean[]{true, false}) {
                List<String> actions = new ArrayList<>();
                FocusInjection.Result result = FocusInjection.send(() -> { actions.add("DOWN"); return down; },
                        () -> { actions.add("CANCEL"); return cancel; });
                JSONObject report = result.describe();
                assertEquals(List.of("DOWN", "CANCEL"), actions);
                assertEquals(down, result.delivered());
                assertEquals(down, report.getBoolean("down_accepted"));
                assertEquals(cancel, report.getBoolean("cancel_accepted"));
                assertFalse(report.has("focus_acquired"));
            }
        }
    }

    @Test
    public void cancelsAfterAnUncertainDownAndPreservesBothErrors() throws Exception {
        List<String> actions = new ArrayList<>();
        CommandException denied = new CommandException("inject_denied", "denied");
        FocusInjection.Result result = FocusInjection.send(() -> { actions.add("DOWN"); throw denied; },
                () -> { actions.add("CANCEL"); throw new IllegalStateException("cancel failed"); });
        assertEquals(List.of("DOWN", "CANCEL"), actions);
        assertSame(denied, assertThrows(CommandException.class, result::delivered));
        assertTrue(result.describe().getString("down_error").contains("inject_denied"));
        assertTrue(result.describe().getString("cancel_error").contains("cancel failed"));
        assertTrue(result.describe().isNull("down_accepted"));
    }

    @Test
    public void anExistingGestureDoesNotPretendAnInjectionWasSent() throws Exception {
        FocusInjection.Result result = FocusInjection.skipped("active_gesture");
        assertTrue(result.delivered()); // 旧模拟器调用约定
        assertFalse(result.describe().getBoolean("attempted"));
        assertTrue(result.describe().isNull("down_accepted"));
    }
}
