
import sys, pprint
sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from agentic_system.common.get_llm import azure_llm_if 
from agentic_system.common import * 


print_hello()  # Call the function from agentic_system.common



prompt = """provide very short answers about fruits and nothig else. 
If you are asked about anything else, respond with 'I only answer questions about fruits.'

Examples:
Q: What is the capital of France?
R: I only answer questions about fruits.

Q: What is an apple?
R: An apple is a sweet, edible fruit produced by an apple tree (Malus domestica). 
"""

query="what is an apple?"
agent = create_agent(model=azure_llm_if(), system_prompt=prompt)

RUN_AGENT = False  
if RUN_AGENT:
    response = agent.invoke({
                "messages": [
                    {"role": "user", "content": query}
                ]
            })
    print(response)  # Should provide a short answer about apples
    print(100*'=')
    print( response['messages'][-1].content )
    print(100*'=')