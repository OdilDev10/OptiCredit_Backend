"""Authentication endpoints."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    VerifyEmailRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    SendOTPRequest,
    VerifyOTPRequest,
    AuthResponse,
    UserResponse,
    RegisterCustomerRequest,
    RegisterLenderRequest,
    RegistrationEntityResponse,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService
from app.dependencies import get_current_user, get_current_claims
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    request_data: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register new user with email verification. Rate limited: 5/minute."""
    service = AuthService(session)
    result = await service.register(
        email=request_data.email,
        password=request_data.password,
        first_name=request_data.first_name,
        last_name=request_data.last_name,
    )
    return RegisterResponse(**result)


@router.post(
    "/register/customer",
    response_model=RegistrationEntityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_customer(
    request: RegisterCustomerRequest,
    session: AsyncSession = Depends(get_db),
) -> RegistrationEntityResponse:
    """Register a customer account."""
    service = AuthService(session)
    names = request.full_name.strip().split()
    first_name = names[0]
    last_name = " ".join(names[1:]) if len(names) > 1 else "Cliente"
    result = await service.register_customer(
        email=request.email,
        password=request.password,
        first_name=first_name,
        last_name=last_name,
        lender_id=request.lender_id,
        document_type=request.document_type,
        document_number=request.document_number,
        phone=request.phone,
    )
    return RegistrationEntityResponse(**result)


@router.post(
    "/register/lender",
    response_model=RegistrationEntityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_lender(
    request: RegisterLenderRequest,
    session: AsyncSession = Depends(get_db),
) -> RegistrationEntityResponse:
    """Register a lender account."""
    service = AuthService(session)
    result = await service.register_lender(
        email=request.email,
        password=request.password,
        legal_name=request.legal_name,
        lender_type=request.lender_type,
        document_type=request.document_type,
        document_number=request.document_number,
        phone=request.phone,
    )
    return RegistrationEntityResponse(**result)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    request: VerifyEmailRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Verify user email with token."""
    service = AuthService(session)
    result = await service.verify_email(request.token)
    return MessageResponse(message=result.get("message", "Email verified"))


@router.post("/login", response_model=AuthResponse, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def login(
    request: Request,
    login_request: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Login user and return access/refresh tokens. Rate limited: 10/minute."""
    service = AuthService(session)
    result = await service.login(login_request.email, login_request.password)
    return AuthResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh access token using refresh token. Rate limited: 15/minute."""
    service = AuthService(session)
    result = await service.refresh_token_service(request.refresh_token)
    return TokenResponse(**result)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Logout user and invalidate current refresh token."""
    service = AuthService(session)
    result = await service.logout(str(current_user.id), request.refresh_token)
    return MessageResponse(message=result.get("message", "Logged out successfully"))


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Logout from all devices - invalidate all refresh tokens."""
    service = AuthService(session)
    result = await service.logout_all(str(current_user.id))
    return MessageResponse(message=result.get("message", "Logged out from all devices"))


@router.get("/me", response_model=UserResponse)
async def get_me(
    claims: dict = Depends(get_current_claims),
) -> UserResponse:
    """Return the authenticated user profile from JWT claims (no DB hit)."""
    return UserResponse(
        id=str(claims.get("sub", "")),
        email=str(claims.get("email", "")),
        first_name=str(claims.get("first_name", "")),
        last_name=str(claims.get("last_name", "")),
        role=str(claims.get("role", "")),
        account_type=claims.get("account_type"),
        status=claims.get("status"),
        lender_id=claims.get("lender_id"),
        phone=claims.get("phone"),
        roles=claims.get("roles") or [],
        permissions=claims.get("permissions") or [],
    )


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    request_data: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Request password reset via email. Rate limited: 5/minute."""
    service = AuthService(session)
    result = await service.forgot_password(request_data.email)
    return MessageResponse(message=result.get("message", "Email sent if exists"))


@router.post("/verify-reset-token", response_model=MessageResponse)
async def verify_reset_token(
    request: VerifyEmailRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Verify that reset token is valid."""
    service = AuthService(session)
    result = await service.verify_reset_token(request.token)
    return MessageResponse(message=result.get("message", "Token is valid"))


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Reset password with token."""
    service = AuthService(session)
    result = await service.reset_password(request.token, request.new_password)
    return MessageResponse(message=result.get("message", "Password reset successfully"))


@router.post("/send-otp", response_model=MessageResponse)
async def send_otp(
    request: SendOTPRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send OTP to authenticated user."""
    service = AuthService(session)
    result = await service.send_otp(str(current_user.id))
    return MessageResponse(message=result.get("message", "OTP sent"))


@router.post("/verify-otp", response_model=MessageResponse)
async def verify_otp(
    request: VerifyOTPRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Verify OTP code."""
    service = AuthService(session)
    result = await service.verify_otp(str(current_user.id), request.otp_code)
    return MessageResponse(message=result.get("message", "OTP verified"))


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Change password for authenticated user."""
    service = AuthService(session)
    result = await service.change_password(
        str(current_user.id),
        request.current_password,
        request.new_password,
    )
    return MessageResponse(message=result.get("message", "Password changed"))
