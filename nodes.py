from state import AgentState
from prompts.refacotr_prompt import RefactorResults

import os
import requests

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from tools.github_tool import github_client

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.2
)


def discovery(state: AgentState) -> AgentState:
    print(f"This is discovery node")
    
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


def selector(state: AgentState) -> AgentState:
    """
    So now i need to focus on things for this node
    
    - First select the queue file_to_process and take out the top most file to rocess

    - Update the queue containing everything except the first element

    - Fetch the raw code form the github using client

    - Return the path with a new updated 
        - files_to_process
        - current_file
        - repo_data having {
                original_code from github client
            }
    """
    print(f"This is inside selector node")
    
    on_focus_file = state["files_to_process"][0]
    remaining_files = state["files_to_process"][1:]
    repo = github_client.get_repo(state["repo_id"])


    try:
        content_file = repo.get_contents(on_focus_file)

        if content_file.type == "file":
            raw_code = content_file.decoded_content.decode("utf-8")
        else:
            print(f"{on_focus_file} is a directory not a file")
    except Exception as e:
        print(f"Error accessing file {e}")

    return {
        **state,
        "current_file": on_focus_file,
        "files_to_process": remaining_files,
        "repo_data": {
            on_focus_file: {
                "original_code": raw_code,
                "status": "pending"
            }
        }
    }

def refractor(state: AgentState) -> AgentState:
    strutured_llm = llm.with_structured_output(RefactorResults)

    print(f"This is Refractor node")
    with open("prompts/refractor_system.txt", "r") as f:
        system_content = f.read()
    
    with open("prompts/refractor_human.txt", "r") as f:
        human_content = f.read()
    
    extension = state["current_file"].split(".")[-1]
    lang_map = {"py": "Python", "cpp": "C++", "c": "C", "js": "JavaScript"}
    current_lang = lang_map.get(extension, "Unknown")

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_content),
        ("human", human_content)
    ])

    final_prompt = prompt_template.format_messages(
        filename=state["current_file"],
        language=current_lang,
        original_code=state["repo_data"][state["current_file"]]["original_code"]
    )

    result = strutured_llm.invoke(final_prompt)

    return {
        **state,
        "repo_data": {
            state["current_file"]: {
                "original_code": state["repo_data"][state["current_file"]]["original_code"],
                "status": "refactored",
                "refactored_code": result.new_code,
                "commit_message": result.commit_message,
                "explanation": result.explanation
            }
        }
    }
    #return state

def editor(state: AgentState) -> AgentState:
    print(f"This is editor node")
    return state

def reviewer(state: AgentState) -> AgentState:
    print(f"This is reviewer node")
    return state

def prmanager(state: AgentState) -> AgentState:
    print(f"This is manager node")
    return state