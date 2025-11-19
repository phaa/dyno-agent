import bcrypt
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def hash_password_async(password: str) -> str:
    # Generate a salt with a recommended number of rounds (e.g., 12)
    executor = ThreadPoolExecutor()
    salt = await asyncio.get_event_loop().run_in_executor(
        executor, bcrypt.gensalt, 12
    )
    # Hash the password using the generated salt
    hashed_password = await asyncio.get_event_loop().run_in_executor(
        executor, bcrypt.hashpw, password.encode('utf-8'), salt
    )
    return hashed_password.decode('utf-8')

async def verify_password_async(password: str, hashed_password: str) -> bool:
    # Verify the password against the stored hash
    executor = ThreadPoolExecutor()
    is_valid = await asyncio.get_event_loop().run_in_executor(
        executor, bcrypt.checkpw, password.encode('utf-8'), hashed_password.encode('utf-8')
    )
    return is_valid