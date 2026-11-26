"""AI Crop Doctor - FastAPI backend.

Run:  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import json
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from . import auth, config, knowledge, shops
from .auth import CurrentUser
from .db import get_conn, init_db
from .image_check import ImageRejected, load_and_check
from .inference import get_model

@asynccontextmanager
async def lifespan(_app):
    init_db()
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="AI Crop Doctor API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


def _lang(lang: str | None) -> str:
    return lang if lang in knowledge.SUPPORTED_LANGUAGES else "en"


# ---------------------------------------------------------------- health / model
@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/model")
def model_info():
    return get_model().info()


# ---------------------------------------------------------------- auth
class RegisterIn(BaseModel):
    name: str
    phone: str
    pin: str
    village: str | None = None
    language: str = "en"


class LoginIn(BaseModel):
    phone: str
    pin: str


class ProfileIn(BaseModel):
    language: str | None = None
    village: str | None = None


@app.post("/api/auth/register")
def register(body: RegisterIn):
    return auth.register(body.name, body.phone, body.pin, body.village, _lang(body.language))


@app.post("/api/auth/login")
def login(body: LoginIn):
    return auth.login(body.phone, body.pin)


@app.post("/api/auth/logout")
def logout(user=CurrentUser):
    auth.logout(user["token"])
    return {"ok": True}


@app.get("/api/me")
def me(user=CurrentUser):
    return {k: v for k, v in user.items() if k != "token"}


@app.patch("/api/me")
def update_me(body: ProfileIn, user=CurrentUser):
    with get_conn() as conn:
        if body.language is not None:
            conn.execute("UPDATE users SET language=? WHERE id=?", (_lang(body.language), user["id"]))
        if body.village is not None:
            conn.execute("UPDATE users SET village=? WHERE id=?", (body.village.strip()[:120] or None, user["id"]))
        return auth.user_public(conn, user["id"])


# ---------------------------------------------------------------- diagnosis
def _save_report(user_id, status, pred, image_file, message):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO reports(user_id, status, class_id, confidence, top_k, image_file, message) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, status, pred.get("class_id") if pred else None,
             pred.get("confidence") if pred else None,
             json.dumps(pred.get("top_k")) if pred else None, image_file, message))
        return cur.lastrowid


def _build_result(report_id, created_at, status, pred, lang, message=None, quality=None):
    res = {"report_id": report_id, "created_at": created_at, "status": status, "message": message,
           "quality": quality, "disease": None, "candidates": [],
           "min_confidence": config.MIN_CONFIDENCE}
    if pred:
        res.update({"confidence": pred["confidence"], "ood_distance": pred.get("ood_distance"),
                    "ood_threshold": pred.get("ood_threshold")})
        if status == "ok":
            res["disease"] = knowledge.get_disease(pred["class_id"], lang)
        if status in ("ok", "uncertain"):
            for c in pred["top_k"]:
                d = knowledge.get_disease(c["class_id"], lang)
                res["candidates"].append({"class_id": c["class_id"], "confidence": c["confidence"],
                                          "name": d["name"], "crop_name": d["crop_name"]})
    return res


@app.post("/api/diagnose")
async def diagnose(image: UploadFile = File(...), lang: str = Form("en"), user=CurrentUser):
    lang = _lang(lang)
    data = await image.read()
    try:
        img, quality = load_and_check(data)
    except ImageRejected as e:
        rid = _save_report(user["id"], "rejected", None, None, e.code)
        return JSONResponse(status_code=422, content={"report_id": rid, "status": "rejected",
                                                      "message": e.code, "detail": e.detail})
    fname = f"{user['id']}_{secrets.token_hex(8)}.jpg"
    img.save(config.UPLOAD_DIR / fname, "JPEG", quality=88)
    pred = await run_in_threadpool(get_model().predict, img)
    rid = _save_report(user["id"], pred["status"], pred, fname, None)
    with get_conn() as conn:
        created = conn.execute("SELECT created_at FROM reports WHERE id=?", (rid,)).fetchone()[0]
    return _build_result(rid, created, pred["status"], pred, lang, quality=quality)


@app.get("/api/reports")
def list_reports(lang: str = "en", user=CurrentUser):
    lang = _lang(lang)
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM reports WHERE user_id=? AND status != 'rejected' "
                            "ORDER BY id DESC LIMIT 100", (user["id"],)).fetchall()
    out = []
    for r in rows:
        d = knowledge.get_disease(r["class_id"], lang) if r["class_id"] else None
        out.append({"id": r["id"], "created_at": r["created_at"], "status": r["status"],
                    "class_id": r["class_id"], "confidence": r["confidence"],
                    "name": d["name"] if d else None, "crop_name": d["crop_name"] if d else None,
                    "healthy": d["healthy"] if d else None,
                    "image_url": f"/api/reports/{r['id']}/image" if r["image_file"] else None})
    return out


def _get_report_row(report_id, user):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM reports WHERE id=? AND user_id=?", (report_id, user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "report_not_found")
    return row


@app.get("/api/reports/{report_id}")
def get_report(report_id: int, lang: str = "en", user=CurrentUser):
    r = _get_report_row(report_id, user)
    pred = None
    if r["top_k"]:
        pred = {"class_id": r["class_id"], "confidence": r["confidence"], "top_k": json.loads(r["top_k"])}
    res = _build_result(r["id"], r["created_at"], r["status"], pred, _lang(lang), r["message"])
    res["image_url"] = f"/api/reports/{r['id']}/image" if r["image_file"] else None
    return res


@app.get("/api/reports/{report_id}/image")
def report_image(report_id: int, token: str = Query(...)):
    # <img> tags cannot send headers, so the session token comes as a query parameter
    user = auth.current_user(f"Bearer {token}")
    r = _get_report_row(report_id, user)
    path = config.UPLOAD_DIR / r["image_file"]
    if not path.exists():
        raise HTTPException(404, "image_missing")
    return FileResponse(path, media_type="image/jpeg")


@app.delete("/api/reports/{report_id}")
def delete_report(report_id: int, user=CurrentUser):
    r = _get_report_row(report_id, user)
    with get_conn() as conn:
        conn.execute("DELETE FROM reports WHERE id=?", (r["id"],))
    if r["image_file"]:
        (config.UPLOAD_DIR / r["image_file"]).unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/diseases")
def list_diseases(lang: str = "en"):
    return [knowledge.get_disease(c, _lang(lang)) for c in knowledge.all_class_ids()]


@app.get("/api/diseases/{class_id}")
def disease(class_id: str, lang: str = "en"):
    d = knowledge.get_disease(class_id, _lang(lang))
    if not d:
        raise HTTPException(404, "unknown_disease")
    return d


# ---------------------------------------------------------------- shops
@app.get("/api/geocode")
async def geocode(q: str):
    try:
        return {"results": await run_in_threadpool(shops.geocode, q)}
    except shops.ShopServiceError as e:
        raise HTTPException(502 if "unavailable" in e.code else 422, e.code)


@app.get("/api/shops")
async def find_shops(lat: float, lon: float, radius: int = 10000):
    try:
        return await run_in_threadpool(shops.search_shops, lat, lon, radius)
    except shops.ShopServiceError as e:
        status = 422 if e.code == "invalid_coordinates" else 503
        raise HTTPException(status, e.code)


# ---------------------------------------------------------------- frontend
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = config.FRONTEND_DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
