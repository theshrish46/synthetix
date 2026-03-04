from langchain_community.utilities.github import GitHubAPIWrapper
from langchain_community.agent_toolkits.github.toolkit import GitHubToolkit
from dotenv import load_dotenv
from github import Github
import os


load_dotenv()

github_client = Github(os.getenv("GITHUB_TOKEN"))


