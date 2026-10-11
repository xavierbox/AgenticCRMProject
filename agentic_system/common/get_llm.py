
 
from langchain.tools import tool, ToolRuntime
from langgraph.runtime import get_runtime 
from langchain.agents import create_agent
from langchain_core.runnables import RunnableLambda
import os 
from langchain_openai import AzureChatOpenAI
#import dataiku 

def laptop_azure_llm_if(imodel:str|None=None,iazure_endpoint:str|None=None,
                 ideployment:str|None=None, iapi_version:str|None=None,):

    endpoint = iazure_endpoint or os.environ['AZURE_OPENAI_ENDPOINT']
    #model_name = "gpt-4o"
    model_name = imodel or "gpt-4.1"
    
    deployment = ideployment or "gpt-4"

    #model_name = "gpt-4o-mini"
    #deployment = "gpt-4o-mini"

    api_version = iapi_version or "2024-12-01-preview"
    
    print('zero temp, seed 42, top_p = 1')
    llm = AzureChatOpenAI(
        azure_deployment=deployment,
        model=model_name,
        temperature=0.0,
        top_p=1.0,
        seed=42,
        azure_endpoint=endpoint,
        api_key=os.environ['AZURE_OPENAI_API_KEY'], # type: ignore
        api_version=api_version,
    )
     
    return llm 

 
def dataiku_azure_llm_if( llm_id:str = "azureopenai:if-digital:gpt-4.1" ):   
    client = dataiku.api_client()
    project = client.get_default_project()
    #llm_id = 'azureopenai:production_genai:gpt-4.1'
    #llm_id = 'azureopenai:production_genai:gpt-4.1'
    #llm_id = "azureopenai:if-digital:gpt-4o" #payload['llm_id']
    #llm_id= "azureopenai:if-digital:gpt-4.1"
    #print('Initializing isolated Dataiku-LangChain model with precise configurations...')
    # Pass model parameters inside the model_kwargs dictionary block 
    # to keep the top-level parameters clear for Pydantic
    llm = DKUChatModel(llm_id = llm_id, temperature=0.0, top_p = 1.0)
    return llm 

azure_llm_if = laptop_azure_llm_if
