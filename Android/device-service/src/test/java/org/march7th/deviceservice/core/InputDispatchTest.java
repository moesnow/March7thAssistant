package org.march7th.deviceservice.core;

import org.junit.Test;
import org.march7th.deviceservice.protocol.Protocol;

import java.lang.reflect.InvocationTargetException;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

public class InputDispatchTest {
    private static final int GAME_UID = 10328;
    private static final int SETTINGS_UID = 10410;
    private static final int WAIT_FOR_RESULT = 1;

    @Test
    public void windowSwitchAfterFocusCheckDoesNotDeliverToSettings() throws Exception {
        TargetedManager manager = new TargetedManager();
        InputDispatch dispatch = new InputDispatch(manager, Event.class, 34);
        assertEquals(GAME_UID, manager.receivingUid);
        manager.receivingUid = SETTINGS_UID;

        InvocationTargetException failure = assertThrows(InvocationTargetException.class,
                () -> dispatch.inject(new Event(), WAIT_FOR_RESULT, GAME_UID));

        assertTrue(failure.getCause() instanceof IllegalArgumentException);
        assertEquals(1, manager.targetedCalls);
        assertEquals(0, manager.untargetedCalls);
        assertEquals(0, manager.delivered);
    }

    @Test
    public void targetRejectionIsNotRetriedAsOrdinaryInjection() throws Exception {
        TargetedManager manager = new TargetedManager();
        manager.accept = false;
        InputDispatch dispatch = new InputDispatch(manager, Event.class, 34);

        assertFalse(dispatch.inject(new Event(), WAIT_FOR_RESULT, GAME_UID));
        assertEquals(1, manager.targetedCalls);
        assertEquals(0, manager.untargetedCalls);
    }

    @Test
    public void android12And13RefuseTargetedInputAndKeepTheVirtualDisplayRoute() throws Exception {
        for (int sdk : new int[] {32, 33}) {
            TargetedManager manager = new TargetedManager();
            InputDispatch dispatch = new InputDispatch(manager, Event.class, sdk);

            assertFalse(dispatch.supportsTargetUid());
            CommandException failure = assertThrows(CommandException.class,
                    () -> dispatch.inject(new Event(), WAIT_FOR_RESULT, GAME_UID));
            assertEquals(Protocol.E_UNSUPPORTED, failure.code);
            assertEquals(0, manager.targetedCalls);
            assertEquals(0, manager.untargetedCalls);

            assertTrue(dispatch.inject(new Event(), WAIT_FOR_RESULT, null));
            assertEquals(1, manager.untargetedCalls);
        }
    }

    @Test
    public void missingTargetMethodAndInvalidUidNeverUseUntargetedInput() throws Exception {
        PlainManager plain = new PlainManager();
        InputDispatch missingMethod = new InputDispatch(plain, Event.class, 34);
        assertFalse(missingMethod.supportsTargetUid());
        assertThrows(CommandException.class, () -> missingMethod.inject(new Event(), WAIT_FOR_RESULT, GAME_UID));
        assertEquals(0, plain.untargetedCalls);

        TargetedManager manager = new TargetedManager();
        InputDispatch dispatch = new InputDispatch(manager, Event.class, 34);
        assertThrows(CommandException.class, () -> dispatch.inject(new Event(), WAIT_FOR_RESULT, -1));
        assertEquals(0, manager.targetedCalls);
        assertEquals(0, manager.untargetedCalls);
        assertTrue(dispatch.inject(new Event(), WAIT_FOR_RESULT, GAME_UID));
        assertEquals(1, manager.delivered);
    }

    public static class Event {
    }

    public static class PlainManager {
        int untargetedCalls;
        int delivered;

        public boolean injectInputEvent(Event event, int mode) {
            untargetedCalls++;
            delivered++;
            return true;
        }
    }

    public static final class TargetedManager extends PlainManager {
        int receivingUid = GAME_UID;
        int targetedCalls;
        boolean accept = true;

        public boolean injectInputEvent(Event event, int mode, int uid) {
            targetedCalls++;
            assertEquals(WAIT_FOR_RESULT, mode);
            if (uid != receivingUid) {
                throw new IllegalArgumentException("touch would be dispatched to another UID");
            }
            if (accept) {
                delivered++;
            }
            return accept;
        }
    }
}
