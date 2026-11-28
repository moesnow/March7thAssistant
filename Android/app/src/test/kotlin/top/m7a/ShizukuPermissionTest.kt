package top.m7a

import org.junit.Assert.assertEquals
import org.junit.Test

class ShizukuPermissionTest {
    @Test
    fun connectedServiceDoesNotRequireAManagerApk() {
        // Sui 没有管理 APK；Stellar 和其他兼容实现也不需要安装原版 Shizuku。
        for (granted in listOf(false, true)) {
            assertEquals(
                if (granted) PermissionState.READY else PermissionState.NOT_AUTHORIZED,
                shizukuPermissionState(
                    hasProvider = { false },
                    pingBinder = { true },
                    isAuthorized = { granted },
                ),
            )
        }
    }

    @Test
    fun connectedServiceDoesNotQueryInstalledPackages() {
        assertEquals(
            PermissionState.READY,
            shizukuPermissionState(
                hasProvider = { error("已连接服务时不应查询管理 APK") },
                pingBinder = { true },
                isAuthorized = { true },
            ),
        )
    }

    @Test
    fun disconnectedServiceDistinguishesMissingManagerFromStoppedService() {
        for (installed in listOf(false, true)) {
            assertEquals(
                if (installed) PermissionState.NOT_RUNNING else PermissionState.NOT_INSTALLED,
                shizukuPermissionState(
                    hasProvider = { installed },
                    pingBinder = { false },
                    isAuthorized = { error("未连接时不应检查授权") },
                ),
            )
        }
    }

    @Test
    fun binderLossDuringPermissionCheckIsNotReportedAsReadyOrMissing() {
        assertEquals(
            PermissionState.NOT_RUNNING,
            shizukuPermissionState(
                hasProvider = { false },
                pingBinder = { true },
                isAuthorized = { throw IllegalStateException("Binder 已断开") },
            ),
        )
    }

    @Test
    fun binderProbeFailureIsReportedAsUnavailable() {
        assertEquals(
            PermissionState.NOT_RUNNING,
            shizukuPermissionState(
                hasProvider = { error("连接检查失败时不应改报未安装") },
                pingBinder = { throw IllegalStateException("Binder 已断开") },
                isAuthorized = { error("未连接时不应检查授权") },
            ),
        )
    }
}
