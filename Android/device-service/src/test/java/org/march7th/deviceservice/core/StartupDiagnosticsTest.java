package org.march7th.deviceservice.core;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;

import static org.junit.Assert.*;

public class StartupDiagnosticsTest {
    @Test
    public void globalSnapshotCacheCannotOverwriteTheLastGameWindow() throws Exception {
        JSONArray windows = StartupDiagnostics.gameWindows("WINDOW MANAGER WINDOWS (dumpsys window game.pkg)\n"
                + "  Window #0 Window{abc u0 game.pkg/.Main}:\n"
                + "    mDisplayId=111 taskId=397\n    mHasSurface=true\n\n"
                + "  mCurrentFocus=Window{def u0 other.pkg/.Main}\n"
                + "  TaskSnapshotCache\n    Entry taskId=316\n    mDisplayId=0 isVisible=false\n", "game.pkg");
        assertEquals(1, windows.length());
        JSONObject window = windows.getJSONObject(0);
        assertEquals("397", window.getString("taskId"));
        assertEquals("111", window.getString("mDisplayId"));
        assertFalse(window.has("isVisible"));
        assertEquals("true", window.getString("mHasSurface"));
    }

    @Test
    public void globalFieldsCannotSupplyAMissingWindowTaskId() throws Exception {
        JSONArray windows = StartupDiagnostics.gameWindows("  Window #0 Window{abc u0 game.pkg/.Main}:\n"
                + "    mDisplayId=111\n\n  TaskSnapshotCache\n    Entry taskId=316\n", "game.pkg");
        assertFalse(windows.getJSONObject(0).has("taskId"));
    }

    @Test
    public void focusMustBeExplicitAndBelongToTheTargetDisplay() {
        // Android 12 的 DisplayContent.dump 把 mCurrentFocus 固定缩进两个空格，和 Display 标题同级。
        String dump = "  Display: mDisplayId=0\n  mLayoutSeq=4\n  mCurrentFocus=Window{abc u0 game.pkg/.Main}\n"
                + "  Display: mDisplayId=111\n  mLayoutSeq=5\n  mCurrentFocus=null\n";
        assertEquals("game", StartupDiagnostics.windowFocus(dump, "game.pkg", 0));
        assertEquals("none", StartupDiagnostics.windowFocus(dump, "game.pkg", 111));
        assertEquals("unknown", StartupDiagnostics.windowFocus(dump, "game.pkg", 112));
        assertEquals("other", StartupDiagnostics.windowFocus(dump.replace("=null", "=Window{abc u0 other.pkg/.Main}"), "game.pkg", 111));
        assertEquals("unknown", StartupDiagnostics.windowFocus("Permission Denial", "game.pkg", 111));
        assertEquals("unknown", StartupDiagnostics.windowFocus("  Display: mDisplayId=111\n"
                + "WINDOW MANAGER GLOBAL\n    mCurrentFocus=null\n", "game.pkg", 111));
    }

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
