from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import Token, UserLogin, UserOut, UserRegister
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])


@router.post("/auth", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    existing = await db.scalar(select(User).where(User.login == data.login))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Login already taken")

    user = User(login=data.login, password_hash=hash_password(data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: Annotated[AsyncSession, Depends(get_db)]) -> Token:
    user = await db.scalar(select(User).where(User.login == data.login))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid login or password")
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
