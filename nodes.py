from state import AgentState
from prompts.structured_output_types import RefactorResults, ReviewResults

import os
import requests

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from tools.github_tool import github_client

load_dotenv()

llm = ChatGroq(
    #model="llama-3.3-70b-versatile",
    model="mixtral-8x7b-32768",
    temperature=0.2
)


def discovery_node(state: AgentState) -> AgentState:
    print(f"This is discovery node state is {state}")
    
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

    ALLOWED_EXTENSIONS = {".py", ".c", ".cpp", ".js", ".java", ".ts"}

    files_to_process = []
    full_tree_paths = []

    for item in tree.tree:
        full_tree_paths.append(item.path)


        if item.type == "blob":
            _, ext = os.path.splitext(item.path)

            if ext.lower() in ALLOWED_EXTENSIONS:
                files_to_process.append(item.path)


    return {
        **state,
        "repo_id": f"{owner}/{repo}",
        "base_branch": default_branch,
        "branches": branche_names,
        "file_tree": [item.path for item in tree.tree],
        "files_to_process": files_to_process,
    }


def selector_node(state: AgentState) -> AgentState:
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
    print(f"This is inside selector node state is {state}")
    
    on_focus_file = state["files_to_process"][0]
    remaining_files = state["files_to_process"][1:]
    repo = github_client.get_repo(state["repo_id"])

    raw_code = ""
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

def refractor_node(state: AgentState) -> AgentState:
    strutured_llm = llm.with_structured_output(RefactorResults)

    print(f"This is Refractor node state is {state}")
    with open("prompts/refractor/refractor_system.txt", "r") as f:
        system_content = f.read()
    
    with open("prompts/refractor/refractor_human.txt", "r") as f:
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
                "refactored_code": result.new_code,
                "status": "refactored",
                "commit_message": result.commit_message,
                "explanation": result.explanation
            }
        }
    }

def reviewer_node(state: AgentState) -> AgentState:
    print(f"Inside the reviewer node state is {state}")

    structured_llm = llm.with_structured_output(ReviewResults)

    with open("prompts/reviewer/reviewer_system.txt", "r") as f:
        system_content = f.read()

    with open("prompts/reviewer/reviewer_human.txt", "r") as f:
        human_content = f.read()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_content),
        ("human", human_content)
    ])


    final_prompt = prompt.format_messages(
        original_code=state["repo_data"][state["current_file"]]["original_code"],
        refactored_code=state["repo_data"][state["current_file"]]["refactored_code"]
    )

    result = structured_llm.invoke(final_prompt)
    return {
        **state,
        "repo_data": {
            state["current_file"]: {
                "original_code": state["repo_data"][state["current_file"]]["original_code"],
                "refactored_code": state["repo_data"][state["current_file"]]["refactored_code"],
                "status": state["repo_data"][state["current_file"]]["status"],
                "commit_message": state["repo_data"][state["current_file"]]["commit_message"],
                "explanation": state["repo_data"][state["current_file"]]["explanation"],
                "review": {
                    "score": result.score,
                    "feedback": result.feedback
                } 
            }
        }
    }


def editor(state: AgentState) -> AgentState:
    print(f"This is editor node state is {state}")
    return state

def reviewer(state: AgentState) -> AgentState:
    print(f"This is reviewer node")
    return state

def prmanager(state: AgentState) -> AgentState:
    print(f"This is manager node")
    return state