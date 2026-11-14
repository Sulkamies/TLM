package com.example.blueprintqa

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF1F4E8C),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD6E3FF),
    onPrimaryContainer = Color(0xFF001B3F),
    secondary = Color(0xFF555F71),
    secondaryContainer = Color(0xFFD9E3F8),
    tertiaryContainer = Color(0xFFFFE9B0),
    onTertiaryContainer = Color(0xFF3A2E00),
    background = Color(0xFFF8F9FD),
    surface = Color(0xFFF8F9FD),
    surfaceVariant = Color(0xFFE6EAF2),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFA9C7FF),
    onPrimary = Color(0xFF003063),
    primaryContainer = Color(0xFF0D3F7A),
    onPrimaryContainer = Color(0xFFD6E3FF),
    secondary = Color(0xFFBDC7DC),
    secondaryContainer = Color(0xFF3D4758),
    tertiaryContainer = Color(0xFF544600),
    onTertiaryContainer = Color(0xFFFFE9B0),
    background = Color(0xFF111418),
    surface = Color(0xFF111418),
    surfaceVariant = Color(0xFF2A2F37),
)

@Composable
fun BlueprintTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content,
    )
}
