
import sys
sys.path.append("./")  # Add the parent directory to the Python path
sys.path.append("../")  # Add the parent directory to the Python path
sys.path.append("../../")  # Add the parent directory to the Python path

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, AIMessage


from agentic_system.common.base_plan import ExecutorState
from agentic_system.common.base_task import ExecutionTask, TaskExecutionContext, TaskResult, TextResult
from agentic_system.components.direct_answer.direct_answer import DirectAnswerComponent


class OuterExecutor:
    
    def __init__(
        self,
        planner: Any,
        direct_answer: DirectAnswerComponent,
        results_interpreter: Any,
        thread_id: str,
        checkpointer=None,
    ):
        self.planner = planner
        self.direct_answer = direct_answer
        self.results_interpreter = results_interpreter
        self.thread_id = thread_id

        self.components = {
            self.direct_answer.agent_name: self.direct_answer,
            self.results_interpreter.agent_name: self.results_interpreter,
        }

        self.checkpointer = (
            checkpointer
            if checkpointer is not None
            else InMemorySaver()
        )

        self.graph = self._build_graph()

    def _plan(self, state: ExecutorState) -> dict:
        plan = self.planner.run(
            user_query=state["user_query"],
            previous_state=state,
        )

        if not plan.tasks:
            raise RuntimeError("The planner returned no tasks.")

        unsupported = {
            task.agent
            for task in plan.tasks
            if task.agent not in self.components
        }

        if unsupported:
            raise ValueError(
                "Components not registered: "
                + ", ".join(sorted(unsupported))
            )

        return {"plan": plan}

    def _start_turn(self, state: ExecutorState) -> dict:
        """Reset temporary execution fields; preserve historical results."""
        return {
            "plan": None,
            "task_index_to_execute": 0,
            "current_task_results": {},
            "facts_context": "",
            "cheap_tool_outputs": [],
            "task_results": list(state.get("task_results", [])),
            "final_answer": None,
            "clarification_request": None,
        }

    def _resolve_dependencies(
        self,
        task: ExecutionTask,
        state: ExecutorState,
    ) -> list[TaskResult]:
        """Resolve same-plan dependencies to completed task results."""
        completed = state.get("current_task_results", {})
        dependencies = []
        seen = set()

        for task_id in task.depends_on or []:
            if task_id in seen:
                continue

            if task_id not in completed:
                raise RuntimeError(
                    f"Task '{task.task_id}' requires '{task_id}', "
                    "but that task has not produced a result."
                )

            dependencies.append(completed[task_id])
            seen.add(task_id)

        return dependencies

    def _execute_task(self, state: ExecutorState) -> dict:
        task = state["plan"].tasks[state["task_index_to_execute"]]
        component = self.components[task.agent]

        dependency_results = self._resolve_dependencies(task, state)

        context = TaskExecutionContext(
            #task=task,
            dependency_results=dependency_results,
        )

        result = component.run(
            query=task.instruction,
            messages=state.get("messages", []),
            context=context,
        )

        if not isinstance(result, TaskResult):
            raise TypeError(
                f"Component '{task.agent}' must return a TaskResult."
            )

        current_results = dict(state.get("current_task_results", {}))
        current_results[task.task_id] = result

        cheap_outputs = list(state.get("cheap_tool_outputs", []))

        if result.cheap_output:
            cheap_outputs.append(result.cheap_output)

        return {
            "current_task_results": current_results,
            "task_results": [
                *state.get("task_results", []),
                result,
            ],
            "cheap_tool_outputs": cheap_outputs,
            "task_index_to_execute": (
                state["task_index_to_execute"] + 1
            ),
        }
    
    def _build_graph(self):
        builder = StateGraph(ExecutorState)

        builder.add_node("start_turn", self._start_turn)
        builder.add_node("planner", self._plan)
        builder.add_node("presenter", self._present)

        destinations = {"presenter": "presenter"}

        for agent_name in self.components:
            builder.add_node(agent_name, self._execute_task)
            destinations[agent_name] = agent_name

        builder.add_edge(START, "start_turn")
        builder.add_edge("start_turn", "planner")

        builder.add_conditional_edges(
            "planner",
            self._route,
            destinations,
        )

        for agent_name in self.components:
            builder.add_conditional_edges(
                agent_name,
                self._route,
                destinations,
            )

        builder.add_edge("presenter", END)

        return builder.compile(checkpointer=self.checkpointer)
    

    def _route(self, state: ExecutorState) -> str:
        """Dispatch the current task without another LLM call."""
        plan = state["plan"]
        index = state["task_index_to_execute"]

        if index >= len(plan.tasks):
            return "presenter"

        return plan.tasks[index].agent

 
    def _present(self, state: ExecutorState) -> dict:
        """Combine this turn's answers without another LLM call."""
        task_count = len(state["plan"].tasks)

        # Tasks execute sequentially and each appends one TaskResult.
        current_results = state["task_results"][-task_count:]

        answers = [
            item.text
            for result in current_results
            for item in result.data_results
            if isinstance(item, TextResult) and item.role == "answer"
        ]

        if not answers:
            raise RuntimeError("No answer text was produced.")

        final_answer = "\n\n".join(answers)

        return {
            "final_answer": final_answer,
            # add_messages appends this message to persisted history.
            "messages": [AIMessage(content=final_answer)],
        }

  
    def run(
        self,
        user_query: str,
        thread_id: str | None = None ,
    ) -> ExecutorState:

        if thread_id is None:
            thread_id = self.thread_id
        
        return self.graph.invoke(
            {
                "user_query": user_query,
                "messages": [HumanMessage(content=user_query)],
            },
            config={
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 100,
            },
        )
