from pydantic import BaseModel, ConfigDict, EmailStr, model_validator

from src.schemas.common import BoolField


class UserAuthorizationSchema(BaseModel):
    email: EmailStr
    password_hash: str


class UserNameSchema(BaseModel):
    surname: str
    first_name: str
    patronymic: str | None


class UserRegistrationSchema(UserAuthorizationSchema, UserNameSchema):
    repeat_password_hash: str
    is_teacher: BoolField = False

    @model_validator(mode='after')
    def passwords_match(self):
        if self.password_hash != self.repeat_password_hash:
            raise ValueError('Пароли не совпадают')
        return self


class UserBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    surname: str
    first_name: str
    patronymic: str
    email: str
    is_teacher: BoolField = False


class UserReadSchema(UserBriefSchema):
    password_hash: str
