from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class CaptchaConfigResponse(BaseModel):
    site_key: str
    enabled: bool
