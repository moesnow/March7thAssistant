package top.m7a.ui

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.net.URI
import javax.net.ssl.HttpsURLConnection

internal const val UPDATE_APK_DIR = "app-updates"

internal class UpdateApkStore(context: Context, private val installedVersion: String) {
    private val directory = File(context.cacheDir, UPDATE_APK_DIR)
    private val readyDirectory = File(directory, "ready")
    private val packageName = context.packageName
    private val packages = context.packageManager

    suspend fun cleanAfterStartup() = useCache {
        // 进程被杀时 Mirror酱的临时文件只能在下次启动后清理。
        directory.listFiles()?.filter { it.name.endsWith(".mirror.part") }?.forEach(File::delete)
        val installed = UpdateVersion.parse(installedVersion)
        readyDirectory.listFiles()?.filter { it.extension == "apk" }?.forEach { file ->
            val version = UpdateVersion.parse(file.nameWithoutExtension.substringBeforeLast('-'))
            if (installed != null && version != null && version <= installed) file.delete()
        }
    }

    suspend fun restore(release: UpdateRelease?): Boolean = useCache {
        val digest = release?.sha256?.let(::normalizeUpdateSha256)
        if (release == null || digest == null) {
            directory.listFiles()?.filter(File::isFile)?.forEach(File::delete)
            readyDirectory.listFiles()?.filter(File::isFile)?.forEach(File::delete)
            return@useCache false
        }
        val file = destination(release, digest)
        prune(release, digest)
        if (!file.exists()) return@useCache false
        try {
            validate(file, release, digest)
            true
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            file.delete()
            false
        }
    }

    suspend fun download(
        release: UpdateRelease,
        candidate: ApkDownload,
        source: UpdateSource,
        openConnection: (URI) -> HttpsURLConnection,
        onState: suspend (UpdatePackageState) -> Unit,
    ) = useCache {
        if (!readyDirectory.isDirectory && !readyDirectory.mkdirs()) throw UpdateException(UpdateProblem.SPACE)
        prune(release, candidate.sha256)
        val target = destination(release, candidate.sha256)
        val part = partFile(release, candidate.sha256, source)
        try {
            transferApk(candidate, part, source, openConnection) { received, total ->
                onState(UpdatePackageState.Downloading(received, total))
            }
            onState(UpdatePackageState.Verifying)
            validate(part, release, candidate.sha256)
            if (!part.renameTo(target)) throw UpdateException(UpdateProblem.SPACE)
            partFile(release, candidate.sha256, UpdateSource.GITHUB).delete()
        } catch (error: Exception) {
            if (source == UpdateSource.MIRROR || (error is UpdateException && error.problem == UpdateProblem.PACKAGE)) {
                part.delete()
            }
            throw error
        }
    }

    /** 安装前再次校验，系统可能已在等待安装期间清空缓存。 */
    suspend fun verifiedApk(release: UpdateRelease): File = useCache {
        val digest = release.sha256?.let(::normalizeUpdateSha256) ?: throw UpdateException(UpdateProblem.PACKAGE)
        val file = destination(release, digest)
        try {
            validate(file, release, digest)
            file
        } catch (error: IOException) {
            file.delete()
            throw error
        }
    }

    private fun destination(release: UpdateRelease, digest: String) = File(readyDirectory, "${release.version}-$digest.apk")

    private fun partFile(release: UpdateRelease, digest: String, source: UpdateSource) =
        File(directory, "${release.version}-$digest.${source.name.lowercase()}.part")

    private fun prune(release: UpdateRelease, digest: String) {
        val keepPartial = setOf(
            partFile(release, digest, UpdateSource.GITHUB).name,
            partFile(release, digest, UpdateSource.MIRROR).name,
        )
        directory.listFiles()?.filter { it.isFile && it.name !in keepPartial }?.forEach(File::delete)
        readyDirectory.listFiles()?.filter { it.isFile && it.name != destination(release, digest).name }?.forEach(File::delete)
    }

    @Suppress("DEPRECATION")
    private suspend fun validate(file: File, release: UpdateRelease, digest: String) {
        val installedName = UpdateVersion.parse(installedVersion)
        val incomingName = UpdateVersion.parse(release.version)
        if (installedName == null || incomingName == null || incomingName <= installedName) {
            throw UpdateException(UpdateProblem.PACKAGE)
        }
        if (!matchesApkDigest(file, release.sizeBytes, digest)) throw UpdateException(UpdateProblem.PACKAGE)

        val incoming = try {
            // AOSP Android 10 的归档解析只在 GET_SIGNATURES 置位时读取证书。
            packages.getPackageArchiveInfo(file.path, PackageManager.GET_SIGNING_CERTIFICATES or PackageManager.GET_SIGNATURES)
        } catch (_: Exception) {
            null
        } ?: throw UpdateException(UpdateProblem.PACKAGE)
        val installed = packages.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES)
        val incomingSigners = incoming.signers()
        if (incoming.packageName != packageName || incoming.versionName != release.version ||
            incoming.longVersionCode <= installed.longVersionCode ||
            (incoming.applicationInfo?.minSdkVersion ?: Int.MAX_VALUE) > Build.VERSION.SDK_INT ||
            incomingSigners.isEmpty() || incomingSigners != installed.signers()
        ) throw UpdateException(UpdateProblem.PACKAGE)
    }

    private fun PackageInfo.signers() = signingInfo?.apkContentsSigners?.toSet().orEmpty()

    // 切换渠道时旧查询可能仍在清理缓存，串行读写避免它影响新下载。
    private suspend fun <T> useCache(action: suspend () -> T): T = withContext(Dispatchers.IO) {
        cacheLock.withLock { action() }
    }

    private companion object {
        val cacheLock = Mutex()
    }
}
