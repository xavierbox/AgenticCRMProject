
import sys
from time import perf_counter
sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path

from langchain.agents import create_agent

from langchain_core.tools import StructuredTool

from agentic_system.common.base_plan import ExecutorState
from agentic_system.common.base_task import DataFrameResult
from agentic_system.components.coordinator_graph import OuterExecutor
from agentic_system.components.planner import * 
from agentic_system.components.direct_answer.direct_answer import * 
from agentic_system.components.results_interpreter import * 
from agentic_system.common.get_llm import azure_llm_if as get_llm 

from agentic_system.components.planner.planner import get_default_planner
from agentic_system.components.results_interpreter.results_interpreter import ResultsInterpreterComponent, get_default_results_interpreter, prepare_test_data
import pprint
import inspect 
import importlib.metadata

from agentic_system.components.direct_answer.direct_answer import get_default_direct_answer
from agentic_system.components.data_analyst.input_data_analyst import *

from agentic_system.components.presenter.presenter import * 

react_prompt_template = """
You act as an expert agent running in the backend of a an application that uses capacitance-resistance models (CRM) to simulate waterflood.
Your job is to answer user questions using the tools provided and your own knowledge.

=====================
Background
=====================
The information in the application is organized into projects. Each project contains one or more 'simulations' and 'input data'. 
You must assume that the data is available for a project selected by the user in a graphical interface.
The user might have selected one or none simulations to analyze. If one is selected, the simulation results will be available.

===============================================================================
PROJECT INFORMATION MODEL
===============================================================================

A project contains three main types of information:

1. INPUT DATA
   Observed historical/project data, including:
   - injection rates
   - production rates
   - producer BHP/pressure, when available
   - well locations
   - well type, sector, subzone, and related metadata

2. MODEL CONFIGURATION
   Settings used to construct and run the simulation, including:
   - modelling timeframe
   - distance screening
   - selected injector-producer pairs
   - wells included or excluded from modelling
   - other simulation parameters

3. SIMULATION RESULTS
   Information produced by the waterflood/CRM simulation, including:
   - injector-producer connectivity
   - model parameters
   - history-match curves
   - history-match quality metrics
   - modelled well support


===============================================================================
APPLICATION-SPECIFIC TERMINOLOGY
===============================================================================

Within this application:

Injector utility:
The useful support an injector provides to one or more producers. An injector
strongly connected to producing wells has high injector utility.

Injector connectivity:
A model-derived quantity describing the relationship between an injector and
producer. Connectivity information is available in simulation results.

Producer support:
A producer is considered supported when it has meaningful connectivity with
one or more injectors.

Producer utility:
The production level of oil relative to the total liquid produced by the well.

Channeling / thief-zone behaviour:
Potential preferential flow where injected water reaches producers unusually
strongly or rapidly. Evidence may involve connectivity and other simulation
results and must be interpreted by the appropriate specialist.


===============================================================================
DEFAULT TERMINOLOGY
===============================================================================

Unless context indicates otherwise:

- "data" refers to project INPUT DATA.
- "historical data" refers to observed INPUT DATA.
- "results" refers to SIMULATION / CRM RESULTS.
- "model" generally refers to the CRM/waterflood simulation.
- "connectivity" refers to model-derived injector-producer connectivity obtained as part of simulation results.

===============================================================================
PLANNING AND TASK EXECUTION
===============================================================================
- Ask for clarification when necessary to understand the request.
- Before answering, call the planner tool to generate an execution plan.
- Execute the tasks in the returned plan using their assigned tools.
- For each execution tool call:
  - Pass the task's instruction as query.
  - Pass the exact task_id assigned by the planner.
  - Pass the task's depends_on list unchanged, or None if it has no dependencies.
- Execute a task only after all its dependencies have completed successfully.
- Task results are stored automatically under their task_id. Dependency results
  are retrieved automatically when depends_on is supplied.
- Do not invent dependency IDs or reference tasks that have not completed.
- If a task fails, do not execute tasks that depend on it. Resolve the failure
  or explain the limitation.
- If the planner returns an empty or failed plan, do not treat it as completed
  work. Explain the planning failure or request clarification as appropriate.
- After completing the tasks, combine their outputs into a clear answer to the
  user's original question.
- Ground project-specific conclusions in tool results. Do not invent findings.


===============================================================================
TOOLS PROVIDED 
===============================================================================
-planner:
Generates a structured execution plan for the user query. 
The plan contains be a list of tasks, each with a unique task_id, an agent responsible for executing it, and any dependencies on other tasks. 
Use this tool to generate a plan.

-direct_answer:
Use for questions that can be answered from stable engineering or generalknowledge without accessing project-specific data or simulation results.
    Examples:
    - What is VRR?
    - What is WOR?
    - What is the density of water at room temperature?
    - How is API gravity calculated?
    - What is waterflood breakthrough?

Do NOT use direct_answer when answering requires inspecting project input data,model configuration, or simulation results.
"""

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


llm = get_llm() 
planner_component = get_default_planner()
print( planner_component.description )

direct_answer = get_default_direct_answer( llm )
print( direct_answer.description )

interpreter = ResultsInterpreterComponent( llm = llm )
interpreter.set_data( *prepare_test_data() )

analyst = get_default_analyst()

presenter = PresenterComponent4( llm=llm)


artifact_storage: dict[str, TaskResult] = {}
direct_answer.artifact_storage = artifact_storage
interpreter.artifact_storage = artifact_storage
analyst.artifact_storage = artifact_storage
presenter.artifact_storage = artifact_storage


tools = [
    planner_component.as_tool(),
    direct_answer.as_tool(),
    interpreter.as_tool(),
    analyst.as_tool()
]

 
print("Creating the outer agent")
agent = create_agent(model = llm, 
                     system_prompt=react_prompt_template, 
                     tools=tools )
print("done")





query = "Whats VRR? and which is the most supported producer and which one is producing the most due to primary depletion?"
query = "Identify the most supported producer, then explain the engineering meaning of the support metrics reported for that producer."
query = "Compare the total liquid production per year"
query = """Identify the 2 producers with the highest historical cummulated liquid-production. 
Are those producers in the simulation?. If they are, show me the supporting injectors for each and the related 
gains """ 

previous_task_ids = set(artifact_storage)

print("invoking")

started = perf_counter()
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


print("done")

current_task_results = {
    task_id: result
    for task_id, result in artifact_storage.items()
    if task_id not in previous_task_ids
}

presentation_state: ExecutorState = {
    "messages": response["messages"],
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
    "final_answer": response["messages"][-1].content,
    "clarification_request": None,
}

started = perf_counter()
print(f"Time in seconds presenter called {perf_counter() - started:.2f}s", flush=True)
presenter_response = presenter.run(presentation_state)
print(f"Time in presenter finished {perf_counter() - started:.2f}s", flush=True)

print("UI item count:", len(presenter_response.items))
for item in presenter_response.items:
    print(item.id, item.type)
    
print()




#print( response['messages'][-1].content )
#print() 

