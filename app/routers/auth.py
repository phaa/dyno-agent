from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from auth.auth_handler import sign_jwt
from auth.passwords_handler import hash_password_async, verify_password_async
from models.user import User
from core.db import get_db
from schemas.user import UserSchema, UserLoginSchema

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
async def register_user(user: UserSchema, db: AsyncSession = Depends(get_db)):
    # Verify if user exists in db
    existing_user = (await db.execute(select(User).where(User.email == user.email))).scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists.")
    
    if not user.email or not user.password or not user.fullname:
        raise HTTPException(status_code=400, detail="Missing user information.")

    # Hash password
    hashed_password = await hash_password_async(user.password)

    # Create new user
    new_user = User(
        email=user.email,
        fullname=user.fullname,
        password=hashed_password,  # In production, hash the password before storing
    )

    # Add user to db    
    db.add(new_user)
    await db.flush() 

    try:
        await db.commit() # persist the new user
    except IntegrityError:
        # handle race where another request created the same email
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered.")

    # return token after successful commit
    return sign_jwt(user.email)


@router.post("/login", tags=["auth"])
async def login_user(user: UserLoginSchema, db: AsyncSession = Depends(get_db)):
    # Check user in db
    existing_user = (await db.execute(select(User).where(User.email == user.email))).scalar_one_or_none()
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    password_valid = await verify_password_async(user.password, existing_user.password)
    if not password_valid:
        raise HTTPException(status_code=401, detail="Invalid password.")    

    # Generate JWT token
    token = sign_jwt(existing_user.email)
    return token


