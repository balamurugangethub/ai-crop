# 🌱 AI Crop Doctor

An AI agricultural assistant for farmers. A farmer can:

1. take or upload a photo of a crop leaf,
2. get a **genuine AI-based possible disease identification** with a confidence score,
3. read the symptoms and **sourced, farmer-friendly guidance** (no chemical dosages),
4. find **real nearby agricultural shops** from OpenStreetMap on a map,
5. open directions to a shop, and
6. use the whole app in **Tamil or English** (with text-to-speech where the device supports it).

> ⚠️ The diagnosis is an AI estimate, not a guaranteed diagnosis. The app says this on
> every result and points farmers to their Agriculture Officer / Krishi Vigyan Kendra.

---

## What works (tested)

| Feature | How it works | Status |
|---|---|---|
| Login / register | Mobile number + 4–6 digit PIN (PBKDF2-hashed), SQLite | ✅ |
| Photo capture / upload | Camera (`capture="environment"`) or gallery; JPG/PNG/WEBP ≤ 10 MB | ✅ |
| Image validation | Rejects non-images, tiny, too dark, over-exposed, blurry photos (OpenCV Laplacian) | ✅ |
| Disease detection | MobileNetV2 fine-tuned on PlantVillage, 13 tomato/potato classes + "unsupported" class | ✅ |
| Unsupported / unclear photos | Safety gates (see below) → "Image not recognised" or "Model not sure" | ✅ |
| Disease info & guidance | Symptoms, causes, what to do now, prevention, non-chemical options, sources (EN + TA) | ✅ |
| Nearby shops | OpenStreetMap Overpass API, falls back to Nominatim; device GPS or typed village | ✅ |
| Map & directions | Leaflet + OSM tiles; Google Maps / OSM directions links | ✅ |
| History | Past reports with photos, re-rendered in the current language, delete | ✅ |
| Tamil / English | All screens + disease content; architecture ready for more languages | ✅ |
| Text-to-speech | Browser Web Speech API; shows a message if no Tamil voice is installed | ✅ (device-dependent) |

### Supported crops and classes

Tomato: Bacterial spot, Early blight, Late blight, Leaf mould, Septoria leaf spot,
Two-spotted spider mite, Target spot, Tomato yellow leaf curl virus, Tomato mosaic virus, Healthy.
Potato: Early blight, Late blight, Healthy.

**Not supported:** rice and all other crops. No rice dataset with verifiable provenance was
available, so rice was left out rather than faked.

---

## Model results (held-out data, never used for training)

Trained on CPU with `backend/ml/train.py` (full numbers in `backend/model/metrics.json`).

* **Test accuracy on supported classes: 96.5%** (3,041 held-out tomato/potato images).
* With the app's decision rule applied:
  * 96.7% of supported test images get a confident result, and **97.7% of those are correct**.
  * 2.4% are reported as "uncertain"; 0.8% are wrongly reported as "unsupported".
* Photos that are clearly not crops (CIFAR-10 everyday objects, tulips, sunflowers — all
  never seen in training): **100% rejected** as "Image not recognised".
* Leaves of *other* crops never seen in training are harder (see limitations).

### Safety rules (backend `app/inference.py`)

1. If the top class is `Unsupported___other`, **or** the image's feature vector is far
   (Mahalanobis distance above the 99th percentile of validation images) from every
   tomato/potato class → **unsupported**, no disease shown.
2. Else if confidence < 70% → **uncertain**: the closest matches are shown only as hints,
   with a request for a clearer photo.
3. Else → **ok**: disease shown with confidence (capped at "99%" on screen), disclaimer,
   sourced guidance and the expert helpline.

### Known limitations (honest)

* **Lab photos vs field photos.** PlantVillage images are single leaves on plain
  backgrounds. Real field photos (soil, many leaves, shadows) will be less accurate. The app
  asks for a single leaf in daylight; this is still the biggest real-world risk.
* **Leaves of other crops.** On held-out grape and bell-pepper leaves, the model still gave
  a confident (wrong) tomato/potato diagnosis for 2%–39% of images depending on the class
  (e.g. grape leaf blight 39%, pepper bacterial spot 16%, pepper healthy 2%). The UI states
  clearly that only tomato and potato are supported.
* **Weakest classes.** Tomato early blight recall is 83% (often confused with late blight); one
  of the committed test images is such a case and is tracked as a strict `xfail` in
  `tests/test_diagnose.py`.
* **Severity** shown is the *general seriousness of the disease* from the sources, not a
  measurement of how badly the photographed plant is affected (the model cannot measure that).
* **Target spot** guidance: the UF/IFAS fact sheet could not be fetched (it blocks automated
  access), so only general UMN tomato-disease practices are shown, marked "limited source".
* **Shop data** is only as complete as OpenStreetMap. Many rural shops are not mapped (a 20 km
  search around Thanjavur or Coimbatore returned none during testing; Chennai returned 7); some
  entries are mis-tagged (e.g. fruit shops tagged as agricultural supplies). The app never
  adds or guesses details, labels every shop's stock as **unconfirmed**, and says
  "No agricultural shops found" when nothing is returned.
* **Kisan Call Centre number (1800-180-1551)** is the widely published national helpline; the
  official site (mkisan.gov.in) blocked automated access, so it could not be re-verified
  while building.
* Tamil text was written for this project and should be reviewed by a native-speaking
  agronomist before field use.

---

## Sources for disease guidance

All guidance in `backend/app/knowledge/diseases.json` was written from these pages, which were
fetched and read while building (no chemical products or doses are included):

* University of Minnesota Extension — early blight, late blight, bacterial spot, tomato leaf
  mold, two-spotted spider mites, growing tomatoes.
* UC Statewide IPM Program — tomato early blight, late blight, bacterial spot, tomato yellow
  leaf curl, tobacco mosaic; potato early blight, late blight; spider mites; Septoria (general).

Each result screen links the exact pages used.

---

## Project structure

```
backend/
  app/
    main.py          FastAPI routes (auth, diagnose, reports, diseases, geocode, shops) + serves the built frontend
    inference.py     model loading + the safety decision rules
    image_check.py   upload validation / quality checks (Pillow + OpenCV)
    shops.py         OpenStreetMap Overpass + Nominatim shop search (no invented data)
    auth.py, db.py   accounts, sessions, SQLite
    knowledge/       diseases.json (EN + TA) and sources.json
  ml/
    prepare_data.py  builds the training folder layout from the downloaded datasets
    train.py         training + held-out evaluation → model/
  model/             crop_doctor.keras, labels.json, ood_stats.npz, metrics.json
  tests/             pytest suite + real held-out test images (see tests/images/ATTRIBUTION.md)
frontend/
  src/               React app (pages/, components.jsx, i18n.js, api.js, index.css)
  e2e/journey.mjs    Playwright end-to-end farmer journey
```

---

## Running it

Requirements: Python 3.11+ (tested on 3.13), Node 18+ (tested on 22). Internet access is
needed for the map, shop search and fonts. **No API keys are required.**

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Frontend (build once; the backend serves it)
cd ../frontend
npm ci
npm run build

# 3. Start
cd ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

For frontend development with hot reload: run the backend on :8000, then `npm run dev` in
`frontend/` and open http://localhost:5173 (Vite forwards `/api` to the backend).

**Camera and GPS on a phone** need HTTPS (or `localhost`). For testing on a phone, put the
server behind HTTPS (e.g. a reverse proxy or a tunnel); otherwise use "Upload photo" and type
the village name.

### Configuration

Optional environment variables are listed in `backend/.env.example` (data directory,
confidence threshold, Overpass/Nominatim servers, User-Agent). Set
`CROP_DOCTOR_USER_AGENT` with your contact details if you deploy publicly — the
[Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/) requires an
identifying User-Agent and at most 1 request per second (the app enforces the rate limit).

### Database

SQLite at `backend/data/crop_doctor.sqlite3`, created automatically on first start.
Uploaded photos are stored in `backend/data/uploads/`. Tables: `users`, `sessions`, `reports`.

---

## Tests

```bash
cd backend
pytest                    # 32 pass + 1 strict xfail (documented model error); uses the real model
pytest --network          # also runs the live OpenStreetMap geocoding + shop-search tests

# Browser end-to-end journey (server running on :8000 with the built frontend)
cd ../frontend
npm i -D playwright && npx playwright install chromium   # once, if Playwright isn't installed
node e2e/journey.mjs http://127.0.0.1:8000
```

The end-to-end script registers in Tamil, scans a held-out late-blight leaf, checks the Tamil
and English results, uploads a tulip photo (must be rejected), uploads a corrupt file, checks
history, searches shops by GPS (Chennai) including map markers and directions links, checks
denied location permission, tips, settings and the desktop layout. Last run: **21/21 passed**.

---

## Re-training the model

```bash
# datasets (~1 GB)
git clone --filter=blob:none --depth 1 https://github.com/spMohanty/PlantVillage-Dataset
mkdir ood && cd ood
curl -O https://storage.googleapis.com/tensorflow/tf-keras-datasets/cifar-10-python.tar.gz
curl -O https://storage.googleapis.com/download.tensorflow.org/example_images/flower_photos.tgz
tar xzf cifar-10-python.tar.gz && tar xzf flower_photos.tgz && cd ..

cd backend
python -m ml.prepare_data --pv ../PlantVillage-Dataset/raw/color --ood ../ood --out ../work
python -m ml.train --data ../work/combined --ood-eval ../work/ood_eval
```

Training on a 4-core CPU takes about 45–60 minutes. The script keeps a 70/15/15
train/validation/test split per class (seed 42); grape, pepper, CIFAR-10 test photos, tulips
and sunflowers are held out entirely for the out-of-distribution evaluation.

Note: the committed model was trained in two stages — first on the 13 tomato/potato classes
only, then `train.py --init-from <stage-1 model>` added the unsupported class starting from that
fine-tuned backbone. A single run from ImageNet weights (the command above) should land close
to, but not exactly at, the numbers reported here.

### Adding a language

1. Add the messages in `frontend/src/i18n.js` (`MESSAGES`, `TIPS`) and an entry in `LANGUAGES`.
2. Add the language block next to `"en"`/`"ta"` for every disease in
   `backend/app/knowledge/diseases.json` and the code to `SUPPORTED_LANGUAGES`.

---

## Data & licences

* PlantVillage dataset — Mohanty, Hughes & Salathé (2016), CC BY-SA 3.0.
* TensorFlow flower photos — individual CC-BY photos (see the dataset's LICENSE.txt).
* CIFAR-10 — Krizhevsky (2009), used only for training/evaluating the "unsupported" class.
* Map data © OpenStreetMap contributors (ODbL).
