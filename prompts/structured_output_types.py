from pydantic import BaseModel, Field
from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate

class RefactorResults(BaseModel):
    new_code: str = Field(description="The complete refactored code.")
    commit_message: str = Field(description="A brief, professional git commit message.")
    explanation: str = Field(description="A 1-sentence Internal note on why these changes were made.")


class ReviewResults(BaseModel):
    score: float = Field(description="A score from 0.0 to 1.0 based on code quality.")
    feedback: str = Field(description="Specific feedback if the score is low < 0.5")
