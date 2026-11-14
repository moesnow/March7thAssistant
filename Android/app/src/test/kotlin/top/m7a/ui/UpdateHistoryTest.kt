package top.m7a.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateHistoryTest {
    @Test
    fun showsOnlySkippedVersionsInDescendingOrderAndPrefersReleaseNotes() {
        val report = collectUpdateHistory(
            """
                ## v2026.11.8
                - 累计日志里的说明
                ## v2026.9.30
                - 九月更新
                ## v2026.10.31
                - 十月更新
                ## v2026.9.25
                - 当前版本
            """.trimIndent(),
            "v2026.9.25.0",
            release("v2026.11.8", "- 发布后的补充<!-- m7a:hide -->广告<!-- /m7a:hide -->"),
            includePrerelease = false,
        )

        assertEquals(listOf("v2026.11.8", "v2026.10.31", "v2026.9.30"), report.sections.map { it.version })
        assertEquals("- 发布后的补充", report.sections.first().markdown)
        assertFalse(report.partial)
    }

    @Test
    fun skipsBetaForStableAndRespectsDesktopVersionSuffixOrdering() {
        val document = """
            ## v2.0-1
            - 后续修订
            ## v2.0
            - 正式版
            ## v2.0-pre2
            - 公测候选
            ## v2.0-beta
            - 公测
            ## v2.0.dev1
            - 开发版
            ## v1.0
            - 旧版
        """.trimIndent()
        val target = release("v2.0.post1")
        val stable = collectUpdateHistory(document, "v1.0", target, includePrerelease = false)
        val beta = collectUpdateHistory(document, "v1.0", target, includePrerelease = true)

        assertEquals(listOf("v2.0.post1", "v2.0"), stable.sections.map { it.version })
        assertEquals("- 后续修订", stable.sections.first().markdown)
        assertEquals(listOf("v2.0.post1", "v2.0", "v2.0-pre2", "v2.0-beta", "v2.0.dev1"), beta.sections.map { it.version })
    }

    @Test
    fun ignoresFakeHeadingsAndPreservesFirstEntryForEquivalentVersions() {
        val report = collectUpdateHistory(
            """
                ## v3.0
                - 版本说明
                ~~~
                ## v9.0
                ~~~
                <!-- m7a:hide -->
                ## v8.0
                <!-- /m7a:hide -->
                ## v3.0.0
                - 重复版本
                ## v2.0-garbage
                - 无效版本
                ## v1.0 ##
                - 旧版
            """.trimIndent(),
            "1.0",
            release("v3.0"),
            includePrerelease = false,
        )

        assertEquals(listOf("v3.0"), report.sections.map { it.version })
        assertTrue(report.sections.single().markdown.startsWith("- 版本说明"))
        assertFalse(report.sections.single().markdown.contains("重复版本"))
        assertFalse(report.partial)
    }

    @Test
    fun partialHistoryKeepsLatestNoteWhenBetaTargetOrOldestVersionIsMissing() {
        val document = "## v2.0\n- 历史说明"
        val result = collectUpdateHistory(document, "v1.0", release("v3.0-beta", "- 当前公测"), true)

        assertTrue(result.partial)
        assertEquals(listOf("v3.0-beta", "v2.0"), result.sections.map { it.version })
        assertEquals("- 当前公测", result.sections.first().markdown)
    }

    @Test
    fun inconsistentTagOrVersionRangeTriggersHistoryFallback() {
        val target = release("v3.0")
        for (document in listOf("", "## v2.0\n- 目标缺失", "## v4.0\n- 未来版本\n## v3.0\n- 目标版本")) {
            assertThrows(IllegalArgumentException::class.java) { collectUpdateHistory(document, "v1.0", target, false) }
        }
        for (installed in listOf("invalid", "v3.0.0", "v4.0")) {
            assertThrows(IllegalArgumentException::class.java) {
                collectUpdateHistory("## v3.0\n- 目标版本", installed, target, false)
            }
        }
    }

    private fun release(version: String, notes: String = "") = UpdateRelease(version, null, notes, null)
}
