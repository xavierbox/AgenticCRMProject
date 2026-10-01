
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter
from typing_extensions import Self
from typing import Any,Annotated, Dict, Generic, List, Iterable, Literal, TypeVar, Union, Optional,TypedDict
from pydantic import BaseModel, Field, model_validator

from langchain_core.messages import HumanMessage, AIMessage, AnyMessage#
from langgraph.graph.message import add_messages

from agentic_system.common.base_task import ExecutionTask, TaskResult


class ExecutorState(TypedDict):
    """
    Shared graph execution state.

    This is the persistent state passed between graph nodes.


    task_results	Historical results across turns; used for the planner’s catalog and future previous-turn dependencies
    current_task_results	Maps current-plan task IDs to completed results for resolving depends_on


    """
    messages: Annotated[list[AnyMessage], add_messages]

    user_query: str
    plan: Any | None
    task_index_to_execute: int

    #facts_context: str
    task_results: list[TaskResult]
    
    cheap_tool_outputs: list[str]


    current_task_results: dict[str, TaskResult]

    final_answer: str | None
    clarification_request: str | None
    #waiting_for_user: bool

class ExecutionPlanTemplate(BaseModel):
    user_intent: str = Field(
        description="One-sentence summary of the user's ultimate goal."
    )
    tasks: List[ExecutionTask] = Field(
        description="The macro-level pipeline. List of Task entries assigned to agents."
    )

    @model_validator(mode="after")
    def validate_execution_plan(self) -> "ExecutionPlanTemplate":
        """
        Comprehensive validator that ensures:
        1. All referenced dependency IDs exist.
        2. There are no circular dependencies (deadlocks).
        """
        # --- 1. Validate Dependency IDs Exist ---
        existing_ids = {task.task_id for task in self.tasks}

        task_ids = [task.task_id for task in self.tasks]

        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Task IDs must be unique within a plan.")


        for task in self.tasks:
            if task.depends_on:
                for dependency in task.depends_on:
                    if dependency not in existing_ids:
                        raise ValueError(
                            f"LLM Generation Error: Task '{task.task_id}' depends on '{dependency}', "
                            f"but '{dependency}' was never defined in the tasks list."
                        )
        
        # --- 2. Validate No Circular Dependencies ---
        try:
            ts = TopologicalSorter()
            for task in self.tasks:
                dependencies = task.depends_on if task.depends_on else []
                # graphlib expects: ts.add(node, *predecessors)
                ts.add(task.task_id, *dependencies)
            
            # This triggers a CycleError if an infinite loop exists
            ts.prepare()
        except CycleError as e:
            raise ValueError(
                f"Circular Dependency Error: The LLM generated a plan with an infinite loop deadlock: {e}"
            )
                        
        return self

    @property
    def execution_order(self) -> List[ExecutionTask]:
        """Returns the tasks sorted chronologically by their execution order."""
        task_lookup = {task.task_id: task for task in self.tasks}
        
        ts = TopologicalSorter()
        for task in self.tasks:
            dependencies = task.depends_on if task.depends_on else []
            ts.add(task.task_id, *dependencies)
        
        return [task_lookup[task_id] for task_id in ts.static_order()]
