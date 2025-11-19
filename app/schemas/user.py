from pydantic import BaseModel, EmailStr, Field

class UserSchema(BaseModel):
    fullname: str = Field(...)
    emai: EmailStr = Field(...)
    password: str = Field(...)


class UserLoginSchema(BaseModel):
    email: EmailStr = Field(...)
    password: str = Field(...)