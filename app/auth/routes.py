from fastapi import APIRouter, HTTPException, Depends

from app.core.config import settings
from app.database.mongo import users_collection
from app.auth.schemas import RegisterRequest, LoginRequest, RefreshTokenRequest
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, verify_access_token
from app.auth.services import verify_google_token

from jose import jwt, JWTError
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


# REGISTER USER
@router.post("/register", status_code=201)
async def register_user(request: RegisterRequest):

    existing_user = await users_collection.find_one({
        "$or": [{"email": request.email}, {"username": request.username}]
    })

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "error",
                "code": "USER_ALREADY_EXISTS",
                "message": "Email or username already in use."
            }
        )

    if request.auth_provider == "google":
        google_data = verify_google_token(request.google_token)
        if not google_data:
            raise HTTPException(
                status_code=401,
                detail={
                    "status": "error",
                    "code": "INVALID_GOOGLE_TOKEN",
                    "message": "Google authentication failed."
                }
            )
        password_hash = None
    else:
        password_hash = hash_password(request.password)

    user_data = {
        "_id": str(uuid.uuid4()),
        "username": request.username,
        "email": request.email,
        "password_hash": password_hash,
        "preferences": request.preferences or {"theme": "dark", "auto_save": True},
        "core_memory": {},
        "constraints": {},
        "auth_provider": request.auth_provider,
        "created_at": datetime.utcnow()
    }

    await users_collection.insert_one(user_data)

    access_token = create_access_token({"user_id": user_data["_id"]})
    refresh_token = create_refresh_token({"user_id": user_data["_id"]})

    return {
        "status": "success",
        "message": "User registered successfully.",
        "data": {
            "user_id": user_data["_id"],
            "username": user_data["username"],
            "email": user_data["email"],
            "auth_provider": user_data["auth_provider"],
            "preferences": user_data["preferences"],
            "created_at": user_data["created_at"]
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    }


# LOGIN USER
@router.post("/login")
async def login_user(request: LoginRequest):

    user = await users_collection.find_one({"email": request.email})

    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"user_id": user["_id"]})
    refresh_token = create_refresh_token({"user_id": user["_id"]})

    return {
        "status": "success",
        "message": "Login successful",
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    }

# USER PROFILE API (PROTECTED)
@router.get("/profile")
async def get_user_profile(payload: dict = Depends(verify_access_token)):

    user_id = payload.get("user_id")

    user = await users_collection.find_one({"_id": user_id}, {"password_hash": 0})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "status": "success",
        "data": user
    }

# REFRESH TOKEN API
@router.post("/refresh")
async def refresh_access_token(request: RefreshTokenRequest):

    try:
        payload = jwt.decode(
            request.refresh_token,
            settings.JWT_REFRESH_SECRET_KEY,
            algorithms=["HS256"]
        )

        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # ✅ create new access token
        new_access_token = create_access_token({"user_id": user_id})

        return {
            "status": "success",
            "access_token": new_access_token
        }

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")