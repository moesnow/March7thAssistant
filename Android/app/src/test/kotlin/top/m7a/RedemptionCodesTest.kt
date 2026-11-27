package top.m7a

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class RedemptionCodesTest {
    private val now = Instant.parse("2026-11-27T08:00:00Z")

    @Test
    fun onlyChinaCodesThatHaveNotExpired() {
        val json = """[
            {"server": "cn", "expires_at": null, "code": "FOREVER"},
            {"server": "cn", "expires_at": "2026-11-27T16:00:01+08:00", "code": "TONIGHT"},
            {"server": "cn", "expires_at": "2026-11-27T16:00:00+08:00", "code": "JUSTEXPIRED"},
            {"server": "cn", "expires_at": "2026-11-28T00:00:00Z", "code": "UTC"},
            {"server": "cn", "expires_at": "2026-11-27T09:00:00", "code": "NAIVE"},
            {"server": "cn", "expires_at": "明天", "code": "BROKEN"},
            {"server": "global", "expires_at": null, "code": "GLOBAL"},
            {"server": "cn", "code": "FOREVER"},
            {"server": "cn", "expires_at": null, "code": ""},
            "坏数据"
        ]"""

        // 与电脑版 valid_codes_for_server 相同：没有时区按 UTC，读不出过期时间的跳过。
        assertEquals(listOf("FOREVER", "TONIGHT", "UTC", "NAIVE"), RedemptionCodeList.validCodes(json, now))
    }

    @Test
    fun aJsonArrayIsRequired() {
        for (broken in listOf("{}", "<html></html>", "")) {
            assertTrue(broken, runCatching { RedemptionCodeList.validCodes(broken, now) }.isFailure)
        }
    }
}
