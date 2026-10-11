
import sys
from time import perf_counter
sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path

import copy 
from langchain.agents import create_agent

from langchain_core.tools import StructuredTool

from agentic_system.common.base_plan import ExecutorState
from agentic_system.common.base_task import DataFrameResult
#from agentic_system.components.coordinator_graph import OuterExecutor
from agentic_system.components.planner import * 
from agentic_system.components.direct_answer.direct_answer import * 
from agentic_system.components.results_interpreter import * 
from agentic_system.common.get_llm import azure_llm_if as get_llm 

from agentic_system.components.react_system.prompts import react_prompt_template
from agentic_system.components.planner.planner import get_default_planner
from agentic_system.components.results_interpreter.results_interpreter import ResultsInterpreterComponent, get_default_results_interpreter, prepare_test_data
import pprint
import inspect 
import importlib.metadata

from agentic_system.components.direct_answer.direct_answer import get_default_direct_answer
from agentic_system.components.data_analyst.input_data_analyst import *
from agentic_system.components.results_interpreter.results_interpreter import ResultsInterpreterComponent, get_default_results_interpreter, prepare_test_data

from agentic_system.components.presenter.presenter import * 


def task_result_to_text( task_result:TaskResult )->str:
    return task_result.cheap_output or " "

 
def get_as_structured_tool(initialized_component, depends_on: list[str]|None = None ) -> StructuredTool:
    """
    Returns a Component instance that can be used as a structured tool in LangChain.
    This tool generates a structured execution plan for the user query, containing a list of tasks with unique task_ids, assigned agents, and dependencies.
    """
 

    # Create the executable wrapper function on the fly
    def wrapper_func(query: str) :
        task_result =  initialized_component.run(query)
        to_return =  task_result_to_text( task_result ) 

        print(100*'=')
        print( to_return)
        print(100*'+')
             
        return to_return

    tool = StructuredTool.from_function(
                    func = wrapper_func,
                    name = initialized_component.agent_name,
                    description = initialized_component.description,
                )
    return tool 


def get_planner_as_structured_tool(initialized_component) -> StructuredTool:
    """
    Returns a Component instance that can be used as a structured tool in LangChain.
    This tool generates a structured execution plan for the user query, containing a list of tasks with unique task_ids, assigned agents, and dependencies.
    """
 

    # Create the executable wrapper function on the fly
    def wrapper_func(query: str) :
        plan = initialized_component.run(query)
        to_return = f"Plan:\n{plan.model_dump_json(indent=2)}"

        print(100*'=')
        print( to_return )
        print(100*'*')

                
        return to_return

    tool = StructuredTool.from_function(
                    func = wrapper_func,
                    name = initialized_component.agent_name,
                    description = initialized_component.description,
                )
    return tool 





class ReactSystem:

    def __init__( self, llm, prompt = None ):

        self.llm =  llm 
        self.execution_state = None 
        self.previous_state  = None 
        self.plan = None  
        self.query, self.previous_query = None, None 
        self.response = None 
        self.prompt = prompt if not prompt is None else react_prompt_template
        self.planner_component = get_default_planner()
        self.direct_answer = get_default_direct_answer( llm )
        self.interpreter =  get_default_results_interpreter( llm = self.llm )# ResultsInterpreterComponent( llm = llm )
        #interpreter.set_data( *prepare_test_data() )
       

        self.analyst = get_default_analyst( llm )
       
        self.presenter = PresenterComponent4( llm=llm)
      
        self.components =[
            self.planner_component,
            self.direct_answer,
            self.interpreter,
            self.analyst,
            self.presenter
        ]
        
        self.long_tasks_memory: dict[str, TaskResult] = {}

        self.turn_tasks_memory: dict[str, TaskResult] = {}

        for component in self.components:
            component.artifact_storage = self.turn_tasks_memory
 
        for component in self.components:
            print(100*'=')
            print( component.agent_name)
            print(100*'=')
                        
            print( component.description )
            #print(100*'-')
            print('\n')
        

        self.tools = [component.as_tool() for component in self.components if component !=  self.presenter ] 
       
        self.agent = create_agent(model = llm, 
                            system_prompt = react_prompt_template, 
                            tools=self.tools )
        
        print("done initializing the system")

    def run( self, query: str, previous_state: ExecutorState | None = None, run_presenter = True  ):

        self.previous_query = copy.deepcopy( self.query )
        self.query = query     
        self.turn_tasks_memory.clear()
        
        previous_task_ids = {}#set(self.artifact_storage)
        
        response = self._get_response( query )
        execution_state = self._build_state()  
        
        #self.plan = copy.deepcopy( self.planner_component.plan ) 

        if run_presenter:
            return self.get_presentation()
        
        return response 

    def get_presentation( self ):

        started = perf_counter()
        self.presenter_response = self.presenter.run(self.execution_state)
        
        print(f"Time in presenter finished {perf_counter() - started:.2f}s", flush=True)
        print("UI item count:", len(self.presenter_response.items))
        print_presenter_response(self.presenter_response,width = 90)

        return self.presenter_response

    def set_analyst_data(self, data):
        self.analyst.update_data( data ) 

    def set_interpreter_data(self, data):
        self.interpreter.update_data( data ) 

    def clear( self ):
        self.turn_tasks_memory.clear()
        self.long_tasks_memory.clear() 
        self.execution_state = None 
        self.previous_state  = None 
        self.plan = None  
        self.query, self.previous_query = None, None 
        self.response = None 
       
    def clear_memory( self ):
        return self.clear()
    
    def _get_response( self, query:str):

        started = perf_counter()
        agent = self.agent

        print(f"Time in seconds outer loop {perf_counter() - started:.2f}s", flush=True)
        response = agent.invoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": query,
                            }
                        ]
                    }
                )
        print(f"Time in seconds outer loop {perf_counter() - started:.2f}s", flush=True)

        self.response = response 
        return response 

    def _build_state( self ):


        current_task_results = {
            task_id: result
            for task_id, result in self.turn_tasks_memory.items()
        }

        presentation_state: ExecutorState = {
            #"messages": self.response["messages"], # type: ignore
            "user_query": query,
            "plan": None,
            "task_index_to_execute": 0,
            "task_results": list(current_task_results.values()),
            "cheap_tool_outputs": [
                result.cheap_output
                for result in current_task_results.values()
                if result.cheap_output
            ],
            "current_task_results": current_task_results,
            #"final_answer": self.response["messages"][-1].content, # type: ignore
            "clarification_request": None,
        }

        if self.response and "messages" in self.response:
            print("We have response messages")
            presentation_state['messages'] = self.response["messages"]
            presentation_state['final_answer'] = self.response["messages"][-1].content


        started = perf_counter()
        print(f"Time in seconds presenter called {perf_counter() - started:.2f}s", flush=True)

        
        self.previous_state = copy.deepcopy( self.execution_state )
        self.execution_state = presentation_state

        return self.execution_state


if __name__ == "__main__":


    query = "Whats VRR? and which is the most supported producer and which one is producing the most due to primary depletion?"
    query = "Identify the most supported producer, then explain the engineering meaning of the support metrics reported for that producer."
    query = "Compare the total liquid production per year"
    query = """Identify the 2 producers with the highest historical cummulated liquid-production. Are those producers in the simulation?. If they are, show me the supporting injectors for each and the related 
    gains """ 
    query = "Summarize main simulation results. Be brief, focus in the highlights"

    query = 'whats the best supported producer?'## whats the general quality of the simulations?'

    llm = get_llm() 

    agent = ReactSystem( llm )

    data, _ = prepare_test_data( )
    agent.set_interpreter_data( data )

    inj, prod,locs =get_default_data()
    agent.set_analyst_data( {'injectors':inj,'producers':prod, 'locations':locs } )



    response =  agent.run( query )
    print( response )

    import time
    print("Starting pause...")
    time.sleep(2) 
    print("awake")

    response =  agent.run( query )
    print( response )
    print() 


