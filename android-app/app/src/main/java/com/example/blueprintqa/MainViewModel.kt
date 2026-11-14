package com.example.blueprintqa

import android.app.Application
import android.content.Context
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import java.io.File

/** One question and its state: waiting (no answer, no error), answered, or failed. */
data class QaItem(
    val id: Long,
    val question: String,
    val answer: Answer? = null,
    val error: String? = null,
) {
    val isLoading: Boolean get() = answer == null && error == null
}

class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = app.getSharedPreferences("settings", Context.MODE_PRIVATE)

    /** Empty means demo mode (placeholder answers). */
    var serverUrl by mutableStateOf(prefs.getString(KEY_SERVER_URL, "").orEmpty())
        private set

    var imageUri by mutableStateOf<Uri?>(null)
        private set

    val items = mutableStateListOf<QaItem>()

    val isDemoMode: Boolean get() = serverUrl.isBlank()

    /** The answer whose evidence markers are drawn on the blueprint. */
    var highlightedId by mutableStateOf<Long?>(null)
        private set

    val highlightedEvidence: List<Evidence>
        get() = items.firstOrNull { it.id == highlightedId }?.answer?.evidence.orEmpty()

    fun highlight(id: Long) {
        highlightedId = id
    }

    private var pendingPhotoUri: Uri? = null
    private var nextId = 0L

    private fun recognizer(): BlueprintRecognizer =
        if (isDemoMode) DemoRecognizer() else HttpRecognizer(serverUrl)

    fun saveServerUrl(url: String) {
        var cleaned = url.trim()
        if (cleaned.isNotEmpty() && "://" !in cleaned) cleaned = "http://$cleaned"
        serverUrl = cleaned
        prefs.edit().putString(KEY_SERVER_URL, cleaned).apply()
    }

    /** Creates the file the camera app will write the photo into. */
    fun newPhotoUri(): Uri {
        val app = getApplication<Application>()
        val dir = File(app.cacheDir, "photos").apply { mkdirs() }
        val file = File(dir, "blueprint_${System.currentTimeMillis()}.jpg")
        return FileProvider.getUriForFile(app, "${app.packageName}.fileprovider", file)
            .also { pendingPhotoUri = it }
    }

    fun onPhotoTaken(success: Boolean) {
        val uri = pendingPhotoUri
        pendingPhotoUri = null
        if (success && uri != null) showImage(uri)
    }

    fun showImage(uri: Uri) {
        imageUri = uri
        items.clear()
        highlightedId = null
    }

    fun clearImage() {
        imageUri = null
        items.clear()
        highlightedId = null
    }

    fun ask(question: String) {
        val uri = imageUri ?: return
        val text = question.trim()
        if (text.isEmpty()) return
        val id = nextId++
        items.add(QaItem(id, text))
        resolve(id, text, uri)
    }

    fun retry(item: QaItem) {
        val uri = imageUri ?: return
        replace(item.id, QaItem(item.id, item.question))
        resolve(item.id, item.question, uri)
    }

    private fun resolve(id: Long, question: String, uri: Uri) {
        viewModelScope.launch {
            val result = try {
                QaItem(id, question, answer = recognizer().answer(getApplication(), uri, question))
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                QaItem(id, question, error = e.message ?: "Something went wrong")
            }
            // If the picture changed meanwhile the item is gone and the result is dropped.
            if (imageUri == uri) {
                replace(id, result)
                // Show the newest answer's markers straight away.
                if (result.answer?.evidence?.isNotEmpty() == true) highlightedId = id
            }
        }
    }

    private fun replace(id: Long, item: QaItem) {
        val index = items.indexOfFirst { it.id == id }
        if (index >= 0) items[index] = item
    }

    private companion object {
        const val KEY_SERVER_URL = "server_url"
    }
}
