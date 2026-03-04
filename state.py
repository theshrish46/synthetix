import operator
from typing import TypedDict, List, Optional, Annotated, Dict



class AgentState(TypedDict):
    """
        This is a tyed dict for managing the Agent's State throughout the workflow
    """
    # Repository Metadata
    repo_url: str
    repo_id: str
    base_branch: str
    new_branch: str
    branches: List[str]


    # The Tree Structure
    file_tree: List[str]


    # Iteraction Control
    files_to_process: List[str]
    current_file: Optional[str]


    # The Database
    repo_data: Annotated[Dict[str, Dict], operator.ior]

    # Final Output
    pr_url: Optional[str]
    error_log: List[str]