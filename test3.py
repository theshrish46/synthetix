from typing import TypedDict
from langgraph.graph import START, END, StateGraph
from dotenv import load_dotenv
from IPython.display import Image
from langchain_groq import ChatGroq
from langchain.agents import create_agent

import os

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.2
)




class AgentState(TypedDict):
    repo_url: str
    repo_name: str
    branch_name: str
    repo_data: dict


def fetch_repo_node(state: AgentState) -> AgentState:
    repo_url = state["repo_url"].rstrip("/")
    parts = repo_url.split("/")
    owner = parts[-2]
    repo = parts[-1]

    repo_obj = github_client.get_repo(f"{owner}/{repo}")
    default_branch = repo_obj.default_branch

    tree = repo_obj.get_git_tree(default_branch, recursive=True)

    files = []
    for item in tree.tree:
        files.append({
            "path": item.path,
            "type": item.type,
        })

    return {
        **state,
        "repo_name": repo,
        "branch_name": default_branch,
        "repo_data": {
            "owner": owner,
            "repo": repo,
            "default_branch": default_branch,
            "files": files,
        },
    }



builder = StateGraph(AgentState)

builder.add_node("fetch_repo", fetch_repo_node)

builder.set_entry_point("fetch_repo")
builder.add_edge("fetch_repo", END)

graph = builder.compile()

result = graph.invoke({
    "repo_url": "https://github.com/theshrish46/synthetix_test_repo",
    "repo_name": "",
    "branch_name": "",
    "repo_data": {}
})

print(result["repo_data"])