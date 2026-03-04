import os

from langgraph.graph import StateGraph, START, END

from nodes import discovery, editor, prmanager, reviewer, strategy
from state import AgentState




graph = StateGraph(AgentState)

graph.add_node("Discovery", discovery)
graph.set_entry_point("Discovery")
graph.add_edge("Discovery", END)

app = graph.compile()


results = app.invoke({
    "repo_url": "https://github.com/theshrish46/synthetix_test_repo",
    "base_branch": "main",
})

print(results)