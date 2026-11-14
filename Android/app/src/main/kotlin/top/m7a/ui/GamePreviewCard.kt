package top.m7a.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import top.m7a.GamePreviewSource
import top.m7a.R
import java.io.IOException

@Composable
internal fun GamePreviewCard(source: GamePreviewSource, displayId: Int, gameOnVirtualScreen: Boolean) {
    var expanded by remember(source) { mutableStateOf(false) }
    val title = tr(R.string.home_game_preview)
    val status = tr(if (expanded) R.string.state_expanded else R.string.state_collapsed)
    PanelCard(padding = PaddingValues(0.dp)) {
        SettingRow(
            title,
            modifier = Modifier.semantics { stateDescription = status },
            icon = M7Icons.Game,
            onClick = { expanded = !expanded },
            trailing = {
                Icon(
                    M7Icons.ExpandMore, null, Modifier.rotate(if (expanded) 180f else 0f),
                    tint = MaterialTheme.colorScheme.outline,
                )
            },
        )
        if (expanded) {
            GamePreviewImage(source, displayId, gameOnVirtualScreen)
        }
    }
}

@Composable
private fun GamePreviewImage(source: GamePreviewSource, displayId: Int, gameOnVirtualScreen: Boolean) {
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    var image by remember(source, displayId, gameOnVirtualScreen) { mutableStateOf<ImageBitmap?>(null) }
    var failed by remember(source, displayId, gameOnVirtualScreen) { mutableStateOf(false) }
    if (gameOnVirtualScreen) {
        LaunchedEffect(source, displayId, lifecycle) {
            lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
                failed = false
                try {
                    source.collectFrames(displayId) { frame ->
                        withContext(Dispatchers.Main) { image = frame.asImageBitmap() }
                    }
                } catch (_: IOException) {
                    failed = true
                } finally {
                    image = null
                }
            }
        }
    }
    Box(
        Modifier.fillMaxWidth().aspectRatio(16f / 9f).background(MaterialTheme.colorScheme.surfaceContainerHigh),
        contentAlignment = Alignment.Center,
    ) {
        val frame = image
        if (frame != null) {
            Image(
                frame, tr(R.string.home_game_preview), Modifier.fillMaxSize(),
                contentScale = ContentScale.Fit,
            )
        } else {
            BodyText(
                tr(if (failed) R.string.home_game_preview_unavailable else R.string.home_game_preview_waiting),
                Modifier.padding(16.dp),
            )
        }
    }
}
