package org.march7th.assistant.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** 外观设置。只影响界面，保存在界面自己的偏好里。 */
enum class ThemeMode { SYSTEM, LIGHT, DARK }

/** Material 配色之外的品牌色和状态色。 */
@Immutable
internal data class BrandColors(
    val card: Color,
    val heroStart: Color,
    val heroEnd: Color,
    val actionStart: Color,
    val actionEnd: Color,
    val onAction: Color,
    val success: Color,
    val successContainer: Color,
    val onSuccessContainer: Color,
    val warning: Color,
    val warningContainer: Color,
    val onWarningContainer: Color,
)

// 主色取桌面端的主题色 #F18CB9，按钮和文字用加深的同色相保证对比度；蓝色取自 Logo 里的相机和裙摆。
private val LightScheme = lightColorScheme(
    primary = Color(0xFFC2397B),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFD9E7),
    onPrimaryContainer = Color(0xFF3E0424),
    inversePrimary = Color(0xFFFFB0CE),
    secondary = Color(0xFF2E6BC2),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFD9E6FF),
    onSecondaryContainer = Color(0xFF052049),
    tertiary = Color(0xFF7A5B00),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFE9A8),
    onTertiaryContainer = Color(0xFF261A00),
    error = Color(0xFFBA1A1A),
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    background = Color(0xFFFFF8FA),
    onBackground = Color(0xFF221A1E),
    surface = Color(0xFFFFF8FA),
    onSurface = Color(0xFF221A1E),
    surfaceVariant = Color(0xFFF6E1E8),
    onSurfaceVariant = Color(0xFF5A474F),
    surfaceTint = Color(0xFFC2397B),
    inverseSurface = Color(0xFF382E32),
    inverseOnSurface = Color(0xFFFFECF1),
    outline = Color(0xFF8A747D),
    outlineVariant = Color(0xFFEFD9E0),
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color(0xFFFFF1F5),
    surfaceContainer = Color(0xFFFCEBF0),
    surfaceContainerHigh = Color(0xFFF8E4EA),
    surfaceContainerHighest = Color(0xFFF2DEE4),
)

private val DarkScheme = darkColorScheme(
    primary = Color(0xFFFFB0CE),
    onPrimary = Color(0xFF5C1138),
    primaryContainer = Color(0xFF7B2850),
    onPrimaryContainer = Color(0xFFFFD9E7),
    inversePrimary = Color(0xFFC2397B),
    secondary = Color(0xFFAAC7FF),
    onSecondary = Color(0xFF0A305F),
    secondaryContainer = Color(0xFF244777),
    onSecondaryContainer = Color(0xFFD7E3FF),
    tertiary = Color(0xFFF3C54B),
    onTertiary = Color(0xFF3F2E00),
    tertiaryContainer = Color(0xFF5B4300),
    onTertiaryContainer = Color(0xFFFFE08F),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
    background = Color(0xFF17131A),
    onBackground = Color(0xFFF0DFE5),
    surface = Color(0xFF17131A),
    onSurface = Color(0xFFF0DFE5),
    surfaceVariant = Color(0xFF3A3037),
    onSurfaceVariant = Color(0xFFD3BFC8),
    surfaceTint = Color(0xFFFFB0CE),
    inverseSurface = Color(0xFFF0DFE5),
    inverseOnSurface = Color(0xFF382E32),
    outline = Color(0xFF9C8A92),
    outlineVariant = Color(0xFF3E333A),
    surfaceContainerLowest = Color(0xFF120E14),
    surfaceContainerLow = Color(0xFF1E1921),
    surfaceContainer = Color(0xFF231D26),
    surfaceContainerHigh = Color(0xFF2D2730),
    surfaceContainerHighest = Color(0xFF38313B),
)

private val LightBrand = BrandColors(
    card = Color.White,
    heroStart = Color(0xFFFFE0EB),
    heroEnd = Color(0xFFE2EDFF),
    actionStart = Color(0xFFEC5F99),
    actionEnd = Color(0xFFD64688),
    onAction = Color.White,
    success = Color(0xFF1E7B4B),
    successContainer = Color(0xFFD5F3E0),
    onSuccessContainer = Color(0xFF0B3A22),
    warning = Color(0xFF8A5A00),
    warningContainer = Color(0xFFFFE9BF),
    onWarningContainer = Color(0xFF2C1B00),
)

private val DarkBrand = BrandColors(
    card = Color(0xFF211B24),
    heroStart = Color(0xFF4B2139),
    heroEnd = Color(0xFF1F2F52),
    actionStart = Color(0xFFFFA3C7),
    actionEnd = Color(0xFFF381B1),
    onAction = Color(0xFF4A0A2B),
    success = Color(0xFF7FDBA6),
    successContainer = Color(0xFF12492D),
    onSuccessContainer = Color(0xFFC5F2D6),
    warning = Color(0xFFF5C262),
    warningContainer = Color(0xFF574000),
    onWarningContainer = Color(0xFFFFE2A8),
)

internal val LocalBrand = staticCompositionLocalOf { LightBrand }

private val Base = Typography()
private val AppTypography = Typography(
    headlineSmall = Base.headlineSmall.copy(fontWeight = FontWeight.Bold, fontSize = 22.sp, lineHeight = 30.sp),
    titleLarge = Base.titleLarge.copy(fontWeight = FontWeight.Bold, fontSize = 20.sp, lineHeight = 28.sp),
    titleMedium = Base.titleMedium.copy(fontWeight = FontWeight.SemiBold, lineHeight = 24.sp),
    titleSmall = Base.titleSmall.copy(fontWeight = FontWeight.SemiBold),
    bodyLarge = Base.bodyLarge.copy(lineHeight = 26.sp),
    bodyMedium = Base.bodyMedium.copy(lineHeight = 22.sp),
    bodySmall = Base.bodySmall.copy(lineHeight = 18.sp),
    labelLarge = Base.labelLarge.copy(fontWeight = FontWeight.SemiBold),
)

internal val LogStyle = TextStyle(fontSize = 12.5.sp, lineHeight = 18.sp)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(22.dp),
    extraLarge = RoundedCornerShape(28.dp),
)

@Composable
internal fun M7ATheme(dark: Boolean, content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalBrand provides if (dark) DarkBrand else LightBrand) {
        MaterialTheme(
            colorScheme = if (dark) DarkScheme else LightScheme,
            typography = AppTypography,
            shapes = AppShapes,
            content = content,
        )
    }
}
