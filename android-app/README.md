# Blueprint Q&A (Android)

Take a photo of a floor plan (or pick one from the gallery) and ask questions about it,
e.g. "How many toilets are there?".

Kotlin + Jetpack Compose, single activity. Min Android 8.0 (API 26).

## Run

Open this folder in Android Studio, let it sync, press Run. Android Studio brings its own
JDK and installs the Android SDK; there is no `gradlew` script checked in, Studio uses
`gradle/wrapper/gradle-wrapper.properties` directly.

## Connecting the recognition model

Until a server address is set (gear icon), the app is in **demo mode**: answers are
made-up placeholders, labelled as such in the UI.

When the model is ready, expose it as:

```
POST {server}/ask      multipart/form-data
  image     the photo (JPEG or PNG)
  question  the question text

200 -> {"answer": 2, "unit": "count", "type": "count"}     same fields as questions.jsonl
else -> {"error": "why"}                                    shown to the user
```

Then enter the address in the app, e.g. `http://192.168.1.20:8000` (phone and PC on the
same Wi-Fi).

To run the model another way (on-device, different API), implement `BlueprintRecognizer`
in `app/src/main/java/com/example/blueprintqa/Recognizer.kt` and return it from
`MainViewModel.recognizer()`.
