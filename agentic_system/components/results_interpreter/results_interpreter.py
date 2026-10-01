
import inspect
import sys
sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path

from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.tools import StructuredTool

from agentic_system.common.base_task import TaskExecutionContext, TaskResult, TextResult
from agentic_system.common.get_llm import azure_llm_if


class ResultsInterpreterComponent:
    """Specialized in interpreting results from CRM simulations. 
    Use this tool to produce a structured summary of the results, including key metrics, insights, and recommendations.
    """
    agent_name = "results_interpreter"

    _artifact_storage: dict[str, TaskResult]|None = None

    @property
    def artifact_storage(self):
        return self._artifact_storage
    
    @artifact_storage.setter
    def artifact_storage(self, value):
        self._artifact_storage = value


    @property
    def description(self) -> str | None:
        """Returns the properly formatted class docstring."""
        if not self.__doc__:
            return None
        return inspect.cleandoc(self.__doc__)

    def build_context_from_task_ids(self,task_ids:list[str]|None=None):

        # fetch from artifact storage the task ids 
        # create a TaskExecutionContext with 
        # dependencies

        if not task_ids is None and self.artifact_storage is not None:
           
            storage = self.artifact_storage
            dependency_results = []
            for task_id in task_ids:

                task_result = storage.get(task_id, None)
                dependency_results.append(task_result)

            context = TaskExecutionContext(
                dependency_results=dependency_results
            )

            return context

        return None 

                                    
    def run(
        self,
        query: str,
        messages: list[AnyMessage] | None = None,
        context: TaskExecutionContext | None = None,
    ) -> TaskResult:
        """Return fixed demo results without calling an LLM."""
        answer = (
            "The best supported producer is P1, being is supported by injectors "
            "I1 and I2, with gains of 0.38 and 0.30 respectively. "
            "Producer P3 is the second best with gains of 0.25 and 0.20 from injectors I1 and I2. "
            "These results confirm a good connectivity between wells."
        )

        return TaskResult(
            agent=self.agent_name,
            instruction=query,
            cheap_output=answer,
            raw_results=[
                {
                    "demo": True,
                    "producer": "P1",
                    "supporting_injectors": [
                        {"injector": "I1", "gain": 0.38},
                        {"injector": "I2", "gain": 0.30},
                    ],
                }
            ],
            data_results=[
                TextResult(
                    text=answer,
                    role="answer",
                )
            ],
        )


def get_results_interpreter_as_structured_tool() -> StructuredTool:
    """
    Returns a ResultsInterpreterComponent instance that can be used as a structured tool in LangChain.
    This tool interprets results from CRM simulations and produces a structured summary.
    """
    interpreter =  ResultsInterpreterComponent()
    description = interpreter.description 

    # Create the executable wrapper function on the fly
    def wrapper_interpreter(query: str, task_result_ids: list[str] | None = None) -> str:
        
        context = interpreter.build_context_from_task_ids(task_result_ids)
        task_result = interpreter.run(query,context=context)
        return task_result.cheap_output or "No output produced."


    tool = StructuredTool.from_function(
                    func = wrapper_interpreter,
                    name = "results_interpreter",
                    description = description,
                )
    return tool 

def test_interpreter():
    interpreter = ResultsInterpreterComponent()
    result = interpreter.run(query="Test query")
    return result 

def test_interpreter_as_tool():
    tool = get_results_interpreter_as_structured_tool()
    result = tool.invoke({"query": "Test query"})
    return result 

if __name__ == "__main__":

 
    response = test_interpreter()
    print( response )
    print( type(response) )
    print() 


    response = test_interpreter_as_tool()
    print( type(response) )
    print() 
