
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
from agentic_system.common.get_llm import azure_llm_if as get_llm 

from agentic_system.components.react_system.prompts import react_prompt_template
from agentic_system.components.planner.planner import get_default_planner
import pprint
import inspect 
import importlib.metadata

from agentic_system.components.direct_answer.direct_answer import get_default_direct_answer
from agentic_system.components.data_analyst.input_data_analyst import *
from agentic_system.components.results_interpreter.results_analyst import (
    ResultsAnalyst,
    get_default_results_analyst,
    prepare_test_data,
)
from agentic_system.components.presenter.presenter import * 
from agentic_system.common.utils import export_presenter_response_html



def task_result_to_text( task_result:TaskResult )->str:
    return task_result.cheap_output or " "


def _xx_format_query_text(query: str) -> str:
    text = str(query or "")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    return "\n".join(lines)

 
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
        self.results_analyst = get_default_results_analyst(self.llm)
       

        self.analyst = get_default_analyst( llm )
       
        self.presenter = PresenterComponent4( llm=llm)
      
        self.components =[
            self.planner_component,
            self.direct_answer,
            self.results_analyst,
            self.analyst,
            self.presenter
        ]
        
        self.long_tasks_memory: dict[str, TaskResult] = {}

        self.turn_tasks_memory: dict[str, TaskResult] = {}

        for component in self.components:
            component.artifact_storage = self.turn_tasks_memory
 
        self.tools = [component.as_tool() for component in self.components if component !=  self.presenter ] 
       
        self.agent = create_agent(model = llm, 
                            system_prompt = react_prompt_template, 
                            tools=self.tools )
        

    def run( self, query: str, previous_state: ExecutorState | None = None, run_presenter = True  ):

        query = _xx_format_query_text(query)

        started = perf_counter()
        print(
            "\n====== [RUN START] ======\n"
            "agent: react_system\n"
            f"instruction: {query}\n"
            "=========================",
            flush=True,
        )

        self.previous_query = copy.deepcopy( self.query )
        self.query = query     
        self.turn_tasks_memory.clear()
        
        previous_task_ids = {}#set(self.artifact_storage)
        
        response = self._get_response( query )
        execution_state = self._build_state()  
        
        #self.plan = copy.deepcopy( self.planner_component.plan ) 

        if run_presenter:
            response = self.get_presentation()
            elapsed = perf_counter() - started
            print(
                "\n====== [RUN END] ======\n"
                "agent: react_system\n"
                "elapsed: {:.2f}s\n"
                "=======================".format(elapsed),
                flush=True,
            )
            print(response, flush=True)
            return response
        
        elapsed = perf_counter() - started
        print(
            "\n====== [RUN END] ======\n"
            "agent: react_system\n"
            "elapsed: {:.2f}s\n"
            "=======================".format(elapsed),
            flush=True,
        )
        print(response, flush=True)
        return response 

    def get_presentation( self ):

        started = perf_counter()
        self.presenter_response = self.presenter.run(self.execution_state)

        return self.presenter_response

    def set_analyst_data(self, data):
        self.analyst.update_data( data ) 

    def set_interpreter_data(self, data):
        self.results_analyst.update_data( data )

    def set_results_analyst_data(self, data):
        self.results_analyst.update_data(data)

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
        self.response = response 
        return response 

    def _build_state( self ):


        current_task_results = {
            task_id: result
            for task_id, result in self.turn_tasks_memory.items()
        }

        presentation_state: ExecutorState = {
            #"messages": self.response["messages"], # type: ignore
            "user_query": self.query or "",
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
            presentation_state['messages'] = self.response["messages"]
            presentation_state['final_answer'] = self.response["messages"][-1].content

        
        self.previous_state = copy.deepcopy( self.execution_state )
        self.execution_state = presentation_state

        return self.execution_state


if __name__ == "__main__":



    llm = get_llm() 

    agent = ReactSystem( llm )

    data, _, _, _ = prepare_test_data()
    agent.set_results_analyst_data(data)

    inj, prod,locs =get_default_data()
    agent.set_analyst_data( {'injectors':inj,'producers':prod, 'locations':locs } )

    #query = "Whats VRR? and which is the most supported producer and which one is producing the most due to primary depletion?"
    
    query="Want to optimize injection to increase the most the oil produced volume while increasing the less water produced, which injectors should I boost. Explain how you came to that answer "
    #query = "Identify the most supported producer, then explain the engineering meaning of the support metrics reported for that producer."
    #query = "Compare the total liquid production per year"
    #query = """Identify the 2 producers with the highest historical cummulated liquid-production. Are those producers in the simulation?. If they are, show me the supporting injectors for each and the related  gains """ 
    #query = "Summarize main simulation results. Be brief, focus in the highlights"
    #query = 'whats the best supported producer?'## whats the general quality of the simulations?'
    #query = "Explain the concept of VRR"
    #query = "List wells with watercut above 0.5"
    #query="""Make a summary of the quality of the simulations and show in a pie chart  
    #the percent of the total production of all the wells combined that is due to injectionm, pressure and primary depletion"""

    #query="""from the simulation results show in a bar chart the percent of the total production of all the wells combined that is due to injection, pressure and primary depletion"""

    #query="""Can you show in a bar chart the percent of production volumes currently (oil, gas and water)
    #from the data in the simulation results? 
    #"""

    #query = "Find the top 5 wells wuith the highest current oil to water production ratio in the input dataset. List the names and then check whether those wells are in the simulation data"

    #query = "List the injectors in decreasing order depending on their attributable oil produced. " \
    #"then estimate what fraction of the total water injected is due to the the top 2. Explain briefly what you did"

    query="""First explain brieflt what VRR is. Then plot the monthly aggregated VRR (aggregate well contributions),   
    From the simulation results, also identify the top 2 producers 
    by total allocation (best supported), and then plot a bar chart 
    of their current liquid production due to injection, pressure, and depletion.
    I also want to see a pie chart of the total volumes of oil and water produced among all the 
    producers in the model
    """

        
    response =  agent.run( query )
    print( response )
    print()
    export_presenter_response_html(response, "presenter_output.html")
    #import time
    #print("Starting pause...")
    #time.sleep(2) 
    #print("awake")

    #response =  agent.run( query )
    #print( response )
    #print() 


