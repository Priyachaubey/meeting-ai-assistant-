from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_current_user_id, hash_password, verify_password
from app.database.session import get_db
from app.models.entities import User, Workspace, WorkspaceMembership
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UpdateProfileRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

VALID_AUDIO_MODES = {"system", "microphone", "hybrid"}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    try:
        db.flush()  # assign user.id without committing yet, so workspace creation below can use it
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Every user gets a personal workspace automatically — see models.Workspace's docstring
    # and migration 0005's backfill, which does the same for users created before this existed.
    workspace = Workspace(name=f"{payload.full_name or payload.email}'s Workspace", created_by=user.id)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role="owner"))
    db.commit()

    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    # Same error for "no such user" and "wrong password" — don't leak which one it was.
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def get_profile(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/me", response_model=UserOut)
async def update_profile(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.preferred_language is not None:
        if len(payload.preferred_language) > 10:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="preferred_language looks invalid")
        user.preferred_language = payload.preferred_language
    if payload.audio_capture_mode is not None:
        if payload.audio_capture_mode not in VALID_AUDIO_MODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"audio_capture_mode must be one of {sorted(VALID_AUDIO_MODES)}",
            )
        user.audio_capture_mode = payload.audio_capture_mode
    db.commit()
    return user
