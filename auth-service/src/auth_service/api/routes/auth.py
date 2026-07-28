from uuid import UUID

from fastapi import APIRouter, Header, Request, status

from auth_service.core.errors import AuthError
from auth_service.schemas.auth import (
    AdminUserResponse,
    AuthUserResponse,
    ForgotPasswordRequest,
    InternalUserResponse,
    LoginRequest,
    LoginResponse,
    LoginSuccessResponse,
    LogoutRequest,
    MessageResponse,
    MessageSuccessResponse,
    PlatformRoleUpdate,
    RefreshRequest,
    ResetPasswordRequest,
    ResponseMeta,
    SignupRequest,
    SignupSuccessResponse,
    SwitchAccountRequest,
    TokenRequest,
    TokenResponse,
    VerifyResetCodeRequest,
)
from auth_service.services.auth import AuthIdentity, AuthResult, AuthService
from auth_service.services.email_verification import EmailVerificationService
from auth_service.services.password_reset import PasswordResetService

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def meta(request: Request) -> ResponseMeta:
    return ResponseMeta(requestId=request.state.request_id, correlationId=request.state.correlation_id)


def user(identity: AuthIdentity) -> AuthUserResponse:
    return AuthUserResponse(
        id=identity.user_id,
        email=identity.email,
        accountId=identity.account_id,
        role=identity.role,
        accountRole=identity.account_role,
        platformRole=identity.platform_role,
    )


def login_data(result: AuthResult) -> LoginResponse:
    return LoginResponse(
        user=user(result.identity),
        tokens=TokenResponse(
            accessToken=result.tokens.access_token,
            refreshToken=result.tokens.refresh_token,
            expiresIn=result.tokens.access_expires_in,
        ),
    )


@router.post(
    "/signup",
    response_model=SignupSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="auth_signup",
)
async def signup(payload: SignupRequest, request: Request) -> SignupSuccessResponse:
    authentication: AuthService = request.app.state.authentication
    identity = await authentication.signup(str(payload.email), payload.password)
    return SignupSuccessResponse(data=user(identity), meta=meta(request))


@router.post("/login", response_model=LoginSuccessResponse, operation_id="auth_login")
async def login(payload: LoginRequest, request: Request) -> LoginSuccessResponse:
    authentication: AuthService = request.app.state.authentication
    ip = request.client.host if request.client is not None else "unknown"
    result = await authentication.login(str(payload.email), payload.password, ip)
    return LoginSuccessResponse(data=login_data(result), meta=meta(request))


@router.get("/me", response_model=AuthUserResponse, operation_id="auth_current_user")
async def current_user(request: Request, authorization: str = Header()) -> AuthUserResponse:
    if not authorization.startswith("Bearer "):
        raise AuthError(401, "MISSING_ACCESS_TOKEN", "Bearer access token is required")
    authentication: AuthService = request.app.state.authentication
    identity = await authentication.current_identity(authorization.removeprefix("Bearer ").strip())
    return user(identity)


async def superadmin(request: Request, authorization: str = Header()) -> AuthService:
    if not authorization.startswith("Bearer "):
        raise AuthError(401, "MISSING_ACCESS_TOKEN", "Bearer access token is required")
    authentication: AuthService = request.app.state.authentication
    await authentication.require_superadmin(authorization.removeprefix("Bearer ").strip())
    return authentication


@router.get(
    "/internal/users/{user_id}",
    response_model=InternalUserResponse,
    operation_id="auth_internal_get_user",
)
async def internal_get_user(
    user_id: UUID, request: Request, authorization: str = Header()
) -> InternalUserResponse:
    """Trusted service-to-service lookup (email only) — guarded by a shared secret,
    not a user JWT. Used by notification-service to resolve who to email for
    events that only carry a user_id (no login/session context)."""
    settings = request.app.state.settings
    token = authorization.removeprefix("Bearer ").strip()
    if not settings.internal_service_token or token != settings.internal_service_token:
        raise AuthError(401, "INVALID_INTERNAL_TOKEN", "Internal service token is invalid")
    authentication: AuthService = request.app.state.authentication
    found = await authentication.get_user_by_id(user_id)
    if found is None:
        raise AuthError(404, "USER_NOT_FOUND", "User was not found")
    return InternalUserResponse(id=found.id, email=found.email)


def admin_user(value: object) -> AdminUserResponse:
    from auth_service.models import User

    if not isinstance(value, User):
        raise TypeError("Expected User")
    return AdminUserResponse(
        id=value.id,
        email=value.email,
        isActive=value.is_active,
        isEmailVerified=value.is_email_verified,
        platformRole=value.platform_role,
    )


@router.get(
    "/admin/users",
    response_model=list[AdminUserResponse],
    operation_id="auth_admin_list_users",
)
async def admin_list_users(request: Request, authorization: str = Header()) -> list[AdminUserResponse]:
    authentication = await superadmin(request, authorization)
    return [admin_user(value) for value in await authentication.list_users()]


@router.patch(
    "/admin/users/{user_id}/platform-role",
    response_model=AdminUserResponse,
    operation_id="auth_admin_update_platform_role",
)
async def admin_update_platform_role(
    user_id: UUID,
    payload: PlatformRoleUpdate,
    request: Request,
    authorization: str = Header(),
) -> AdminUserResponse:
    authentication = await superadmin(request, authorization)
    return admin_user(await authentication.update_platform_role(user_id, payload.platformRole))


def message(request: Request, value: str) -> MessageSuccessResponse:
    return MessageSuccessResponse(data=MessageResponse(message=value), meta=meta(request))


@router.post("/logout", response_model=MessageSuccessResponse, operation_id="auth_logout")
async def logout(
    payload: LogoutRequest, request: Request, authorization: str = Header()
) -> MessageSuccessResponse:
    if not authorization.startswith("Bearer "):
        raise AuthError(401, "MISSING_ACCESS_TOKEN", "Bearer access token is required")
    authentication: AuthService = request.app.state.authentication
    await authentication.logout(authorization.removeprefix("Bearer ").strip(), payload.refreshToken)
    return message(request, "Logged out successfully")


@router.post("/verify-email", response_model=MessageSuccessResponse, operation_id="auth_verify_email")
async def verify_email(payload: TokenRequest, request: Request) -> MessageSuccessResponse:
    verification: EmailVerificationService = request.app.state.email_verification
    await verification.verify(payload.token)
    return message(request, "Email verified successfully")


@router.post("/forgot-password", response_model=MessageSuccessResponse, operation_id="auth_forgot_password")
async def forgot_password(payload: ForgotPasswordRequest, request: Request) -> MessageSuccessResponse:
    password_reset: PasswordResetService = request.app.state.password_reset
    await password_reset.request(str(payload.email))
    return message(request, "If the account exists, a reset code will be sent")


@router.post(
    "/forgot-password/verify",
    response_model=MessageSuccessResponse,
    operation_id="auth_verify_reset_code",
)
async def verify_reset_code(payload: VerifyResetCodeRequest, request: Request) -> MessageSuccessResponse:
    password_reset: PasswordResetService = request.app.state.password_reset
    ip = request.client.host if request.client is not None else "unknown"
    await password_reset.verify(str(payload.email), payload.code, ip)
    return message(request, "Reset code is valid")


@router.post("/reset-password", response_model=MessageSuccessResponse, operation_id="auth_reset_password")
async def reset_password(payload: ResetPasswordRequest, request: Request) -> MessageSuccessResponse:
    password_reset: PasswordResetService = request.app.state.password_reset
    ip = request.client.host if request.client is not None else "unknown"
    await password_reset.reset(str(payload.email), payload.code, payload.password, ip)
    return message(request, "Password reset successfully")


@router.post("/refresh", response_model=LoginSuccessResponse, operation_id="auth_refresh")
async def refresh(payload: RefreshRequest, request: Request) -> LoginSuccessResponse:
    authentication: AuthService = request.app.state.authentication
    result = await authentication.refresh(payload.refreshToken)
    return LoginSuccessResponse(data=login_data(result), meta=meta(request))


@router.post(
    "/switch-account",
    response_model=LoginSuccessResponse,
    operation_id="auth_switch_account",
)
async def switch_account(
    payload: SwitchAccountRequest,
    request: Request,
    authorization: str = Header(),
) -> LoginSuccessResponse:
    if not authorization.startswith("Bearer "):
        raise AuthError(401, "MISSING_ACCESS_TOKEN", "Bearer access token is required")
    authentication: AuthService = request.app.state.authentication
    result = await authentication.switch_account(
        authorization.removeprefix("Bearer ").strip(), payload.accountId
    )
    return LoginSuccessResponse(data=login_data(result), meta=meta(request))
