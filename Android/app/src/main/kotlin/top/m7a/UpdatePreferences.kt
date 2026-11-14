package top.m7a

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import top.m7a.ui.UpdateChannel
import top.m7a.ui.UpdateSource
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

internal class UpdatePreferences(context: Context) {
    private val prefs = context.getSharedPreferences("app-update", Context.MODE_PRIVATE)
    private val cdkPath = File(context.noBackupFilesDir, "mirror-cdk")
    private val cdkFile = AtomicFile(cdkPath)
    // Android 10 的 AtomicFile 从带 .bak 后缀的文件恢复被中断的写入。
    private val cdkBackup = File(cdkPath.path + ".bak")

    var source: UpdateSource
        get() {
            val saved = prefs.getString("source", null)
            return UpdateSource.entries.firstOrNull { it.name == saved } ?: UpdateSource.GITHUB
        }
        set(value) {
            prefs.edit().putString("source", value.name).apply()
        }

    var channel: UpdateChannel
        get() = if (prefs.getBoolean("include-prerelease", false)) UpdateChannel.BETA else UpdateChannel.STABLE
        set(value) {
            prefs.edit().putBoolean("include-prerelease", value.includesPrerelease).remove("detected-version").apply()
        }

    val detectedVersion: String? get() = prefs.getString("detected-version", null)

    fun setDetectedVersion(version: String?) {
        prefs.edit().putString("detected-version", version).apply()
    }

    val hasCdk: Boolean get() = cdkPath.exists() || cdkBackup.exists()

    suspend fun readCdk(): String? = withContext(Dispatchers.IO) {
        cdkLock.withLock {
            if (!hasCdk) return@withLock null
            val stored = cdkFile.readFully()
            check(stored.size > IV_BYTES + TAG_BITS / 8)
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, checkNotNull(key()), GCMParameterSpec(TAG_BITS, stored, 0, IV_BYTES))
            cipher.doFinal(stored, IV_BYTES, stored.size - IV_BYTES).decodeToString()
        }
    }

    suspend fun saveCdk(value: String) = withContext(Dispatchers.IO) {
        cdkLock.withLock {
            require(value.isNotBlank())
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.ENCRYPT_MODE, key() ?: newKey())
            val iv = cipher.iv
            check(iv.size == IV_BYTES)
            val stored = iv + cipher.doFinal(value.encodeToByteArray())
            val stream = cdkFile.startWrite()
            try {
                stream.write(stored)
                stream.fd.sync()
            } catch (error: Exception) {
                cdkFile.failWrite(stream)
                throw error
            }
            cdkFile.finishWrite(stream)
            check(cdkFile.readFully().contentEquals(stored))
        }
    }

    suspend fun removeCdk() = withContext(Dispatchers.IO) {
        cdkLock.withLock {
            cdkFile.delete()
            check(!hasCdk)
        }
    }

    private fun key(): SecretKey? = KeyStore.getInstance(KEYSTORE).run {
        load(null)
        getKey(KEY_ALIAS, null) as? SecretKey
    }

    private fun newKey(): SecretKey = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE).run {
        init(
            KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        generateKey()
    }

    private companion object {
        val cdkLock = Mutex()
        const val KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "m7a-mirror-cdk"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val IV_BYTES = 12
        const val TAG_BITS = 128
    }
}
