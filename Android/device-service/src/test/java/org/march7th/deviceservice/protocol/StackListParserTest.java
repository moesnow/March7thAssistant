package org.march7th.deviceservice.protocol;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.List;

/** 样例取自 Redmi Note 7（Android 10）和 MuMu（Android 12）上 {@code cmd activity stack list} 的真实输出。 */
public class StackListParserTest {
    private static final String GAME = "com.miHoYo.hkrpg";

    private static final String ANDROID_10_SDK_ON_TOP = String.join("\n",
            "Stack id=79 bounds=[0,0][1080,2340] displayId=0 userId=0",
            " configuration={1.0 460mcc11mnc [zh_CN] ldltr sw392dp w392dp h774dp 440dpi nrml long port night finger"
                    + " -keyb/v/h -nav/h winConfig={ mBounds=Rect(0, 0 - 1080, 2340) mAppBounds=Rect(0, 79 - 1080, 2210)"
                    + " mWindowingMode=fullscreen mDisplayWindowingMode=fullscreen mActivityType=standard"
                    + " mAlwaysOnTop=undefined mRotation=ROTATION_0} s.3867 themeChanged=0 themeChangedFlags=0"
                    + " extraData = Bundle[{}]}",
            "  taskId=122: com.miHoYo.hkrpg/com.mihoyo.combosdk.ComboSDKActivity bounds=[0,0][1080,2340] userId=0"
                    + " visible=true topActivity=ComponentInfo{com.miHoYo.hkrpg/com.miHoYo.sdk.platform.SdkActivity}",
            "",
            "Stack id=0 bounds=[0,0][1080,2340] displayId=0 userId=0",
            " configuration={1.0 460mcc11mnc [zh_CN] ldltr sw392dp w392dp h774dp 440dpi}",
            "  taskId=1: com.miui.home/com.miui.home.launcher.Launcher bounds=[0,0][1080,2340] userId=0 visible=true"
                    + " topActivity=ComponentInfo{com.miui.home/com.miui.home.launcher.Launcher}",
            "",
            "Stack id=90 bounds=[0,0][1080,2340] displayId=0 userId=0",
            " configuration={1.0 460mcc11mnc [zh_CN] ldltr}",
            "  taskId=131: com.android.browser/com.android.browser.launch.SplashActivity bounds=[0,0][1080,2340]"
                    + " userId=0 visible=false",
            "");

    private static final String ANDROID_12_ON_VIRTUAL_DISPLAY = String.join("\r\n",
            "RootTask id=129 bounds=[0,0][1280,720] displayId=5 userId=0",
            " configuration={1.0 302mcc780mnc [en_US] ldltr sw480dp w853dp h480dp 240dpi lrg long land finger"
                    + " -keyb/v/v dpad/v winConfig={ mBounds=Rect(0, 0 - 1280, 720) mAppBounds=Rect(0, 0 - 1280, 720)"
                    + " mMaxBounds=Rect(0, 0 - 1280, 720) mWindowingMode=fullscreen mDisplayWindowingMode=fullscreen"
                    + " mActivityType=standard mAlwaysOnTop=undefined mRotation=ROTATION_0} as.2 s.22"
                    + " fontWeightAdjustment=0}",
            "  taskId=129: com.miHoYo.hkrpg/com.mihoyo.combosdk.ComboSDKActivity bounds=[0,0][1280,720] userId=0"
                    + " visible=true topActivity=ComponentInfo{com.miHoYo.hkrpg/com.mihoyo.combosdk.ComboSDKActivity}",
            "",
            "RootTask id=130 bounds=[0,0][1280,720] displayId=0 userId=0",
            " configuration={1.0 302mcc780mnc [en_US] ldltr}",
            "  taskId=130: com.android.settings/com.android.settings.homepage.SettingsHomepageActivity"
                    + " bounds=[0,0][1280,720] userId=0 visible=true"
                    + " topActivity=ComponentInfo{com.android.settings/com.android.settings.SubSettings}",
            "");

    @Test
    public void android10StackWithSdkOnTop() {
        List<StackEntry> stacks = StackListParser.parse(ANDROID_10_SDK_ON_TOP);
        assertEquals(3, stacks.size());

        StackEntry game = stacks.get(0);
        assertEquals(79, game.stackId);
        assertEquals(0, game.displayId);
        assertTrue(game.visible);
        assertTrue(game.belongsTo(GAME));
        assertEquals(122, game.taskIdOf(GAME));
        assertEquals("com.miHoYo.hkrpg/com.miHoYo.sdk.platform.SdkActivity", game.topActivity);
        assertEquals("com.miHoYo.sdk.platform.SdkActivity", game.topActivityClass());

        assertFalse(stacks.get(1).belongsTo(GAME));
        assertEquals("com.miui.home.launcher.Launcher", stacks.get(1).topActivityClass());
    }

    @Test
    public void taskWithoutRunningActivityHasNoTop() {
        StackEntry browser = StackListParser.parse(ANDROID_10_SDK_ON_TOP).get(2);
        assertEquals(90, browser.stackId);
        assertNull(browser.topActivity);
        assertNull(browser.topActivityClass());
        assertFalse(browser.visible);
        assertEquals(131, (int) browser.taskIds.get(0));
        assertTrue(browser.belongsTo("com.android.browser"));
    }

    @Test
    public void android12RootTasksWithWindowsLineEndings() {
        List<StackEntry> stacks = StackListParser.parse(ANDROID_12_ON_VIRTUAL_DISPLAY);
        assertEquals(2, stacks.size());

        StackEntry game = stacks.get(0);
        assertEquals(129, game.stackId);
        assertEquals(5, game.displayId);
        assertTrue(game.belongsTo(GAME));
        assertEquals("com.mihoyo.combosdk.ComboSDKActivity", game.topActivityClass());

        StackEntry settings = stacks.get(1);
        assertEquals(0, settings.displayId);
        assertEquals("com.android.settings.SubSettings", settings.topActivityClass());
        assertFalse(settings.belongsTo(GAME));
    }

    @Test
    public void packagePrefixMustMatchExactly() {
        StackEntry entry = new StackEntry(1, 0, true, "com.miHoYo.hkrpg.beta/x.Main");
        entry.taskIds.add(5);
        entry.taskNames.add("com.miHoYo.hkrpg.beta/x.Main");
        assertFalse(entry.belongsTo(GAME));
        assertTrue(entry.belongsTo("com.miHoYo.hkrpg.beta"));
    }

    @Test
    public void shortClassNamesAreExpanded() {
        StackEntry entry = new StackEntry(1, 0, true, "com.example/.Main");
        assertEquals("com.example.Main", entry.topActivityClass());
    }

    @Test
    public void garbageProducesNothing() {
        assertTrue(StackListParser.parse("").isEmpty());
        assertTrue(StackListParser.parse("Error: unknown command\n  taskId=1: a/b visible=true\n").isEmpty());
    }
}
