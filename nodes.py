from state import AgentState
from prompts.structured_output_types import RefactorResults, ReviewResults

import os
import requests
import time

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from tools.github_tool import github_client

load_dotenv()

llm = ChatGroq(
    # model="mixtral-8x7b-32768",
    model="llama-3.3-70b-versatile",
    temperature=0.2,
)


def discovery_node(state: AgentState) -> AgentState:
    # So I already have the info about the Github repo owner and his repo inside the state dict which I can use to get the entire thing to the state dict using github client

    # Get the main repo
    repo_url = state["repo_url"].rstrip("/")
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
        "repo_data": {on_focus_file: {"original_code": raw_code, "status": "pending"}},
    }


def refractor_node(state: AgentState) -> AgentState:
    strutured_llm = llm.with_structured_output(RefactorResults)

    with open("prompts/refractor/refractor_system.txt", "r") as f:
        system_content = f.read()

    with open("prompts/refractor/refractor_human.txt", "r") as f:
        human_content = f.read()

    extension = state["current_file"].split(".")[-1]
    lang_map = {"py": "Python", "cpp": "C++", "c": "C", "js": "JavaScript"}
    current_lang = lang_map.get(extension, "Unknown")

    prompt_template = ChatPromptTemplate.from_messages(
        [("system", system_content), ("human", human_content)]
    )

    final_prompt = prompt_template.format_messages(
        filename=state["current_file"],
        language=current_lang,
        original_code=state["repo_data"][state["current_file"]]["original_code"],
    )

    result = strutured_llm.invoke(final_prompt)

    return {
        "repo_data": {
            state["current_file"]: {
                "original_code": state["repo_data"][state["current_file"]][
                    "original_code"
                ],
                "refactored_code": result.new_code,
                "status": "refactored",
                "commit_message": result.commit_message,
                "explanation": result.explanation,
            }
        },
    }


def reviewer_node(state: AgentState) -> AgentState:

    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.2)
    structured_llm = llm.with_structured_output(ReviewResults)

    with open("prompts/reviewer/reviewer_system.txt", "r") as f:
        system_content = f.read()

    with open("prompts/reviewer/reviewer_human.txt", "r") as f:
        human_content = f.read()

    prompt = ChatPromptTemplate.from_messages(
        [("system", system_content), ("human", human_content)]
    )

    final_prompt = prompt.format_messages(
        original_code=state["repo_data"][state["current_file"]]["original_code"],
        refactored_code=state["repo_data"][state["current_file"]]["refactored_code"],
    )

    result = structured_llm.invoke(final_prompt)
    return {
        **state,
        "repo_data": {
            state["current_file"]: {
                "original_code": state["repo_data"][state["current_file"]][
                    "original_code"
                ],
                "refactored_code": state["repo_data"][state["current_file"]][
                    "refactored_code"
                ],
                "status": state["repo_data"][state["current_file"]]["status"],
                "commit_message": state["repo_data"][state["current_file"]][
                    "commit_message"
                ],
                "explanation": state["repo_data"][state["current_file"]]["explanation"],
                "review": {"score": result.score, "feedback": result.feedback},
            }
        },
    }


def pr_manager(state: AgentState) -> AgentState:

    # 1. Get the github repo using the repo id in state for further functionalities
    repo = github_client.get_repo(state["repo_id"])

    # 2. Create a unique branch, right now using time for simplicity but should improve in the future
    new_branch = f"ai-refactor-{int(time.time())}"
    base_sha = repo.get_branch(state["base_branch"]).commit.sha
    repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=base_sha)

    # 3. Creating commit and raising pr
    # 3.1 Creating the payload for request

    for path, data in state["repo_data"].items():
        if "refactored_code" in data:
            file_content = repo.get_contents(path=path, ref=state["base_branch"])
            repo.update_file(
                path=path,
                message=data["commit_message"],
                content=data["refactored_code"],
                sha=file_content.sha,
                branch=new_branch,
            )

    # 4. Create a pull request and raise it
    pr = repo.create_pull(
        title="AI Refactor: Improvements & Bug Fixes",
        body=f"Refactored files :\n "
        + "\n".join(
            [
                f"- {k} : {v["explanation"]}"
                for k, v in state["repo_data"].items()
                if "explanation" in v
            ]
        ),
        head=new_branch,
        base=state["base_branch"],
    )

    return {"pr_url": pr.html_url}
