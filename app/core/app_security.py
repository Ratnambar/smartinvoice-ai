import os
from fastapi import Depends, HTTPException, status  # pyright: ignore[reportMissingImports]
from typing import Annotated
from sqlalchemy.orm import Session
import jwt
from fastapi.security import OAuth2PasswordBearer  # pyright: ignore[reportMissingImports]
from app.schemas.invoice_schema import TokenData
from app.models.invoice_model import User
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash  # pyright: ignore[reportMissingImports]
from app.core.config import get_db
import math
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
_ = load_dotenv()
SECRET_KEY = os.environ["secret_key"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("dummypassword")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def fake_hash_password(password: str):
    return "fakehashed" + password

def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)

def get_password_hash(password):
    return password_hash.hash(password)

def fake_decode_token(token):
    return get_user(get_db(), token)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user(db, username):
    user = db.query(User).filter(User.email.ilike(username)).first()
    if user:
        return user
    return None

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(db, token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if getattr(current_user, "is_active", True) is False:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def authenticate_user(db, email, password):
    user = get_user(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user