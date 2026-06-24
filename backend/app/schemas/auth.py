from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AppleAuthRequest(BaseModel):
    identity_token: str
    authorization_code: str | None = None
    # Apple only returns name on first sign-in; client may pass these through.
    email: EmailStr | None = None
    display_name: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    # In production this token is emailed to the user. There is no email
    # service in this local instance, so it is returned directly.
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=6, max_length=128)


class AuthUser(BaseModel):
    id: str
    username: str
    display_name: str
    is_new_user: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: AuthUser
