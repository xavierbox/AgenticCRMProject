from dataclasses import dataclass, field

from typing_extensions import Self
from typing import Any, Dict, Generic, List, Iterable, Literal, TypeVar, Union, Optional,TypedDict
from typing_extensions import Self
from pydantic import BaseModel, Field


from pydantic import BaseModel, Field

class TextResult(BaseModel):
    text: str
    role: str = "answer"

class DataFrameResult(BaseModel):
    table_name: str
    description: str | None = None
    #dataframe: Any
    records: Any 



class TaskResult(BaseModel):
    """
    Output produced by one executed task.

    This object separates the task output into three layers:
    cheap prompt context, raw agent-specific outputs, and normalized
    downstream-consumable data.

    agent: str the name of the agent
    instruction: str the instruction passed to the agent
    cheap_output: the agent might return a short text, or similar to be added to context.Cheap, few tokens
    raw_results: 
    data_results: downstream other modules will consume these results. The  related data is here 
    """

    agent: str = Field(
        description="Name of the agent/component that executed the task."
    )

    instruction: str = Field(
        description="Original instruction given to the agent/component."
    )

    cheap_output: str | None = Field(
        default=None,
        description=(
            "Short, cheap textual summary of the result. "
            "This is intended to be added to facts_context and reused in prompts."
        ),
    )

    raw_results: list[Any] = Field(
        default_factory=list,
        description=(
            "Original agent-specific outputs, such as structured LLM responses, "
            "Pydantic models, tool call responses, or metadata objects."
        ),
    )

    data_results: list[TextResult|DataFrameResult] = Field(
        default_factory=list,
        description=(
            "Materialized downstream-friendly objects, such as DataFrames, "
            "figures, arrays, or tables. Downstream components should consume "
            "these without knowing the raw output schema."
        ),
    )

 





class BaseSystemTask(BaseModel):
    instruction: str = Field(
        description=(
            "The comprehensive, high-level objective for this agent phase. "
            "Do NOT break down sub-steps, intermediate calculations, or plotting adjustments. "
            "Provide the complete end-goal description verbatim so the receiving agent "
            "can handle its own internal execution steps."
        )
    )
    agent: str = Field(
        description=(
            "The name of the specific domain-expert agent assigned to execute this task."
        )
    )

class ExecutionTask(BaseSystemTask):

    task_id: str = Field(
        description=(
            "A unique identifier for this task. "
            "Use a simple, human-readable format that can be referenced in downstream tasks "
            "and that reflects the task's purpose. For example: 'plot_the_VRR_over_time_for_sector_1','list_all_sectors_in_input_dataset', identify_top5_producers_by_support_level'"
        )
    )

    depends_on: Optional[List[str]] = Field(
        description=(   
        "List of task_ids that this task depends on. "
        "If this task requires the output of other tasks, list their task_ids here. "
        "If there are no dependencies, leave this field empty or null."
        )
    )
    

@dataclass
class TaskExecutionContext:
    #task: ExecutionTask
    dependency_results: list[TaskResult] = field(default_factory=list)
