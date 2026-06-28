from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth import service
from app.modules.auth.models import User
from app.modules.auth.schemas import Token, UserCreate, UserLogin, UserRead
from app.rate_limit import enforce_auth_rate_limit

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=UserRead, status_code=201)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    enforce_auth_rate_limit(request, payload.email)
    user = service.register_user(db, payload.email, payload.display_name, payload.password)
    return user


@router.post("/auth/login", response_model=Token)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    enforce_auth_rate_limit(request, payload.email)
    user = service.authenticate_user(db, payload.email, payload.password)
    return Token(access_token=service.issue_token(user))


@router.get("/users/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user
