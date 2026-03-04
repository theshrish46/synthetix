from state import AgentState

import os

from tools.github_tool import github_client


def discovery(state: AgentState) -> AgentState:
    print(f"This is discovery node")
    print(f"Starting to go through the github repo")
    
    # So I already have the info about the Github repo owner and his repo inside the state dict which I can use to get the entire thing to the state dict using github client

    # Get the main repo
    repo_url = state['repo_url'].rstrip("/")
    parts = repo_url.split("/")
    owner = parts[-2]
    repo = parts[-1]


    # Get the default and other branches
    repo_obj = github_client.get_repo(f"{owner}/{repo}")
    default_branch = repo_obj.default_branch
    all_branches = repo_obj.get_branches()
    branche_names = [branch.name for branch in all_branches]


    # Get the tree structure
    tree = repo_obj.get_git_tree(default_branch, recursive=True)


    files = []
    IGNORE_EXTENSIONS = {".pyc", ".lock", ".log", ".txt"}

    for item in tree.tree:
        # Get the file extension
        _, ext = os.path.splitext(item.path)

        # Skip if the extension is in the ignore list
        if ext.lower() in IGNORE_EXTENSIONS:
            continue

        files.append(item.path)

    return {
        **state,
        "repo_id": f"{owner}/{repo}",
        "base_branch": default_branch,
        "branches": branche_names,

        "file_tree": [item.path for item in tree.tree],

        "files_to_process": files,
        
    }


def strategy(state: AgentState) -> AgentState:
    print(f"This is strategy node")
    return state

def editor(state: AgentState) -> AgentState:
    print(f"This is editor node")
    return state

def reviewer(state: AgentState) -> AgentState:
    print(f"This is reviewer node")
    return state

def prmanager(state: AgentState) -> AgentState:
    print(f"This is manager node")
    return state