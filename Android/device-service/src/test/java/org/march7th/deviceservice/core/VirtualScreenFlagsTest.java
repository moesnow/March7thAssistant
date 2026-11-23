package org.march7th.deviceservice.core;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class VirtualScreenFlagsTest {
    @Test
    public void keepsExistingFlagSetsAndReportsTheFlagsActuallyPassed() {
        for (int[] version : new int[][]{{29, 0x1cb}, {31, 0x1cb}, {33, 0x3dcb}, {34, 0xfdcb}, {36, 0xfdcb}}) {
            int flags = VirtualScreen.flagsFor(true, version[0]);
            assertEquals(version[1], flags);
            assertEquals(flags & ~0x100, VirtualScreen.flagsFor(false, version[0]));
            String names = VirtualScreen.flagDescription(flags);
            assertTrue(names.startsWith("0x" + Integer.toHexString(flags) + " PUBLIC|PRESENTATION|OWN_CONTENT_ONLY|"));
            assertEquals(version[0] >= 33, names.contains("TRUSTED"));
            assertEquals(version[0] >= 34, names.contains("OWN_FOCUS"));
        }
    }
}
