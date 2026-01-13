import sys
import types
import asyncio
import pytest


class FakeCompiledGraph:
    def __init__(self, nodes, entry, edges, conditional_nodes, end_sentinel):
        self.nodes = nodes
        self.entry = entry
        self.edges = edges
        self.conditional_nodes = conditional_nodes
        self.END = end_sentinel

    async def ainvoke(self, inputs, config=None):
        state = dict(inputs or {})
        current = self.entry
        steps = 0
        while steps < 20:
            steps += 1
            # Conditional node (decision)
            if current in self.conditional_nodes:
                fn = self.conditional_nodes[current]
                res = fn(state)
                # route can be a string, list of tuples, or END
                if res is None:
                    return state
                if res is self.END:
                    return state
                if isinstance(res, str):
                    current = res
                    continue
                if isinstance(res, list):
                    # pick first truthy condition or first route
                    for item in res:
                        if isinstance(item, tuple) and len(item) == 2:
                            name, cond = item
                            if cond:
                                current = name
                                break
                        else:
                            current = item
                            break
                    continue

            # Regular node
            node = self.nodes.get(current)
            if node is None:
                return state
            if asyncio.iscoroutinefunction(node):
                out = await node(state)
            else:
                out = node(state)
            if isinstance(out, dict):
                state.update(out)
            # after node execution, check conditional routing (e.g., llm -> route_from_llm)
            if current in self.conditional_nodes:
                fn = self.conditional_nodes[current]
                res = fn(state)
                if res is None:
                    return state
                if res is self.END:
                    return state
                if isinstance(res, str):
                    current = res
                    continue
                if isinstance(res, list):
                    for item in res:
                        if isinstance(item, tuple) and len(item) == 2:
                            name, cond = item
                            if cond:
                                current = name
                                break
                        else:
                            current = item
                            break
                    continue
            # follow explicit edge if present
            if current in self.edges:
                current = self.edges[current]
                continue
            # no next edge -> return
            return state
        return state


class FakeStateGraph:
    def __init__(self, state_cls=None, end_sentinel=None):
        self.nodes = {}
        self.entry = None
        self.edges = {}
        self.conditional_nodes = {}
        self.END = end_sentinel or object()

    def add_node(self, name, fn):
        self.nodes[name] = fn

    def set_entry_point(self, name):
        self.entry = name

    def add_conditional_edges(self, name, fn):
        self.conditional_nodes[name] = fn

    def add_edge(self, src, dst):
        self.edges[src] = dst

    def compile(self, checkpointer=None):
        return FakeCompiledGraph(self.nodes, self.entry, self.edges, self.conditional_nodes, self.END)


def _install_langgraph_fakes():
    # Overwrite a minimal langgraph.graph with our FakeStateGraph to avoid cross-test pollution
    lg_graph = types.ModuleType('langgraph.graph')
    lg_graph.StateGraph = FakeStateGraph
    lg_graph.END = object()
    lg_graph.MessagesState = dict
    sys.modules['langgraph.graph'] = lg_graph

    lg_mem = types.ModuleType('langgraph.checkpoint.memory')
    class InMemorySaver:
        pass
    lg_mem.InMemorySaver = InMemorySaver
    sys.modules['langgraph.checkpoint.memory'] = lg_mem


def make_coroutine(fn):
    async def coro(state):
        return fn(state)
    return coro


@pytest.mark.asyncio
async def test_graph_deterministic_tool_execution():
    _install_langgraph_fakes()

    # deterministic nodes
    fake_nodes = types.ModuleType('agents.nodes')

    def check_db(state):
        return 'summarize'

    def summarization_node(state):
        return {'summary': 'deterministic-summary'}

    def llm_node(state):
        # decide to call tools and provide tool args
        return {'call_tools': True, 'tool_args': {'action': 'allocate', 'vehicle_id': 'V1'}}

    def route_from_llm(state):
        if state.get('call_tools'):
            return [('tools', True)]
        return sys.modules['langgraph.graph'].END

    def tool_node(state):
        args = state.get('tool_args', {})
        # simulate performing the tool action and returning a concrete result
        return {'tools': {args.get('action'): {'vehicle_id': args.get('vehicle_id'), 'status': 'done'}}}

    def graceful_error_handler(state):
        return {'error_handled': True}

    def get_schema_node(state):
        return {'schema': {'tables': []}}

    def db_disabled_node(state):
        return {'db': 'disabled'}

    fake_nodes.check_db = check_db
    fake_nodes.summarization_node = make_coroutine(lambda s: summarization_node(s))
    fake_nodes.llm_node = make_coroutine(lambda s: llm_node(s))
    fake_nodes.route_from_llm = route_from_llm
    fake_nodes.tool_node = make_coroutine(lambda s: tool_node(s))
    fake_nodes.graceful_error_handler = make_coroutine(lambda s: graceful_error_handler(s))
    fake_nodes.get_schema_node = make_coroutine(lambda s: get_schema_node(s))
    fake_nodes.db_disabled_node = make_coroutine(lambda s: db_disabled_node(s))

    sys.modules['agents.nodes'] = fake_nodes

    # import graph builder and execute (reload to pick up overwritten langgraph fakes)
    import importlib
    if 'agents.graph' in sys.modules:
        importlib.reload(sys.modules['agents.graph'])
    graph_mod = importlib.import_module('agents.graph')

    g = await graph_mod.build_graph(checkpointer=None)

    assert hasattr(g, 'ainvoke')
    res = await g.ainvoke({'messages': []}, config={})

    # deterministic expectations
    assert isinstance(res, dict)
    assert 'summary' in res and res['summary'] == 'deterministic-summary'
    assert 'tools' in res and 'allocate' in res['tools']
    assert res['tools']['allocate']['vehicle_id'] == 'V1'
