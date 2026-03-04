import os

from langgraph.graph import StateGraph, START, END

from nodes import discovery, selector, refractor
from state import AgentState




graph = StateGraph(AgentState)

graph.add_node("Discovery", discovery)
graph.add_node("Selector", selector)
graph.add_node("Refractor", refractor)

graph.set_entry_point("Discovery")


# Edges

# START -> Discovery -> Selector -> END
graph.add_edge("Discovery", "Selector")
graph.add_edge("Selector", "Refractor")
graph.add_edge("Refractor", END)


app = graph.compile()


results = app.invoke({
    "repo_url": "https://github.com/theshrish46/synthetix_test_repo",
    "base_branch": "main",
})

print(results)