
from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict
from uuid import uuid4

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END


STEPS = [
    "create_well_list",
    "compute_unconstrained_injection",
    "compute_constrained_injection",
    "impose_facility_constraints",
    "producer_report",
]


class TaskResult(BaseModel):
    step: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    input_steps: list[str] = Field(default_factory=list)

    # In-memory artifacts: dataframes, arrays, etc.
    data: dict[str, Any] = Field(default_factory=dict)


class WorkflowState(TypedDict):
    run_id: str
    start_step: str
    config: dict[str, Any]
    results: dict[str, TaskResult]


class InjectionWorkflow:
    def __init__(self, llm=None):
        self.llm = llm
        self.runs: dict[str, WorkflowState] = {}
        self.graph = self._build_graph()

    # ---------------------------------------------------------
    # Numerical workflow steps: all dummy for now
    # ---------------------------------------------------------

    def create_well_list(self, config, results) -> TaskResult:
        return TaskResult(
            step="create_well_list",
            description="Selected the wells to include.",
            parameters={
                "excluded_wells": config.get("excluded_wells", [])
            },
            data={"well_list": ["I1", "I2"]},
        )

    def compute_unconstrained_injection(
        self, config, results
    ) -> TaskResult:
        wells = results["create_well_list"].data["well_list"]

        return TaskResult(
            step="compute_unconstrained_injection",
            description="Computed injection rates before constraints.",
            parameters={
                "max_decrease_fraction": config.get(
                    "max_decrease_fraction", 0.5
                )
            },
            input_steps=["create_well_list"],
            data={"rates": {well: 100.0 for well in wells}},
        )

    def compute_constrained_injection(
        self, config, results
    ) -> TaskResult:
        previous = results["compute_unconstrained_injection"]

        return TaskResult(
            step="compute_constrained_injection",
            description="Applied per-well injection limits.",
            input_steps=["compute_unconstrained_injection"],
            data=deepcopy(previous.data),
        )

    def impose_facility_constraints(
        self, config, results
    ) -> TaskResult:
        previous = results["compute_constrained_injection"]

        return TaskResult(
            step="impose_facility_constraints",
            description="Applied facility injection limits.",
            parameters={
                "facility_max": config.get("facility_max")
            },
            input_steps=["compute_constrained_injection"],
            data=deepcopy(previous.data),
        )

    def producer_report(self, config, results) -> TaskResult:
        return TaskResult(
            step="producer_report",
            description="Generated the producer response report.",
            input_steps=["impose_facility_constraints"],
            data={"report": "Dummy producer report"},
        )

    # ---------------------------------------------------------
    # Graph wrappers
    # ---------------------------------------------------------

    def _make_node(self, step):
        def node(state: WorkflowState) -> dict:
            calculation = getattr(self, step)
            result = calculation(state["config"], state["results"])

            # Return a new mapping containing previous + new results.
            return {
                "results": {
                    **state["results"],
                    step: result,
                }
            }

        return node

    def _build_graph(self):
        builder = StateGraph(WorkflowState)

        for step in STEPS:
            builder.add_node(step, self._make_node(step))

        # A new execution can start at any workflow step.
        builder.add_conditional_edges(
            START,
            lambda state: state["start_step"],
            {step: step for step in STEPS},
        )

        for current, following in zip(STEPS, STEPS[1:]):
            builder.add_edge(current, following)

        builder.add_edge(STEPS[-1], END)
        return builder.compile()

    # ---------------------------------------------------------
    # Execution and tools available to an agent
    # ---------------------------------------------------------

    def run(self, config=None) -> WorkflowState:
        return self._execute(
            config=deepcopy(config or {}),
            start_step=STEPS[0],
            previous_results={},
        )

    def _execute(
        self, config, start_step, previous_results
    ) -> WorkflowState:
        state = self.graph.invoke({
            "run_id": str(uuid4()),
            "start_step": start_step,
            "config": config,
            "results": previous_results,
        })

        self.runs[state["run_id"]] = state
        return deepcopy(state)

    def get_step_result(self, run_id, step) -> TaskResult:
        """Tool: retrieve artifacts from a specific step."""
        return deepcopy(self.runs[run_id]["results"][step])

    def describe_run(self, run_id) -> dict:
        """Tool: provide lightweight context without large artifacts."""
        state = self.runs[run_id]

        return {
            "run_id": run_id,
            "config": deepcopy(state["config"]),
            "steps": {
                step: {
                    "description": result.description,
                    "parameters": deepcopy(result.parameters),
                    "available_data": list(result.data),
                }
                for step, result in state["results"].items()
            },
        }

    def rerun_from_step(
        self,
        run_id: str,
        start_step: str,
        config_updates: dict[str, Any],
    ) -> WorkflowState:
        """Tool: preserve upstream results and recompute downstream."""
        if start_step not in STEPS:
            raise ValueError(f"Unknown step: {start_step}")

        previous = self.runs[run_id]
        start_index = STEPS.index(start_step)

        # Only retain results before the changed step.
        retained_results = {
            step: deepcopy(previous["results"][step])
            for step in STEPS[:start_index]
        }

        config = deepcopy(previous["config"])
        config.update(config_updates)

        # TODO: validate parameters and which steps they affect.
        return self._execute(
            config=config,
            start_step=start_step,
            previous_results=retained_results,
        )

    def ask(self, query: str, run_id: str):
        """
        Future agent entry point:
        1. Read describe_run(run_id).
        2. Inspect artifacts through tools.
        3. Answer, or request a validated rerun.
        """
        raise NotImplementedError("Natural-language agent not added yet")


if __name__ == "__main__":
    workflow = InjectionWorkflow(llm=None)

    first = workflow.run({
        "max_decrease_fraction": 0.5,
        "facility_max": 1000.0,
    })

    # Inspect an intermediate result.
    result = workflow.get_step_result(
        first["run_id"],
        "compute_unconstrained_injection",
    )
    print(result.description)
    print(result.data)

    # Equivalent operation for:
    # "Limit decreases to 20%, keeping the same selected wells."
    second = workflow.rerun_from_step(
        run_id=first["run_id"],
        start_step="compute_unconstrained_injection",
        config_updates={"max_decrease_fraction": 0.2},
    )

    print("Original run:", first["run_id"])
    print("Modified run:", second["run_id"])
    