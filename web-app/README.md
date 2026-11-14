# Blueprint Q&A (web page)

A single static page, `index.html`, with no build step and no libraries. Add a picture of a floor plan,
ask a question, and see the answer with numbered boxes on the drawing. Works on desktop and phones
(zoom with the wheel, buttons or a two-finger pinch; "Take a photo" opens the phone camera).

It contains **no recognition code**. It only needs a server that offers the same endpoint as the apps:

```
POST /ask      multipart/form-data: image, question
200 -> {"answer": 2, "unit": "count", "type": "count", "working": "...",
        "evidence": [{"label": "...", "x": 0.18, "y": 0.73, "w": 0.05, "h": 0.03}]}
else -> {"error": "why"}
```

`evidence` boxes are fractions (0..1) of the image width and height. Serve `index.html` at `/`, this
folder's `samples/` at `/samples/`, and `/ask` from the same origin (the page calls these relative paths).

Quick local look with a stand-in server: `python -m http.server 8080` in this folder shows the welcome
screen; questions need a real `/ask`.

Sample plans: see `samples/LICENSE.md` (CC BY-NC-SA 4.0, non-commercial).
