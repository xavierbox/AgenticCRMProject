from typing import List
from pydantic import Field

from agentic_system.common.semantic_models import SemanticContext


class ResultsInterpreterSemanticContext( SemanticContext): 
    interpretation_guidelines: List[str] = Field(
        default_factory=list,
        description=(
            "Guidelines for interpreting data, combining evidence, "
            "identifying patterns, and forming conclusions."
        )
    )
