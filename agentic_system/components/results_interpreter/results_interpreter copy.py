
import inspect as inspect_module
import sys
from pathlib import Path

from time import perf_counter
from pydantic import BaseModel, Field
from typing import Iterable, List, Literal, Optional
from langchain.agents.structured_output import ToolStrategy
from threading import Lock
sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path

from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.tools import StructuredTool

from agentic_system.common.base_task import DataFrameResult, TableItemAgentResponse, TaskExecutionContext, TaskResult, TextResult
from agentic_system.common.get_llm import azure_llm_if
from agentic_system.components.results_interpreter.semantic_context import ResultsInterpreterSemanticContext


from langchain.agents import create_agent

#from agentic_system.common.semantic_models import SemanticCatalog 

from dataclasses import dataclass
import sys, pprint, pandas as pd , os, json, re, plotly.io as pio 
from pathlib import Path
from typing_extensions import Self
from typing import Any, Optional, cast

from agentic_system.common.get_llm import azure_llm_if as get_llm
from agentic_system.components.results_interpreter.prompts import RESULTS_INTERPRETER_PROMPT_TEMPLATE
from agentic_system.common.data_component import BaseDataComponent, BaseDomainTools, SmartData, SmartDataTools
from agentic_system.common.semantic_models import CatalogTablesSnapshot, ColumnCard, SemanticCatalog, SemanticContext, TableCard


from agentic_system.components.results_interpreter.known_tables_models import (
    interpreter_semantic_catalog,
    interpreter_semantic_context,
)
from langchain.agents.structured_output import ToolStrategy
class ResultsInterpreterData(BaseDataComponent):
    """
    Data component for CRM simulation results.

    Stores the result tables, simulation metadata, configuration,
    and logs required by ResultsInterpreterComponent and its tools.
    """
    def get_connectivity_table(self) -> pd.DataFrame:
        """
        Return the injector-producer connectivity table.

        The table contains one row per modeled injector-producer pair.
        """
        self._check_if_data()

        if "connectivity_table" not in self.raw_data:
            raise KeyError(
                "connectivity_table was not found in the ResultsInterpreter data."
            )

        return self.raw_data["connectivity_table"]

    def get_simulation_quality_table(self) -> pd.DataFrame:
        """
        Return the producer-level simulation quality table.

        The table contains one row per producer.
        """
        self._check_if_data()

        if "simulation_quality_table" not in self.raw_data:
            raise KeyError(
                "simulation_quality_table was not found in the ResultsInterpreter data."
            )

        return self.raw_data["simulation_quality_table"]

    def get_producer_model(self, producer_names: list[str] | None = None) -> pd.DataFrame:
        """
        Return the producer-level model table.

        The table contains one row per producer.
        """
        self._check_if_data()

        if "producer_model_table" not in self.raw_data:
            raise KeyError(
                "producer_model_table was not found in the ResultsInterpreter data."
            )

        df = self.raw_data["producer_model_table"]
        if producer_names is not None:
            df = df[df["PRODUCER"].isin(producer_names)]
        return df       

    def get_injector_summary(self, injector_names: list[str] | None = None) -> pd.DataFrame:    
        
        """
        Return the injector-level summary table.

        The table contains one row per injector.
        """
        self._check_if_data()

        if "connectivity_table" not in self.raw_data:
            raise KeyError(
                "connectivity_table was not found in the ResultsInterpreter data."
            )

        df = self.raw_data["connectivity_table"]
        if injector_names is not None:
            df = df[df["INJECTOR"].isin(injector_names)]

        summary_rows = []

        for injector, group in df.groupby("INJECTOR", sort=False):

            strongest_idx = group["GAIN"].idxmax()
            strongest_row = group.loc[strongest_idx]

            summary_rows.append(
                {
                    "INJECTOR": injector,
                    "UTILITY": group["GAIN"].sum(),
                    "NUMBER_SUPPORTED_PRODUCERS": (
                        group.loc[group["GAIN"] >= 0.05, "PRODUCER"].nunique()
                    ),
                    "MAX_GAIN": strongest_row["GAIN"],
                    "STRONGEST_CONNECTED_PRODUCER": strongest_row["PRODUCER"],
                }
            )

        return pd.DataFrame(summary_rows).sort_values("UTILITY", ascending=False).reset_index(drop=True)    

    def get_simulation_config(self) -> Any:
        """
        Return the simulation configuration.

        The configuration contains the parameters used to run the simulation.
        """
        self._check_if_data()

        if "simulation_config" not in self.raw_data:
            raise KeyError(
                "simulation_config was not found in the ResultsInterpreter data."
            )

        return self.raw_data["simulation_config"]

    def get_simulation_logs(self) -> Any:
        """
        Return the simulation logs.

        The logs may contain:
        - simulation or modeling errors;
        - reasons why specific wells were not modeled;
        - warnings and other messages produced by the simulation engine.
        """
        self._check_if_data()

        if "simulation_logs" not in self.raw_data:
            raise KeyError(
                "simulation_logs were not found in the ResultsInterpreter data."
            )

        return self.raw_data["simulation_logs"]         

class ResultsInterpreterTools(BaseDomainTools[ResultsInterpreterData]):

    def _no_generate_summary(self):
        """Generates a summary of simulation results."""
        return "all results were produced, status = 200"

    @property
    def data(self) -> ResultsInterpreterData:
        return self.data_component

    @property
    def raw_data(self) -> Any:
        return self.data_component.raw_data

    def _get_connectivity_table(
        self,
        producer_names: list[str] | None = None,
        injector_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return CRM injector-producer connectivity results.

        Each returned record represents one modeled injector-producer pair.

        Important column semantics:
        - GAIN:
        Fraction of water injected in an injector that is recovered as
        liquid production in the producer. GAIN is injector-centric.
        - PALLOCATION:
        Fraction of the producer's total liquid production attributed to
        injection from that specific injector. PALLOCATION is producer-centric.
        - GAIN_CLASS:
        Classification of GAIN. Gains below 0.05 are negligible.

        Parameters
        ----------
        producer_names:
            Optional list of producer well names to keep.

            If None:
                Do not filter by producer.

            If provided:
                Return only rows whose PRODUCER value is in this list.

        injector_names:
            Optional list of injector well names to keep.

            If None:
                Do not filter by injector.

            If provided:
                Return only rows whose INJECTOR value is in this list.

        Filtering behavior
        ------------------
        If both producer_names and injector_names are provided, both filters
        are applied.

        These parameters only filter rows by well name. They do not rank wells,
        apply GAIN thresholds, or change the meaning of the CRM results.

        Returns
        -------
        list[dict[str, Any]]
            Connectivity records, one record per injector-producer pair.
        """

        print("[get_connectivity_table]")
        df = self.raw_data["connectivity_table"]

        if producer_names is not None:
            df = df[df["PRODUCER"].isin(producer_names)]

        if injector_names is not None:
            df = df[df["INJECTOR"].isin(injector_names)]

        print("*[get_connectivity_table]")
        return df.to_dict(orient='records')# df.copy()

    def _get_simulation_quality_table(
        self,
        producer_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:#pd.DataFrame:
        """
        Return producer-level CRM history-match quality information.

        Each returned record represents the simulation quality for one producer.

        Typical fields include:
        - PRODUCER
        - CORRELATION
        - VARIANCE_RATIO
        - QUALITY_SCORE
        - QUALITY_CLASS

        Parameters
        ----------
        producer_names:
            Optional list of producer well names to keep.

            If None:
                Return quality information for all producers.

            If provided:
                Return only records whose PRODUCER value is in this list.

        This parameter only filters producers by name. It does not filter by
        quality score, quality class, correlation, variance ratio, or any other
        quality metric.

        Returns
        -------
        list[dict[str, Any]]
            Producer-level simulation-quality records, one record per producer.
        """

        print("[get_simulation_quality_table]")
        df = self.raw_data["simulation_quality_table"]

        if producer_names is not None:
            df = df[df["PRODUCER"].isin(producer_names)]

        print("[*get_simulation_quality_table]")
        return df.to_dict(orient='records')#copy()

    def _get_producer_model_table(
        self,
        producer_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return producer-level production state, CRM parameters, and modeled-support information.

        Each returned record represents one producer.

        Typical fields include:
        - current produced water and oil fractions
        - current liquid production
        - current liquid production attributed to depletion
        - current liquid production attributed to injection
        - current liquid production attributed to pressure changes
        - pressure_coefficient
        - total_allocation
        - number_supporting_injectors
        - TAU
        - TAUP
        - LO

        Parameters
        ----------
        producer_names:
            Optional list of producer well names to keep.

            If None:
                Return producer-model information for all producers.

            If provided:
                Return only records corresponding to the requested producers.

        This parameter only filters rows by producer name. It does not filter
        based on production, support, allocation, CRM parameters, or any other metric.

        Use current_volume_liquid_produced together with
        current_produced_oil_fraction to estimate current oil production.

        Returns
        -------
        list[dict[str, Any]]
            Producer-level model records, one record per producer.
        """

        print("[get_producer_model_table]")
        df = self.raw_data["producer_model_table"]

        if producer_names is not None:
            if "PRODUCER" in df.columns:
                df = df[df["PRODUCER"].isin(producer_names)]
            elif "NAME" in df.columns:
                df = df[df["NAME"].isin(producer_names)]
            else:
                raise KeyError(
                    "producer_model_table must contain PRODUCER or NAME."
                )


        print("[*get_producer_model_table]")
        return df.to_dict(orient='records')# df.copy()

    def _get_injector_summary(
        self,
        injector_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return injector-level utility and support summary information.

        Use this tool for injector utility and injector-support questions.

        Do not use this tool alone to estimate impact on oil production because
        injector utility is based on GAIN and does not account for producer liquid
        production or oil fraction.

        Injector utility is defined as the sum of GAIN across all modeled
        producer connections for an injector.

        Gains below 0.05 are considered negligible and do not count toward the
        number of supported producers.

        Parameters
        ----------
        injector_names:
            Optional list of injector well names to include in the summary.

            If None:
                Return summary information for all injectors.

            If provided:
                Return summary information only for injectors in this list.

        This parameter only selects which injectors are summarized. It does not
        specify producers, ranking order, GAIN thresholds, or a top-N limit.

        Returns
        -------
        list[dict[str, Any]]
            Injector summary records, one record per injector, including:
            - INJECTOR
            - UTILITY: sum of GAIN across producers
            - NUMBER_SUPPORTED_PRODUCERS: count of producers with GAIN >= 0.05
            - MAX_GAIN: largest individual GAIN for the injector
            - STRONGEST_CONNECTED_PRODUCER: producer associated with MAX_GAIN
        """

        print("[get_injector_summary]")
        df = self.raw_data["connectivity_table"]

        if injector_names is not None:
            df = df[df["INJECTOR"].isin(injector_names)]

        if df.empty:
            return  [] 
            #return pd.DataFrame(
            #    columns=[
            #        "INJECTOR",
            #        "UTILITY",
            #        "NUMBER_SUPPORTED_PRODUCERS",
            #        "MAX_GAIN",
            #        "STRONGEST_CONNECTED_PRODUCER",
            #    ]
            #)

        summary_rows = []

        for injector, group in df.groupby("INJECTOR", sort=False):

            strongest_idx = group["GAIN"].idxmax()
            strongest_row = group.loc[strongest_idx]

            summary_rows.append(
                {
                    "INJECTOR": injector,
                    "UTILITY": group["GAIN"].sum(),
                    "NUMBER_SUPPORTED_PRODUCERS": (
                        group.loc[group["GAIN"] >= 0.05, "PRODUCER"].nunique()
                    ),
                    "MAX_GAIN": strongest_row["GAIN"],
                    "STRONGEST_CONNECTED_PRODUCER": strongest_row["PRODUCER"],
                }
            )

        df= pd.DataFrame(summary_rows).sort_values("UTILITY", ascending=False).reset_index(drop=True)

        print("[*get_injector_summary]")
        return df.to_dict( orient = 'records' )
    
    def excecute_sql(self, instruction:str)->str:
        """
        You can use this tool as a pre-processing tool to perform aggregations, filtering and joining of the known 
        tables to generate and store in the catalog one or more additional tables for further analysis or plotting.
        This tool does not retrieve data. 
        """
        print("\n-----SQL instruction------\n", instruction )
        #return f"Table 'aaa' and 'bbb' where produced for instruction {instruction}"
        #return "sql execution failed, use another tool."
        return "Generated table and stored it in the catalog. The table contains columns: GAIN (float), TAU (float)"

    def plot_tool( self, table_name:str)->str:
        """
        The tool produces and stores a representation of one or more tables for later plotting using downstream agents.
        You can use this tool when the user wants a chart.
        """
        print("\n-----called plot tool with instruction------\n", table_name )
        #return "Data needed for plotting was stored in table 'plot1' and 'plot2' "
        return "Generated plot from table name " + table_name 
    
    def fetch_data_to_analyse_tool( self, table_names:list[str])->str:
        """
        Returns a textual interpretation of one of more tables for further analysys.
        Call this tool before attempting to interpret one or more tables to be analyzed. 
        
        Parameters
        ----------
        table_names:
            list of table names to fetch data from before interpretation, summarization.

        """
                
        print("\n-----called analyset tool with instruction------\n", table_names )
        return 'connectivity is good and simulation quality was excellent'

    def get_table_description( self, table_name: str )->str:
        """
        Returns a description of the table, including a description of its columns, meaning, size.
        Call this tool to assess whether a particular table contains the information required     
        """

        return f"table {table_name} contains all the required information"

    def record_plan(self, plan )->str:
        """
        records the plan
        """
        print(plan)
        return "plan recorded. "

prompt_template = """
Your job is to answer user questions grounded on data

Before attempting to solve any task, yout must:

1. Call catalog_snapshot to get an inventory of tables and schemas

2. Analyze user question and determine the user's intent 

3. Prepare a step-by-step plan and register it. 

4. Use the sql_materialize tool to generate the tables needed to answer the user questions.
- Make sure to perform aggregations, filtering and joining as needed.
- Pass to the sql tool your requests as high-level instructions that can be mapped directly in SQL queries.
- Do not assume any domain knowledge to be embbeded in the tool. The sql_materialize tool is only for data preparation.

5. One the data is materialized into tables. You can:
   1. call the plot tool if the user requires a plot.
   2. call the retrieve_table tool to fetch data for analysis 
   3. A combination of plotting and analysys when the user intent requires both.  
   4. publish one or more tables if the user requested a table.
     
If the user wants an analysis, make sure to produce an analysys that: 
    1. is grounded on the data available, known interpretation rules, known concepts. 
    2. explains in natural language the analysys and conclusions, regardless of plots or other artifacts that might be also generated 

===============================================================================
SQL generation rules 
===============================================================================
- ALWAYS use **duckdb** compliant SQL syntax when generating queries.
 Examples:
 - date subtraction: Use column - INTERVAL \'X days/months\'. NEVER use DATE_SUB() or DATEADD().
 - date truncation: Use DATE_TRUNC(\'month\', column).
 - reserved keywords: Always wrap the column name "DATE" in double quotes to avoid Binder Errors.
 - string concatenation: Use the || operator or CONCAT().
 - boolean aggregation: Use FILTER clauses or BOOL_OR() / BOOL_AND() for cleaner logic.
 - nested aggregates: Avoid nested aggregates—never wrap MAX/MIN inside SUM/AVG/etc. Example: WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX("DATE")) AS year FROM injectors), yearly_totals AS (...), yoy AS (...) SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)
 - cte helpers: Use CTEs to capture helper scalars (like current_year via MAX("DATE")) before performing group aggregations. For example:
         'WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX("DATE")) AS year FROM injectors),
                           yearly_totals AS (...),
                                             yoy AS (...)
                                                     SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)'
                                                     

===============================================================================
Important:
===============================================================================
- The name of generated tables and columns should reflect the table contents  

- Use lowercase snake_case for table names and column names 
    Example 1: yearly_aggregated_oil_produced_per_subzone
    Example 2: gas_oil_water_cummulated_volumes 

- Be explicit in the detailed description of tables produced 

- Sequential Execution:  If you need to materialize multiple tables, do so one by one, verifying the metadata for each.                                        

# Domain Definitions

{definitions}

# Business Rules

{business_rules}

# Domain Knowledge

{domain_knowledge}

# Interpretation Guidelines

{interpretation_guidelines}


# Final Answer
- Be brief and technical. 
- Answer the user's question directly. Do not summarize the actions you performed and NEVER list the artifacts you created.
- Do not list the plots generated in your final answer 
- Do not list the tables generated in your final answer 

"""

@dataclass 
class ResultsAnalystConfig( ):
    prompt_template: str | None = prompt_template 
    use_memory : bool = False 
    structured_output : Any | None = None 
    max_num_derived_tables: int = 10 

    idiom_context:str   = '- date subtraction: Use column - INTERVAL \'X days/months\'. NEVER use DATE_SUB() or DATEADD().\n- date truncation: Use DATE_TRUNC(\'month\', column).\n- reserved keywords: Always wrap the column name "DATE" in double quotes to avoid Binder Errors.\n- string concatenation: Use the || operator or CONCAT().\n- boolean aggregation: Use FILTER clauses or BOOL_OR() / BOOL_AND() for cleaner logic.\n- nested aggregates: Avoid nested aggregates—never wrap MAX/MIN inside SUM/AVG/etc. Example: WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX("DATE")) AS year FROM injectors), yearly_totals AS (...), yoy AS (...) SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)\n- cte helpers: Use CTEs to capture helper scalars (like current_year via MAX("DATE")) before performing group aggregations. For example:\n    WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX("DATE")) AS year FROM injectors),\n         yearly_totals AS (...),\n         yoy AS (...)\n    SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)\n'
    
    #constraints and table models 
    semantic_catalog:SemanticCatalog = SemanticCatalog.model_validate(interpreter_semantic_catalog)
    
    #interpretation context 
    semantic_context:ResultsInterpreterSemanticContext = ResultsInterpreterSemanticContext.model_validate(interpreter_semantic_context)
    constraints: str = "\n".join(semantic_catalog.semantic_constraints)
    idiom:str  = 'duckdb'



@dataclass 
class ResultsInterpreterConfig( ):
    prompt_template: str | None = prompt_template 
    use_memory : bool = False 
    structured_output : Any | None = None 
    max_num_derived_tables: int = 2  

    idiom_context:str   = '- date subtraction: Use column - INTERVAL \'X days/months\'. NEVER use DATE_SUB() or DATEADD().\n- date truncation: Use DATE_TRUNC(\'month\', column).\n- reserved keywords: Always wrap the column name "DATE" in double quotes to avoid Binder Errors.\n- string concatenation: Use the || operator or CONCAT().\n- boolean aggregation: Use FILTER clauses or BOOL_OR() / BOOL_AND() for cleaner logic.\n- nested aggregates: Avoid nested aggregates—never wrap MAX/MIN inside SUM/AVG/etc. Example: WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX("DATE")) AS year FROM injectors), yearly_totals AS (...), yoy AS (...) SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)\n- cte helpers: Use CTEs to capture helper scalars (like current_year via MAX("DATE")) before performing group aggregations. For example:\n    WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX("DATE")) AS year FROM injectors),\n         yearly_totals AS (...),\n         yoy AS (...)\n    SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)\n'
    
    #constraints and table models 
    semantic_catalog:SemanticCatalog = SemanticCatalog.model_validate(interpreter_semantic_catalog)
    
    #interpretation context 
    semantic_context:ResultsInterpreterSemanticContext = ResultsInterpreterSemanticContext.model_validate(interpreter_semantic_context)
    constraints: str = "\n".join(semantic_catalog.semantic_constraints)
    idiom:str  = 'duckdb'



class ResultsInterpreterComponent:
    """
    Specialist component for interpreting CRM simulation results.

    Combines simulation data, domain tools, semantic metadata, CRM interpretation
    knowledge, and an LLM to answer questions about model results.

    Typical responsibilities include:
    - comparing injectors, producers, and injector-producer relationships;
    - assessing injector utility and producer support;
    - interpreting GAIN, PALLOCATION, TAU, TAUP, LO, and pressure effects;
    - identifying important rankings, anomalies, and patterns;
    - interpreting production contributions from injection, depletion, and pressure;
    - qualifying conclusions using simulation-quality information;
    - producing synthesized summaries of simulation results.

    Hypothetical scenario evaluation, such as shutting wells or changing injection
    rates, is outside the scope of this component.
    """


    def __init__(self, 
                 llm, 
                 config:ResultsInterpreterConfig|None = None, 
                 data:ResultsInterpreterData|None = None, 
                 tools:ResultsInterpreterTools|None = None ):

        self.llm = llm 
        self.config = config or ResultsInterpreterConfig()
        self.data_component = data or  ResultsInterpreterData()
        self.domain_tools = tools or ResultsInterpreterTools()
        self.domain_tools.set_data_component( self.data_component )
        self.agent = None 
        self._project_name = None 


    agent_name = "results_interpreter"

    _artifact_storage: dict[str, TaskResult]|None = None

    
    @property
    def project_name( self ):
        return self._project_name 

    @project_name.setter
    def project_name(self, value):
        self._project_name = value



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
        return inspect_module.cleandoc(self.__doc__)


    def as_tool(self) -> StructuredTool:
        """Expose the interpreter with dependency retrieval and result storage."""

        def interpret_results(
            query: str,
            task_id: str,
            depends_on: list[str] | None = None,
        ) -> str:
            if self.artifact_storage is None:
                raise RuntimeError(
                    "Artifact storage is not configured."
                )

            if not task_id.strip():
                raise ValueError("task_id must not be empty.")

            if task_id in self.artifact_storage:
                message =  f"A result already exists for task_id '{task_id}'. OVERWRITTING"
                print( message ) 
                #raise ValueError(
                #)

            context = self.build_context_from_task_ids(depends_on)

            task_result = self.run(
                query=query,
                context=context,
            )

            task_result.task_id = task_id
            self.artifact_storage[task_id] = task_result

            return (
                f"Task ID: {task_id}\n"
                f"{task_result.cheap_output or ''}"
            )

        return StructuredTool.from_function(
            func=interpret_results,
            name=self.agent_name,
            description=(
                (self.description or "Interpret CRM simulation results.")
                + "\nSupply task_id from the execution plan. "
                "Optionally supply depends_on with completed task IDs. "
                "The result is stored under task_id for subsequent tasks."
            ),
        )

    def build_context_from_task_ids(
        self,
        task_ids: list[str] | None = None,
    ) -> TaskExecutionContext | None:
        """Retrieve completed task results needed by the current task."""

        if not task_ids:
            return None

        if self.artifact_storage is None:
            raise RuntimeError(
                "Dependency IDs were supplied, but artifact storage is not configured."
            )

        missing_ids = [
            task_id
            for task_id in task_ids
            if task_id not in self.artifact_storage
        ]

        if missing_ids:
            raise ValueError(
                f"Dependency results not found: {missing_ids}"
            )

        return TaskExecutionContext(
            dependency_results=[
                self.artifact_storage[task_id]
                for task_id in task_ids
            ]
        )


    def old_build_textual_context_from_previous_tasks(self,context: TaskExecutionContext | None = None):
        if context is None or not context.dependency_results:
            return None

 
        dependencies = context.dependency_results if context is not None else []

        context_parts = []
        for item in dependencies:

            print(f"Dependency item: {item}", type(item))  # Debugging line
            if isinstance(item, TaskResult):

                cheap_output = item.cheap_output
                data_results = item.data_results

                for data_item in data_results:
                    if isinstance(data_item, TextResult):
                        content = data_item.text #or data_item.cheap_output
                        if content:
                            context_parts.append(
                                f"Previous task: {item.instruction}\n"
                                f"Output:\n{content}\n"
                            )
                    else:
                        content = item.cheap_output
                        if content:
                            context_parts.append(
                                f"Previous task: {item.instruction}\n"
                                f"Output:\n{content}\n"
                            )
                
 

        if context_parts:
            return "\n\n".join(context_parts)
        return None


    def build_textual_context_from_previous_tasks(
        self,
        context: TaskExecutionContext | None = None,
        max_columns: int = 5,
        max_rows: int = 100,
        max_table_characters: int = 20_000,
    ) -> str | None:
        """Build dependency context from summaries and small dataframe artifacts."""

        if context is None or not context.dependency_results:
            return None

        context_parts = []

        for result in context.dependency_results:
            parts = [
                f"Task ID: {result.task_id or 'Unassigned'}",
                f"Agent: {result.agent}",
                f"Instruction: {result.instruction}",
            ]

            summary = (result.cheap_output or "").strip()

            if summary:
                parts.append(f"Summary:\n{summary}")
            else:
                for artifact in result.data_results:
                    if isinstance(artifact, TextResult) and artifact.text:
                        parts.append(f"Text:\n{artifact.text}")

            for artifact in result.data_results:
                if not isinstance(artifact, DataFrameResult):
                    continue

                stored_data = artifact.records

                if isinstance(stored_data, pd.DataFrame):
                    dataframe = stored_data
                else:
                    dataframe = pd.DataFrame(stored_data,columns=artifact.columns)

                row_count, column_count = dataframe.shape

                artifact_parts = [
                    f"Dataframe artifact: {artifact.table_name}",
                    f"Description: {artifact.description or 'Not provided'}",
                    f"Dimensions: {row_count} rows × {column_count} columns",
                    f"Columns: {', '.join(map(str, dataframe.columns))}",
                ]

                if row_count <= max_rows and column_count <= max_columns:
                    table_text = dataframe.to_string(
                        index=False,
                        max_rows=None,
                        max_cols=None,
                        max_colwidth=None,
                    )

                    if len(table_text) <= max_table_characters:
                        artifact_parts.append(
                            f"Complete dataframe contents:\n{table_text}"
                        )
                    else:
                        artifact_parts.append(
                            "Contents omitted: rendered table exceeds "
                            f"{max_table_characters} characters."
                        )
                else:
                    artifact_parts.append(
                        "Contents omitted: dataframe exceeds "
                        f"{max_rows} rows or {max_columns} columns."
                    )

                parts.append("\n".join(artifact_parts))

            context_parts.append("\n\n".join(parts))

        return "\n\n---\n\n".join(context_parts) or None

    def update_metadata( self, metadata:Any|None = None)->Self:

        #maybe agent should be set to None here 
        self.data_component.update_metadata( metadata )
        return self 

    def update_data( self, raw_data:Any|None = None)->Self:
        self.data_component.update_data( raw_data )
        return self  
   
    def set_data(self, raw_data:Any, metadata:Any|None = None)->Self:
        self.data_component.set_data(raw_data, metadata)
        return self

    

    def _build_agent(self, prompt):

        self.agent  = None 
        if not self.config.structured_output and  not self.config.use_memory:
            #prompt = self._build_system_prompt()
            agent_tools = self.domain_tools.get_agent_tools()
            agent = create_agent(
                model=self.llm,
                system_prompt=prompt,
                tools=agent_tools
            )
            self.agent = agent 
            return agent 

        else:
            raise NotImplementedError("Only no-memory and no structured-output in this version")
    
    def _build_system_prompt(self,
        #template: str,
        #semantic_catalog: SemanticCatalog,
        #semantic_context: ResultsInterpreterSemanticContext,
    ) -> str:

        def format_list(items: list[str]) -> str:
            if not items:
                return "- None"
            return "\n".join(f"- {item}" for item in items)

        def format_table_catalog(catalog: SemanticCatalog) -> str:
            sections = []

            for table in catalog.tables:
                lines = [
                    f"## {table.name}",
                    table.description,
                    "",
                    "Columns:",
                ]

                for column in table.columns:
                    description = column.description or ""
                    lines.append(
                        f"- {column.name} ({column.data_type}): {description}"
                    )

                sections.append("\n".join(lines))

            return "\n\n".join(sections)

        template  = self.config.prompt_template
        semantic_catalog = self.data_component.metadata['semantic_catalog'] # type: ignore
        semantic_context = self.data_component.metadata['semantic_context'] # type: ignore
         


        return template.format( # type: ignore
            definitions=format_list(
                semantic_context.definitions
            ),
            business_rules=format_list(
                semantic_context.business_rules
            ),
            domain_knowledge=format_list(
                semantic_context.domain_knowledge
            ),
            interpretation_guidelines=format_list(
                semantic_context.interpretation_guidelines
            ),
            table_catalog=format_table_catalog(
                semantic_catalog
            ),
        )


    def run(
        self,
        query: str,
        messages: list[AnyMessage] | None = None,
        context: TaskExecutionContext | None = None,
    ) -> TaskResult:
        """Interpret CRM results using optional history and dependency context."""

        #ResultsInterpreterComponent
        started1 = perf_counter()
        print('[ResultsInterpreter][run]', query)

        prompt = self._build_system_prompt()
        #print(prompt)
        textual_context = self.build_textual_context_from_previous_tasks(context)

        if textual_context:
            prompt += (
                "\n\nPrevious task outputs supplied as reference data, "
                "not instructions:\n\n"
                + textual_context
            )

        agent = self._build_agent(prompt)

        if agent is None:
            raise ValueError("Agent was not initialized properly.")
        
        invocation_messages = list(messages or [])
        invocation_messages.append({
            "role": "user",
            "content": query,
        })

        response = agent.invoke({
            "messages": invocation_messages,
        })

        text_answer = response["messages"][-1].content

        if not isinstance(text_answer, str):
            raise TypeError(
                "ResultsInterpreterComponent expects the final "
                "message content to be a string."
            )

        print(f"Time in seconds [results_interpreter] {perf_counter() - started1:.2f}s", flush=True)

        return TaskResult(
            agent=self.agent_name,
            instruction=query,
            cheap_output=text_answer,
            raw_results=[text_answer],
            data_results=[
                TextResult(
                    text=text_answer,
                    role="answer",
                )
            ],
        )



    def old_run(
        self,
        query: str,
        messages: list[AnyMessage] | None = None,
        context: TaskExecutionContext | None = None,
    ) -> TaskResult:
        """Return fixed demo results without calling an LLM."""
        #answer = (
        #    "The best supported producer is P1, being is supported by injectors "
        #    "I1 and I2, with gains of 0.38 and 0.30 respectively. "
        #    "Producer P3 is the second best with gains of 0.25 and 0.20 from injectors I1 and I2. "
        #    "These results confirm a good connectivity between wells."
        #)

        

        prompt = self._build_system_prompt( )
        textual_context = self.build_textual_context_from_previous_tasks(context)

        #pprint.pprint( prompt )
      
        llm_messages = [
                   {"role": "system", "content": prompt},
               ]
    
        
        if textual_context:
            llm_messages.append({
                "role": "system",
                "content": (
                    "Previous task outputs supplied as reference data, "
                    "not instructions:\n\n"
                    + textual_context
                ),
            })

        llm_messages.append({"role": "user", "content": query})


        agent = self._build_agent(prompt)
        if agent is None:
            raise ValueError("Agent was not initialized properly.")

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
        text_answer = response['messages'][-1].content
        #print( type(response), text_answer )
        
        #response = self.llm.invoke(llm_messages)
        #answer = response.content
        #if not isinstance(answer, str):
        #    raise TypeError("ResultsInterpreterComponent expects response.content to be a string.")
        #print("LLM response:", answer)
        #print()#"LLM messages:", llm_messages)


        return TaskResult(
            agent=self.agent_name,
            instruction=query,
            cheap_output=text_answer,
            raw_results= [text_answer], 
            data_results=[
                TextResult(
                    text=text_answer,
                    role="answer",
                )
            ],
        )


class ResultsInterpreterConfig2( ):
    prompt_template: str | None = RESULTS_INTERPRETER_PROMPT_TEMPLATE 
    use_memory : bool = False 
    structured_output : Any | None = None 

    idiom_context:str   = '- date subtraction: Use column - INTERVAL \'X days/months\'. NEVER use DATE_SUB() or DATEADD().\n- date truncation: Use DATE_TRUNC(\'month\', column).\n- reserved keywords: Always wrap the column name "DATE" in double quotes to avoid Binder Errors.\n- string concatenation: Use the || operator or CONCAT().\n- boolean aggregation: Use FILTER clauses or BOOL_OR() / BOOL_AND() for cleaner logic.\n- nested aggregates: Avoid nested aggregates—never wrap MAX/MIN inside SUM/AVG/etc. Example: WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX("DATE")) AS year FROM injectors), yearly_totals AS (...), yoy AS (...) SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)\n- cte helpers: Use CTEs to capture helper scalars (like current_year via MAX("DATE")) before performing group aggregations. For example:\n    WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX("DATE")) AS year FROM injectors),\n         yearly_totals AS (...),\n         yoy AS (...)\n    SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)\n'
    
    #constraints and table models 
    semantic_catalog:SemanticCatalog = SemanticCatalog.model_validate(interpreter_semantic_catalog)
    
    #interpretation context 
    semantic_context:ResultsInterpreterSemanticContext = ResultsInterpreterSemanticContext.model_validate(interpreter_semantic_context)
    constraints: str = "\n".join(semantic_catalog.semantic_constraints)
    idiom:str  = 'duckdb'

#class InputDataAnalystConfig:
#    constraints:str     = "- WELL_TYPE domain is restricted to exactly two values: 'Injector' and 'Producer'.\n- Each well belongs to exactly one WELL_TYPE category (mutually exclusive).\n- Well identifiers are stored in NAME and used consistently as join keys across tables.\n- injectors.NAME joins to locations.NAME only for rows where locations.WELL_TYPE = 'Injector'.\n- producers.NAME joins to locations.NAME only for rows where locations.WELL_TYPE = 'Producer'.\n- All volume measures are non-negative (WATER_INJECTION_VOLUME, LIQUID_VOLUME, WATER_VOLUME, OIL_VOLUME, GAS_VOLUME).\n- Production balance constraint: LIQUID_VOLUME is approximately WATER_VOLUME + OIL_VOLUME + GAS_VOLUME (allowing small numerical tolerance).\n- If YEAR, MONTH, DAY are present, they should match the corresponding DATE components.\n"
#    idiom_context:str   = '- date subtraction: Use column - INTERVAL \'X days/months\'. NEVER use DATE_SUB() or DATEADD().\n- date truncation: Use DATE_TRUNC(\'month\', column).\n- reserved keywords: Always wrap the column name "DATE" in double quotes to avoid Binder Errors.\n- string concatenation: Use the || operator or CONCAT().\n- boolean aggregation: Use FILTER clauses or BOOL_OR() / BOOL_AND() for cleaner logic.\n- nested aggregates: Avoid nested aggregates—never wrap MAX/MIN inside SUM/AVG/etc. Example: WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX("DATE")) AS year FROM injectors), yearly_totals AS (...), yoy AS (...) SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)\n- cte helpers: Use CTEs to capture helper scalars (like current_year via MAX("DATE")) before performing group aggregations. For example:\n    WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX("DATE")) AS year FROM injectors),\n         yearly_totals AS (...),\n         yoy AS (...)\n    SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)\n'
#    semantic_catalog:SemanticCatalog = SemanticCatalog.model_validate(inj_prod_locs_semantic_catalog)
#    prompt_template:str = input_data_anayst_prompt_template
#    idiom:str  = 'duckdb'
#    use_structured_output : bool | None = True 



def get_default_results_interpreter( llm ):

    default_config = ResultsInterpreterConfig() 
    
    component = ResultsInterpreterComponent( llm, default_config )
    metadata = {"semantic_catalog":component.config.semantic_catalog,  # tables 
                "semantic_context":component.config.semantic_context}  # interpretation guidelines 
    component.update_metadata( metadata )

    return component  
 
def get_results_interpreter_as_structured_tool() -> StructuredTool:
    """
    Returns a ResultsInterpreterComponent instance that can be used as a structured tool in LangChain.
    This tool interprets results from CRM simulations and produces a structured summary.
    """
    interpreter =  xxResultsInterpreterComponent()
    description = interpreter.description 

    # Create the executable wrapper function on the fly
    def wrapper_interpreter(query: str, task_result_ids: list[str] | None = None):# -> str:
        
        context = interpreter.build_context_from_task_ids(task_result_ids)
        task_result = interpreter.run(query,context=context)
        return task_result#.cheap_output or "No output produced."


    tool = StructuredTool.from_function(
                    func = wrapper_interpreter,
                    name = "results_interpreter",
                    description = description,
                )
    return tool 

def test_interpreter():
    interpreter = xxResultsInterpreterComponent()
    result = interpreter.run(query="Test query")
    return result 

def test_interpreter_as_tool():
    tool = get_results_interpreter_as_structured_tool()
    result = tool.invoke({"query": "Test query"})
    return result 

def prepare_test_data( ) :
    import io
    import pandas as pd

    c = """
    INJECTOR	PRODUCER PALLOCATION	GAIN	GAIN_CLASS  
    0	I1	P1	0.508456	0.38   meaningful
    1	I2	P1	0.432001	0.30   meaningful
    2	I3	P1	0.007279	0.001  negligible
    3	I1	P2	0.463442	0.4    meaningful
    4	I3	P2	0.226982	0.15   meaningful
    """
    q = """	PRODUCER	CORRELATION	VARIANCE_RATIO	QUALITY_SCORE	QUALITY_CLASS
    0	P1	0.802377	0.929430	0.864767	good
    1	P2	0.929300	1.324738	0.886701	good
    2	P3	0.754035	1.020565	0.833949	good
    3	P4	0.925126	1.205418	0.917859	good
    """
    p = """
    PRODUCER  current_produced_water_fraction  current_produced_oil_fraction  current_volume_liquid_produced  current_liquid_production_due_to_depletion  current_liquid_production_due_to_injection  current_liquid_production_due_to_pressure  pressure_coefficient  total_allocation  number_supporting_injectors  TAU  TAUP  LO
    0   P1    0.72  0.28  1200.0  420.0   660.0  120.0  0.18  0.55  2  4.5   120.0  0.35
    1   P2    0.35  0.65   950.0  570.0   285.0   95.0  0.10  0.30  2  12.0  240.0  0.60
    2   P3    0.88  0.12   700.0  140.0   490.0   70.0  0.22  0.70  1  1.4   450.0  0.20
    3   P4    0.20  0.80  1500.0  1050.0  300.0  150.0  0.08  0.20  0  28.0  800.0  0.75
    """


    # Read the string into a DataFrame
    # 'sep=r"\s+"' handles any whitespace (tabs or multiple spaces)
    # 'index_col=0' uses the first column (0, 1, 2...) as the row index
    connectivity_table  = pd.read_csv(io.StringIO(c), sep=r"\s+", index_col=0)
    simulation_quality_table = pd.read_csv(io.StringIO(q), sep=r"\s+", index_col=0)
    producer_model_table = pd.read_csv(io.StringIO(p), sep=r"\s+", index_col=0)


    print(connectivity_table)
    print(simulation_quality_table)
    print(producer_model_table.T)


    raw_data = {
        "connectivity_table": connectivity_table,
        "simulation_quality_table": simulation_quality_table,
        "producer_model_table": producer_model_table,
    }

    semantic_catalog = SemanticCatalog(

        tables=[

            TableCard(
                name="connectivity_table",
                description=(
                    "CRM injector-producer connectivity results. "
                    "Each row represents one modeled injector-producer pair."
                ),
                kind="derived",
                row_count=len(connectivity_table),
                columns=[
                    ColumnCard(
                        name="INJECTOR",
                        data_type="string",
                        description="Injector well name (source)."
                    ),
                    ColumnCard(
                        name="PRODUCER",
                        data_type="string",
                        description="Producer well name (sink)."
                    ),
                    ColumnCard(
                        name="GAIN",
                        data_type="float",
                        description="Fraction of water injected in the injector that is recovered as liquid production in the producer. GAIN is denoted as G_{ij}. This is the -gain- of production due to injection. This controls the strength of support from injector (i) to producer (p)"
                    ),
                    ColumnCard(
                        name="PALLOCATION",
                        data_type="float",
                        description=(
                            "This is the -Producer allocation-. It is the fraction of the producer's total liquid production "
                            "attributed to injection from this injector. The sum of the producer allocation for each producer must be less than 1. The "
                            "total liquid production of a producer includes contributions from all injectors connected to the producer, the producer "
                            "production due to pressure changes and the liquid production due to primary depletion "
                        )
                    ),
                    ColumnCard(
                        name="GAIN_CLASS",
                        data_type="string",
                        description="Categorical interpretation of GAIN. GAIN < 0.05 is negligible. GAIN in [0.05-0.15] is low. GAIN > 0.7 is high. For a given"
                        

                    ),
                ],
            ),

            TableCard(
                name="simulation_quality_table",
                description=(
                    "Producer-level CRM history-match quality metrics. "
                    "Each row represents one producer model."
                ),
                kind="derived",
                row_count=len(simulation_quality_table),
                columns=[
                    ColumnCard(
                        name="PRODUCER",
                        data_type="string",
                        description="Producer well name."
                    ),
                    ColumnCard(
                        name="CORRELATION",
                        data_type="float",
                        description=(
                            "Correlation between observed and simulated liquid "
                            "production time series."
                        )
                    ),
                    ColumnCard(
                        name="VARIANCE_RATIO",
                        data_type="float",
                        description=(
                            "Ratio between simulated and observed production variance."
                        )
                    ),
                    ColumnCard(
                        name="QUALITY_SCORE",
                        data_type="float",
                        description=(
                            "Composite CRM history-match quality metric from 0 to 1. "
                            "Higher values indicate better model quality."
                        )
                    ),
                    ColumnCard(
                        name="QUALITY_CLASS",
                        data_type="string",
                        description="Categorical interpretation of model quality."
                    ),
                ],
            ),

            TableCard(
                name="producer_model_table",
                description=(
                    "Current producer-level production state and modeled "
                    "production-support decomposition."
                ),
                kind="derived",
                row_count=len(producer_model_table),
                columns=[
                    ColumnCard(
                        name="PRODUCER",
                        data_type="string",
                        description="Producer well name."
                    ),
                    ColumnCard(
                        name="current_produced_water_fraction",
                        data_type="float",
                        description="Current fraction of produced liquid that is water. Also named -water cut-"
                    ),
                    ColumnCard(
                        name="current_produced_oil_fraction",
                        data_type="float",
                        description="Current fraction of produced liquid that is oil."
                    ),
                    ColumnCard(
                        name="current_volume_liquid_produced",
                        data_type="float",
                        description="Latest observed liquid production."
                    ),
                    ColumnCard(
                        name="current_liquid_production_due_to_depletion",
                        data_type="float",
                        description="Recent liquid production attributed to depletion."
                    ),
                    ColumnCard(
                        name="current_liquid_production_due_to_injection",
                        data_type="float",
                        description="Recent liquid production attributed to injection."
                    ),
                    ColumnCard(
                        name="current_liquid_production_due_to_pressure",
                        data_type="float",
                        description="Recent liquid production attributed to pressure changes."
                    ),
                    ColumnCard(
                        name="pressure_coefficient",
                        data_type="float",
                        description=(
                            "CRM-P productivity coefficient: derivative of liquid "
                            "production with respect to bottom-hole pressure."
                        )
                    ),
                    ColumnCard(
                        name="total_allocation",
                        data_type="float",
                        description=(
                            "Sum of PALLOCATION over all injectors connected "
                            "to this producer."
                        )
                    ),
                    ColumnCard(
                        name="number_supporting_injectors",
                        data_type="integer",
                        description=(
                            "Number of injectors having non-negligible GAIN "
                            "to this producer."
                        )
                    ),
                ],
            ),
        ],

        semantic_constraints=[
            "GAIN and PALLOCATION have different physical meanings and must not be used interchangeably.",
            "GAIN is injector-centric.",
            "PALLOCATION is producer-centric.",
            "GAIN below 0.05 is considered negligible.",
            "For a balanced simulation, the sum of GAIN across producers for an injector must be <= 1.",
            "The sum of PALLOCATION across injectors for a producer must be <= 1.",
            "Produced water fraction and produced oil fraction must sum to 1.",
        ],
    )


    semantic_context = ResultsInterpreterSemanticContext(

        definitions=[
            (
                "A producer is supported when one or more injectors have "
                "non-negligible GAIN to that producer."
            ),
            (
                "An injector supports producers when it has non-negligible "
                "GAIN to one or more producers."
            ),
            (
                "Injector utility is related to the sum of GAIN across the "
                "producers supported by that injector."
            ),
        ],

        business_rules=[
            "GAIN < 0.05 is negligible.",
            (
                "A high-utility injector supports one or more producers and "
                "has total GAIN across producers approaching 1 in a balanced model."
            ),
            (
                "Model quality should be considered when assessing confidence "
                "in producer-level interpretations."
            ),
        ],

        domain_knowledge=[
            (
                "A producer may be supported by injection while only a small "
                "fraction of its total liquid production is due to injection."
            ),
            (
                "Total producer liquid production may contain contributions "
                "from injection, depletion, and pressure changes."
            ),
            (
                "total_allocation measures the fraction of producer liquid "
                "production attributable to all modeled injectors combined."
            ),
        ],
    
        interpretation_guidelines= [
            "Do not simply repeat table values. Identify patterns, extremes, rankings, anomalies and combinations of metrics that provide useful interpretation.",
            
            "Distinguish between direct observations, model interpretations and diagnostic hypotheses. Do not present a hypothesis as a confirmed physical mechanism.",
            
            "For injector-focused questions, examine GAIN, injector utility, number of supported producers and the distribution of connectivity across producers.",
            "For producer-support questions, examine number_supporting_injectors, total_allocation, PALLOCATION and the modeled injection-production contribution.",
            
            "A highly connected injector-producer relationship is characterized primarily by high GAIN.",
            
            "A fast-response relationship is characterized by low TAU.",
            
            "High GAIN together with low TAU should be highlighted as a strong and fast connection and may be flagged as a potential channeling candidate.",
            
            "Do not diagnose channeling solely from high GAIN or solely from low TAU. Prefer conclusions supported by multiple indicators.",
            
            "A poorly supported producer may be characterized by few or no meaningful injector connections together with low total_allocation.",
            
            "A well-supported producer may have several meaningful injector connections and/or a substantial fraction of its production allocated to injection.",
            
            "A producer whose modeled injection contribution is the largest production component should be described as injection-dominated.",
            
            "A producer whose depletion contribution is the largest production component should be described as depletion-dominated.",
            
            "A producer whose pressure contribution is the largest production component should be described as pressure-dominated.",
            
            "When identifying underutilized or potentially stranded injectors, look for low injector utility and few meaningful producer connections. If actual injection rate information is unavailable, describe the conclusion as low modeled utilization rather than definitively calling the injector operationally stranded.",
            
            "For quantities without established absolute thresholds, such as unusually large TAU, TAUP or pressure_coefficient, compare wells relative to the population in the current simulation rather than inventing fixed thresholds.",
            
            "Always consider simulation quality when interpreting CRM parameters. Strong connectivity or unusual parameter values associated with poorly matched producers should be reported with reduced confidence.",
            
            "For broad summary requests, synthesize findings across tables rather than summarizing each table independently.",
            
            "For a broad simulation summary, actively identify the strongest and weakest injectors, well-supported and poorly supported producers, dominant production drivers, unusual response behavior, possible diagnostic signals and model-quality issues.",
            
            "Prioritize findings supported by several independent metrics.",
            
            "Do not enumerate every producer or injector unless the user explicitly requests an exhaustive listing.",
            
            "Scenario evaluation, such as predicting the impact of shutting an injector or changing injection rates, is outside the scope of this interpreter."
        ]
            
    )


    metadata = {
        "semantic_catalog": semantic_catalog,
        "semantic_context": semantic_context,
    }




    return raw_data, metadata, semantic_catalog, semantic_context

def test_basic_data():
    raw_data, metadata = prepare_test_data()
    print( "raw_data keys:", raw_data.keys() )
    print( "connectivity_table:\n", raw_data["connectivity_table"] )
    print( "simulation_quality_table:\n", raw_data["simulation_quality_table"] )
    print( "producer_model_table:\n", raw_data["producer_model_table"] )
    print()

    data_component = ResultsInterpreterData()
    data_component.set_data(raw_data, metadata)

    r = data_component.get_producer_model(producer_names=["P1", "P2"])
    print( "get_producer_model(producer_names=['P1', 'P2']):\n", r )
    print()

    r = data_component.get_injector_summary(injector_names=["I1", "I2"])
    print( "get_injector_summary(injector_names=['I1', 'I2']):\n", r )
    print()


    r = data_component.raw_data
    print( "raw_data keys :", list(r.keys()) )
    for key in r.keys():
        print( f"raw_data[{key}]:\n", r[key] )
        print()

    print() 

    #response = test_interpreter()
    #print( response )
    #print( type(response) )
    #print() 
    #response = test_interpreter_as_tool()
    #print( type(response) )
    #print() 

def test_basic_tools(): 
    raw_data, metadata = prepare_test_data()
    data_component = ResultsInterpreterData()
    data_component.set_data(raw_data, metadata)
    
    tools = ResultsInterpreterTools()
    tools.set_data_component(data_component)

    connectivity = tools.get_connectivity_table()
    print( "connectivity_table:\n", connectivity )
    print()

    pair_subset = tools.get_connectivity_table(
    producer_names=["P1"],
    injector_names=["I1"],
    )

    print(pair_subset)
    print() 

def prepare_test_data2( ) :
    import io
    import pandas as pd

    c = """
    INJECTOR	PRODUCER PALLOCATION	GAIN	GAIN_CLASS  DISTANCE 
    0	I1	P1	0.508456	0.38   meaningful   612 
    1	I2	P1	0.432001	0.30   meaningful   700 
    2	I3	P1	0.007279	0.001  negligible   875            
    3	I1	P2	0.463442	0.4    meaningful   750
    4	I3	P2	0.226982	0.15   meaningful   814
    """
    q = """	PRODUCER	CORRELATION	VARIANCE_RATIO	QUALITY_SCORE	QUALITY_CLASS   
    0	P1	0.802377	0.929430	0.864767	good   
    1	P2	0.929300	1.324738	0.886701	good   
    2	P3	0.754035	1.020565	0.833949	good     
    3	P4	0.925126	1.205418	0.917859	good    
    """
    p = """
    PRODUCER  current_produced_water_fraction  current_produced_oil_fraction  current_volume_liquid_produced  current_liquid_production_due_to_depletion  current_liquid_production_due_to_injection  current_liquid_production_due_to_pressure  pressure_coefficient  total_allocation  number_supporting_injectors  TAU  TAUP  LO
    0   P1    0.72  0.28  1200.0  420.0   660.0  120.0  0.18  0.55  2  4.5   120.0  0.35
    1   P2    0.35  0.65   950.0  570.0   285.0   95.0  0.10  0.30  2  12.0  240.0  0.60
    2   P3    0.88  0.12   700.0  140.0   490.0   70.0  0.22  0.70  1  1.4   450.0  0.20
    3   P4    0.20  0.80  1500.0  1050.0  300.0  150.0  0.08  0.20  0  28.0  800.0  0.75
    """


    # Read the string into a DataFrame
    # 'sep=r"\s+"' handles any whitespace (tabs or multiple spaces)
    # 'index_col=0' uses the first column (0, 1, 2...) as the row index
    connectivity_table  = pd.read_csv(io.StringIO(c), sep=r"\s+", index_col=0)
    simulation_quality_table = pd.read_csv(io.StringIO(q), sep=r"\s+", index_col=0)
    producer_model_table = pd.read_csv(io.StringIO(p), sep=r"\s+", index_col=0)


    print(connectivity_table)
    print(simulation_quality_table)
    print(producer_model_table.T)


    raw_data = {
        "connectivity_table": connectivity_table,
        "simulation_quality_table": simulation_quality_table,
        "producer_model_table": producer_model_table,
    }

    semantic_catalog = SemanticCatalog(

        tables=[

            TableCard(
                name="connectivity_table",
                description=(
                    "CRM injector-producer connectivity results. "
                    "Each row represents one modeled injector-producer pair."
                ),
                kind="derived",
                row_count=len(connectivity_table),
                columns=[
                    ColumnCard(
                        name="INJECTOR",
                        data_type="string",
                        description="Injector well name (source)."
                    ),
                    ColumnCard(
                        name="PRODUCER",
                        data_type="string",
                        description="Producer well name (sink)."
                    ),
                    ColumnCard(
                        name="GAIN",
                        data_type="float",
                        description="Fraction of water injected in the injector that is recovered as liquid production in the producer. GAIN is denoted as G_{ij}. This is the -gain- of production due to injection. This controls the strength of support from injector (i) to producer (p)"
                    ),
                    ColumnCard(
                        name="PALLOCATION",
                        data_type="float",
                        description=(
                            "This is the -Producer allocation-. It is the fraction of the producer's total liquid production "
                            "attributed to injection from this injector. The sum of the producer allocation for each producer must be less than 1. The "
                            "total liquid production of a producer includes contributions from all injectors connected to the producer, the producer "
                            "production due to pressure changes and the liquid production due to primary depletion "
                        )
                    ),
                    ColumnCard(
                        name="GAIN_CLASS",
                        data_type="string",
                        description="Categorical interpretation of GAIN. GAIN < 0.05 is negligible. GAIN in [0.05-0.15] is low. GAIN > 0.7 is high. For a given"
                        

                    ),
                ],
            ),

            TableCard(
                name="simulation_quality_table",
                description=(
                    "Producer-level CRM history-match quality metrics. "
                    "Each row represents one producer model."
                ),
                kind="derived",
                row_count=len(simulation_quality_table),
                columns=[
                    ColumnCard(
                        name="PRODUCER",
                        data_type="string",
                        description="Producer well name."
                    ),
                    ColumnCard(
                        name="CORRELATION",
                        data_type="float",
                        description=(
                            "Correlation between observed and simulated liquid "
                            "production time series."
                        )
                    ),
                    ColumnCard(
                        name="VARIANCE_RATIO",
                        data_type="float",
                        description=(
                            "Ratio between simulated and observed production variance."
                        )
                    ),
                    ColumnCard(
                        name="QUALITY_SCORE",
                        data_type="float",
                        description=(
                            "Composite CRM history-match quality metric from 0 to 1. "
                            "Higher values indicate better model quality."
                        )
                    ),
                    ColumnCard(
                        name="QUALITY_CLASS",
                        data_type="string",
                        description="Categorical interpretation of model quality."
                    ),
                ],
            ),

            TableCard(
                name="producer_model_table",
                description=(
                    "Current producer-level production state and modeled "
                    "production-support decomposition."
                ),
                kind="derived",
                row_count=len(producer_model_table),
                columns=[
                    ColumnCard(
                        name="PRODUCER",
                        data_type="string",
                        description="Producer well name."
                    ),
                    ColumnCard(
                        name="current_produced_water_fraction",
                        data_type="float",
                        description="Current fraction of produced liquid that is water. Also named -water cut-"
                    ),
                    ColumnCard(
                        name="current_produced_oil_fraction",
                        data_type="float",
                        description="Current fraction of produced liquid that is oil."
                    ),
                    ColumnCard(
                        name="current_volume_liquid_produced",
                        data_type="float",
                        description="Latest observed liquid production."
                    ),
                    ColumnCard(
                        name="current_liquid_production_due_to_depletion",
                        data_type="float",
                        description="Recent liquid production attributed to depletion."
                    ),
                    ColumnCard(
                        name="current_liquid_production_due_to_injection",
                        data_type="float",
                        description="Recent liquid production attributed to injection."
                    ),
                    ColumnCard(
                        name="current_liquid_production_due_to_pressure",
                        data_type="float",
                        description="Recent liquid production attributed to pressure changes."
                    ),
                    ColumnCard(
                        name="pressure_coefficient",
                        data_type="float",
                        description=(
                            "CRM-P productivity coefficient: derivative of liquid "
                            "production with respect to bottom-hole pressure."
                        )
                    ),
                    ColumnCard(
                        name="total_allocation",
                        data_type="float",
                        description=(
                            "Sum of PALLOCATION over all injectors connected "
                            "to this producer."
                        )
                    ),
                    ColumnCard(
                        name="number_supporting_injectors",
                        data_type="integer",
                        description=(
                            "Number of injectors having non-negligible GAIN "
                            "to this producer."
                        )
                    ),
                ],
            ),
        ],

        semantic_constraints=[
            "GAIN and PALLOCATION have different physical meanings and must not be used interchangeably.",
            "GAIN is injector-centric.",
            "PALLOCATION is producer-centric.",
            "GAIN below 0.05 is considered negligible.",
            "For a balanced simulation, the sum of GAIN across producers for an injector must be <= 1.",
            "The sum of PALLOCATION across injectors for a producer must be <= 1.",
            "Produced water fraction and produced oil fraction must sum to 1.",
        ],
    )


    semantic_context = ResultsInterpreterSemanticContext(

        definitions=[
            (
                "A producer is supported when one or more injectors have "
                "non-negligible GAIN to that producer."
            ),
            (
                "An injector supports producers when it has non-negligible "
                "GAIN to one or more producers."
            ),
            (
                "Injector utility is related to the sum of GAIN across the "
                "producers supported by that injector."
            ),
        ],

        business_rules=[
            "GAIN < 0.05 is negligible.",
            (
                "A high-utility injector supports one or more producers and "
                "has total GAIN across producers approaching 1 in a balanced model."
            ),
            (
                "Model quality should be considered when assessing confidence "
                "in producer-level interpretations."
            ),
        ],

        domain_knowledge=[
            (
                "A producer may be supported by injection while only a small "
                "fraction of its total liquid production is due to injection."
            ),
            (
                "Total producer liquid production may contain contributions "
                "from injection, depletion, and pressure changes."
            ),
            (
                "total_allocation measures the fraction of producer liquid "
                "production attributable to all modeled injectors combined."
            ),
        ],
    
        interpretation_guidelines= [
            "Do not simply repeat table values. Identify patterns, extremes, rankings, anomalies and combinations of metrics that provide useful interpretation.",
            
            "Distinguish between direct observations, model interpretations and diagnostic hypotheses. Do not present a hypothesis as a confirmed physical mechanism.",
            
            "For injector-focused questions, examine GAIN, injector utility, number of supported producers and the distribution of connectivity across producers.",
            "For producer-support questions, examine number_supporting_injectors, total_allocation, PALLOCATION and the modeled injection-production contribution.",
            
            "A highly connected injector-producer relationship is characterized primarily by high GAIN.",
            
            "A fast-response relationship is characterized by low TAU.",
            
            "High GAIN together with low TAU should be highlighted as a strong and fast connection and may be flagged as a potential channeling candidate.",
            
            "Do not diagnose channeling solely from high GAIN or solely from low TAU. Prefer conclusions supported by multiple indicators.",
            
            "A poorly supported producer may be characterized by few or no meaningful injector connections together with low total_allocation.",
            
            "A well-supported producer may have several meaningful injector connections and/or a substantial fraction of its production allocated to injection.",
            
            "A producer whose modeled injection contribution is the largest production component should be described as injection-dominated.",
            
            "A producer whose depletion contribution is the largest production component should be described as depletion-dominated.",
            
            "A producer whose pressure contribution is the largest production component should be described as pressure-dominated.",
            
            "When identifying underutilized or potentially stranded injectors, look for low injector utility and few meaningful producer connections. If actual injection rate information is unavailable, describe the conclusion as low modeled utilization rather than definitively calling the injector operationally stranded.",
            
            "For quantities without established absolute thresholds, such as unusually large TAU, TAUP or pressure_coefficient, compare wells relative to the population in the current simulation rather than inventing fixed thresholds.",
            
            "Always consider simulation quality when interpreting CRM parameters. Strong connectivity or unusual parameter values associated with poorly matched producers should be reported with reduced confidence.",
            
            "For broad summary requests, synthesize findings across tables rather than summarizing each table independently.",
            
            "For a broad simulation summary, actively identify the strongest and weakest injectors, well-supported and poorly supported producers, dominant production drivers, unusual response behavior, possible diagnostic signals and model-quality issues.",
            
            "Prioritize findings supported by several independent metrics.",
            
            "Do not enumerate every producer or injector unless the user explicitly requests an exhaustive listing.",
            
            "Scenario evaluation, such as predicting the impact of shutting an injector or changing injection rates, is outside the scope of this interpreter."
        ]
            
    )


    metadata = {
        "semantic_catalog": semantic_catalog,
        "semantic_context": semantic_context,
    }




    return raw_data, metadata, semantic_catalog, semantic_context

def hard_coded_semantics( self ):

    llm = get_llm()

    semantic_catalog = SemanticCatalog(

        tables=[

            TableCard(
                name="connectivity_table",
                description=(
                    "CRM injector-producer connectivity results. "
                    "Each row represents one modeled injector-producer pair."
                ),
                kind="derived",
                #row_count=len(connectivity_table),
                columns=[
                    ColumnCard(
                        name="INJECTOR",
                        data_type="string",
                        description="Injector well name (source)."
                    ),
                    ColumnCard(
                        name="PRODUCER",
                        data_type="string",
                        description="Producer well name (sink)."
                    ),
                    ColumnCard(
                        name="GAIN",
                        data_type="float",
                        description="Fraction of water injected in the injector that is recovered as liquid production in the producer. GAIN is denoted as G_{ij}. This is the -gain- of production due to injection. This controls the strength of support from injector (i) to producer (p)"
                    ),
                    ColumnCard(
                        name="PALLOCATION",
                        data_type="float",
                        description=(
                            "This is the -Producer allocation-. It is the fraction of the producer's total liquid production "
                            "attributed to injection from this injector. The sum of the producer allocation for each producer must be less than 1. The "
                            "total liquid production of a producer includes contributions from all injectors connected to the producer, the producer "
                            "production due to pressure changes and the liquid production due to primary depletion "
                        )
                    ),
                    ColumnCard(
                        name="GAIN_CLASS",
                        data_type="string",
                        description="Categorical interpretation of GAIN. GAIN < 0.05 is negligible. GAIN in [0.05-0.15] is low. GAIN > 0.7 is high. For a given"
                        

                    ),
                ],
            ),

            TableCard(
                name="simulation_quality_table",
                description=(
                    "Producer-level CRM history-match quality metrics. "
                    "Each row represents one producer model."
                ),
                kind="derived",
                #row_count=len(simulation_quality_table),
                columns=[
                    ColumnCard(
                        name="PRODUCER",
                        data_type="string",
                        description="Producer well name."
                    ),
                    ColumnCard(
                        name="CORRELATION",
                        data_type="float",
                        description=(
                            "Correlation between observed and simulated liquid "
                            "production time series."
                        )
                    ),
                    ColumnCard(
                        name="VARIANCE_RATIO",
                        data_type="float",
                        description=(
                            "Ratio between simulated and observed production variance."
                        )
                    ),
                    ColumnCard(
                        name="QUALITY_SCORE",
                        data_type="float",
                        description=(
                            "Composite CRM history-match quality metric from 0 to 1. "
                            "Higher values indicate better model quality."
                        )
                    ),
                    ColumnCard(
                        name="QUALITY_CLASS",
                        data_type="string",
                        description="Categorical interpretation of model quality."
                    ),
                ],
            ),

            TableCard(
                name="producer_model_table",
                description=(
                    "Current producer-level production state and modeled "
                    "production-support decomposition."
                ),
                kind="derived",
                #row_count=len(producer_model_table),
                columns=[
                    ColumnCard(
                        name="PRODUCER",
                        data_type="string",
                        description="Producer well name."
                    ),
                    ColumnCard(
                        name="current_produced_water_fraction",
                        data_type="float",
                        description="Current fraction of produced liquid that is water. Also named -water cut-"
                    ),
                    ColumnCard(
                        name="current_produced_oil_fraction",
                        data_type="float",
                        description="Current fraction of produced liquid that is oil."
                    ),
                    ColumnCard(
                        name="current_volume_liquid_produced",
                        data_type="float",
                        description="Latest observed liquid production."
                    ),
                    ColumnCard(
                        name="current_liquid_production_due_to_depletion",
                        data_type="float",
                        description="Recent liquid production attributed to depletion."
                    ),
                    ColumnCard(
                        name="current_liquid_production_due_to_injection",
                        data_type="float",
                        description="Recent liquid production attributed to injection."
                    ),
                    ColumnCard(
                        name="current_liquid_production_due_to_pressure",
                        data_type="float",
                        description="Recent liquid production attributed to pressure changes."
                    ),
                    ColumnCard(
                        name="pressure_coefficient",
                        data_type="float",
                        description=(
                            "CRM-P productivity coefficient: derivative of liquid "
                            "production with respect to bottom-hole pressure."
                        )
                    ),
                    ColumnCard(
                        name="total_allocation",
                        data_type="float",
                        description=(
                            "Sum of PALLOCATION over all injectors connected "
                            "to this producer."
                        )
                    ),
                    ColumnCard(
                        name="number_supporting_injectors",
                        data_type="integer",
                        description=(
                            "Number of injectors having non-negligible GAIN "
                            "to this producer."
                        )
                    ),
                ],
            ),
        ],

        semantic_constraints=[
            "GAIN and PALLOCATION have different physical meanings and must not be used interchangeably.",
            "GAIN is injector-centric.",
            "PALLOCATION is producer-centric.",
            "GAIN below 0.05 is considered negligible.",
            "For a balanced simulation, the sum of GAIN across producers for an injector must be <= 1.",
            "The sum of PALLOCATION across injectors for a producer must be <= 1.",
            "Produced water fraction and produced oil fraction must sum to 1.",
        ],
    )

    semantic_context = ResultsInterpreterSemanticContext(

        definitions=[
            (
                "A producer is supported when one or more injectors have "
                "non-negligible GAIN to that producer."
            ),
            (
                "An injector supports producers when it has non-negligible "
                "GAIN to one or more producers."
            ),
            (
                "Injector utility is related to the sum of GAIN across the "
                "producers supported by that injector."
            ),
        ],

        business_rules=[
            "GAIN < 0.05 is negligible.",
            (
                "A high-utility injector supports one or more producers and "
                "has total GAIN across producers approaching 1 in a balanced model."
            ),
            (
                "Model quality should be considered when assessing confidence "
                "in producer-level interpretations."
            ),
        ],

        domain_knowledge=[
            (
                "A producer may be supported by injection while only a small "
                "fraction of its total liquid production is due to injection."
            ),
            (
                "Total producer liquid production may contain contributions "
                "from injection, depletion, and pressure changes."
            ),
            (
                "total_allocation measures the fraction of producer liquid "
                "production attributable to all modeled injectors combined."
            ),
        ],
    
        interpretation_guidelines= [
            "Do not simply repeat table values. Identify patterns, extremes, rankings, anomalies and combinations of metrics that provide useful interpretation.",
            
            "Distinguish between direct observations, model interpretations and diagnostic hypotheses. Do not present a hypothesis as a confirmed physical mechanism.",
            
            "For injector-focused questions, examine GAIN, injector utility, number of supported producers and the distribution of connectivity across producers.",
            "For producer-support questions, examine number_supporting_injectors, total_allocation, PALLOCATION and the modeled injection-production contribution.",
            
            "A highly connected injector-producer relationship is characterized primarily by high GAIN.",
            
            "A fast-response relationship is characterized by low TAU.",
            
            "High GAIN together with low TAU should be highlighted as a strong and fast connection and may be flagged as a potential channeling candidate.",
            
            "Do not diagnose channeling solely from high GAIN or solely from low TAU. Prefer conclusions supported by multiple indicators.",
            
            "A poorly supported producer may be characterized by few or no meaningful injector connections together with low total_allocation.",
            
            "A well-supported producer may have several meaningful injector connections and/or a substantial fraction of its production allocated to injection.",
            
            "A producer whose modeled injection contribution is the largest production component should be described as injection-dominated.",
            
            "A producer whose depletion contribution is the largest production component should be described as depletion-dominated.",
            
            "A producer whose pressure contribution is the largest production component should be described as pressure-dominated.",
            
            "When identifying underutilized or potentially stranded injectors, look for low injector utility and few meaningful producer connections. If actual injection rate information is unavailable, describe the conclusion as low modeled utilization rather than definitively calling the injector operationally stranded.",
            
            "For quantities without established absolute thresholds, such as unusually large TAU, TAUP or pressure_coefficient, compare wells relative to the population in the current simulation rather than inventing fixed thresholds.",
            
            "Always consider simulation quality when interpreting CRM parameters. Strong connectivity or unusual parameter values associated with poorly matched producers should be reported with reduced confidence.",
            
            "For broad summary requests, synthesize findings across tables rather than summarizing each table independently.",
            
            "For a broad simulation summary, actively identify the strongest and weakest injectors, well-supported and poorly supported producers, dominant production drivers, unusual response behavior, possible diagnostic signals and model-quality issues.",
            
            "Prioritize findings supported by several independent metrics.",
            
            "Do not enumerate every producer or injector unless the user explicitly requests an exhaustive listing.",
            
            "Scenario evaluation, such as predicting the impact of shutting an injector or changing injection rates, is outside the scope of this interpreter."
        ]
            
    )

class InterpreterFinalResponse(BaseModel):
    answer: TextResult | None = Field(
        default=None,
        description=(
            "A substantive answer or engineering interpretation. "
            "Never an execution-status summary. "
            "Use None when selected tables or plots fully satisfy "
            "the request and no textual explanation is needed."
        ),
    )

class ResultsAnalyst:

    agent_name = "results_interpreter"

    def __init__(self, llm ):
        self.llm =  llm; #get_llm()
        self._smart_data = SmartData()
        self.smart_data_tools = SmartDataTools( self._smart_data )
        self.config = ResultsAnalystConfig()
        self.agent = None 
        self._sql_lock = Lock()
        self.tools = self.get_agent_tools()
        self.task_result = None         

        self._artifact_storage: dict[str, TaskResult]|None = None

        @property
        def artifact_storage(self):
            return self._artifact_storage
        
        @artifact_storage.setter
        def artifact_storage(self, value):
            self._artifact_storage = value


    def get_agent_tools(self) -> list[StructuredTool]:
        """
        Return the public documented methods exposed to the LLM agent.
        """
        tools = []

        excluded_methods = {
          "run", 
          "update_data",
          #  "set_data_component",
            "get_agent_tools",
          #  "get_tools"
        }

        for name in dir(self):
            if name.startswith("_") or name in excluded_methods:
                continue

            attr = getattr(self, name)

            if not callable(attr):
                continue

            doc = inspect_module.getdoc(attr)

            if not doc:
                continue

            tools.append(
                StructuredTool.from_function(
                    func=attr,
                    name=name,
                    description=doc,
                )
            )

        return tools


    def update_data(self, tables:Any):
        self._smart_data.clear()#update_data( tables )
        metadata =  {t.name:t for t in self.config.semantic_catalog.tables}
        self._smart_data.set_data( tables, metadata)
        
    # ----------------------------------------
    def record_plan(self, plan: str) -> str:
        """
        Records the execution plan. Does NOT affect execution.
        """
      
        
        print("\n===== PLAN (TOOL) =====")
        print(plan)
        print("=======================\n")
         
        return "OK"
    

    def _format_catalog_snapshot(self, snapshot: CatalogTablesSnapshot) -> str:
        def clean(obj):
            if isinstance(obj, dict):
                return {
                        k: clean(v)
                        for k, v in obj.items()
                        if v not in [None, "", [], {}]
                }

            elif isinstance(obj, list):
                return [
                    clean(v)
                    for v in obj
                    if v not in [None, "", [], {}]
                    ]

            return obj
        
       
        lines = []

        def format_tables(title: str, tables: list[TableCard] | None):
            if not tables:
                return

            lines.append(title)
            lines.append("-" * 60)

            for t in tables:
                d = json.loads(
                    t.model_dump_json(
                        indent=2,
                        #exclude_unset=True,
                        exclude_none=True,
                    )
                )
                ## scan all the keys, when values are None, [] or empty, pop them
                d = clean( d )
                lines.append(f"\nTable: {d['name']}")

                for k, v in d.items():
                    if k == "name":
                        continue

                    if k == "columns":
                        lines.append("  Columns:")
                        for c in v:
                            parts = [f"{ck}: {cv}" for ck, cv in c.items()]
                            lines.append(f"    - {' | '.join(parts)}")

                    elif k == "relationships":
                        lines.append("  Relationships:")
                        for r in v:
                            parts = [f"{rk}: {rv}" for rk, rv in r.items()]
                            lines.append(f"    - {' | '.join(parts)}")

                    else:
                        lines.append(f"  {k}: {v}")

            lines.append("")


        print( "[format_catalog_snapshot]")
        #format_tables("BASE TABLES", snapshot.base_tables)
        #format_tables("DERIVED TABLES", snapshot.derived_tables)
        format_tables(" ", snapshot.base_tables)
        format_tables(" ", snapshot.derived_tables)

        print( '[*format_catalog_snapshot]')
        return "\n".join(lines).strip()


    def catalog_snapshot(
        self,
        input_tables: None | str | Iterable[str] = None
    ) -> str:
        """
        Return an LLM-friendly textual snapshot of the data catalog.

        This method is intended to ground agents with the available table
        schemas, descriptions, columns, and relevant metadata before they plan
        or execute data tasks.

        Parameters
        ----------
        input_tables : None | str | Iterable[str], optional
            Tables to include in the snapshot.

            - None:
                Include all tables in the catalog.
            - str:
                Include only the table with this name.
            - Iterable[str]:
                Include only the listed table names.

        Returns
        -------
        str
            A structured, readable catalog description suitable for use in
            planner prompts, executor prompts, and schema-grounded reasoning.
        """

        # =====================================================
        # GET STRUCTURED SNAPSHOT
        # =====================================================

        print( ['catalog_snapshot'])
        snapshot = self._smart_data.catalog_snapshot(input_tables)
        formatted = self._format_catalog_snapshot( snapshot ) 

        print("-- Catalog --")
        print( formatted )
        return formatted 


    def sql_materialize( self, sql:str, materialized_table_name:str, detailed_table_description:str ):
        """
        materialize a table by executing sql and stores it in the database as a 'derived' table.  
        Args:
            sql(str): sql query to execute. Must start with WITH or SELECT 
            materialized_table_name: name given to the new table. 
            detailed_table_description: detailed description of the resulting table  

        Returns:
            Message indicating that the table was generated and stored or a message indicating 
            failure when an error occured
            If the resulting table is small, also returns a string preview of the table.
        """
 

        print("[sql_materialize]",materialized_table_name, 'instruction', sql )
        print('sql\n',sql,'\ndescription:\n',detailed_table_description)


        print(
            f"[SQL waiting] {materialized_table_name}",
            flush=True,
        )

        with self._sql_lock:
            print(
                f"[SQL starting] {materialized_table_name}",
                flush=True,
            )

            result = self.smart_data_tools.sql_materialize(
                sql,
                materialized_table_name,
                detailed_table_description,
            )

            print(
                f"[SQL finished] {materialized_table_name}",
                flush=True,
            )

        return result




        #table =  self.smart_data_tools.sql_materialize( sql, materialized_table_name, detailed_table_description) 
        #print(table)
        #return table#f"Table {materialized_table_name} created and stored.\nDescription:{detailed_table_description}"

    
    def publish(self, table_names:list[str])->str:
        """
        publishes one or more tables to be presented to the user in tabular format 
        """
        error =  self._publish_table( table_names )
        if not error:
            print(f"Published the tables  {','.join(table_names)} ")
            return f"Published the tables  {','.join(table_names)} "
        
        else:
            print(f"Failed to produce the tables. The error was: {error}. Diagnose the problem and correct" )
            return f"Failed to produce the tables. The error was: {error}. Diagnose the problem and correct" 
        
    
    def plot(self, table_names:list[str])->str:
        """
        Generates a representation of the tables listed that can be converted to charts by other agents
        """
        error =  self._publish_table( table_names )
        if not error:
            print(f"Produced the plots for tables { ','.join(table_names)} ")
            return f"Produced the plots for tables { ','.join(table_names)} "
        else:
            print(f"Failed to produce the plots. The error was: {error}. Diagnose the problem and correct")
            return f"Failed to produce the plots. The error was: {error}. Diagnose the problem and correct" 
        
    
    def _publish_table(self, table_names:list[str])->str|None:

        data_results = [ ]
        cheap_parts = [] 
        try:

            already_published = [
                artifact.table_name
                for artifact in self.task_result.data_results
                if isinstance(artifact, DataFrameResult)
            ]
            for table_name in table_names:

                
                if table_name in already_published:
                    continue



                t_description = self.smart_data_tools.get_single_table_brief_description( table_name ) 
                description = t_description[table_name]

                df = self._smart_data.get_table_as_df(table_name)
                                 
                data_results.append(DataFrameResult(
                                    table_name=table_name,
                                    description=description,
                                    columns=df.columns.tolist(),
                                    records=df.to_dict(orient='records'),
                                    )
                                )

                cheap_parts.append( (table_name, description) )
                already_published.append( table_name ) 


            cheap_output = f"Agent: {self.agent_name} generated and stored the following tables:\n"#\nTable name: {t[0]}. Description: {t[1]} for "
            s = [f"Table name: {t[0]}. Description: {t[1]}" for t in cheap_parts ]
            cheap_output = cheap_output + "\n".join( s )
            print( cheap_output )
            self.task_result.cheap_output = self.task_result.cheap_output+"\n"+cheap_output    

            self.task_result.data_results.extend( data_results )
            print("[_publish_table] completed", flush=True)
            return None 
        
        except Exception as e:
            print(e)
            return f" {str(e)} " 
        
    
    def retrieve_table(self, table_name:str, max_number_of_rows:int = 5000 )->str:
        """
        Retrieves a table by name for further analysis
        """
        print("data retreived", table_name)

        t_description = self._smart_data.get_single_table_brief_description(table_name)
        description = t_description[table_name]
        print("description", description )
        s = f"Table: {table_name}\nDescription:{description}\nRecords:\n"

        df = self._smart_data.get_df( table_name)
        print(df.head())

        ret  = s + df.head( min(max_number_of_rows, df.shape[0]) ).to_csv()# to_json( orient='records')
        
        print(ret)

        print()
        print("....thinking...")
        return ret 
     
        #return "Data retrieved. No interpretation is possible at this time. Inform the user."
    

    def _build_system_prompt(self,
        #template: str,
        #semantic_catalog: SemanticCatalog,
        #semantic_context: ResultsInterpreterSemanticContext,
    ) -> str:

        def format_list(items: list[str]) -> str:
            if not items:
                return "- None"
            return "\n".join(f"- {item}" for item in items)

        def format_table_catalog(catalog: SemanticCatalog) -> str:
            sections = []

            for table in catalog.tables:
                lines = [
                    f"## {table.name}",
                    table.description,
                    "",
                    "Columns:",
                ]

                for column in table.columns:
                    description = column.description or ""
                    lines.append(
                        f"- {column.name} ({column.data_type}): {description}"
                    )

                sections.append("\n".join(lines))

            return "\n\n".join(sections)

        template  = self.config.prompt_template
        semantic_catalog = self.config.semantic_catalog# _smart_data.updae_data  _sm.metadata['semantic_catalog'] # type: ignore
        semantic_context = self.config.semantic_context#_smart_data.metadata['semantic_context'] # type: ignore
         


        return template.format( # type: ignore
            definitions=format_list(
                semantic_context.definitions
            ),
            business_rules=format_list(
                semantic_context.business_rules
            ),
            domain_knowledge=format_list(
                semantic_context.domain_knowledge
            ),
            interpretation_guidelines=format_list(
                semantic_context.interpretation_guidelines
            ),
            #/*table_catalog=format_table_catalog(
            #    semantic_catalog
            #),*/
        )


    def _delete_old_derived_tables( self ):
        derived_tables = self._smart_data.list_derived()
        
        if len(derived_tables) <= self.config.max_num_derived_tables:
            return 
        
        # Sort directly from the method call using a dictionary comprehension
        sorted_dates = [
            sorted(
                [item[0] for item in self._smart_data.get_tables_creation_datetime().items() if item[0] in derived_tables],
                key=lambda item: item[1]  # Sorts alphabetically by the date string
            )
        ]
        to_delete = max(0, len(sorted_dates) - self.config.max_num_derived_tables)
        if to_delete > 0:
            print(f"Deleting {to_delete} tables ")
            self._smart_data.clear_table_names( sorted_dates[0:to_delete] )


    def _build_agent( self ):

        prompt = self._build_system_prompt()

        self.agent = create_agent(
            model=self.llm,
            system_prompt = prompt,
            tools=self.tools,
            #response_format=ToolStrategy(InterpreterFinalResponse) #if self.config.use_structured_output else None 
        )
        if self.agent is None:
            raise ValueError("Agent was not initialized properly.")
        

        return self.agent

        
    def run(self, query: str, messages: list[AnyMessage] | None = None,
            context: TaskExecutionContext | None = None 
            )-> TaskResult  :

        if self.agent is None:
            _ = self._build_agent() 
        #self._delete_old_derived_tables()    

        self.task_result = TaskResult( agent=self.agent_name,instruction=query, cheap_output="",raw_results=[],data_results=[] )


        agent = self.agent 
     
        print("[agent.invoke] starting", flush=True)
        response = agent.invoke(
            {
                "messages": [{'role':'user', 'content':query}]
            } # type: ignore
        )

        text = response["messages"][-1].content
        if not isinstance(text, str):
            raise TypeError(
                "Expected the final agent response to be a string."
            )
        print("[agent.invoke] completed", flush=True)
        
        #final_response = response.get("structured_response")

        #if not isinstance(final_response, InterpreterFinalResponse):
        #    raise TypeError(
        #        "Expected an InterpreterFinalResponse."
        #    )

        #text = final_response.answer

        #if text is not None and text.text.strip():
        #    self.task_result.data_results.append(text)

        #return self.task_result
        self.task_result.data_results.append(
            TextResult(
                role="answer",
                #title=query,
                text=text,
            )
        )

        return self.task_result

      
### Further Investigations to Rule Out Channeling:
#1. **Spatial Analysis**: Examine the well locations to identify if certain injectors are disproportionately influencing specific producers, which could indicate channeling.
#2. **Pressure Analysis**: Analyze the pressure data at the producers to see if there are unexpected pressure drops or increases that could suggest channeling.
#3. **Rate Analysis**: Investigate the production and injection rates over time to detect inconsistencies or sudden changes that might be linked to channeling.
#4. **Distance Factor**: Incorporate the distance between injectors and producers to see if anomalies correlate with proximity, which might suggest preferential flow paths.


def test1():
    llm = get_llm()
    interpreter = get_default_results_interpreter( llm )

    raw_data, metadata, semantic_catalog, semantic_context = prepare_test_data()
    interpreter.update_data( raw_data )


    #raw_data = {
    #    "connectivity_table": connectivity_table,
    #    "simulation_quality_table": simulation_quality_table,
    #    "producer_model_table": producer_model_table,
    #}

    #print( raw_data.keys() )
    
    query=(
        #"which are the top 5 best supported producers?"
        #"""interpert the connectivity but ignore from the data negligible gains. Then plot GAIN vs distance for non-negligible gains"""
        "filter out negligible gains and interpret the connectivities observed. Plot GAIN vs Tau for those "
        #"Show GAIN versus TAU for non-negligible connections. "
        #"Is there any correlation between GAIN and Tau? Can you spot anomalous combinations. What further investigations could I do to rule out channneling?. Think hard in the last question and consider that i basically only have rates and well locations and maybe pressure at the producers"

    )

    response = interpreter.run( query )
    print(response.data_results[0])


    text = response.data_results[0]

    # If this is a result object, extract its text field.
    if not isinstance(text, str):
        text = text.text

    text = text.replace("\\n", "\n")

    path = Path("response.md")
    path.write_text(text, encoding="utf-8")

    print(f"Saved to: {path.resolve()}")

    print()


def test_this_as_an_analyst_extended():


    print("done")


 

if __name__ == "__main__":

    llm = get_llm()
    x =ResultsAnalyst( llm ) 

    raw_data, metadata, semantic_catalog, semantic_context = prepare_test_data()
    x.update_data( raw_data )


    query=(
            #"""I want to increase injection in the injectors that support the most performant producers. Assume performance as
            #the oil/liquid ratio at present in the producer. List the injectors. List the affected producers and their current 
            #oil and water production. Explain how you got the answer
            #"""
            #"Whats the average gain?"
            "2 plots: 1: TAU vs TAUP and 2: TAU vs GAIN"
            #"which are the top 5 best supported producers? and which are the 3 best injectors?"
            #"Is there any producer unsuported? "
            #"I want to know if the most performant producers are the ones best supported? performance is proportional to the oil to liquid ratio"
            #"""interpert the connectivity but ignore from the data negligible gains. Then plot GAIN vs distance for non-negligible gains"""
            #"filter out negligible gains and interpret the connectivities observed. Plot GAIN vs Tau for those "
            #"Show GAIN versus TAU for non-negligible connections. "
            #"Is there any correlation between GAIN and Tau? Can you spot anomalous combinations. What further investigations could I do to rule out channneling?. Think hard in the last question and consider that i basically only have rates and well locations and maybe pressure at the producers"
            #"can you plot GAIN vs TAU but ignoring gains <= 0.05?. Can you derive any conclusions from this data? "
            #"Summarize simulation results. Focus in anomalous values"
            #--no rates--"plot the liquid rate over time (monthly aggragated) of the 2 best performing producers and also the worst of all"    
            #"generate a TAU vs GAIN plot. Interpret it. "
            #"Make a summary of the quality of the simulations and show the percent of the total production of all the wells combined that is due to injectionm, pressure and primary depletion"
            #"Determine how many injectors -on average- support a producer with a non-negligible gain?. For the best supported producer show a pie chart of its produced volume fractions (oil, gas,water) and compare those volumes to those of the worst performing producer"
            #"Rank the injectors according to the attributable oil produced due to their injection. Plot in a bar chart the oil  produced currently by each producer"
            #"Is there any evidence of channelling?"
        )

    print(100*'+')
    print(100*'+')
    print(100*'+')
            
    task_result = x.run( query )
    

    from agentic_system.common.utils import print_task_result

    print_task_result( task_result )

    #test1()


    #interpreter = ResultsInterpreterComponent( llm = llm )
    #interpreter.set_data( *prepare_test_data() )
    #result = interpreter.run(query="Whats the most supported producer and its supporting injectors?. Rank the producers according to support")
    #print(100*'=')
    #print(100*'=')
    #print( result.cheap_output )
    print(100*'=')
    print(100*'=')
    





