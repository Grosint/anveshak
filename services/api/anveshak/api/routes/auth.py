"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
import asyncpg
from ..db.pool import get_db
from ..db import auth as auth_db
from ..auth.jwt import create_access_token, pwd_context

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    username: str
    password: str


@router.post("/login")
async def login(
    req: LoginRequest,
    db: asyncpg.Connection = Depends(get_db),
):
    row = await auth_db.get_user_by_username(db, req.username)
    if not row or not pwd_context.verify(req.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(subject=str(row["id"]), username=req.username)
    return {"access_token": token, "token_type": "bearer"}
