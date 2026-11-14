package com.example.blueprintqa

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.abs

/**
 * One answer about a drawing. Mirrors a row of the dataset's questions.jsonl:
 * {"answer": 2, "unit": "count", "type": "count"}.
 */
data class Answer(
    val value: String,
    val unit: String? = null,
    val type: String? = null,
    /** True when the answer is a placeholder and did not come from the real model. */
    val isDemo: Boolean = false,
    /** The model's short notes on how it got the answer. */
    val working: String? = null,
    /** Where on the drawing the answer came from: one entry per counted item or label used. */
    val evidence: List<Evidence> = emptyList(),
)

/** A box on the drawing, as fractions (0..1) of the image's width and height. */
data class Evidence(val label: String, val x: Float, val y: Float, val w: Float, val h: Float)

/** The seam between the UI and the recognition system. Swap implementations here. */
interface BlueprintRecognizer {
    suspend fun answer(context: Context, image: Uri, question: String): Answer
}

/**
 * Placeholder used until the trained model is reachable. Returns made-up but
 * stable values so the UI can be exercised end to end.
 */
class DemoRecognizer : BlueprintRecognizer {
    override suspend fun answer(context: Context, image: Uri, question: String): Answer {
        delay(1200)
        val q = question.lowercase()
        val seed = abs((q + image.toString()).hashCode())
        return when {
            "area" in q || "m²" in q || "square" in q || "pinta-ala" in q ->
                Answer("%.1f".format(40 + seed % 900 / 10.0), unit = "m²", type = "area", isDemo = true)
            "how long" in q || "length" in q || "perimeter" in q || "pituus" in q ->
                Answer("%.1f".format(5 + seed % 400 / 10.0), unit = "m", type = "length", isDemo = true)
            "how many" in q || "count" in q || "number of" in q || "kuinka monta" in q || "montako" in q ->
                Answer((1 + seed % 6).toString(), unit = "count", type = "count", isDemo = true)
            else ->
                Answer("The recognition model isn't connected yet.", type = "text", isDemo = true)
        }
    }
}

/**
 * Talks to the recognition server.
 *
 *   POST {baseUrl}/ask   multipart/form-data: image=<file>, question=<text>
 *   200 -> {"answer": 2, "unit": "count", "type": "count"}
 *   else -> {"error": "..."} (optional)
 */
class HttpRecognizer(private val baseUrl: String) : BlueprintRecognizer {

    override suspend fun answer(context: Context, image: Uri, question: String): Answer =
        withContext(Dispatchers.IO) {
            val imageBytes = context.contentResolver.openInputStream(image)?.use { it.readBytes() }
                ?: throw IOException("Could not read the picture")
            val mime = context.contentResolver.getType(image) ?: "image/jpeg"
            val extension = if (mime.endsWith("png")) "png" else "jpg"

            val boundary = "----blueprintqa" + System.nanoTime()
            val body = ByteArrayOutputStream().apply {
                fun text(s: String) = write(s.toByteArray(Charsets.UTF_8))
                text("--$boundary\r\n")
                text("Content-Disposition: form-data; name=\"question\"\r\n\r\n")
                text(question)
                text("\r\n--$boundary\r\n")
                text("Content-Disposition: form-data; name=\"image\"; filename=\"blueprint.$extension\"\r\n")
                text("Content-Type: $mime\r\n\r\n")
                write(imageBytes)
                text("\r\n--$boundary--\r\n")
            }.toByteArray()

            val connection = URL(baseUrl.trimEnd('/') + "/ask").openConnection() as HttpURLConnection
            try {
                connection.requestMethod = "POST"
                connection.doOutput = true
                connection.connectTimeout = 15_000
                connection.readTimeout = 120_000
                connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
                connection.setRequestProperty("Accept", "application/json")
                connection.setFixedLengthStreamingMode(body.size)
                connection.outputStream.use { it.write(body) }

                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val response = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
                val json = runCatching { JSONObject(response) }.getOrNull()

                if (code !in 200..299) {
                    val detail = json?.optString("error").orEmpty()
                    throw IOException(detail.ifEmpty { "Server returned $code" })
                }
                if (json == null || json.isNull("answer")) {
                    throw IOException("Server sent no answer")
                }
                Answer(
                    value = formatValue(json.get("answer")),
                    unit = json.stringOrNull("unit"),
                    type = json.stringOrNull("type"),
                    working = json.stringOrNull("working"),
                    evidence = parseEvidence(json),
                )
            } finally {
                connection.disconnect()
            }
        }

    private fun parseEvidence(json: JSONObject): List<Evidence> {
        val array = json.optJSONArray("evidence") ?: return emptyList()
        val result = ArrayList<Evidence>(array.length())
        for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: continue
            result.add(
                Evidence(
                    label = item.optString("label"),
                    x = item.optDouble("x", 0.0).toFloat(),
                    y = item.optDouble("y", 0.0).toFloat(),
                    w = item.optDouble("w", 0.0).toFloat(),
                    h = item.optDouble("h", 0.0).toFloat(),
                )
            )
        }
        return result
    }

    private fun JSONObject.stringOrNull(key: String): String? =
        if (isNull(key)) null else optString(key).ifEmpty { null }

    private fun formatValue(raw: Any): String = when (raw) {
        is Int, is Long -> raw.toString()
        is Number -> {
            val d = raw.toDouble()
            if (d == Math.floor(d) && abs(d) < 1e12) d.toLong().toString()
            else "%.2f".format(d).trimEnd('0').trimEnd('.', ',')
        }
        else -> raw.toString()
    }
}
