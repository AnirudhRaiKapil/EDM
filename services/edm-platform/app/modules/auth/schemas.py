from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

# Length over character-class rules, per NIST SP 800-63B: mandatory complexity rules
# (must contain a digit/symbol/etc.) push users toward predictable patterns and don't
# meaningfully resist guessing; a length floor does. 128 is a DoS guard, not a usability
# rule -- PBKDF2's cost is proportional to input size, so an unbounded password lets a
# single request burn far more CPU than a normal login.
_MIN_PASSWORD_LENGTH = 10
_MAX_PASSWORD_LENGTH = 128


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str
    password: str

    @field_validator("password")
    @classmethod
    def password_within_length_bounds(cls, value: str) -> str:
        if len(value) < _MIN_PASSWORD_LENGTH:
            raise ValueError(f"password must be at least {_MIN_PASSWORD_LENGTH} characters")
        if len(value) > _MAX_PASSWORD_LENGTH:
            raise ValueError(f"password must be at most {_MAX_PASSWORD_LENGTH} characters")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: str
    email: str
    display_name: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
