import json
import sys
from pathlib import Path

import pandas as pd
sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path


from agentic_system.common.base_task import DataFrameResult, TaskResult, TextResult


def print_task_result(task_result: TaskResult) -> None:
    """Print task metadata, text answers, and table previews."""

    separator = "=" * 90

    print(f"\n{separator}")
    print(f"Agent: {task_result.agent}")
    print(f"Task ID: {task_result.task_id or 'Unassigned'}")
    print(f"Instruction: {task_result.instruction}")

    for index, artifact in enumerate(task_result.data_results, start=1):
        print(f"\n{'-' * 90}")

        if isinstance(artifact, TextResult):
            print(f"{index}. {artifact.title or 'Answer'}\n")
            print(artifact.text)

        elif isinstance(artifact, DataFrameResult):
            print(f"{index}. Table: {artifact.table_name}")

            if artifact.description:
                print(artifact.description)

            dataframe = pd.DataFrame.from_records(
                artifact.records,
                columns=artifact.columns,
            )

            print(f"\nShape: {dataframe.shape[0]} rows × "
                  f"{dataframe.shape[1]} columns\n")

            print(
                dataframe.to_string(
                    index=False,
                    max_rows=20,
                    max_cols=10,
                    max_colwidth=50,
                    line_width=120,
                )
            )

        else:
            print(f"{index}. Unsupported artifact: {type(artifact).__name__}")

    print(f"\n{separator}\n")


def export_presenter_response_html(presenter_response, file_name: str) -> str:
    """
    Export PresenterResponse-like output to an HTML file.

    Args:
        presenter_response: object expected to have an `items` attribute.
        file_name: destination HTML file path.

    Returns:
        Absolute path to the exported HTML file.
    """
    try:
        output_path = Path(file_name).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        items = getattr(presenter_response, "items", None)
        if items is None:
            raise ValueError("presenter_response does not contain an 'items' attribute.")

        sections: list[str] = []

        for index, item in enumerate(items, start=1):
            item_type = getattr(item, "type", "unknown")
            item_title = getattr(item, "title", None) or f"Item {index}"
            item_data = getattr(item, "data", {}) or {}
            safe_title = str(item_title)

            if item_type in {"text", "markdown", "question", "error"}:
                text_value = ""
                if isinstance(item_data, dict):
                    text_value = (
                        item_data.get("text")
                        or item_data.get("question")
                        or item_data.get("message")
                        or json.dumps(item_data, indent=2)
                    )
                else:
                    text_value = str(item_data)

                sections.append(
                    "<section>"
                    f"<h3>{safe_title}</h3>"
                    f"<pre>{str(text_value)}</pre>"
                    "</section>"
                )
                continue

            if item_type in {"chart", "table"}:
                chart_payload = item_data.get("plotly") if isinstance(item_data, dict) else None
                if not chart_payload:
                    sections.append(
                        "<section>"
                        f"<h3>{safe_title}</h3>"
                        "<pre>Missing plotly payload.</pre>"
                        "</section>"
                    )
                    continue

                chart_json = json.dumps(chart_payload)
                div_id = f"plot_{index}"
                sections.append(
                    "<section>"
                    f"<h3>{safe_title}</h3>"
                    f"<div id=\"{div_id}\" style=\"width:100%;height:500px;\"></div>"
                    "<script>"
                    f"(function(){{var fig={chart_json};"
                    f"if(window.Plotly){{Plotly.newPlot('{div_id}', fig.data||[], fig.layout||{{}}, fig.config||{{responsive:true}});}}"
                    "})();"
                    "</script>"
                    "</section>"
                )
                continue

            sections.append(
                "<section>"
                f"<h3>{safe_title}</h3>"
                f"<pre>Unsupported item type: {item_type}</pre>"
                "</section>"
            )

        html = (
            "<!doctype html>"
            "<html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Presenter Output</title>"
            "<script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script>"
            "<style>body{font-family:Arial,sans-serif;margin:16px;}"
            "section{margin-bottom:24px;padding:12px;border:1px solid #ddd;border-radius:6px;}"
            "pre{white-space:pre-wrap;word-break:break-word;}</style>"
            "</head><body>"
            "<h1>Presented Output</h1>"
            + "".join(sections)
            + "</body></html>"
        )

        output_path.write_text(html, encoding="utf-8")
        print(f"Exported presenter output to HTML: {output_path}")
        return str(output_path)

    except Exception as exc:
        print(f"Error exporting presenter output to HTML: {exc}")
        return ""
    
