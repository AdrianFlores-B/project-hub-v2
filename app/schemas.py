from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import Role


class UserRegister(BaseModel):
    login: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)
    repeat_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "UserRegister":
        if self.password != self.repeat_password:
            raise ValueError("passwords do not match")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str


class UserLogin(BaseModel):
    login: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class MemberOut(BaseModel):
    login: str
    role: Role
