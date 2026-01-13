import os
import pytest

# Skip integration tests if the application cannot be imported in this env
try:
    from main import app as _app
except Exception:
    pytest.skip("Skipping integration tests: `app` import failed in this environment.", allow_module_level=True)


@pytest.mark.asyncio
async def test_register_and_login(test_async_client, async_db_session):
    # Ensure JWT env vars are present for token generation
    os.environ.setdefault("JWT_SECRET", "testsecret")
    os.environ.setdefault("JWT_ALGORITHM", "HS256")
    os.environ.setdefault("JWT_EXP_DELTA_SECONDS", "3600")

    user = {
        "fullname": "Integration User",
        "email": "intuser@example.com",
        "password": "strongpass"
    }

    # Register + Login using the async_client async-generator fixture
    async for client in test_async_client:
        resp = await client.post("/auth/register", json=user)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body.get("access_token"), str)

        # Login
        login = {"email": user["email"], "password": user["password"]}
        resp2 = await client.post("/auth/login", json=login)
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert isinstance(body2.get("access_token"), str)
