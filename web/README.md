# AI Crop Doctor – phone version

A single-page version that runs the **same trained model in the phone's browser**
(TensorFlow.js), so it works without a server or laptop. Your photo never leaves the phone.

* `crop-doctor.html` – the page (Tamil/English, scan, result, history, tips, about).
* `model.json`, `w1.wasm`, `w2.wasm` – the trained model converted with `tensorflowjs_converter`
  (float16 weights). The weight files use a `.wasm` extension only because the hosting page
  serves a fixed set of file types; they are raw TensorFlow.js weight shards.
* `ood.wasm` – class means (float32) and the Mahalanobis precision matrix (float16) for the
  "image not recognised" check. `meta.json` – labels, thresholds, held-out metrics.
* `knowledge.json` – the same sourced disease guidance as `backend/app/knowledge/`.

Differences from the full app: no accounts (history is stored on the phone only), and
shop search opens Google Maps / OpenStreetMap in a new tab instead of listing shops in the
page (the hosting sandbox blocks calls to map services and GPS).

Verification: `compare-with-python.cjs` loads the page in Chromium and runs all 16 test images
from `backend/tests/images`; the browser and the Python backend made the same decision on 16/16.
