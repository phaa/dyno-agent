import pytest
from datetime import datetime, date
from types import SimpleNamespace
import sys
import types

import agents.tools as tools_module

# Provide lightweight fakes for external AI libs to avoid importing heavy dependencies
if 'langchain_core.tools' not in sys.modules:
    lc = types.ModuleType('langchain_core')
    lc_tools = types.ModuleType('langchain_core.tools')
    def tool(fn=None, **kwargs):
        # simple decorator passthrough
        if fn is None:
            return lambda f: f
        return fn
    lc_tools.tool = tool
    sys.modules['langchain_core'] = lc
    sys.modules['langchain_core.tools'] = lc_tools

if 'langgraph.runtime' not in sys.modules:
    lg_rt = types.ModuleType('langgraph.runtime')
    def get_runtime():
        return SimpleNamespace(context=SimpleNamespace(db=None))
    lg_rt.get_runtime = get_runtime
    sys.modules['langgraph.runtime'] = lg_rt

if 'langgraph.config' not in sys.modules:
    lg_cfg = types.ModuleType('langgraph.config')
    lg_cfg.get_stream_writer = lambda: (lambda s: None)
    sys.modules['langgraph.config'] = lg_cfg


def test_get_datetime_now_calls_service():
    called = {}

    class FakeService:
        def get_datetime_now_core(self):
            called['ok'] = True
            return datetime(2025, 1, 1)

    tools_module._get_service_from_runtime = lambda: FakeService()

    res = tools_module.get_datetime_now()
    assert isinstance(res, datetime)
    assert called.get('ok', False) is True


@pytest.mark.asyncio
async def test_find_available_dynos_uses_service_and_writer():
    messages = []

    def fake_writer(msg):
        messages.append(msg)

    tools_module.get_stream_writer = lambda: fake_writer

    async def fake_find(start_date, end_date, weight_lbs, drive_type, test_type):
        return [{'id': 1, 'name': 'DYNO-1'}]

    class FakeService:
        async def find_available_dynos_core(self, start_date, end_date, weight_lbs, drive_type, test_type):
            return await fake_find(start_date, end_date, weight_lbs, drive_type, test_type)

    tools_module._get_service_from_runtime = lambda: FakeService()

    res = await tools_module.find_available_dynos(start_date=date.today(), end_date=date.today(), weight_lbs=1000, drive_type='AWD', test_type='brake')
    assert isinstance(res, list)
    assert messages, "writer should have been called"


@pytest.mark.asyncio
async def test_auto_allocate_vehicle_delegates_to_service():
    class FakeService:
        async def auto_allocate_vehicle_core(self, **kwargs):
            return {"success": True, "allocation": {"allocation_id": 42}}

    tools_module._get_service_from_runtime = lambda: FakeService()

    res = await tools_module.auto_allocate_vehicle(start_date=date.today(), days_to_complete=1, vehicle_id=1)
    assert res['success'] is True
    assert res['allocation']['allocation_id'] == 42


@pytest.mark.asyncio
async def test_query_database_validates_and_calls_service():
    class FakeService:
        async def query_database_core(self, sql: str):
            return [{'col': 1}]

    tools_module._get_service_from_runtime = lambda: FakeService()
    tools_module.get_stream_writer = lambda: (lambda s: None)

    res = await tools_module.query_database("SELECT 1")
    assert isinstance(res, list)
    assert res[0]['col'] == 1
