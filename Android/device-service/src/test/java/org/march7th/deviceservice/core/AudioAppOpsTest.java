package org.march7th.deviceservice.core;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class AudioAppOpsTest {
    @Test
    public void packageWithoutAnExplicitModeIsAllowed() {
        assertEquals("allow", AudioAppOps.parseMode("No operations.\nDefault mode: allow\n"));
    }

    @Test
    public void explicitModesAreReportedAsWritten() {
        assertEquals("ignore", AudioAppOps.parseMode("PLAY_AUDIO: ignore\n"));
        assertEquals("default", AudioAppOps.parseMode("Uid mode: CAMERA: ignore\nPLAY_AUDIO: default\n"));
    }
}
