import sys
from typing import Any

sys.path.append("./")
sys.path.append("../")
sys.path.append("../../")

from agentic_system.common.data_component import get_default_data
from agentic_system.common.get_llm import azure_llm_if as get_llm
from agentic_system.components.react_system.react_agent import ReactSystem
from agentic_system.components.results_interpreter.results_analyst import (
    prepare_test_data as prepare_results_test_data,
)


def _extract_results_tables(prepared: Any) -> dict[str, Any]:
    if isinstance(prepared, tuple):
        if not prepared:
            raise ValueError("prepare_test_data returned an empty tuple.")
        candidate = prepared[0]
    else:
        candidate = prepared

    if not isinstance(candidate, dict):
        raise TypeError(
            "Expected prepare_test_data to return a dict or a tuple "
            "whose first item is a dict of dataframes."
        )

    return candidate


def test_react_system_end_to_end_smoke() -> None:
    """
    Quick end-to-end smoke test for ReactSystem:
    planner -> execution tools -> presenter UIItems.

    Requirements:
    - AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be configured.
    """
    llm = get_llm()
    react = ReactSystem(llm)

    results_tables = _extract_results_tables(prepare_results_test_data())
    react.set_interpreter_data(results_tables)

    injectors, producers, locations = get_default_data()
    react.set_analyst_data(
        {
            "injectors": injectors,
            "producers": producers,
            "locations": locations,
        }
    )

    query = (
        #"Interpret the connectivity while ignoring negligible gains, "
        #"and also plot GAIN versus DISTANCE for non-negligible gains."
        "list wells with watercut above 0.05"
    )

    presenter_response = react.run(query=query, run_presenter=True)

    assert react.planner_component.last_plan is not None, "Planner did not run."
    assert len(react.planner_component.last_plan.tasks) > 0, "Planner returned no tasks."
    assert presenter_response.agent == "presenter"
    assert len(presenter_response.items) > 0, "Presenter returned no UI items."

    valid_item_types = {"table", "chart", "text", "markdown", "error", "question"}
    invalid_types = [item.type for item in presenter_response.items if item.type not in valid_item_types]
    assert not invalid_types, f"Unexpected UI item types: {invalid_types}"


if __name__ == "__main__":
    test_react_system_end_to_end_smoke()
    print("test_react1 passed")

