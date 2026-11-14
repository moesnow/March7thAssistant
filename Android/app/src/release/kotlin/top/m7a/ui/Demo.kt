package top.m7a.ui

import android.content.Intent
import androidx.compose.runtime.Composable
import top.m7a.UpdatePreferences

/** 演示状态只存在于调试构建。 */
@Suppress("UNUSED_PARAMETER")
internal fun demoFrom(intent: Intent): Demo? = null

@Composable
@Suppress("UNUSED_PARAMETER")
internal fun rememberDemoUpdater(intent: Intent, preferences: UpdatePreferences): AppUpdater = error("仅调试构建支持预览")
