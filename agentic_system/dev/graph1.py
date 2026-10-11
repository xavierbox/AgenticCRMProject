
import sys
sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path

from typing import Any

from langgraph.graph import END, START, StateGraph

from pathlib import Path
from typing import TypedDict
import webbrowser

from langgraph.graph import StateGraph, START, END


class ExecutorState(TypedDict):
    query: str


def planner_node(state: ExecutorState) -> dict:
    """Placeholder: no state updates yet."""
    return {}

def interpreter_node(state: ExecutorState) -> dict:
    """Placeholder: no state updates yet."""
    return {}

def scenario_node(state: ExecutorState) -> dict:
    """Placeholder: no state updates yet."""
    return {}

def data_analyst_node(state: ExecutorState) -> dict:
    """Placeholder: no state updates yet."""
    return {}

def router_node(state: ExecutorState) -> dict:
    """Placeholder: no state updates yet."""
    return {}

def create_graph():
    builder = StateGraph(ExecutorState)

    builder.add_node("planner", planner_node)
    builder.add_edge(START, "planner")

    builder.add_edge(START, "router")
        
    builder.add_edge("planner", END)

    return builder.compile()


def display_graph(graph, output_path: str = "graph.png") -> Path:
    """Save the graph as a PNG and open it in the default browser."""
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    image = graph.get_graph().draw_mermaid_png()
    path.write_bytes(image)

    webbrowser.open(path.as_uri())
    return path


if __name__ == "__main__":
    graph = create_graph()
    path = display_graph(graph)
    print(f"Graph saved to: {path}")

