import sys, pandas as pd 
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
    