package org.march7th.deviceservice.core;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;

import static org.junit.Assert.*;

public class StartupDiagnosticsTest {
    @Test
    public void windowVisibilityBelongsToTheReportedActivityAndDisplay() throws Exception {
        JSONArray windows = StartupDiagnostics.gameWindows("Window #0 Window{abc u0 game.pkg/.Main}:\n"
                + "    mDisplayId=103 taskId=355\n    mHasSurface=true\n    isVisible=false\n"
                + "Window #1 Window{def u0 other.pkg/.Login}:\n    isVisible=true\n"
                + "Window #2 Window{ghi u0 game.pkg/.SDK}:\n    mDisplayId=0\n", "game.pkg");
        assertEquals(2, windows.length());
        assertEquals("false", windows.getJSONObject(0).getString("isVisible"));
        assertEquals("103", windows.getJSONObject(0).getString("mDisplayId"));
        assertEquals("game.pkg/.SDK", windows.getJSONObject(1).getString("activity"));
    }

    @Test
    public void reportsAvailableBufferFieldsWithoutAssigningOtherLayersToTheGame() throws Exception {
        String old = "- Output Layer 0x123(game.pkg/.Main)";
        String blast = "Layer [100] SurfaceView[game.pkg/.Main](BLAST)#100";
        JSONObject layers = StartupDiagnostics.gameLayers("  " + old + "\n"
                + "      composition type=INVALID\n      buffer: slot=-1\n"
                + "  - Output Layer 0x456(another.pkg/.Main)\n      buffer: slot=2\n"
                + "    " + blast + "\n      visible reason= buffer=487 frame=12\n"
                + "    Some vendor section\n      slot=3\n", "game.pkg");
        assertEquals(2, layers.length());
        assertEquals("[\"composition type=INVALID\",\"slot=-1\"]", layers.getJSONArray(old).toString());
        assertEquals("[\"buffer=487\",\"frame=12\"]", layers.getJSONArray(blast).toString());
        assertEquals(0, StartupDiagnostics.gameLayers("Permission Denial", "game.pkg").length());
    }
}
