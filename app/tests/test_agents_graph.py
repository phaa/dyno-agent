import sys
import types
import asyncio
import pytest


# Minimal fake StateGraph implementation to allow compiling and invoking
class FakeCompiledGraph:
    def __init__(self, nodes, entry_point):
        self.nodes = nodes
        self.entry = entry_point

    async def ainvoke(self, inputs, config=None):
        # simple execution: call entry node with a simple state dict
        state = {**inputs}
        node_fn = self.nodes.get(self.entry)
        if asyncio.iscoroutinefunction(node_fn):
            return await node_fn(state)
        else:
            return node_fn(state)


class FakeStateGraph:
    def __init__(self, state_cls=None):
        self.nodes = {}
        self.entry = None

    def add_node(self, name, fn):
        self.nodes[name] = fn

    def set_entry_point(self, name):
        self.entry = name

    def add_conditional_edges(self, *args, **kwargs):
        # If called with (name, fn) register the conditional node
        if len(args) >= 2 and callable(args[1]):
            name = args[0]
            fn = args[1]
            self.nodes[name] = fn
        return None

    def add_edge(self, *args, **kwargs):
        return None

    def compile(self, checkpointer=None):
        return FakeCompiledGraph(self.nodes, self.entry)


# Provide fakes for langgraph modules before importing agents.graph
if 'langgraph.graph' not in sys.modules:
    lg_graph = types.ModuleType('langgraph.graph')
    lg_graph.StateGraph = FakeStateGraph
    lg_graph.END = object()
    # Minimal MessagesState used as base for GraphState
    class MessagesState(dict):
        pass
    lg_graph.MessagesState = MessagesState
    sys.modules['langgraph.graph'] = lg_graph

if 'langgraph.checkpoint.memory' not in sys.modules:
    lg_mem = types.ModuleType('langgraph.checkpoint.memory')
    class InMemorySaver:
        pass
    lg_mem.InMemorySaver = InMemorySaver
    sys.modules['langgraph.checkpoint.memory'] = lg_mem

if 'langgraph.checkpoint.postgres.aio' not in sys.modules:
    pg = types.ModuleType('langgraph.checkpoint.postgres.aio')
    class AsyncPostgresSaver:
        @classmethod
        def from_conn_string(cls, *args, **kwargs):
            return cls()
    pg.AsyncPostgresSaver = AsyncPostgresSaver
    sys.modules['langgraph.checkpoint.postgres.aio'] = pg

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

if 'langgraph.prebuilt' not in sys.modules:
    lg_pre = types.ModuleType('langgraph.prebuilt')
    class ToolNode:
        def __init__(self, tools):
            self.tools = tools

        async def ainvoke(self, state):
            return state

    lg_pre.ToolNode = ToolNode
    sys.modules['langgraph.prebuilt'] = lg_pre


def make_coroutine_return(value):
    async def fn(state):
        return value
    return fn


@pytest.mark.asyncio
async def test_build_graph_compiles_and_invokes():
    # Monkeypatch simple nodes by injecting into agents.nodes module
    # Inject a fake `agents.nodes` module to avoid importing heavy dependencies
    fake_nodes = types.ModuleType('agents.nodes')
    fake_nodes.llm_node = make_coroutine_return({'messages': ['ok']})
    fake_nodes.summarization_node = make_coroutine_return({'summary': {}})
    fake_nodes.get_schema_node = make_coroutine_return({'schema': 'ok'})
    fake_nodes.db_disabled_node = make_coroutine_return({'db': 'disabled'})
    fake_nodes.tool_node = make_coroutine_return({'tools': {}})
    fake_nodes.graceful_error_handler = make_coroutine_return({'error_handled': True})
    fake_nodes.route_from_llm = lambda state: [('tools', True)]
    fake_nodes.check_db = lambda state: 'summarize'

    sys.modules['agents.nodes'] = fake_nodes

    import agents.graph as graph_mod
    import agents.nodes as nodes_mod

    # Build graph with fake checkpointer (None -> uses InMemorySaver internally)
    g = await graph_mod.build_graph(checkpointer=None)

    # Ensure compiled has ainvoke and returns expected structure
    assert hasattr(g, 'ainvoke')
    res = await g.ainvoke({'messages': []}, config={})
    assert res is not None
