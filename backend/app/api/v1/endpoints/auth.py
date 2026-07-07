"""Administrative browser authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin_user
from app.core.config import settings
from app.models.auth import AdminUser
from app.schemas.auth import AuthSessionResponse, AuthenticatedUser, LoginRequest
from app.schemas.base import ResponseBase
from app.services.auth import AuthService

router = APIRouter()


def _present_user(user: AdminUser) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        auth_provider=user.auth_provider,
    )


@router.post("/login", response_model=ResponseBase[AuthSessionResponse])
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    created = await AuthService(db).authenticate_local(
        username=payload.username,
        password=payload.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    if created is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=created.session_token,
        max_age=settings.auth_session_hours * 3600,
        httponly=True,
        secure=settings.auth_cookie_secure_effective,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=created.csrf_token,
        max_age=settings.auth_session_hours * 3600,
        httponly=False,
        secure=settings.auth_cookie_secure_effective,
        samesite="lax",
        path="/",
    )
    return ResponseBase(
        data=AuthSessionResponse(
            user=_present_user(created.user),
            csrf_token=created.csrf_token,
        )
    )


@router.get("/me", response_model=ResponseBase[AuthSessionResponse])
async def me(
    request: Request,
    user: AdminUser = Depends(require_admin_user),
):
    return ResponseBase(
        data=AuthSessionResponse(
            user=_present_user(user),
            csrf_token=request.state.csrf_token,
        )
    )


@router.post("/logout", response_model=ResponseBase[dict])
async def logout(
    request: Request,
    response: Response,
    _user: AdminUser = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    await AuthService(db).revoke(request.cookies.get(settings.auth_session_cookie_name))
    response.delete_cookie(
        settings.auth_session_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure_effective,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        settings.auth_csrf_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure_effective,
        httponly=False,
        samesite="lax",
    )
    return ResponseBase(data={"logged_out": True})
