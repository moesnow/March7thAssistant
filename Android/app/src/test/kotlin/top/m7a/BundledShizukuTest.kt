package top.m7a

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File
import java.security.MessageDigest
import java.util.HexFormat

class BundledShizukuTest {
    @Test
    fun bundledAssetMatchesTheOfficialRelease() {
        val apk = File("src/main/assets", BUNDLED_SHIZUKU_APK)
        val digest = MessageDigest.getInstance("SHA-256").digest(apk.readBytes())
        assertEquals(
            "6e273ab0e991c4e79bc8b1bbb9b9dd739ccac1a8712a541a214078886b7b790f",
            HexFormat.of().formatHex(digest),
        )
    }
}
