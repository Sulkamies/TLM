package com.example.blueprintqa

import android.content.ActivityNotFoundException
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.geometry.isSpecified
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.sp
import coil.request.ImageRequest
import kotlin.math.min
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage

private val SUGGESTIONS = listOf(
    "How many toilets are there?",
    "How many rooms are there?",
    "How many windows are there?",
    "How many doors are there?",
    "What is the total floor area?",
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            BlueprintTheme { App() }
        }
    }
}

@Composable
private fun App(vm: MainViewModel = viewModel()) {
    val context = LocalContext.current
    var showSettings by rememberSaveable { mutableStateOf(false) }

    val takePicture = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { saved ->
        vm.onPhotoTaken(saved)
    }
    val pickImage = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) vm.showImage(uri)
    }
    val onCamera: () -> Unit = {
        try {
            takePicture.launch(vm.newPhotoUri())
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(context, "No camera app found", Toast.LENGTH_SHORT).show()
        }
    }
    val onGallery: () -> Unit = {
        pickImage.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
    }

    val uri = vm.imageUri
    if (uri == null) {
        HomeScreen(
            isDemoMode = vm.isDemoMode,
            onCamera = onCamera,
            onGallery = onGallery,
            onSettings = { showSettings = true },
        )
    } else {
        BlueprintScreen(
            vm = vm,
            imageUri = uri,
            onCamera = onCamera,
            onGallery = onGallery,
            onSettings = { showSettings = true },
        )
    }

    if (showSettings) {
        SettingsDialog(
            currentUrl = vm.serverUrl,
            onSave = {
                vm.saveServerUrl(it)
                showSettings = false
            },
            onDismiss = { showSettings = false },
        )
    }
}

// ---------------------------------------------------------------- Home

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HomeScreen(
    isDemoMode: Boolean,
    onCamera: () -> Unit,
    onGallery: () -> Unit,
    onSettings: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Blueprint Q&A") },
                actions = {
                    IconButton(onClick = onSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.weight(1f))
            Text(
                "Ask a floor plan anything",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "Photograph a blueprint, then ask how many toilets, rooms or windows it has.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(32.dp))
            Button(
                onClick = onCamera,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
            ) {
                Text("Take a photo", style = MaterialTheme.typography.titleMedium)
            }
            Spacer(Modifier.height(12.dp))
            OutlinedButton(
                onClick = onGallery,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
            ) {
                Text("Choose from gallery", style = MaterialTheme.typography.titleMedium)
            }
            Spacer(Modifier.height(24.dp))
            Text(
                "For best results shoot from straight above, fit the whole drawing in the frame and avoid glare.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.weight(1f))
            if (isDemoMode) {
                DemoBanner(onClick = onSettings)
            }
        }
    }
}

@Composable
private fun DemoBanner(onClick: () -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.tertiaryContainer,
        contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick),
    ) {
        Text(
            "Demo mode: answers are placeholders until a recognition server is set. Tap to connect.",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(12.dp),
        )
    }
}

// ---------------------------------------------------------------- Blueprint + questions

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BlueprintScreen(
    vm: MainViewModel,
    imageUri: Uri,
    onCamera: () -> Unit,
    onGallery: () -> Unit,
    onSettings: () -> Unit,
) {
    BackHandler { vm.clearImage() }

    var showFullscreen by remember { mutableStateOf(false) }
    var showNewMenu by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()
    val headerCount = if (vm.isDemoMode) 2 else 1

    LaunchedEffect(vm.items.size) {
        if (vm.items.isNotEmpty()) listState.animateScrollToItem(headerCount + vm.items.size - 1)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Your drawing", maxLines = 1) },
                navigationIcon = {
                    IconButton(onClick = { vm.clearImage() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    Box {
                        IconButton(onClick = { showNewMenu = true }) {
                            Icon(Icons.Default.Add, contentDescription = "New drawing")
                        }
                        DropdownMenu(expanded = showNewMenu, onDismissRequest = { showNewMenu = false }) {
                            DropdownMenuItem(
                                text = { Text("Take a photo") },
                                onClick = {
                                    showNewMenu = false
                                    onCamera()
                                },
                            )
                            DropdownMenuItem(
                                text = { Text("Choose from gallery") },
                                onClick = {
                                    showNewMenu = false
                                    onGallery()
                                },
                            )
                        }
                    }
                    IconButton(onClick = onSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                },
            )
        },
        bottomBar = { AskBar(onAsk = vm::ask) },
    ) { padding ->
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(
                start = 16.dp,
                end = 16.dp,
                top = padding.calculateTopPadding() + 8.dp,
                bottom = padding.calculateBottomPadding() + 12.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item(key = "image") {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(260.dp)
                        .clip(RoundedCornerShape(16.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                        .clickable { showFullscreen = true },
                ) {
                    BlueprintImage(
                        imageUri = imageUri,
                        evidence = vm.highlightedEvidence,
                        modifier = Modifier.fillMaxSize(),
                    )
                    Text(
                        "Tap to zoom",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White,
                        modifier = Modifier
                            .align(Alignment.BottomEnd)
                            .padding(8.dp)
                            .background(Color.Black.copy(alpha = 0.55f), RoundedCornerShape(8.dp))
                            .padding(horizontal = 8.dp, vertical = 4.dp),
                    )
                }
            }
            if (vm.isDemoMode) {
                item(key = "demo") { DemoBanner(onClick = onSettings) }
            }
            if (vm.items.isEmpty()) {
                item(key = "empty") {
                    Text(
                        "Type a question below or pick one of the suggestions.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 24.dp),
                    )
                }
            }
            items(vm.items, key = { it.id }) { item ->
                QaRow(
                    item = item,
                    isHighlighted = item.id == vm.highlightedId,
                    onRetry = { vm.retry(item) },
                    onShowEvidence = {
                        vm.highlight(item.id)
                        showFullscreen = true
                    },
                )
            }
        }
    }

    if (showFullscreen) {
        ZoomableImageDialog(
            imageUri = imageUri,
            evidence = vm.highlightedEvidence,
            onDismiss = { showFullscreen = false },
        )
    }
}

private val MarkerColor = Color(0xFFE53935)

/** The blueprint with numbered evidence boxes drawn over it. */
@Composable
private fun BlueprintImage(
    imageUri: Uri,
    evidence: List<Evidence>,
    modifier: Modifier = Modifier,
    fullResolution: Boolean = false,
) {
    val context = LocalContext.current
    // Only the aspect ratio is used: it tells where the fitted image sits inside this box.
    var imageSize by remember(imageUri) { mutableStateOf(Size.Unspecified) }
    val textMeasurer = rememberTextMeasurer()
    val model = remember(imageUri, fullResolution) {
        ImageRequest.Builder(context)
            .data(imageUri)
            .apply { if (fullResolution) size(coil.size.Size.ORIGINAL) }
            .build()
    }

    Box(modifier) {
        AsyncImage(
            model = model,
            contentDescription = "Blueprint",
            contentScale = ContentScale.Fit,
            modifier = Modifier.fillMaxSize(),
            onSuccess = { imageSize = it.painter.intrinsicSize },
        )
        val size = imageSize
        if (evidence.isNotEmpty() && size.isSpecified && size.width > 0f && size.height > 0f) {
            Canvas(Modifier.fillMaxSize()) {
                val scale = min(this.size.width / size.width, this.size.height / size.height)
                val width = size.width * scale
                val height = size.height * scale
                val left = (this.size.width - width) / 2f
                val top = (this.size.height - height) / 2f
                val badgeRadius = 8.dp.toPx()
                val numberStyle = TextStyle(color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold)

                evidence.forEachIndexed { index, e ->
                    val topLeft = Offset(left + e.x * width, top + e.y * height)
                    val boxSize = Size(e.w * width, e.h * height)
                    drawRect(MarkerColor.copy(alpha = 0.15f), topLeft, boxSize)
                    drawRect(MarkerColor, topLeft, boxSize, style = Stroke(1.5.dp.toPx()))

                    drawCircle(MarkerColor, badgeRadius, topLeft)
                    val number = textMeasurer.measure((index + 1).toString(), numberStyle)
                    drawText(
                        number,
                        topLeft = Offset(
                            topLeft.x - number.size.width / 2f,
                            topLeft.y - number.size.height / 2f,
                        ),
                    )
                }
            }
        }
    }
}

@Composable
private fun QaRow(item: QaItem, isHighlighted: Boolean, onRetry: () -> Unit, onShowEvidence: () -> Unit) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        // The question, right-aligned like a sent message.
        Surface(
            color = MaterialTheme.colorScheme.primary,
            contentColor = MaterialTheme.colorScheme.onPrimary,
            shape = RoundedCornerShape(18.dp, 18.dp, 4.dp, 18.dp),
            modifier = Modifier
                .align(Alignment.End)
                .widthIn(max = 300.dp),
        ) {
            Text(item.question, modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp))
        }

        // The answer, left-aligned.
        Surface(
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(18.dp, 18.dp, 18.dp, 4.dp),
            modifier = Modifier
                .align(Alignment.Start)
                .widthIn(max = 300.dp),
        ) {
            Box(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                val answer = item.answer
                when {
                    answer != null -> AnswerContent(answer, isHighlighted, onShowEvidence)
                    item.error != null -> Column {
                        Text(
                            "Couldn't get an answer",
                            style = MaterialTheme.typography.titleSmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                        Text(item.error, style = MaterialTheme.typography.bodySmall)
                        TextButton(onClick = onRetry, contentPadding = PaddingValues(0.dp)) {
                            Text("Try again")
                        }
                    }
                    else -> Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(10.dp))
                        Text("Reading the drawing…", style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}

@Composable
private fun AnswerContent(answer: Answer, isHighlighted: Boolean, onShowEvidence: () -> Unit) {
    Column {
        if (answer.type == "text" || answer.value.length > 12) {
            Text(answer.value, style = MaterialTheme.typography.bodyLarge)
        } else {
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    answer.value,
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.SemiBold,
                )
                val unit = answer.unit
                if (unit != null && unit != "count") {
                    Spacer(Modifier.width(6.dp))
                    Text(
                        unit,
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.padding(bottom = 6.dp),
                    )
                }
            }
        }
        if (answer.isDemo) {
            Text(
                "Placeholder, not a real reading",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (!answer.working.isNullOrBlank()) {
            Text(
                answer.working,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
        if (answer.evidence.isNotEmpty()) {
            val count = answer.evidence.size
            TextButton(onClick = onShowEvidence, contentPadding = PaddingValues(0.dp)) {
                Text(
                    (if (isHighlighted) "Marked on the drawing" else "Show on the drawing") +
                        " ($count)",
                )
            }
        }
    }
}

@Composable
private fun AskBar(onAsk: (String) -> Unit) {
    var text by rememberSaveable { mutableStateOf("") }
    val submit = {
        if (text.isNotBlank()) {
            onAsk(text)
            text = ""
        }
    }

    Surface(tonalElevation = 3.dp) {
        Column(
            Modifier
                .fillMaxWidth()
                .windowInsetsPadding(WindowInsets.ime.union(WindowInsets.navigationBars)),
        ) {
            LazyRow(
                contentPadding = PaddingValues(horizontal = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(SUGGESTIONS) { suggestion ->
                    SuggestionChip(onClick = { onAsk(suggestion) }, label = { Text(suggestion) })
                }
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 12.dp, end = 8.dp, bottom = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it },
                    placeholder = { Text("Ask a question") },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(28.dp),
                    maxLines = 3,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(onSend = { submit() }),
                )
                Spacer(Modifier.width(8.dp))
                FilledIconButton(onClick = submit, enabled = text.isNotBlank()) {
                    Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Ask")
                }
            }
        }
    }
}

// ---------------------------------------------------------------- Dialogs

@Composable
private fun ZoomableImageDialog(imageUri: Uri, evidence: List<Evidence>, onDismiss: () -> Unit) {
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        var scale by remember { mutableFloatStateOf(1f) }
        var offset by remember { mutableStateOf(Offset.Zero) }
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black)
                .pointerInput(Unit) {
                    detectTransformGestures { _, pan, zoom, _ ->
                        scale = (scale * zoom).coerceIn(1f, 8f)
                        offset = if (scale == 1f) Offset.Zero else offset + pan
                    }
                },
        ) {
            BlueprintImage(
                imageUri = imageUri,
                evidence = evidence,
                fullResolution = true,
                modifier = Modifier
                    .fillMaxSize()
                    .graphicsLayer {
                        scaleX = scale
                        scaleY = scale
                        translationX = offset.x
                        translationY = offset.y
                    },
            )
            IconButton(
                onClick = onDismiss,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .statusBarsPadding()
                    .padding(8.dp),
            ) {
                Icon(Icons.Default.Close, contentDescription = "Close", tint = Color.White)
            }
        }
    }
}

@Composable
private fun SettingsDialog(currentUrl: String, onSave: (String) -> Unit, onDismiss: () -> Unit) {
    var url by rememberSaveable { mutableStateOf(currentUrl) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Recognition server") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    "Address of the server that answers questions. Leave empty to stay in demo mode with placeholder answers.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it },
                    label = { Text("Server address") },
                    placeholder = { Text("http://192.168.1.20:8000") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = { TextButton(onClick = { onSave(url) }) { Text("Save") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
