# External services

User data MUST NOT be sent to any service not listed here (R7.4). Adding a service, or widening what data
it receives, requires human approval. Append-only.

| Service | Used by | Data sent | Approved by | Date | Notes |
|---|---|---|---|---|---|
| Google Gemini API (`generativelanguage.googleapis.com`, SDK `google-genai`) | A2 Question Interpreter, via `src/blueprint_qa/common/llm.py` | The user's question text and locale hint | ry | 2026-11-14 | Model set in `config/llm.yaml` (`gemini-2.5-flash`). Key: `GEMINI_API_KEY`. **Plan images are NOT yet approved**, see OPEN_QUESTIONS Q2. Check the API terms on data use and retention before sending real customer data. |
| Google Gemini API (update) | A2, via `common/llm.py` | Unchanged: question text and locale hint | ry | 2026-11-14 | Model changed to `gemini-3.8-flash` (D-008); `gemini-2.5-flash` is closed to new users. |
