
import inspect
import sys
import pprint
import json

from time import perf_counter
sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path
 
from datetime import datetime
from pathlib import Path 
import duckdb
from langchain_core.tools import StructuredTool
from typing import Dict, Generic, Iterable, List, Literal, TypeVar
from abc import ABC, abstractmethod
from typing import Any
import pandas  as pd 
from typing_extensions import Self
import yaml

from agentic_system.common.semantic_models import CatalogTablesSnapshot, ColumnCard, SemanticCatalog, TableCard
from agentic_system.common.base_task import DataFrameResult, TaskResult


class BaseDataComponent(ABC):
    """
    Base class for stateful domain data components.

    Concrete implementations define how raw domain data is stored
    and exposed to the rest of the system.
    """

    def __init__(self):
        self._raw_data = None
        self._metadata = None

    def set_data(self, data:Any, metadata:Any|None = None ) -> Self:
        """
        Set or replace the RAW domain data.
        """
        self._raw_data = data
        self._metadata = metadata
        return self
        
    def update_metadata( self, metadata:Any|None = None)->Self:
        self._metadata = metadata
        return self

    def update_data( self, raw_data:Any|None = None)->Self:
        self._raw_data = raw_data
        return self 


    @property
    def raw_data(self) -> Any:
        self._check_if_data()
        return self._raw_data

    @property
    def metadata(self) -> Any | None:
        return self._metadata
    

    
    def set_raw_data(self, data:Any, metadata:Any|None = None ) -> Self:
        """
        Set or replace the RAW domain data.
        """
        return self.set_data(data, metadata)



    def _check_if_data(self) -> None:
        """
        Raise an error if data has not been set.
        """
        if self._raw_data is None:
            raise RuntimeError( "No data has been set. Call set_data(...) first.")
        

    def _check_if_raw_data(self) -> None:
        """
        Raise an error if data has not been set.
        """
        return self._check_if_data()
    
      
TData = TypeVar("TData", bound=BaseDataComponent)

class BaseDomainTools(Generic[TData]):
    """
    Base class for domain-specific tools exposed to an LLM agent.

    Concrete subclasses define public methods with docstrings.
    Those methods are automatically exposed as StructuredTools.
    """

    def __init__(self, llm = None ):
        self._data_component: TData | None = None
        self.llm = llm 


    @property
    def data_component(self) -> TData:
        """
        Return the attached data component.

        Raises:
            RuntimeError: If no data component has been assigned.
        """
        if self._data_component is None:
            raise RuntimeError(
                "No data component has been assigned. "
                "Call set_data_component(...) first."
            )

        return self._data_component

    
    def set_data_component(self, data_component: TData) -> Self :
        """
        Attach the data component used by these tools.
        """
        self._data_component = data_component
        return self 

    def _check_if_data_component(self) -> None:
        """
        Return the attached data component or raise if none is available.
        """
        _ = self.data_component

        return None 

    def get_tools(self) -> list[StructuredTool]:
        return self.get_agent_tools()
    
    def get_agent_tools(self) -> list[StructuredTool]:
        """
        Return the public documented methods exposed to the LLM agent.
        """
        tools = []

        excluded_methods = {
            "set_data_component",
            "get_agent_tools",
            "get_tools"
        }

        for name in dir(self):
            if name.startswith("_") or name in excluded_methods:
                continue

            attr = getattr(self, name)

            if not callable(attr):
                continue

            doc = inspect.getdoc(attr)

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


class Catalog:

    def __init__(self):
        self.tables: Dict[str, TableCard] = {}

    def snapshot(
        self,
        input_tables=None
    ) -> CatalogTablesSnapshot:
        """
        Return structured catalog snapshot.

        Output:
        CatalogTablesSnapshot(
            base_tables=[...],
            derived_tables=[...]
        )
        """

        # =====================================================
        # SELECT TABLES
        # =====================================================

        if input_tables is None:
            items = self.tables.values()

        elif isinstance(input_tables, TableCard):
            items = [input_tables]

        else:
            items = input_tables

        # =====================================================
        # OUTPUT CONTAINERS
        # =====================================================

        base_tables = []
        derived_tables = []

        # =====================================================
        # BUILD TABLE CARDS
        # =====================================================

        for tc in items:

            columns = []

            for c in tc.columns:

                #print( type(c) )    
                #column_card = ColumnCard(
                #    name=c.name,
                #    data_type=c.data_type or "",
                #    semantic_type=getattr(c, "semantic_type", None),
                #    description=c.description if c.description else None,
                #    allowed_values=getattr(c, "allowed_values", None),
                #)

                columns.append( c )#column_card)

            # -----------------------------------------
            # Preserve created SQL if available
            # -----------------------------------------
            created_by_sql = None

            #if hasattr(tc, "created_by_sql"):
            #    created_by_sql = tc.created_by_sql

            #elif getattr(tc, "sql_examples", None):
            #    if tc.sql_examples:
            #        created_by_sql = tc.sql_examples[0].sql

            # -----------------------------------------
            # Build structured table card
            # -----------------------------------------
            table_card = TableCard(
                name=tc.name,
                description=tc.description,
                kind=tc.kind or "base",
                row_count=tc.row_count,
                columns=columns,
                creation_date=tc.creation_date,
                #relationships=tc.relationships if hasattr(tc, "relationships") else None,   
                #created_by_sql=created_by_sql,
            )

            # -----------------------------------------
            # Route by type
            # -----------------------------------------
            if table_card.kind == "derived":
                derived_tables.append(table_card)

            else:
                base_tables.append(table_card)

        # =====================================================
        # RETURN STRUCTURED SNAPSHOT
        # =====================================================

        return CatalogTablesSnapshot(
            base_tables=base_tables if base_tables else None,
            derived_tables=derived_tables if derived_tables else None,
        )
            
    def textual_snapshot(self, input_tables=None) -> dict:

        if input_tables is None:
            items = self.tables.values()
        elif isinstance(input_tables, TableCard):
            items = [input_tables]
        else:
            items = input_tables

        out = {
            "base_tables": {},
            "derived_tables": {}
        }

        for tc in items:
            cols = {}

            for c in tc.columns:
                dtype = c.data_type if c.data_type else ""

                col_entry = {"type": dtype}

                if c.description:
                    col_entry["description"] = c.description

                cols[c.name] = col_entry

            #created_by_sql = None
            #if hasattr(tc, "created_by_sql"):
            #    created_by_sql = tc.created_by_sql
            #elif tc.sql_examples:
            #    created_by_sql = tc.sql_examples[0].sql

            table_entry = {
                "description": tc.description,
                "kind": tc.kind or "base",
                "row_count": tc.row_count,
                "columns": cols,
                #"created_by_sql": created_by_sql,

            }

            if tc.kind == "derived":
                out["derived_tables"][tc.name] = table_entry
            else:
                out["base_tables"][tc.name] = table_entry

        return out        
            
    def good_snapshot(self, input_tables=None) -> dict:
        """
        Return a simplified catalog:
        {
          "tables": {
             table_name: {
                "columns": {col: dtype},
                "created_by_sql": str | None,
                "description": str,
                "kind": "base" | "derived"
             }
          }
        }
        """
        if input_tables is None:
            items = self.tables.values()
        elif isinstance(input_tables, TableCard):
            items = [input_tables]
        else:
            items = input_tables

        out = {"tables": {}}

        for tc in items:
            # columns: name -> dtype
            cols = {}
            for c in tc.columns:
                dtype = c.data_type if c.data_type else ""
                col_entry = {"type": dtype}
                #if c.description:
                #    col_entry["description"] = c.description
                cols[c.name] = col_entry
                        
                #cols[c.name] = dtype
                #cols[c.name] = {
                #"type": dtype,
                #"description": c.description or ""
                #}

            # created_by_sql (you already store this in sql_examples or elsewhere?)
            #created_by_sql = None
            #if hasattr(tc, "created_by_sql"):
            #    created_by_sql = tc.created_by_sql
            #elif tc.sql_examples:
            #    # optional: pick first example as origin
            #    created_by_sql = tc.sql_examples[0].sql

            out["tables"][tc.name] = {
                "columns": cols,
                #"created_by_sql": created_by_sql,
                "description": tc.description,
                "kind": tc.kind or "base",
            }

        return out

    def yaml_snapshot(
        self,
        input_tables: None | TableCard | Iterable[TableCard] = None,
    ) -> str:
        """
        Returns a clean YAML snapshot of one or more table cards.

        Output shape:

        tables:
          - name: injectors
            ...
          - name: producers
            ...
        """

        if input_tables is None:
            items = list(self.tables.values())

        elif isinstance(input_tables, TableCard):
            items = [input_tables]

        elif isinstance(input_tables, Iterable):
            items = list(input_tables)

        else:
            raise TypeError(f"{type(input_tables).__name__} is not supported")

        tables = []

        for tc in sorted(items, key=lambda x: x.name):
            d = tc.model_dump(
                exclude_none=True,
                exclude_defaults=True,
                exclude_unset=True,
                mode="json",
            )

            tables.append(d)

        return yaml.dump(
            {"tables": tables},
            sort_keys=False,
            allow_unicode=True,
            width=1000,
    ).rstrip()    
                   
    def old_snapshot(self, input_tables: None | TableCard | Iterable[TableCard] = None ) -> str: # pyright: ignore[reportArgumentType]
        
        table_blocks: list[str] = []
        
        items = (
            self.tables.values()
            if input_tables is None
            else [input_tables]
            if isinstance(input_tables, TableCard)
            else input_tables if isinstance(input_tables,Iterable)
            else list(input_tables)
        )
        '''
        s = "tables:\n"
        for tc in  sorted( items,  key=lambda x: x.name):
            s1 = f" - table:{tc.name}\n{tc.description}"
            cols = ""
            s = s + s1 

        return s 
        '''
 

        for tc in  sorted( items,  key=lambda x: x.name):
            d = tc.model_dump(
                exclude_none=True,
                exclude_defaults=True,
                exclude_unset = True,
                mode = 'json',
                #exclude = {'columns'}
            )

            block = yaml.dump(
                {"table": [d]},
                sort_keys=False,
                allow_unicode=True,
                width=1000  # avoid wrapping
            ).rstrip()

            table_blocks.append(block)
            table_blocks.append("")


        return "\n".join(table_blocks) 
  
    @staticmethod  
    def dataframe_to_table_card( df: pd.DataFrame, name, description, kind:Literal['base','derived'], **kwargs):
        dt = datetime.now() if hasattr(datetime, "now") else datetime.datetime.now()  
             
        cols = [ ColumnCard( name = col, data_type = str(df[col].dtype), description = None) for col in df.columns] 
        table_card = TableCard(
            name=name,
            description=description,
            kind = kind, 
            creation_date=str( dt ),
            row_count=df.shape[0],
            columns = cols,
            relationships = [] if not kwargs else kwargs.get('relationships', []),
            #sql_examples  = [] if not kwargs else kwargs.get('sql_exampled',  [])

        )

        return table_card
        
    def clear(self):
        self.tables = {} 

    def initialize_from_semantic_model( self, named_table_models:Dict[str,TableCard] ):
        return self.init_from_semantic_models( named_table_models )
    
    def init_from_semantic_models( self, named_table_models:dict[str,TableCard] ):
        self.clear()   

        for name,model in named_table_models.items():
                            
            dt = datetime.now() if hasattr(datetime, "now") else datetime.datetime.now()  
            model.creation_date = str( dt )
            self.tables[name] = model
            
    def initialize_from_named_dataframes( self, df_dict: Dict[str,pd.DataFrame], 
                                         named_table_models:Dict[str,TableCard] ):
        self.clear() 
        self.initialize_from_semantic_model( named_table_models )
        self.set_data( df_dict )

        return 

        for name,df in df_dict.items():
            model = named_table_models.get(name, None)
            if model:
                model.row_count = df.shape[0]

                dt = datetime.now() if hasattr(datetime, "now") else datetime.datetime.now()  
                model.creation_date = str( dt )
                self.tables[name] = model
            else:
                raise ValueError(f"Table named {name} is not in the known tables catalog")
       
    def set_data(self,  df_dict: Dict[str,pd.DataFrame]):
        """
        Sets the new tables (data) assuming that the semantic model is already stored.
        Useful when chaning the project dataset, while still having the same table structure.
        Note that all derived tables will be lost.
        """
        temporal = {}
        dt = datetime.now() if hasattr(datetime, "now") else datetime.datetime.now()  
        creation_date = str( dt )


        for name, df in df_dict.items():
            if name not in self.tables:
                raise ValueError(f"Table named {name} is not in the known tables catalog")

            model = self.tables[name]
            model.row_count = df.shape[0]
            model.creation_date = creation_date
          
            #print('catalog setting',name, model.creation_date, model.row_count)
            temporal[name] = model

        self.tables = temporal 




    def register_table(self, table_card: TableCard ):
        dt = datetime.now() if hasattr(datetime, "now") else datetime.datetime.now()  
             
        table_card.creation_date = str( dt )
        self.tables[ table_card.name ] = table_card

    def __repr__(self) -> str:
        return self.snapshot()

    def __getitem__(self, value):
        
        cards = None 
        if isinstance(value, slice):
            cards =  list(self.tables.values())[value] 

        if isinstance(value, str ):
            cards = self.tables[value]

        if isinstance(value, Iterable ):
            cards = [ self.tables[v] for v in value] 
 

        return cards  


class SmartData(BaseDataComponent):

    def __init__(self):
        self._catalog = Catalog() 
        self.conn= duckdb.connect()

    #this is the interface that we need to implement. 
    
    #creates the tables in the db and the metadata in the catalog
    #set_data(self, data:Any, metadata:Any|None = None )

    #Creates a default catalog.  
    #update_metadata( self, metadata:Any|None = None)->Self:

    #also touches the row count and creation date in the catalog 
    #update_data( self, raw_data:Any|None = None)->Self


    #def get_table_tools(self):
    #    """
    #    Return a SmartDataTools instance bound to this SmartData object.
    #    Creates it lazily and reuses the same instance.
    #    """
    #    
    #    smart_tools = SmartDataTools(self)
    #    return smart_tools

    #def get_tools(self):
    #    return self.get_agent_tools()
    
    #def get_agent_tools(self):
    #    """
    #    Return a SmartDataTools instance bound to this SmartData object.
    #    Creates it lazily and reuses the same instance.
    #    """
    #    
    #    smart_tools = SmartDataTools(self)
    #    return smart_tools.get_tools()


    def _normalize_sql(self, sql: str) -> str:
        lines = sql.strip().splitlines()
        #print(lines)
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()


    def execute_sql( self, sql:str):#, table_description:str ):
        """
        materialize a table by executing sql.  
        Args:
            sql(str): sql quiery to execute. Must start with WITH or SELECT  
        """
        #print('materializing')
        #print('sql', sql)
        #print('description', table_description)
        norm_sql = self._normalize_sql( sql )
        result = self.conn.execute(norm_sql).fetchdf()
        return result 

    def clear( self ):
        self._catalog.clear()
        #self.conn.close()
        #self.conn= duckdb.connect()
        self.restart_connection()

    def restart_connection( self ):
        self.conn.close()
        self.conn= duckdb.connect()

    def clear_derived( self ):
        derived_table_names = [
            name
            for name, card in self._catalog.tables.items()
            if card.kind == 'derived'
        ]

        for name in derived_table_names:
            try:
                self.conn.unregister(name)
            except duckdb.CatalogException:
                pass
            self._catalog.tables.pop(name, None)

    def sanitize_df(self, df):

        df = df.copy()
        return df 
    
        # Ensure index is not problematic
        if df.index.name is not None or not isinstance(df.index, pd.RangeIndex):
            df = df.reset_index()

        # Attempt to convert object columns
        for col in df.columns:
            if df[col].dtype == "object":
                # try datetime
                converted = pd.to_datetime(df[col], errors="ignore")
                if not pd.api.types.is_object_dtype(converted):
                    df[col] = converted
                    continue

                # try numeric
                converted = pd.to_numeric(df[col], errors="ignore")
                if not pd.api.types.is_object_dtype(converted):
                    df[col] = converted

        return df
    
    def set_data( self, data:Any, metadata:Any|None = None)->Self:
        # ADict[str,pd.DataFrame], metadata : dict[str,TableCard]|None=None):

        df_dict = data 
        super().set_data( df_dict, metadata )

        if metadata:

            self.update_metadata( metadata )

        if data:
            self.update_data( data )

        return Self  # type: ignore
    

    def update_data(self, raw_data: Any | None = None) -> Self:

        super().update_data(raw_data)
        try:
                
            self.restart_connection()
            self._catalog.set_data( raw_data ) # type: ignore
                
            
            for name, df in raw_data.items(): # type: ignore
                df = self.sanitize_df(df)
                self.conn.register(name, df)

        except Exception as e:
            print("exception", str(e))
            self.clear()
            raise

        return self

    def update_metadata(self, metadata: Any | None = None) -> Self:

        super().update_metadata(metadata)

        try:
                
            known_table_models = { t: v for t,v in metadata.items() } 
            self._catalog.init_from_semantic_models( known_table_models )

        except Exception as e:
            print("exception", str(e))
            self.clear()
            raise

        return self 
    
            

    
        

    def _init_from_data_and_models( self, df_dict: Dict[str,pd.DataFrame],table_models: List[TableCard]):

        raise NotImplementedError
        #super().set_data(df_dict, table_models) 
        
        self.init_from_semantic_models( table_models )
        #self.set_data( df_dict )



    #@staticmethod
    def init_from_semantic_models( self,table_models: list[TableCard]):

        raise NotImplementedError
        #smart_data = self#, SmartData()
        
        try:
            
            known_table_models = { t.name: t for t in table_models } 
            self._catalog.init_from_semantic_models( known_table_models )

        except Exception as e:
            print("exception", str(e))
            self.clear()
            raise

        #return smart_data




    @staticmethod
    def initialize_from_named_dataframes(
        df_dict: Dict[str, pd.DataFrame],
        named_table_models: Dict[str, TableCard],
    ):
        smart_data = SmartData()
        raise NotImplementedError

        try:
            conn = smart_data.conn
            smart_data._catalog.initialize_from_named_dataframes(
                df_dict,
                named_table_models,
            )

            for name, df in df_dict.items():
                df = smart_data.sanitize_df(df)
                conn.register(name, df)

        except Exception as e:
            print("exception", str(e))
            smart_data.clear()
            raise

        return smart_data

    def catalog_snapshot(self, input_tables: None | str | Iterable[str] = None) -> CatalogTablesSnapshot:
        """
        Returns schema and description of all tables (base and derived) in the database
        """
        if input_tables is None:
            return self._catalog.snapshot()
        if isinstance(input_tables, str):
            card = self._catalog.tables[input_tables]
            return self._catalog.snapshot(card)
        if isinstance(input_tables, Iterable):
            cards = [self._catalog.tables[name] for name in input_tables]
            return self._catalog.snapshot(cards)
        raise TypeError(f"{type(input_tables).__name__} is not supported")

    
    def catalog_textual_snapshot(self, input_tables=None) -> dict:
        """Return table descriptions and columns for agent context."""

        if input_tables is None:
            return self._catalog.textual_snapshot()

        if isinstance(input_tables, str):
            card = self._catalog.tables[input_tables]
            return self._catalog.textual_snapshot(card)

        cards = [self._catalog.tables[name] for name in input_tables]
        return self._catalog.textual_snapshot(cards)

    def register_derived_table(self, df:pd.DataFrame, name:str, table_description:str ):
        card = Catalog.dataframe_to_table_card( df, name, table_description, 'derived' )
        self._catalog.register_table( card )
        self.conn.register(name, df)

    def get_table_names( self ):
        """Returns the table names"""
        return [name for name in self._catalog.tables ] 
    
    def get_tables_creation_datetime( self )-> Dict[str,str]  :
        """Returns the creation date of each table"""
        return { t: v.creation_date  for t,v in self._catalog.tables.items() }   # pyright: ignore[reportReturnType]
    
    def get_single_table_brief_description( self, table_name:str ):
        """Returns a brief textual description of a single table"""
        return { t: v.description  for t,v in self._catalog.tables.items() if t.lower()==table_name }  

    def get_tables_brief_description( self ):
        """Returns a brief textual description of the tables"""
        return { t: v.description  for t,v in self._catalog.tables.items() }  

    def get_table_as_df( self, table_name:str )->pd.DataFrame:
        return self.conn.execute(f"SELECT * FROM {table_name}").fetchdf()

    def get_df( self, table_name:str )->pd.DataFrame:
        return self.get_table_as_df( table_name )


class SmartDataTools(BaseDomainTools[SmartData]):

    def __init__(self, data:SmartData|None = None):
        super().__init__()
        self._data_component = data 

    def set_data_component(self, data_component: SmartData) -> BaseDomainTools[SmartData]:
        return super().set_data_component(data_component)
        #self.domain_tools.set_data_component( self.data_component )

    # ----------------------------------------
    def record_plan(self, plan: str) -> str:
        """
        Records the execution plan. Does NOT affect execution.
        """
      
        
        print("\n===== PLAN (TOOL) =====")
        print(plan)
        print("=======================\n")
         
        return "OK"
    

    def format_catalog_snapshot(self, snapshot: CatalogTablesSnapshot) -> str:
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

        snapshot = self._data_component.catalog_snapshot(input_tables)
        #print(snapshot)
        return self.format_catalog_snapshot( snapshot )

    def _get_table_names( self ):
        """Returns the table names"""
        
        return  self._data_component.get_table_names() 
    
    def get_tables_creation_datetime( self )-> Dict[str,str]  :
        """Returns the creation date of each table"""
        print( ['get_tables_creation_datetime'])
        return self._data_component.get_tables_creation_datetime()
        
    def get_tables_brief_description( self ):
        """Returns a brief textual description of the tables"""
        print( ['get_tables_brief_description'])
        return self._data_component.get_tables_brief_description() 

    def get_single_table_brief_description( self, table_name:str ):
        """Returns a brief textual description of a single table"""
        print( ['get_single_table_brief_description'])
        return self._data_component.get_single_table_brief_description( table_name )  

    def materialize_select( self, table_name, rows )->str:
        """
        Return a full table to produce a textual response. 
        **Do not call this tool ** unless the table has less than 20 rows
        """

        print( ['materialize_select'])
        #return self._conn.execute(f'SELECT * FROM "{table_name}"').fetchdf()
        if not table_name:
            return "table_name cannot be empty"

        # Validate table exists
        exists = self._data_component.conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = ?
            """,
            [table_name],
        ).fetchone()[0]

        if exists == 0:
            raise ValueError(f"Table '{table_name}' does not exist in DuckDB")

        # Safe quoting for table names
        safe_name = table_name.replace('"', '""')
        limit = min(20, int(rows))
        return self._data_component.conn.execute(f'SELECT * FROM "{safe_name}" LIMIT {limit}').fetchdf().to_string()

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
        retries = 0 

        print("[sql_materialize]")
        try:
            df_result = self._data_component.execute_sql(sql)#, detailed_table_description)
            self._data_component.register_derived_table( df_result, materialized_table_name, detailed_table_description)
        
            snapshot = self._data_component.catalog_snapshot(materialized_table_name)
            txt_snapshot = self.format_catalog_snapshot( snapshot )
            n_rows, n_cols = df_result.shape

            table_preview = ""
            if n_rows < 10 and n_cols < 5:
                table_preview = f"Table {materialized_table_name} preview:\n{df_result.to_string(index=True)}\n"
                

            return (
                        f"Observation: table {materialized_table_name} created.\n"
                        f"\n{txt_snapshot}\n"
                        f"{table_preview}"
                    )
            #return f"Observation: table {materialized_table_name} created.\nTable metadata:\n{txt_snapshot}\n"

        except Exception as e:
            error_msg = (
                        f"Observation: Materialization failed for table '{materialized_table_name}'.\n"
                        f"Error Type: {type(e).__name__}\n"
                        f"Error Detail: {str(e)}\n"
                        f"Failed SQL: {sql}\n"
                    )
            return error_msg

    def reuse_derived_table(self, derived_table_name:str, table_description:str):
        """Call this function to reuse a **derived** table present in the catalog."""

        print("[reuse_derived_table]")

        if derived_table_name in self._get_table_names():
            return f"Table {derived_table_name} is in the catalog and can be reused.\ndescription: {table_description} "
        else:
            return f"Table {derived_table_name} **IS NOT in the catalog** and **CANNOT** be reused. "


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




def get_default_data():
    inj, prod,locs = MockDataDrivenStorage( None ).get_project_dataset()
    return inj, prod,locs

def get_default_smart_data():
    inj, prod,locs =get_default_data()

    print( inj.head(4))
    print( prod.head(4))
    print( locs.head(4))
    print( )

    # to create a smart data object we need: dict[ table_name, pd.Dataframe] and , 
    # metadata = dict[ table_name, TableCard ]
    #This is a dictionary of table-name: semantic info
    from agentic_system.components.data_analyst.known_tables_models import inj_prod_locs_semantic_catalog 
    semantic_catalog = SemanticCatalog.model_validate(inj_prod_locs_semantic_catalog)

    tables = semantic_catalog.tables
    tables_dict = {'injectors':inj, 'producers':prod, 'locations':locs }
    tables_metadata = { t.name: t for t in tables }  

    # this should immediately create a smart data object that we can query
    # the object should be able to execure sql.
    smart_data =  SmartData(  )
    smart_data.set_data( tables_dict, tables_metadata )

    return smart_data

def test_smart_data():
    inj, prod,locs =get_default_data()

    print( inj.head(4))
    print( prod.head(4))
    print( locs.head(4))
    print( )

    # to create a smart data object we need: dict[ table_name, pd.Dataframe] and , 
    # metadata = dict[ table_name, TableCard ]
    #This is a dictionary of table-name: semantic info
    from agentic_system.components.data_analyst.known_tables_models import inj_prod_locs_semantic_catalog 
    semantic_catalog = SemanticCatalog.model_validate(inj_prod_locs_semantic_catalog)

    tables = semantic_catalog.tables
    tables_dict = {'injectors':inj, 'producers':prod, 'locations':locs }
    tables_metadata = { t.name: t for t in tables }  

    # this should immediately create a smart data object that we can query
    # the object should be able to execure sql.
    smart_data =  SmartData(  )
    smart_data.set_data( tables_dict, tables_metadata )

    smart_data.clear()
    smart_data.set_data( tables_dict, tables_metadata )
        

    print(100*'=')
    prod_desc = smart_data.get_single_table_brief_description('producers')
    print( prod_desc )

    #smart_data.catalog_snapshot
    creation_dates = smart_data.get_tables_creation_datetime()
    print( creation_dates )


    df_locs= smart_data.get_table_as_df('locations')
    print( df_locs.head(4))

    print("Datasets in the catalog -the agents use these- ")

    print("Query a single table")
    #self, input_tables: None | str | Iterable[str] = None)

    catalog_output = smart_data.catalog_snapshot( 'injectors' )
    print(catalog_output.model_dump())
    print()

    #better for prompts:
    text_snapshot = smart_data.catalog_textual_snapshot("injectors")
    print( text_snapshot )
    print()


    return 


    catalog_output = smart_data.catalog_snapshot( ['producers','locations']  )
    pprint.pprint(catalog_output.model_dump())
    print()

    #returns all 
    catalog_output = smart_data.catalog_snapshot(  )
    pprint.pprint(catalog_output.model_dump())
    print()

    print(100*'=')
    print("I can use sql instructions directly on this data")

    print("#1. Top 10 injectors by total injected water")
    sql1="""SELECT
        NAME,
        SUM(WATER_INJECTION_VOLUME) AS TOTAL_INJECTED_WATER
    FROM injectors
    GROUP BY NAME
    ORDER BY TOTAL_INJECTED_WATER DESC
    LIMIT 10;"""


    print("#2. Monthly injected water by sector")
    sql2="""SELECT
        DATE_TRUNC('month', "DATE") AS INJECTION_MONTH,
        SECTOR,
        SUM(WATER_INJECTION_VOLUME) AS TOTAL_INJECTED_WATER
    FROM injectors
    GROUP BY INJECTION_MONTH, SECTOR
    ORDER BY INJECTION_MONTH, SECTOR;""" 

    print("#3. Injection summary by subzone")
    sql3="""
    SELECT
        SUBZONE,
        COUNT(DISTINCT NAME) AS NUMBER_OF_INJECTORS,
        SUM(WATER_INJECTION_VOLUME) AS TOTAL_INJECTED_WATER,
        AVG(WATER_INJECTION_VOLUME) AS MEAN_VOLUME_PER_RECORD
    FROM injectors
    GROUP BY SUBZONE
    ORDER BY TOTAL_INJECTED_WATER DESC;
    """


    result = smart_data.execute_sql( sql1 )
    print( result )
    print() 


    result = smart_data.execute_sql( sql2 )
    print( result )
    print() 


    result = smart_data.execute_sql( sql3 )
    print( result )
    print( type(result) )



    
    #agent: str  
    #instruction: str  
    #cheap_output: str  
    #raw_results: list[Any] #Original agent-specific outputs, such as structured LLM responses 
    #data_results: list[TextResult|DataFrameResult] = #dataframes, text, etcx 
 
    tr = TaskResult( agent="analyst",instruction="Injection summary by subzone",
                    cheap_output="Generated a pretty cool table",
                    raw_results=[],
                    data_results= [DataFrameResult(table_name="dfgdfg",description="dsfsd",
                                                   records=result.to_dict(orient='records'))] 
                    )

    print(100*'=')

def test_smart_data_tools():

    smart_data = get_default_smart_data()
    smart_tools =  SmartDataTools()
    smart_tools.set_data_component( smart_data )

    # test some basic tools 
    print( smart_tools._get_table_names( ))

    print( smart_tools.get_tables_creation_datetime( ))

    print( smart_tools.get_single_table_brief_description( 'producers' ))

    print( smart_tools.record_plan( 'dummy plan....' ))

    # llm friendly -> parses the structured from the catalog 
    print( smart_tools.catalog_snapshot())
    
    print()

if __name__ == "__main__":

    #test_smart_data() 
    test_smart_data_tools()
    print()
