from pydantic import BaseModel, Field

from typing import (
    List,
    Optional,
    Literal,
    Union,
    TypeVar,
    Type,
)

from pathlib import Path


PathLike = Union[str, Path]



# not used 
class SQLExample(BaseModel):
    name: str = Field(description="Short name for the SQL example.")
    purpose: str = Field(description="What this query demonstrates or answers.")
    sql: str = Field(description="Executable SQL snippet.")
    notes: Optional[str] = Field(
        default=None,
        description="Optional assumptions, caveats, or interpretation guidance."
    )

  
class Relationship(BaseModel):
    tables_involved: List[str] = Field(description="Tables participating in the relationship, typically [left_table, right_table].")
    join_type: Literal["inner", "left", "right", "full", "cross"] = Field(
        description="Recommended SQL join type for combining the tables."
    )
    join_condition: Optional[str] = Field(
        default=None,
        description=("SQL join condition, for example \"injectors.NAME = locations.NAME AND locations.WELL_TYPE = 'Injector'\". "))
    description: Optional[str] = Field(default=None,description="Business meaning of this relationship.")

class ColumnCard(BaseModel):
    name: str = Field(description = 'column name')
    data_type: str 
    description: Optional[str] = Field( default = None, description = "meaning of the data in the column")
    derived_column: Optional[bool] = Field( default = False, description="True if column was generated, calculated, or created by an agent")
    #is_categorical: Optional[bool] = Field(description='True if the column contains categorical values and False otherwise')
    #business_rules: List[str] = Field(default_factory=list, description="Actionable business rules for this column, one rule per item.")

class TableCard(BaseModel):
    name : str = Field( description = "table name")
    description : str = Field( description = "brief description of table contents")
    kind : Optional[Literal[ 'base', 'derived']] = Field( description = "wheather this is a base table or a derived one")
    creation_date: Optional[str] = Field(default=None, description = "creation date_time")
    row_count: Optional[int] = Field(default=None, description = "number of rows")


    columns: List[ColumnCard] = Field(
        default_factory=list,
        description="Semantic metadata for columns in this table."
    )
    relationships: List[Relationship] = Field(
        default_factory=list,
        description="Relationships from this table to other tables."
    )
    #sql_examples: List[SQLExample] = Field(
    #    default_factory=list,
    #    description="Representative SQL queries relevant to this table."
    #) 

class CatalogTablesSnapshot(BaseModel):
    
    base_tables: Optional[List[TableCard]] = Field( default=None)
    derived_tables: Optional[List[TableCard]] = Field( default=None)
    
class QueryCatalogItem(BaseModel):
    id: str = Field(description="Stable identifier for the query pattern.")
    question: str = Field(description="Natural-language intent answered by the query.")
    tables: List[str] = Field(default_factory=list, description="Tables used by the query.")
    sql: str = Field(description="Executable SQL query.")
    tags: List[str] = Field(default_factory=list, description="Search tags for retrieval/routing.")
    notes: Optional[str] = Field(default=None, description="Optional caveats or engine-specific guidance.")

class SemanticCatalog(BaseModel):
    semantic_constraints: List[str] = Field(default_factory=list, description="Global semantic constraints for the domain.")
    tables: List[TableCard] = Field(default_factory=list, description="Table metadata cards.")
    query_catalog: Optional[List[QueryCatalogItem]] = Field(default = None, description="Reusable SQL query templates.")

class SQLIdiom(BaseModel):
    topic: str = Field(description="Topic area for the SQL idiom.")
    rule: str = Field(description="Recommended SQL idiomatic rule.")
    examples: List[str] = Field(default_factory=list, description="Short SQL snippets that illustrate the rule.")
    notes: Optional[str] = Field(default=None, description="Optional caveats for the SQL dialect.")

class SQLIdiomsCatalog(BaseModel):
    dialect: str = Field(description="SQL dialect the idioms target.")
    idioms: List[SQLIdiom] = Field(default_factory=list, description="Dialect-specific SQL idioms.")


class SemanticContext(BaseModel):
    definitions: List[str] = Field(default_factory=list, description="Canonical definitions for domain terms.")
    business_rules: List[str] = Field(default_factory=list, description="Business-level rules and policies.")
    domain_knowledge: List[str] = Field(default_factory=list, description="General domain guidance and assumptions.")


TSemanticContext = TypeVar(
    "TSemanticContext",
    bound=SemanticContext,
)


def load_text(path: PathLike, encoding: str = "utf-8") -> str:
    """Read a text file and return its complete contents as a string."""
    return Path(path).read_text(encoding=encoding)


def load_catalog_text(path: PathLike, encoding: str = "utf-8") -> str:
    """Read a semantic-catalog JSON file without parsing it."""
    return load_text(path, encoding)


def load_context_text(path: PathLike, encoding: str = "utf-8") -> str:
    """Read a semantic-context JSON file without parsing it."""
    return load_text(path, encoding)


def catalog_from_text(text: str) -> SemanticCatalog:
    """Validate JSON text and return a SemanticCatalog instance."""
    if not text or not text.strip():
        raise ValueError("Semantic catalog text cannot be empty.")
    return SemanticCatalog.model_validate_json(text)

def catalog_from_file(path: PathLike, encoding: str = "utf-8") -> SemanticCatalog:
    """Read, validate, and return a semantic catalog from a JSON file."""
    return catalog_from_text(load_catalog_text(path, encoding))




#def old_context_from_text(text: str) -> SemanticContext:
#    """Validate JSON text and return a SemanticContext instance."""
#    if not text or not text.strip():
#        raise ValueError("Semantic context text cannot be empty.")
#    return SemanticContext.model_validate_json(text)


#def old_context_from_file(path: PathLike, encoding: str = "utf-8") -> SemanticContext:
#    """Read, validate, and return semantic context from a JSON file."""
#    return context_from_text(load_context_text(path, encoding))




TSemanticContext = TypeVar(
    "TSemanticContext",
    bound=SemanticContext
)



def context_from_text(
    text: str,
    context_type: Type[TSemanticContext] = SemanticContext,
) -> TSemanticContext:

    """Validate JSON text and return a semantic context instance."""

    if not text or not text.strip():
        raise ValueError("Semantic context text cannot be empty.")

    return context_type.model_validate_json(text)


def context_from_file(
    path: str | PathLike,
    context_type: Type[TSemanticContext] = SemanticContext,
    encoding: str = "utf-8",
) -> TSemanticContext:

    """Read, validate, and return a semantic context instance from JSON."""

    return context_from_text(
        load_context_text(path, encoding),
        context_type=context_type,
    )
