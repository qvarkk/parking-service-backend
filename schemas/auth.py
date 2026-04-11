from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class CaptchaConfigResponse(BaseModel):
    site_key: str
    enabled: bool
