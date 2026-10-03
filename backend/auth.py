import os
import uuid
import secrets
from datetime import datetime, timezone, timedelta

import bcrypt
import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from db import db

JWT_ALGORITHM = "HS256"
ACCESS_MINUTES = 60
SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
SAMESITE = "none" if SECURE else "lax"
REFRESH_DAYS = 7
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

router = APIRouter(prefix="/api/auth")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_token(user_id: str, kind: str, delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "type": kind, "iat": now, "jti": secrets.token_urlsafe(24),
               "exp": now + delta}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def _token_revoked(payload: dict, user: dict) -> bool:
    revoked_at = user.get("sessions_revoked_at")
    if not revoked_at:
        return False
    if isinstance(revoked_at, str):
        revoked_at = datetime.fromisoformat(revoked_at)
    if revoked_at.tzinfo is None:
        revoked_at = revoked_at.replace(tzinfo=timezone.utc)
    issued_at = payload.get("iat")
    if isinstance(issued_at, (int, float)):
        issued_at = datetime.fromtimestamp(issued_at, timezone.utc)
    return bool(issued_at and issued_at <= revoked_at)


def set_auth_cookies(response: Response, user_id: str):
    response.set_cookie("access_token", create_token(user_id, "access", timedelta(minutes=ACCESS_MINUTES)),
                        httponly=True, secure=SECURE, samesite=SAMESITE, max_age=ACCESS_MINUTES * 60, path="/")
    response.set_cookie("refresh_token", create_token(user_id, "refresh", timedelta(days=REFRESH_DAYS)),
                        httponly=True, secure=SECURE, samesite=SAMESITE, max_age=REFRESH_DAYS * 86400, path="/")


def public_user(u: dict) -> dict:
    return {"user_id": u["user_id"], "email": u["email"], "name": u.get("name", ""),
            "picture": u.get("picture"), "auth_provider": u.get("auth_provider", "password")}


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") == "access":
                user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
                if user and not _token_revoked(payload, user):
                    return user
        except jwt.InvalidTokenError:
            pass
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    if session_token:
        try:
            payload = jwt.decode(session_token, _secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") == "access":
                user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
                if user and not _token_revoked(payload, user):
                    return user
        except jwt.InvalidTokenError:
            pass
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if session:
            expires_at = session["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at > datetime.now(timezone.utc):
                user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
                if user:
                    return user
    raise HTTPException(status_code=401, detail="غير مصرح. يرجى تسجيل الدخول")


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(default="", max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")
    user = {"user_id": f"user_{uuid.uuid4().hex[:12]}", "email": email, "name": body.name or email.split("@")[0],
            "password_hash": hash_password(body.password), "auth_provider": "password",
            "role": "user", "created_at": datetime.now(timezone.utc)}
    await db.users.insert_one(user)
    set_auth_cookies(response, user["user_id"])
    return public_user(user)


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.lower()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    now = datetime.now(timezone.utc)
    if attempt and attempt.get("count", 0) >= 5:
        locked_at = attempt["last"]
        if locked_at.tzinfo is None:
            locked_at = locked_at.replace(tzinfo=timezone.utc)
        if now - locked_at < timedelta(minutes=15):
            raise HTTPException(status_code=429, detail="محاولات كثيرة. حاول بعد 15 دقيقة")
        await db.login_attempts.delete_one({"identifier": identifier})
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        await db.login_attempts.update_one({"identifier": identifier},
                                           {"$inc": {"count": 1}, "$set": {"last": now}}, upsert=True)
        raise HTTPException(status_code=401, detail="البريد أو كلمة المرور غير صحيحة")
    await db.login_attempts.delete_one({"identifier": identifier})
    set_auth_cookies(response, user["user_id"])
    return public_user(user)


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="لا توجد جلسة")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="جلسة غير صالحة")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="جلسة غير صالحة")
    user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
    if not user or _token_revoked(payload, user):
        raise HTTPException(status_code=401, detail="المستخدم غير موجود أو الجلسة ملغاة")
    set_auth_cookies(response, user["user_id"])
    return public_user(user)


class SessionIn(BaseModel):
    session_id: str


@router.post("/google/session")
async def google_session(body: SessionIn, response: Response):
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": body.session_id})
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="فشل التحقق من جلسة Google")
    data = r.json()
    email = data["email"].lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        await db.users.update_one({"email": email}, {"$set": {"name": data.get("name") or user.get("name"),
                                                               "picture": data.get("picture")}})
        user_id = user["user_id"]
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({"user_id": user_id, "email": email, "name": data.get("name", ""),
                                   "picture": data.get("picture"), "auth_provider": "google",
                                   "role": "user", "created_at": datetime.now(timezone.utc)})
    await db.user_sessions.insert_one({"user_id": user_id, "session_token": data["session_token"],
                                       "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
                                       "created_at": datetime.now(timezone.utc)})
    response.set_cookie("session_token", data["session_token"], httponly=True, secure=SECURE,
                        samesite=SAMESITE, max_age=7 * 86400, path="/")
    set_auth_cookies(response, user_id)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return public_user(user)


@router.get("/me")
async def me(request: Request):
    return public_user(await get_current_user(request))


@router.post("/logout")
async def logout(request: Request, response: Response):
    st = request.cookies.get("session_token")
    if st:
        await db.user_sessions.delete_one({"session_token": st})
    # Revoke all access/refresh JWTs issued before logout, not only the OAuth session.
    access = request.cookies.get("access_token") or request.cookies.get("refresh_token")
    user_id = None
    if access:
        try:
            user_id = jwt.decode(access, _secret(), algorithms=[JWT_ALGORITHM]).get("sub")
        except jwt.InvalidTokenError:
            pass
    if user_id:
        await db.users.update_one({"user_id": user_id}, {"$set": {"sessions_revoked_at": datetime.now(timezone.utc)}})
    for name in ("access_token", "refresh_token", "session_token"):
        response.delete_cookie(name, path="/", secure=SECURE, samesite=SAMESITE)
    return {"ok": True}


async def seed_admin():
    email = os.environ["ADMIN_EMAIL"].lower()
    password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if existing is None:
        await db.users.insert_one({"user_id": f"user_{uuid.uuid4().hex[:12]}", "email": email, "name": "Admin",
                                   "password_hash": hash_password(password), "auth_provider": "password",
                                   "role": "admin", "created_at": datetime.now(timezone.utc)})
    elif not existing.get("password_hash") or not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})
