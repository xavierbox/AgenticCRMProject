import sys

sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path

from agentic_system.components.data_analyst.input_data_analyst import *
from agentic_system.components.results_interpreter.results_interpreter import ResultsInterpreterComponent, get_default_results_interpreter, prepare_test_data


from agentic_system.components.react_system.react_agent import *
from agentic_system.webapp_coupling.ui_state import UIState, process_ui_state_changes

ui_state = UIState() 
agent = ReactSystem(get_llm())

# request arrives from the UI
payload  = {
    # reaches the route: [results_interpreter_query]
    'subzone': 'LW', 
    'project_name': 'Demo1', 
    'study_name': 'KovalExtrapolation', 
    'data_dates': ['2020-10-05', '2021-11-25'], 
    #'sectors': [0], 
    'user_query': 'This is a query received in the backend'
}


(project_changed, 
 study_changed, 
 data_changed
)  = process_ui_state_changes( ui_state=ui_state,payload=payload, agentic_system=agent)
print(project_changed, 
 study_changed, 
 data_changed
) 

print()

