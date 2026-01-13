"""
Pytest configuration and shared fixtures for the Dyno-Agent test suite.

This module provides:
- Database fixtures (in-memory SQLite for fast tests)
- FastAPI test client fixtures
- Mock data factories
- Agent testing utilities
"""

import pytest
import sys
import types
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
from datetime import date, datetime, timedelta

import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers directly to avoid importing `app.main` which pulls heavy deps
from routers import auth as auth_router_module

# Provide a lightweight dummy for langgraph.checkpoint.postgres.aio to allow
# importing `app` in environments where langgraph is not installed or incompatible.
if 'langgraph.checkpoint.postgres.aio' not in sys.modules:
    pkg = types.ModuleType('langgraph')
    cp = types.ModuleType('langgraph.checkpoint')
    pg = types.ModuleType('langgraph.checkpoint.postgres')
    aio_mod = types.ModuleType('langgraph.checkpoint.postgres.aio')

    class AsyncPostgresSaver:
        def __init__(self, *args, **kwargs):
            self._setup_done = False

        async def setup(self):
            self._setup_done = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        @classmethod
        def from_conn_string(cls, *args, **kwargs):
            # Return an async context-manager instance
            return cls()

    aio_mod.AsyncPostgresSaver = AsyncPostgresSaver

    sys.modules['langgraph'] = pkg
    sys.modules['langgraph.checkpoint'] = cp
    sys.modules['langgraph.checkpoint.postgres'] = pg
    sys.modules['langgraph.checkpoint.postgres.aio'] = aio_mod

try:
    from main import app
except Exception:
    app = None
from core.db import get_db, Base
from models.user import User
from models.vehicle import Vehicle
from models.dyno import Dyno
from models.allocation import Allocation
import auth.passwords_handler as passwords_handler


# Test Database Configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine():
    """Create async engine for testing with in-memory SQLite."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def async_db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for testing."""
    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
async def async_client(async_db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client with database dependency override."""
    
    async def override_get_db():
        yield async_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    if app is None:
        # If the real `app` couldn't be imported, provide a minimal test app
        test_app = FastAPI()
        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        # include routers from modules
        test_app.include_router(auth_router_module.router)
        target_app = test_app
    else:
        target_app = app

    target_app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=target_app, base_url="http://test") as client:
        yield client

    target_app.dependency_overrides.clear()


@pytest.fixture
async def test_async_client(async_db_session) -> AsyncGenerator[AsyncClient, None]:
    """A lightweight test FastAPI app mounting only auth and allocation routers."""
    async def override_get_db():
        yield async_db_session

    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(auth_router_module.router)

    test_app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client

    test_app.dependency_overrides.clear()


@pytest.fixture
def sync_client() -> Generator[TestClient, None, None]:
    """Create synchronous test client for simple tests."""
    with TestClient(app) as client:
        yield client


# Test Data Factories
@pytest.fixture
async def test_user(async_db_session) -> User:
    """Create a test user."""
    user = User(
        fullname="Test User",
        email="test@example.com",
        hashed_password=await passwords_handler.hash_password_async("testpass123")
    )
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)
    return user


@pytest.fixture
async def test_vehicle(async_db_session) -> Vehicle:
    """Create a test vehicle."""
    vehicle = Vehicle(
        vin="TEST123456789",
        weight_lbs=4500,
        drive_type="AWD",
        preferred_test_type="brake"
    )
    async_db_session.add(vehicle)
    await async_db_session.commit()
    await async_db_session.refresh(vehicle)
    return vehicle


@pytest.fixture
async def test_dyno(async_db_session) -> Dyno:
    """Create a test dyno."""
    dyno = Dyno(
        name="TEST-DYNO-01",
        max_weight_lbs=6000,
        supported_drive=["AWD", "FWD"],
        supported_test_types=["brake", "emissions"],
        enabled=True
    )
    async_db_session.add(dyno)
    await async_db_session.commit()
    await async_db_session.refresh(dyno)
    return dyno


@pytest.fixture
async def test_allocation(async_db_session, test_vehicle, test_dyno) -> Allocation:
    """Create a test allocation."""
    allocation = Allocation(
        vehicle_id=test_vehicle.id,
        dyno_id=test_dyno.id,
        start_date=date.today() + timedelta(days=1),
        end_date=date.today() + timedelta(days=3),
        test_type="brake",
        status="confirmed"
    )
    async_db_session.add(allocation)
    await async_db_session.commit()
    await async_db_session.refresh(allocation)
    return allocation


# Mock Fixtures for Agent Testing
@pytest.fixture
def mock_llm():
    """Mock LLM for agent testing."""
    mock = MagicMock()
    mock.ainvoke = AsyncMock()
    return mock


@pytest.fixture
def mock_agent_tools():
    """Mock agent tools for testing."""
    return {
        "query_database": AsyncMock(),
        "auto_allocate_vehicle": AsyncMock(),
        "get_available_dynos": AsyncMock(),
        "check_conflicts": AsyncMock(),
        "get_allocation_details": AsyncMock(),
        "update_allocation": AsyncMock(),
        "cancel_allocation": AsyncMock(),
        "get_dyno_schedule": AsyncMock(),
        "analyze_utilization": AsyncMock()
    }


# Authentication Fixtures
@pytest.fixture
async def auth_headers(async_client, test_user) -> dict:
    """Get authentication headers for API requests."""
    login_data = {
        "email": test_user.email,
        "password": "testpass123"
    }
    
    response = await async_client.post("/auth/login", json=login_data)
    assert response.status_code == 200
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# Performance Testing Fixtures
@pytest.fixture
def performance_test_data():
    """Generate test data for performance testing."""
    vehicles = []
    dynos = []
    
    # Create 100 test vehicles
    for i in range(100):
        vehicles.append({
            "vin": f"PERF{i:06d}",
            "weight_lbs": 3000 + (i * 50),
            "drive_type": ["FWD", "AWD", "RWD"][i % 3],
            "preferred_test_type": ["brake", "emissions", "durability"][i % 3]
        })
    
    # Create 20 test dynos
    for i in range(20):
        dynos.append({
            "name": f"PERF-DYNO-{i:02d}",
            "max_weight_lbs": 5000 + (i * 500),
            "supported_drive": ["FWD", "AWD", "RWD"],
            "supported_test_types": ["brake", "emissions", "durability"],
            "enabled": True
        })
    
    return {"vehicles": vehicles, "dynos": dynos}


# Utility Functions
def assert_allocation_valid(allocation_data: dict):
    """Assert that allocation data is valid."""
    required_fields = ["allocation_id", "vehicle_id", "dyno_id", "start_date", "end_date"]
    for field in required_fields:
        assert field in allocation_data
        assert allocation_data[field] is not None


def create_mock_graph_state(messages=None, error=None, retry_count=2):
    """Create mock GraphState for agent testing."""
    return {
        "messages": messages or [],
        "error": error,
        "retry_count": retry_count,
        "error_node": None
    }


# Common Test Doubles
@pytest.fixture
def mock_async_session():
    """Provide a reusable AsyncSession-like test double.

    - `begin()` returns an async context manager that commits on exit
    - `add` is a `MagicMock` (synchronous)
    - `flush`, `commit`, `refresh`, `execute` are `AsyncMock`
    Tests can override `execute.side_effect` / `flush.side_effect` as needed.
    """
    session = AsyncMock()

    class DummyAsyncCtx:
        def __init__(self, sess):
            self.sess = sess
        async def __aenter__(self):
            return None
        async def __aexit__(self, exc_type, exc, tb):
            # mimic commit on successful context exit
            await self.sess.commit()
            return False

    # `begin` should be a callable returning an async context manager
    session.begin = lambda: DummyAsyncCtx(session)

    # `add` is synchronous on SQLAlchemy session
    session.add = MagicMock()

    # Async methods
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()

    return session


@pytest.fixture
def install_langgraph_fakes():
    """Install lightweight langgraph fakes into sys.modules for tests."""
    # minimal graph + checkpoint fakes used by agent tests
    lg_graph = types.ModuleType('langgraph.graph')
    class FakeStateGraph:
        def __init__(self, *args, **kwargs):
            self.nodes = {}
            self.entry = None
        def add_node(self, name, fn):
            self.nodes[name] = fn
        def set_entry_point(self, name):
            self.entry = name
        def add_conditional_edges(self, *a, **k):
            return None
        def add_edge(self, *a, **k):
            return None
        def compile(self, checkpointer=None):
            class Compiled:
                async def ainvoke(self, inputs, config=None):
                    return inputs
            return Compiled()

    lg_graph.StateGraph = FakeStateGraph
    lg_graph.END = object()
    lg_graph.MessagesState = dict
    sys.modules['langgraph.graph'] = lg_graph

    lg_mem = types.ModuleType('langgraph.checkpoint.memory')
    class InMemorySaver:
        pass
    lg_mem.InMemorySaver = InMemorySaver
    sys.modules['langgraph.checkpoint.memory'] = lg_mem

    lg_pg = types.ModuleType('langgraph.checkpoint.postgres.aio')
    class AsyncPostgresSaver:
        @classmethod
        def from_conn_string(cls, *a, **k):
            return cls()
    lg_pg.AsyncPostgresSaver = AsyncPostgresSaver
    sys.modules['langgraph.checkpoint.postgres.aio'] = lg_pg

    # config/runtime stubs
    lg_rt = types.ModuleType('langgraph.runtime')
    lg_rt.get_runtime = lambda: types.SimpleNamespace(context=types.SimpleNamespace(db=None))
    sys.modules['langgraph.runtime'] = lg_rt

    lg_cfg = types.ModuleType('langgraph.config')
    lg_cfg.get_stream_writer = lambda: (lambda s: None)
    sys.modules['langgraph.config'] = lg_cfg

    lg_pre = types.ModuleType('langgraph.prebuilt')
    class ToolNode:
        def __init__(self, tools):
            self.tools = tools
        async def ainvoke(self, state):
            return state
    lg_pre.ToolNode = ToolNode
    sys.modules['langgraph.prebuilt'] = lg_pre

    yield

    # cleanup fakes after test
    for mod in [
        'langgraph.graph',
        'langgraph.checkpoint.memory',
        'langgraph.checkpoint.postgres.aio',
        'langgraph.runtime',
        'langgraph.config',
        'langgraph.prebuilt',
    ]:
        if mod in sys.modules:
            del sys.modules[mod]


@pytest.fixture
def install_agents_nodes():
    """Return a helper to inject a fake `agents.nodes` module for tests.

    Usage:
        fake_nodes = install_agents_nodes({ 'llm_node': my_fn, ... })
    """
    def _installer(mapping: dict):
        mod = types.ModuleType('agents.nodes')
        for k, v in mapping.items():
            setattr(mod, k, v)
        sys.modules['agents.nodes'] = mod
        return mod
    yield _installer
    if 'agents.nodes' in sys.modules:
        del sys.modules['agents.nodes']