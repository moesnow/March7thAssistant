package org.march7th.deviceservice.core;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class SideEffectsTest {
    @Test
    public void keepAwakePreservesDimmingWithThePanelOn() {
        assertEquals(1, SideEffects.userActivityFlags(false));
    }

    @Test
    public void keepAwakeUsesNormalActivityWithThePanelOff() {
        assertEquals(0, SideEffects.userActivityFlags(true));
    }
}
