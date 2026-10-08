
import sys



sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path
from agentic_system.common.base_task import DataFrameResult
from agentic_system.components.coordinator_graph import OuterExecutor
from agentic_system.components.planner import * 
from agentic_system.components.direct_answer.direct_answer import * 
from agentic_system.components.results_interpreter import * 
from agentic_system.common.get_llm import azure_llm_if
from agentic_system.components.planner.planner import get_default_planner
from agentic_system.components.results_interpreter.results_interpreter import ResultsInterpreterComponent, get_default_results_interpreter


import pprint
import inspect 

import importlib.metadata

for package in [
    "langgraph",
    "langgraph-checkpoint",
    "pydantic",
]:
    print(package, importlib.metadata.version(package))




planner = get_default_planner()
interpreter = get_default_results_interpreter()
direct_answer = get_default_direct_answer(llm=azure_llm_if())
llm = azure_llm_if()



executor = OuterExecutor(
    planner=planner,
    direct_answer=direct_answer,
    results_interpreter=interpreter,
    thread_id="dependency-execution-test-1",
)

import pandas as pd
from uuid import uuid4

original_df = pd.DataFrame({
    "PRODUCER": ["P1", "P2"],
    "GAIN": [0.38, 0.30],
    "DATE": pd.to_datetime(["2026-01-01", "2026-01-02"]),
})



from uuid import uuid4

original_data = {
    "PRODUCER": ["P1", "P2"],
    "GAIN": [0.38, 0.30],
}

test_result = TaskResult(
    agent="results_interpreter",
    instruction="Test DataFrameResult with a dictionary payload.",
    cheap_output="Demo table with two producers.",
    data_results=[
        DataFrameResult(
            table_name="checkpoint_test",
            dataframe= pd.DataFrame(original_data).to_dict(orient='records'),
        )
    ],
)

test_config = {
    "configurable": {
        "thread_id": f"dictionary-test-{uuid4().hex}",
    }
}

try:
    executor.graph.update_state(
        test_config,
        {
            "task_results": [test_result],
            "current_task_results": {
                "test_dataframe": test_result,
            },
        },
        as_node="presenter",
    )

    restored_state = executor.graph.get_state(test_config).values
    restored_result = restored_state["task_results"][0]
    restored_data_result = restored_result.data_results[0]


    print("Restored type:", type(restored_data_result))
    print("Expected type:", DataFrameResult)
    print("Restored value:", restored_data_result)

    print(
        "Restored class is current class:",
        type(restored_data_result) is DataFrameResult,
    )



    print(
        "data_results annotation:",
        TaskResult.model_fields["data_results"].annotation,
    )

    print("Restored TaskResult type:", type(restored_result))
    print("Current TaskResult class:", TaskResult)


    payload = (
        restored_result.model_dump()
        if isinstance(restored_result, TaskResult)
        else restored_result
    )

    validated_result = TaskResult.model_validate(payload)

    print("Validated output type:", type(validated_result.data_results[0]))



    assert isinstance(restored_result, TaskResult)
    assert isinstance(restored_data_result, DataFrameResult)
    assert restored_data_result.table_name == "checkpoint_test"
    assert isinstance(restored_data_result.dataframe, list)
    assert restored_data_result.dataframe == original_data

    print("Passed: DataFrameResult with dictionary payload restored correctly.")

except Exception as e:
    print(f"Failed: {type(e).__name__}: {e}")
    raise




from pathlib import Path

# For OuterExecutor:
graph = executor.graph

# For create_agent, use instead:
# graph = agent

output = Path("agent_graph.png")
output.write_bytes(graph.get_graph().draw_mermaid_png())

print(f"Graph saved to: {output.resolve()}")






query = (
    "First, identify the injectors supporting producer P1 and report "
    "their gains using the simulation results. "
    "Then, have the direct-answer component rewrite those findings "
    "as one short sentence for management, preserving any demo labels."
)

state = executor.run(query)

print(state["plan"].model_dump_json(indent=2)) # type: ignore

tasks = state["plan"].tasks # type: ignore

assert len(tasks) == 2
assert tasks[0].agent == "results_interpreter"
assert tasks[1].agent == "direct_answer"
assert tasks[0].task_id in (tasks[1].depends_on or [])

resolved = executor._resolve_dependencies(tasks[1], state)

assert len(resolved) == 1
assert resolved[0] is state["current_task_results"][tasks[0].task_id]

for task in tasks:
    result = state["current_task_results"][task.task_id]
    print(f"\nAGENT: {result.agent}")
    print(result.cheap_output)

print("\nFINAL ANSWER:")
print(state["final_answer"])

print("\nPassed: plan dependencies and full graph execution.")

