import os

from langgraph.graph import StateGraph, START, END

from nodes import discovery_node, selector_node, refractor_node, reviewer_node, editor
from state import AgentState




graph = StateGraph(AgentState)

def check_score_and_files(state: AgentState):
    score = state["repo_data"][state["current_file"]]["review"]["score"]
    files_left = state["files_to_process"]

    if score <= 5.0:
        return "refractor"
    
    if len(files_left) > 0:
        return "selector"
    
    return "move"
    



graph.add_node("Discovery", discovery_node)
graph.add_node("Selector", selector_node)
graph.add_node("Refractor", refractor_node)
graph.add_node("Reviewer", reviewer_node)
graph.add_node("Editor", editor)

graph.set_entry_point("Discovery")


# Edges

# START -> Discovery -> Selector -> END
graph.add_edge("Discovery", "Selector")
graph.add_edge("Selector", "Refractor")
graph.add_edge("Refractor", "Reviewer")

graph.add_conditional_edges(
    "Reviewer",
    check_score_and_files,
    {
        "refractor": "Refractor",
        "selector": "Selector",
        "move": "Editor"
    }
)

graph.add_edge("Editor", END)


app = graph.compile()


results = app.invoke({
    "repo_url": "https://github.com/theshrish46/synthetix_test_repo",
    "base_branch": "main",
})

print(results)