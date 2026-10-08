import sys
from uuid import uuid4

#from yaml 
import warnings as warnings_module

sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path


from agentic_system.common.base_plan import ExecutorState
from agentic_system.components.presenter.prompts import * 

import inspect  as inspect_module 

from langchain_core.messages import HumanMessage, AIMessage, AnyMessage, SystemMessage
from langchain_core.tools import StructuredTool

from agentic_system.common.base_task import DataFrameResult, TaskExecutionContext, TaskResult, TextResult
from agentic_system.common.get_llm import azure_llm_if
 

from langchain.agents import create_agent

#from agentic_system.common.semantic_models import SemanticCatalog 


import sys, pprint, pandas as pd , os, json, re, plotly.io as pio 
from pathlib import Path
from typing_extensions import Self
from typing import Any, Literal, cast

from agentic_system.common.get_llm import azure_llm_if as get_llm
from agentic_system.components.presenter.prompts import * 
#from agentic_system.common.data_component import BaseDataComponent, BaseDomainTools
#from agentic_system.common.semantic_models import ColumnCard, SemanticCatalog, SemanticContext, TableCard

from pydantic import BaseModel, Field, TypeAdapter

adapter = TypeAdapter(list[TaskResult])

 
class UIItem(BaseModel):
    id: str
    type: Literal["table", "chart", "text", "markdown", "error", "question"]
    title: str | None = None
    data: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)

 
class PresenterResponse(BaseModel):
    agent: Literal["presenter"] = "presenter"
    layout: Literal["vertical", "horizontal"] = "vertical"
    items: list[UIItem] = Field(default_factory=list)


class PresenterChartingTools:

    ALLOWED_AGGS = {"sum", "mean", "median", "min", "max", "count", "nunique"}


    plotly_config = {
                "responsive": True,
                "displaylogo": False,
            }



    def run_preprocess(
        self,
        df: pd.DataFrame,
        preprocess_steps: list[dict] | None,
    ) -> pd.DataFrame:
        work = df.copy()

        for step in preprocess_steps or []:
            
            operation = step.get("operation")

            if not operation:
                raise ValueError("Preprocess step is missing 'operation'")

            args = step.get("args") or {}

            work = self.run_preprocess_operation(
                operation=operation,
                df=work,
                args=args,
            )

        return work


    def run_preprocess_operation(
        self,
        operation: str,
        df: pd.DataFrame,
        args: dict[str, Any],
    ) -> pd.DataFrame:
        preprocess_tools = {
            "filter_rows": self.filter_rows,
            "aggregate": self.aggregate_for_chart,
            "sort_rows": self.sort_rows,
            "limit_rows": self.limit_rows,
            "select_columns": self.select_columns,
            "select_top_entities": self.select_top_entities,
            "create_combined_category": self.create_combined_category,
            "create_date_bucket": self.create_date_bucket,
        }

        if operation not in preprocess_tools:
            raise ValueError(f"Unknown preprocess operation: {operation}")

        return preprocess_tools[operation](
            df=df,
            **args,
        )


    ##########################
    #       pre-process      # 
    ##########################
    def filter_rows(self,df: pd.DataFrame,filters: list[dict]) -> pd.DataFrame:
        
        work = df.copy()
        for item in filters:
            column = item["column"]
            operator = item["operator"]
            value = item["value"]

            self._validate_columns(work, [column])

            if operator == "==":
                work = work[work[column] == value]
            elif operator == "!=":
                work = work[work[column] != value]
            elif operator == ">":
                work = work[work[column] > value]
            elif operator == ">=":
                work = work[work[column] >= value]
            elif operator == "<":
                work = work[work[column] < value]
            elif operator == "<=":
                work = work[work[column] <= value]
 


            elif operator == "in":
                if not isinstance(value, (list, tuple, set)):
                    raise ValueError("'in' filter value must be a list")
                work = work[work[column].isin(value)]

            elif operator == "not_in":
                if not isinstance(value, (list, tuple, set)):
                    raise ValueError("'not_in' filter value must be a list")
                work = work[~work[column].isin(value)]




            else:
                raise ValueError(f"Unsupported filter operator: {operator}")

        return work

    def aggregate_for_chart( self, df: pd.DataFrame, group_by: list[str],
        metrics: dict[str, str],
    ) -> pd.DataFrame:
        
        self._validate_columns(df, group_by)

        for column, aggregate in metrics.items():
            self._validate_columns(df, [column])

            if aggregate not in self.ALLOWED_AGGS:
                raise ValueError(f"Unsupported aggregate: {aggregate}")

        return (df.groupby(group_by, dropna=False, as_index=False).agg(metrics))

    def sort_rows(
        self,
        df: pd.DataFrame,
        sort_by: str | list[str],
        ascending: bool = True,
    ) -> pd.DataFrame:
        sort_columns = self._as_list(sort_by)
        self._validate_columns(df, sort_columns)

        return df.sort_values(
            sort_columns,
            ascending=ascending,
        )

    def limit_rows(
        self,
        df: pd.DataFrame,
        n: int,
    ) -> pd.DataFrame:
        return df.head(n)

    def select_columns(
        self,
        df: pd.DataFrame,
        columns: list[str],
    ) -> pd.DataFrame:
        self._validate_columns(df, columns)
        return df[columns].copy()

    def create_combined_category(
        self,
        df: pd.DataFrame,
        col1: str,
        col2: str,
        new_col: str | None = None,
        sep: str = " / ",
    ) -> pd.DataFrame:
        out = df.copy()

        self._validate_columns(out, [col1, col2])

        new_col = new_col or f"{col1}_{col2}"

        out[new_col] = (
            out[col1].fillna("").astype(str)
            + sep
            + out[col2].fillna("").astype(str)
        )

        return out

    def create_date_bucket(
        self,
        df: pd.DataFrame,
        date_col: str,
        bucket: str,
        new_col: str | None = None,
    ) -> pd.DataFrame:
        out, generated_col = self._bucket_date(
            df,
            date_col,
            bucket,
        )

        if new_col and new_col != generated_col:
            out = out.rename(
                columns={generated_col: new_col}
            )

        return out

    def select_top_entities(
        self,
        df: pd.DataFrame,
        entity_col: str,
        metric_col: str,
        n: int,
        aggregate: str = "sum",
        ascending: bool = False,
        filters: list[dict] | None = None,
        keep_all_rows: bool = True,
    ) -> pd.DataFrame:
        
        self._validate_columns(df,[entity_col, metric_col])
        if aggregate not in self.ALLOWED_AGGS:
            raise ValueError(f"Unsupported aggregate: {aggregate}")

        if n <= 0:
            raise ValueError("n must be greater than zero")
        
        ranking_data = df.copy()

        if filters:
            ranking_data = self.filter_rows(
                ranking_data,
                filters,
            )

        ranking = (
            ranking_data
            .groupby(entity_col, dropna=False, as_index=False)[metric_col]
            .agg(aggregate)
            .sort_values(metric_col, ascending=ascending)
            .head(n)
        )

        selected_entities = ranking[entity_col].tolist()

        if keep_all_rows:
            return df[df[entity_col].isin(selected_entities)].copy()

        return ranking


    ##########################
    #       plot             # 
    ##########################

    def run_plot_tool(
        self,
        tool_name: str,
        df: pd.DataFrame,
        args: dict[str, Any],
    ) -> dict:
        plotting_tools = {
            "plot_bar_chart": self.plot_bar_chart,
            "plot_line_chart": self.plot_line_chart,
            "plot_pie_chart": self.plot_pie_chart,
            "plot_scatter_chart": self.plot_scatter_chart,
            "plot_table": self.plot_table,
            "plot_list": self.plot_list,
        }

        if tool_name not in plotting_tools:
            raise ValueError(f"Unknown plot tool: {tool_name}")

        args = self._filter_args(tool_name, args)
        return plotting_tools[tool_name](df=df, **args)

    def format_label(self, name: str) -> str:
        """
        Convert column-like names to display labels.

        Examples:
        - year_quarter -> Year quarter
        - percentage_contribution -> Percentage contribution
        - TOTAL_WATER_INJECTION_VOLUME -> Total water injection volume
        """
        if name is None:
            return ""

        text = str(name).replace("_", " ").strip().lower()
        return text[:1].upper() + text[1:]

    def _as_list(self, value):
        if value is None:
            return []
        return [value] if isinstance(value, str) else list(value)

    def _strip_markdown_json(self, text: str) -> str:
        """
        Remove markdown code fences from LLM JSON responses.

        Examples:
        ```json
        {...}
        ```

        ->
        {...}
        """

        text = text.strip()

        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        return text.strip()

    def _validate_columns(
        self,
        df: pd.DataFrame,
        columns: list[str],
        label: str = "column",
    ):
        """
        Validate that all requested columns exist in the dataframe.
        """

        missing = [c for c in columns if c not in df.columns]

        if missing:
            raise ValueError(f"Missing {label}(s): {missing}")

    def _filter_args(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Remove unsupported arguments generated by the LLM.
        """

        allowed_args = {
            "plot_bar_chart": {
                "x",
                "y",
                "series_by",
                "orientation",
                "barmode",
                "title",
            },
            "plot_line_chart": {
                "x",
                "y",
                "series_by",
                "title",
            },
            "plot_pie_chart": {
                "labels",
                "values",
                "title",
                "hole",
            },        
            "plot_scatter_chart": {
                "x",
                "y",
                "series_by",
                "size_by",
                "text_by",
                "title",
            },
            "plot_table": {
                "title",
            },
            "plot_list": {
                "columns",
                "sort_by",
                "sort_order",
                "limit",
                "title",
            },
        }

        if tool_name not in allowed_args:
            raise ValueError(f"Unknown tool: {tool_name}")

        return {
            k: v
            for k, v in args.items()
            if k in allowed_args[tool_name]
        }

    def _aggregate(
        self,
        df: pd.DataFrame,
        group_by: list[str],
        value_cols: list[str],
        aggregate: str,
    ) -> pd.DataFrame:
        if aggregate not in self.ALLOWED_AGGS:
            raise ValueError(f"Unsupported aggregate: {aggregate}")

        self._validate_columns(df, group_by, "group_by column")
        self._validate_columns(df, value_cols, "value column")

        return (
            df.groupby(group_by, dropna=False, as_index=False)[value_cols]
            .agg(aggregate)
        )

    def _bucket_date(
        self,
        df: pd.DataFrame,
        date_col: str,
        bucket: str,
    ) -> tuple[pd.DataFrame, str]:
        """
        Create a date bucket column.

        bucket:
        - "D": day
        - "W": week
        - "M": month
        - "Q": quarter
        - "Y": year
        """

        out = df.copy()
        bucket_col = f"{date_col}_{bucket}"

        self._validate_columns(out, [date_col])

        out[date_col] = pd.to_datetime(out[date_col], errors="coerce")

        if bucket == "D":
            out[bucket_col] = out[date_col].dt.to_period("D").dt.to_timestamp()
        elif bucket == "W":
            out[bucket_col] = out[date_col].dt.to_period("W").dt.start_time
        elif bucket == "M":
            out[bucket_col] = out[date_col].dt.to_period("M").dt.to_timestamp()
        elif bucket == "Q":
            out[bucket_col] = out[date_col].dt.to_period("Q").dt.to_timestamp()
        elif bucket == "Y":
            out[bucket_col] = out[date_col].dt.to_period("Y").dt.to_timestamp()
        else:
            raise ValueError("date_bucket must be one of: D, W, M, Q, Y")

        return out, bucket_col

    def plot_bar_chart(
        self,
        df: pd.DataFrame,
        x: str,
        y: str | list[str],
        *,
        series_by: str | None = None,
        orientation: str = "v",
        barmode: str = "group",
        title: str | None = None,
    ) -> dict:
        y_cols = self._as_list(y)

        required = [x, *y_cols]

        if series_by:
            required.append(series_by)

        self._validate_columns(df, required)

        if orientation not in {"v", "h"}:
            raise ValueError("orientation must be 'v' or 'h'")

        if barmode not in {"group", "stack", "relative"}:
            raise ValueError(
                "barmode must be 'group', 'stack', or 'relative'"
            )

        work = df.copy()

        groups = (
            work.groupby(series_by, dropna=False)
            if series_by
            else [(None, work)]
        )

        data = []

        for group_value, group in groups:
            for y_col in y_cols:

                if group_value is None:
                    trace_name = self.format_label(y_col)

                elif len(y_cols) == 1:
                    trace_name = str(group_value)

                else:
                    trace_name = (
                        f"{group_value} - {self.format_label(y_col)}"
                    )

                trace = {
                    "type": "bar",
                    "name": trace_name,
                    "orientation": orientation,
                }

                if orientation == "h":
                    trace["x"] = group[y_col].tolist()
                    trace["y"] = group[x].astype(str).tolist()

                else:
                    trace["x"] = group[x].astype(str).tolist()
                    trace["y"] = group[y_col].tolist()

                data.append(trace)

        x_label = self.format_label(x)
        y_label = self.format_label(", ".join(y_cols))

        return {
            "data": data,
            "layout": {
                "title": {
                    "text": (
                        self.format_label(title)
                        or f"{y_label} by {x_label}"
                    )
                },
                "xaxis": {
                    "title": {
                        "text": y_label if orientation == "h" else x_label
                    }
                },
                "yaxis": {
                    "title": {
                        "text": x_label if orientation == "h" else y_label
                    }
                },
                "barmode": barmode,
            },
            "config": self.plotly_config,
        }

    def plot_line_chart(
        self,
        df: pd.DataFrame,
        x: str,
        y: str | list[str],
        *,
        series_by: str | None = None,
        title: str | None = None,
    ) -> dict:
        y_cols = self._as_list(y)

        required = [x, *y_cols]

        if series_by:
            required.append(series_by)

        self._validate_columns(df, required)

        work = df.copy()

        sort_cols = [series_by, x] if series_by else [x]
        work = work.sort_values(sort_cols)

        groups = (
            work.groupby(series_by, dropna=False)
            if series_by
            else [(None, work)]
        )

        data = []

        for group_value, group in groups:
            for y_col in y_cols:

                if group_value is None:
                    trace_name = self.format_label(y_col)

                elif len(y_cols) == 1:
                    trace_name = str(group_value)

                else:
                    trace_name = (
                        f"{group_value} - {self.format_label(y_col)}"
                    )

                data.append({
                    "type": "scatter",
                    "mode": "lines",
                    "x": group[x].tolist(),
                    "y": group[y_col].tolist(),
                    "name": trace_name,
                })

        return {
            "data": data,
            "layout": {
                "title": {
                    "text": (
                        self.format_label(title)
                        or f"{self.format_label(', '.join(y_cols))} over "
                        f"{self.format_label(x)}"
                    )
                },
                "xaxis": {
                    "title": {
                        "text": self.format_label(x)
                    }
                },
                "yaxis": {
                    "title": {
                        "text": self.format_label(", ".join(y_cols))
                    }
                },
            },
            "config": self.plotly_config,
        }


    def plot_pie_chart(
        self,
        df: pd.DataFrame,
        labels: str,
        values: str,
        *,
        title: str | None = None,
        hole: float = 0.0,
    ) -> dict:
        self._validate_columns(df, [labels, values])

        if not 0.0 <= hole <= 1.0:
            raise ValueError("hole must be between 0 and 1")

        return {
            "data": [
                {
                    "type": "pie",
                    "labels": df[labels].astype(str).tolist(),
                    "values": df[values].tolist(),
                    "hole": hole,
                }
            ],
            "layout": {
                "title": {
                    "text": (
                        self.format_label(title)
                        or (
                            f"{self.format_label(values)} share by "
                            f"{self.format_label(labels)}"
                        )
                    )
                },
            },
            "config": self.plotly_config,
        }


    def plot_scatter_chart(
        self,
        df: pd.DataFrame,
        x: str,
        y: str | list[str],
        *,
        series_by: str | None = None,
        size_by: str | None = None,
        text_by: str | None = None,
        title: str | None = None,
    ) -> dict:
        y_cols = self._as_list(y)

        required = [x, *y_cols]

        if series_by:
            required.append(series_by)

        if size_by:
            required.append(size_by)

        if text_by:
            required.append(text_by)

        self._validate_columns(df, required)

        work = df.copy()

        groups = (
            work.groupby(series_by, dropna=False)
            if series_by
            else [(None, work)]
        )

        data = []

        for group_value, group in groups:
            for y_col in y_cols:

                if group_value is None:
                    trace_name = self.format_label(y_col)

                elif len(y_cols) == 1:
                    trace_name = str(group_value)

                else:
                    trace_name = (
                        f"{group_value} - {self.format_label(y_col)}"
                    )

                trace = {
                    "type": "scattergl",
                    "mode": "markers",
                    "x": group[x].tolist(),
                    "y": group[y_col].tolist(),
                    "name": trace_name,
                }

                if size_by:
                    size_values = (
                        pd.to_numeric(
                            group[size_by],
                            errors="coerce",
                        )
                        .fillna(0)
                    )

                    max_size = max(
                        float(size_values.max()),
                        1.0,
                    )

                    trace["marker"] = {
                        "size": size_values.tolist(),
                        "sizemode": "area",
                        "sizeref": max_size / 40,
                        "sizemin": 4,
                    }

                if text_by:
                    trace["text"] = (
                        group[text_by]
                        .fillna("")
                        .astype(str)
                        .tolist()
                    )

                    trace["hovertemplate"] = (
                        f"{self.format_label(x)}: %{{x}}<br>"
                        f"{self.format_label(y_col)}: %{{y}}<br>"
                        f"{self.format_label(text_by)}: %{{text}}"
                        "<extra></extra>"
                    )

                data.append(trace)

        return {
            "data": data,
            "layout": {
                "title": {
                    "text": (
                        self.format_label(title)
                        or (
                            f"{self.format_label(', '.join(y_cols))} vs "
                            f"{self.format_label(x)}"
                        )
                    )
                },
                "xaxis": {
                    "title": {
                        "text": self.format_label(x)
                    }
                },
                "yaxis": {
                    "title": {
                        "text": self.format_label(", ".join(y_cols))
                    }
                },
            },
            "config": self.plotly_config,
        }


    def plot_table(
        self,
        df: pd.DataFrame,
        *,
        title: str | None = None,
    ) -> dict:
        header_values = [
            self.format_label(column)
            for column in df.columns
        ]

        cell_values = []

        for column in df.columns:
            series = df[column]

            if pd.api.types.is_datetime64_any_dtype(series):
                values = (
                    series
                    .dt.strftime("%Y-%m-%d")
                    .fillna("")
                    .tolist()
                )
            else:
                values = (
                    series
                    .fillna("")
                    .astype(str)
                    .tolist()
                )

            cell_values.append(values)

        return {
            "data": [
                {
                    "type": "table",
                    "header": {
                        "values": header_values,
                        "align": "left",
                    },
                    "cells": {
                        "values": cell_values,
                        "align": "left",
                    },
                }
            ],
            "layout": {
                "title": {
                    "text": self.format_label(title) or "Table"
                },
            },
            "config": self.plotly_config,
        }

    def plot_list(
        self,
        df: pd.DataFrame,
        columns: list[str] | str | None = None,
        *,
        sort_by: str | None = None,
        sort_order: str = "desc",
        limit: int | None = None,
        title: str | None = None,
    ) -> dict:
        work = df.round(2)#df.copy()

        if columns is not None:
            columns = self._as_list(columns)
            self._validate_columns(work, columns)
            work = work[columns]

        if sort_by is not None:
            self._validate_columns(work, [sort_by])

            ascending = sort_order.lower() == "asc"
            work = work.sort_values(sort_by, ascending=ascending)

        if limit is not None:
            work = work.head(limit)

        header_values = [self.format_label(c) for c in work.columns]

        cell_values = []
        for col in work.columns:
            s = work[col]

            if pd.api.types.is_datetime64_any_dtype(s):
                values = s.dt.strftime("%Y-%m-%d").fillna("").tolist()
            else:
                values = s.fillna("").astype(str).tolist()

            cell_values.append(values)

        return {
            "data": [
                {
                    "type": "table",
                    "header": {
                        "values": header_values,
                        "align": "left",
                    },
                    "cells": {
                        "values": cell_values,
                        "align": "left",
                    },
                }
            ],
            "layout": {
                "title": {
                    "text": self.format_label(title) or "Table"
                },
            },
            "config": self.plotly_config
        }

  
   
class PresenterConfig:

    prompt :str  = presenter_preproces_and_plan_prompt
    split_subinstructions_prompt: str = presenter_split_subinstructions_prompt  
    small_table_prompt: str = small_table_prompt 
    
    def __init__(
        self,
        charting_tools: PresenterChartingTools | None = None,
    ):
        self.charting_tools = charting_tools or PresenterChartingTools()

    
class TableResponseProcessor:
    """
    Builds compact, chart-oriented table summaries for a Plotly presenter LLM.
    The LLM receives metadata and limited column examples, but never the full data.
    """

    def __init__(
        self,
        max_examples: int = 3,
        low_cardinality_threshold: int = 10,
        medium_cardinality_threshold: int = 50,
        categorical_numeric_threshold: int = 12,
    ):
        self.max_examples = max_examples
        self.low_cardinality_threshold = low_cardinality_threshold
        self.medium_cardinality_threshold = medium_cardinality_threshold
        self.categorical_numeric_threshold = categorical_numeric_threshold

    def extract_table_context(
        self,
        data_result: Any,
    ) -> str:
        """
        Convert one DataFrameResult into compact, LLM-friendly text.
        """
        table_name = getattr(data_result, "table_name", "unknown_table")
        table_description = getattr(data_result, "description", None)
        #df = data_result.dataframe
        df = pd.DataFrame.from_records(
                    data_result.records,
                    columns=data_result.columns,
                )

        if df is None or df.empty:
            return f"Table: {table_name}\nRows: 0\nColumns: 0\nColumn summaries: []"

        nrows, ncols = df.shape

        lines: list[str] = [f"Table: {table_name}"]

        if table_description:
            lines.append(f"Description: {table_description}")

        lines.extend([
            f"Rows: {nrows}",
            f"Columns: {ncols}",
            "",
            "Column summaries:",
        ])

        preferred_order = [
            "description",
            "dtype",
            "role",
            "unique_count",
            "unique_ratio",
            "cardinality",
            "null_count",
            "null_ratio",
            "min",
            "max",
            "mean",
            "median",
            "min_date",
            "max_date",
            "common_interval",
            "is_monotonic_increasing",
            "has_negative_values",
            "has_zero_values",
            "example_values",
        ]

        for col in df.columns:
            series = df[col]

            # Handle duplicate column names gracefully.
            if isinstance(series, pd.DataFrame):
                series = series.iloc[:, 0]

            summary = self.infer_column_summary(series)

            lines.append(f"- Column: {col}")

            for key in preferred_order:
                if key in summary and summary[key] is not None:
                    val = summary[key]

                    if isinstance(val, float):
                        lines.append(f"  {key}: {val:.4f}")
                    else:
                        lines.append(f"  {key}: {val}")

        return "\n".join(lines)

    def _safe_parse_datetime_candidate(self, s: pd.Series) -> pd.Series:
        values = s.dropna()

        if values.empty:
            return pd.Series(dtype="datetime64[ns]")

        with warnings_module.catch_warnings():
            warnings_module.filterwarnings(
                "ignore",
                message="Could not infer format.*",
                category=UserWarning,
            )

            return pd.to_datetime(values, errors="coerce")

    def infer_column_role(self, s: pd.Series) -> str:
        """
        Infer a chart-oriented semantic role.
        """
        if pd.api.types.is_datetime64_any_dtype(s):
            return "temporal"

        if pd.api.types.is_bool_dtype(s):
            return "categorical"

        if pd.api.types.is_numeric_dtype(s):
            nunique = s.nunique(dropna=True)

            if nunique <= self.categorical_numeric_threshold:
                return "categorical_numeric"

            return "quantitative"

        if pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s):
            parsed = self._safe_parse_datetime_candidate(s)

            valid_ratio = parsed.notna().mean() if len(parsed) else 0.0

            if valid_ratio >= 0.9:
                return "temporal"

            return "categorical"

        return "unknown"

    def infer_column_summary(self, s: pd.Series) -> dict[str, Any]:
        """
        Produce compact metadata for one DataFrame column.
        """
        non_null = s.dropna()

        row_count = len(s)
        non_null_count = len(non_null)

        null_count = row_count - non_null_count
        null_ratio = null_count / row_count if row_count else 0.0

        unique_count = non_null.nunique(dropna=True)
        unique_ratio = unique_count / row_count if row_count else 0.0

        role = self.infer_column_role(s)

        summary: dict[str, Any] = {
            "dtype": str(s.dtype),
            "role": role,
            "non_null_count": int(non_null_count),
            "null_count": int(null_count),
            "null_ratio": round(null_ratio, 4),
            "unique_count": int(unique_count),
            "unique_ratio": round(unique_ratio, 4),
        }

        if role in {"categorical", "categorical_numeric"}:
            summary["cardinality"] = self.classify_cardinality(unique_count)

            examples = (
                non_null
                .drop_duplicates()
                .astype(str)
                .head(self.max_examples)
                .tolist()
            )

            if examples:
                summary["example_values"] = examples

        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            numeric = pd.to_numeric(non_null, errors="coerce").dropna()

            if not numeric.empty:
                summary.update({
                    "min": round(float(numeric.min()), 4),
                    "max": round(float(numeric.max()), 4),
                    "mean": round(float(numeric.mean()), 4),
                    "median": round(float(numeric.median()), 4),
                })

        if role == "temporal" or pd.api.types.is_datetime64_any_dtype(s):
            dt = pd.to_datetime(non_null, errors="coerce").dropna()

            if not dt.empty:
                summary.update({
                    "min_date": str(dt.min()),
                    "max_date": str(dt.max()),
                })

        return summary

    def classify_cardinality(self, unique_count: int) -> str:
        """
        Convert unique count into low/medium/high cardinality label.
        """
        if unique_count <= self.low_cardinality_threshold:
            return "low"

        if unique_count <= self.medium_cardinality_threshold:
            return "medium"

        return "high"


class SubInstruction(BaseModel):
    """
    One presentation item to produce from one source.
    """

    sub_instruction: str = Field(
        description=(
            "The specific part of the original instruction that this source "
            "should answer."
        )
    )

    kind: Literal["table", "text"] = Field(
        description="Whether the source is a table or a text result."
    )

    source_id: str = Field(
        description=(
            "The exact SOURCE_ID provided in the available sources. "
            "For tables use the table name. "
            "For text use the text SOURCE_ID."
        )
    )


class SubInstructions(BaseModel):
    """
    Ordered presentation plan for one TaskResult.
    """

    items: list[SubInstruction] = Field(
        description=(
            "The ordered list of presentation items to generate."
        )
    )
    
    
 
class PresenterComponent4:
    """
    Converts an ExecutorState into UI display items.

    Each TaskResult is processed as a whole:
    - all TextResult and DataFrameResult objects are added to one context;
    - one LLM call splits the task instruction into sub-instructions;
    - each sub-instruction is associated with one source;
    - text sources become text UIItems;
    - table sources are passed to the existing dataframe presentation logic.
    """

    def __init__(
        self,
        llm: Any,
        config: PresenterConfig | None = None,
    ):
        self.llm = llm
        self.config = config or PresenterConfig()
        self.charting_tools = self.config.charting_tools


    agent_name = "presenter"

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
        return inspect_module.cleandoc(self.__doc__)




    def run(self, result_state: ExecutorState) -> PresenterResponse:
        return self.process_task_results(result_state)

    def _make_clarification_item(
        self,
        clarification_request: str,
    ) -> UIItem:
        return UIItem(
            id=f"question_{uuid4().hex[:8]}",
            type="question",
            title="Additional information required",
            data={"question": clarification_request},
        )

    def _make_text_item(
        self,
        data_result: TextResult,
    ) -> UIItem:
        return UIItem(
            id=f"text_{uuid4().hex[:8]}",
            type="text",
            title=None,
            data={"text": data_result.text},
        )

    def _make_error_item(
        self,
        task_result: TaskResult,
        data_result: object | None = None,
    ) -> UIItem:
        return UIItem(
            id=f"error_{uuid4().hex[:8]}",
            type="error",
            title="Presentation error",
            data={
                "message": f"No presenter for result from {task_result.agent}",
                "details": (
                    str(type(data_result))
                    if data_result is not None
                    else task_result.instruction
                ),
            },
        )

    def build_task_result_context(
        self,
        task_result: TaskResult,
    ) -> tuple[str, dict[str, TextResult | DataFrameResult]]:
        """
        Build:
        - one text context containing all TextResult and DataFrameResult objects;
        - a source map used later to recover the original result objects.
        """
        processor = TableResponseProcessor()

        context_parts: list[str] = []
        source_map: dict[str, TextResult | DataFrameResult] = {}

        for n, data_result in enumerate(task_result.data_results):

            if isinstance(data_result, TextResult):
                source_id = f"text_{n}"

                context_parts.append(
                    "\n".join([
                        f"SOURCE_ID: {source_id}",
                        "SOURCE_TYPE: text",
                        "CONTENT:",
                        data_result.text,
                    ])
                )

                source_map[source_id] = data_result

            elif isinstance(data_result, DataFrameResult):
                source_id = data_result.table_name
                table_context = processor.extract_table_context(data_result)

                context_parts.append(
                    "\n".join([
                        f"SOURCE_ID: {source_id}",
                        "SOURCE_TYPE: table",
                        table_context,
                    ])
                )

                source_map[source_id] = data_result

        context_text = "\n\n---\n\n".join(context_parts)

        return context_text, source_map

    def get_subinstructions(
        self,
        task_result: TaskResult,
        context_text: str,
    ) -> SubInstructions:
        """
        Split the task instruction and associate each sub-instruction
        with one available source.
        """
        messages = [
            SystemMessage(content=self.config.split_subinstructions_prompt),
            HumanMessage(
                content=(
                    f"INSTRUCTION\n"
                    f"{task_result.instruction}\n\n"
                    f"AVAILABLE SOURCES\n"
                    f"{context_text}"
                )
            ),
        ]

        structured_llm = self.llm.with_structured_output(SubInstructions)

        return structured_llm.invoke(messages)

    def process_single_task_result(
        self,
        task_result: TaskResult,
    ) -> list[UIItem]:
        context_text, source_map = self.build_task_result_context(
            task_result
        )

        sub_instructions = self.get_subinstructions(
            task_result=task_result,
            context_text=context_text,
        )
        print(sub_instructions.model_dump(), flush=True)

        ui_items: list[UIItem] = []

        for item in sub_instructions.items:
            source = source_map[item.source_id]

            if item.kind == "text":
                ui_items.append(
                    self._make_text_item(source)
                )

            elif item.kind == "table":
                ui_items.append(
                    self._process_dataframe(
                        source,
                        item.sub_instruction,
                    )
                )

        return ui_items

    def process_task_results(
        self,
        execution_state: ExecutorState,
    ) -> PresenterResponse:
        ui_items: list[UIItem] = []

        clarification_request = execution_state.get(
            "clarification_request"
        )

        if clarification_request:
            ui_items.append(
                self._make_clarification_item(
                    clarification_request
                )
            )

            return PresenterResponse(items=ui_items)

        for task_result in execution_state.get("task_results", []):

            print("Processing task result from agent:", task_result.task_id)
            ui_task_items = self.process_single_task_result(
                task_result
            )

            ui_items.extend(ui_task_items)

        return PresenterResponse(items=ui_items)

    def _present_very_small_table(
        self,
        df: pd.DataFrame,
        data_result: DataFrameResult,
        instruction: str,
    ) -> UIItem:
        data_string = df.to_json()

        print('processing very small table')
        prompt = (
            self.config.small_table_prompt
            + "\n\n"
            + (
                "### Context\n"
                f"- Table Name: {getattr(data_result, 'table_name', 'N/A')}\n"
                f"- Description: "
                f"{getattr(data_result, 'description', 'No description provided.')}\n\n"
                "### Data\n"
                f"{data_string}\n\n"
                "User question:\n"
                f"{instruction}\n"
            )
        )

        response = self.llm.invoke(prompt)

        text_output = (
            response.content
            if hasattr(response, "content")
            else str(response)
        )

        return UIItem(
            id=f"text_{uuid4().hex[:8]}",
            type="text",
            title=None,
            data={"text": text_output},
        )

    def _make_chart_item(
        self,
        figure_title: str,
        plotly_json_figure: dict,
        description: str | None = None,
    ) -> UIItem:
        return UIItem(
            id=f"chart_{uuid4().hex[:8]}",
            type="chart",
            title=figure_title,
            data={
                "engine": "plotly",
                "plotly": plotly_json_figure,
            },
            meta={
                "description": description,
            },
        )

    def _make_table_item(
        self,
        figure_title: str,
        plotly_json_figure: dict,
        description: str | None = None,
    ) -> UIItem:
        return UIItem(
            id=f"table_{uuid4().hex[:8]}",
            type="table",
            title=figure_title,
            data={
                "engine": "plotly",
                "plotly": plotly_json_figure,
            },
            meta={
                "description": description,
            },
        )

    def _run_chart_plan(
        self,
        plan: dict,
        df: pd.DataFrame,
    ) -> dict | None:
        work = df.copy()

        preprocess_steps = plan.get("preprocess") or []
        plot = plan.get("plot")

        if preprocess_steps:
            work = self.charting_tools.run_preprocess(
                work,
                preprocess_steps,
            )

        if not plot:
            return None

        tool_name = plot.get("tool")
        args = plot.get("args") or {}

        return self.charting_tools.run_plot_tool(
            tool_name=tool_name,
            df=work,
            args=args,
        )

    def _format_label(
        self,
        name: str,
    ) -> str:
        if name is None:
            return ""

        text = str(name).replace("_", " ").strip().lower()

        return text[:1].upper() + text[1:]

    def _process_dataframe(
        self,
        data_result: DataFrameResult,
        instruction: str,
    ) -> UIItem:
        df = pd.DataFrame( data_result.records, columns=data_result.columns ) # it musty arrive here as rows, records.
        nrows, ncols = df.shape

        print("Processing dataframe result with shape:", df.shape)
        #print( df )

        if nrows <= 2 and ncols <= 2:
        #if nrows <= 5 and ncols <= 5:
            
            return self._present_very_small_table(
                df,
                data_result,
                instruction,
            )

        processor = TableResponseProcessor()

        table_context = processor.extract_table_context(
            data_result
        )

        chart_plan = self._select_chart_plan(
            instruction,
            table_context,
        )

        print('****chart plan****')
        print(chart_plan)


        chart_output = self._run_chart_plan(
            chart_plan,
            df,
        )

        plot = chart_plan.get("plot") or {}
        tool_name = plot.get("tool")


        if tool_name == "plot_table":
            return self._make_table_item(
                self._format_label(data_result.table_name),
                chart_output,
                data_result.description,
            )

        return self._make_chart_item(
            self._format_label(data_result.table_name),
            chart_output,
            data_result.description,
        )


        return self._make_chart_item(
            self._format_label(data_result.table_name),
            chart_output,
            data_result.description,
        )

    def _strip_markdown_json(
        self,
        text: str,
    ) -> str:
        text = text.strip()

        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

        return text.strip()

    def _select_chart_plan(
        self,
        user_query: str,
        table_context: str,
    ) -> dict:
        messages = [
            SystemMessage(content=self.config.prompt),
            HumanMessage(
                content=(
                    f"USER QUERY\n"
                    f"{user_query}\n\n"
                    f"TABLE\n"
                    f"{table_context}"
                )
            ),
        ]

        response = self.llm.invoke(messages)

        text = self._strip_markdown_json(
            response.content
        )

        return json.loads(text)
    



def get_default_presenter(): 

    llm = get_llm()
    config = PresenterConfig()
    presenter = PresenterComponent4( llm=llm, config=config)

    return presenter 

def get_default_task_results():
    txt = '[{"agent":"direct_answer","instruction":"Explain the concept of VRR (Voidage Replacement Ratio) in reservoir engineering.","cheap_output":"The Voidage Replacement Ratio (VRR) is a key concept in reservoir engineering that measures the balance between the volume of fluids injected into a reservoir and the volume of fluids produced from it. It is defined as:\\n\\n\\\\[\\n\\\\text{VRR} = \\\\frac{\\\\text{Volume of injected fluids}}{\\\\text{Volume of produced fluids}}\\n\\\\]\\n\\n### Key Points:\\n1. **Purpose**: VRR is used to assess reservoir pressure maintenance and the effectiveness of secondary recovery methods, such as waterflooding or gas injection.\\n2. **Ideal Value**: A VRR of 1.0 indicates that the volume of injected fluids equals the volume of produced fluids, which helps maintain reservoir pressure.\\n3. **Implications**:\\n   - **VRR < 1**: Indicates insufficient injection, leading to pressure depletion and potentially reduced recovery.\\n   - **VRR > 1**: Indicates over-injection, which may cause operational issues like fracturing or inefficient sweep.\\n\\nMaintaining an appropriate VRR is critical for optimizing recovery, managing reservoir pressure, and ensuring long-term reservoir performance.","raw_results":["The Voidage Replacement Ratio (VRR) is a key concept in reservoir engineering that measures the balance between the volume of fluids injected into a reservoir and the volume of fluids produced from it. It is defined as:\\n\\n\\\\[\\n\\\\text{VRR} = \\\\frac{\\\\text{Volume of injected fluids}}{\\\\text{Volume of produced fluids}}\\n\\\\]\\n\\n### Key Points:\\n1. **Purpose**: VRR is used to assess reservoir pressure maintenance and the effectiveness of secondary recovery methods, such as waterflooding or gas injection.\\n2. **Ideal Value**: A VRR of 1.0 indicates that the volume of injected fluids equals the volume of produced fluids, which helps maintain reservoir pressure.\\n3. **Implications**:\\n   - **VRR < 1**: Indicates insufficient injection, leading to pressure depletion and potentially reduced recovery.\\n   - **VRR > 1**: Indicates over-injection, which may cause operational issues like fracturing or inefficient sweep.\\n\\nMaintaining an appropriate VRR is critical for optimizing recovery, managing reservoir pressure, and ensuring long-term reservoir performance."],"data_results":[{"text":"The Voidage Replacement Ratio (VRR) is a key concept in reservoir engineering that measures the balance between the volume of fluids injected into a reservoir and the volume of fluids produced from it. It is defined as:\\n\\n\\\\[\\n\\\\text{VRR} = \\\\frac{\\\\text{Volume of injected fluids}}{\\\\text{Volume of produced fluids}}\\n\\\\]\\n\\n### Key Points:\\n1. **Purpose**: VRR is used to assess reservoir pressure maintenance and the effectiveness of secondary recovery methods, such as waterflooding or gas injection.\\n2. **Ideal Value**: A VRR of 1.0 indicates that the volume of injected fluids equals the volume of produced fluids, which helps maintain reservoir pressure.\\n3. **Implications**:\\n   - **VRR < 1**: Indicates insufficient injection, leading to pressure depletion and potentially reduced recovery.\\n   - **VRR > 1**: Indicates over-injection, which may cause operational issues like fracturing or inefficient sweep.\\n\\nMaintaining an appropriate VRR is critical for optimizing recovery, managing reservoir pressure, and ensuring long-term reservoir performance.","role":"answer"}]},{"agent":"direct_answer","instruction":"Explain the concept of waterflooding in reservoir engineering.","cheap_output":"Waterflooding is a secondary recovery technique in reservoir engineering used to enhance oil production after the natural reservoir drive has declined. It involves injecting water into the reservoir through dedicated injection wells to maintain reservoir pressure and displace oil toward production wells. \\n\\nThe process works by increasing the sweep efficiency, both areally and vertically, pushing the oil trapped in the pore spaces toward producing wells. Waterflooding is particularly effective in reservoirs with good permeability and connectivity. Key considerations include the water injection rate, pattern design (e.g., five-spot, seven-spot), and the mobility ratio between water and oil to ensure efficient displacement.","raw_results":["Waterflooding is a secondary recovery technique in reservoir engineering used to enhance oil production after the natural reservoir drive has declined. It involves injecting water into the reservoir through dedicated injection wells to maintain reservoir pressure and displace oil toward production wells. \\n\\nThe process works by increasing the sweep efficiency, both areally and vertically, pushing the oil trapped in the pore spaces toward producing wells. Waterflooding is particularly effective in reservoirs with good permeability and connectivity. Key considerations include the water injection rate, pattern design (e.g., five-spot, seven-spot), and the mobility ratio between water and oil to ensure efficient displacement."],"data_results":[{"text":"Waterflooding is a secondary recovery technique in reservoir engineering used to enhance oil production after the natural reservoir drive has declined. It involves injecting water into the reservoir through dedicated injection wells to maintain reservoir pressure and displace oil toward production wells. \\n\\nThe process works by increasing the sweep efficiency, both areally and vertically, pushing the oil trapped in the pore spaces toward producing wells. Waterflooding is particularly effective in reservoirs with good permeability and connectivity. Key considerations include the water injection rate, pattern design (e.g., five-spot, seven-spot), and the mobility ratio between water and oil to ensure efficient displacement.","role":"answer"}]}]'
    
    restored_task_results = adapter.validate_json(txt)
    return restored_task_results
 

if __name__ == "__main__":

    task_results = get_default_task_results() 
    presenter = get_default_presenter() 

    task_results = get_default_task_results()

    state = ExecutorState(
        messages=[],
        user_query="",
        plan=None,
        task_index_to_execute=0,
        task_results=task_results,
        cheap_tool_outputs=[
            result.cheap_output
            for result in task_results
            if result.cheap_output
        ],
        current_task_results={},
        final_answer=None,
        clarification_request=None,
    )

    result = presenter.process_task_results( state )
    #result  = presenter.process_single_task_result( task_results[0] )

    print() 



