

import inspect
from pathlib import Path
import sys

import inspect
import sys

import pandas as pd
sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path


from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.tools import StructuredTool

from agentic_system.common.base_task import TaskExecutionContext, TaskResult, TextResult
from agentic_system.common.get_llm import azure_llm_if


class DataAnalyst:
    """Specialized in quantitative analysis of the input data. 
    Use this tool to answer questions about the data, perform calculations, and provide insights based on the data.
    """
    agent_name = "data_analyst"

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
            "The forecated amount of oil is 2231.22 with a VRRR of 1.2"
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


class MockDataDrivenStorage:
        
    def __init__( self, config_vars ):
        pass 

    def get_project_dataset(self, project_name=None, filters=None):
        #path =  "../datasets/Demo1/"
        path =  Path("C:/Work/2026/AgenticCRMProject/agentic_system/datasets/IX5I_4P/") 
        print( str(path.resolve()) )
        print(f"{path}")
        print() 

        inj, prod, locs = self.fetch_data(path) 

                        
        return inj, prod, locs

    def fetch_data(self,path:Path):
        inj  = pd.read_csv(path / "injectors.csv")
        pinj = pd.read_csv(path / "producers.csv")
        locs = pd.read_csv(path / "locations.csv")
        inj['DATE'] = pd.to_datetime( inj['DATE'],dayfirst=True)
        inj['DAY']   = inj['DATE'].dt.day
        inj['MONTH'] = inj['DATE'].dt.month
        inj['YEAR']  = inj['DATE'].dt.year
        pinj['DATE'] = pd.to_datetime( pinj['DATE'],dayfirst=True)
        pinj['DAY']   = pinj['DATE'].dt.day
        pinj['MONTH'] = pinj['DATE'].dt.month
        pinj['YEAR']  = pinj['DATE'].dt.year


        return inj, pinj, locs


def get_data_analyst_as_structured_tool() -> StructuredTool:
    """
    Returns a DataAnalyst instance that can be used as a structured tool in LangChain.
    This tool answers questions about the data, performs calculations, and provides insights.
    """
    analyst =  DataAnalyst()
    description = analyst.description 

    # Create the executable wrapper function on the fly
    def wrapper_analyst(query: str, task_result_ids: list[str] | None = None):# -> str:
        
        context = analyst.build_context_from_task_ids(task_result_ids)
        task_result = analyst.run(query,context=context)
        return task_result#.cheap_output or "No output produced."


    tool = StructuredTool.from_function(
                    func = wrapper_analyst,
                    name = "data_analyst",
                    description = description,
                )
    return tool 

def test_component():
    analyst = DataAnalyst()
    result = analyst.run(query="Test query")
    return result 

def test_component_as_tool():
    tool = get_data_analyst_as_structured_tool()
    result = tool.invoke({"query": "Test query"})
    return result 

if __name__ == "__main__":


    storage = MockDataDrivenStorage( None ) 
    inj, prod, locs = storage.get_project_dataset(); 
    print( inj.sample(3))
    print( prod.sample(3))
    print( locs.sample(3)) 
    print() 





    #response = test_component()
    #print( response )
    #print( type(response) )
    #print() 


    #response = test_component_as_tool()
    #print( type(response) )
    #print() 

