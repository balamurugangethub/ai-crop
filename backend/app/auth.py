"""Simple farmer accounts: mobile number + 4-6 digit PIN (PBKDF2-hashed)."""
import hashlib
import hmac
import re
import secrets

from fastapi import Depends, Header, HTTPException

from . import config
from .db import get_conn

PHONE_RE = re.compile(r"^[6-9]\d{9}$")  # Indian 10-digit mobile numbers
PIN_RE = re.compile(r"^\d{4,6}$")


def normalise_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits


def _hash_pin(pin: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000)


def register(name: str, phone: str, pin: str, village: str | None, language: str) -> dict:
    name = (name or "").strip()
    phone = normalise_phone(phone)
    if not (1 <= len(name) <= 80):
        raise HTTPException(422, "invalid_name")
    if not PHONE_RE.match(phone):
        raise HTTPException(422, "invalid_phone")
    if not PIN_RE.match(pin or ""):
        raise HTTPException(422, "invalid_pin")
    salt = secrets.token_bytes(16)
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE phone=?", (phone,)).fetchone():
            raise HTTPException(409, "phone_exists")
        cur = conn.execute(
            "INSERT INTO users(name, phone, village, language, pin_salt, pin_hash) VALUES (?,?,?,?,?,?)",
            (name, phone, (village or "").strip()[:120] or None, language, salt, _hash_pin(pin, salt)))
        return _new_session(conn, cur.lastrowid)


def login(phone: str, pin: str) -> dict:
    phone = normalise_phone(phone)
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
        if not row or not hmac.compare_digest(row["pin_hash"], _hash_pin(pin or "", row["pin_salt"])):
            raise HTTPException(401, "bad_credentials")
        return _new_session(conn, row["id"])


def _new_session(conn, user_id: int) -> dict:
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions(token, user_id) VALUES (?,?)", (token, user_id))
    return {"token": token, "user": user_public(conn, user_id)}


def user_public(conn, user_id: int) -> dict:
    row = conn.execute("SELECT id, name, phone, village, language, created_at FROM users WHERE id=?",
                       (user_id,)).fetchone()
    return dict(row)


def logout(token: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "not_logged_in")
    token = authorization.split(" ", 1)[1].strip()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE token=? AND created_at > datetime('now', ?)",
            (token, f"-{config.SESSION_DAYS} days")).fetchone()
        if not row:
            raise HTTPException(401, "session_expired")
        user = user_public(conn, row["user_id"])
    user["token"] = token
    return user


CurrentUser = Depends(current_user)
