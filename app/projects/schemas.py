from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ProjectCreateRequest(BaseModel):
    # User might provide an initial folder to group, or it can be empty
    initial_folder_id: Optional[str] = None

class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    is_initialized: Optional[bool] = None

class AddFolderToProjectRequest(BaseModel):
    folder_id: str

class ProjectResponse(BaseModel):
    project_id: str = Field(..., alias="_id")
    name: str
    folder_ids: List[str] = []
    created_at: datetime
    is_initialized: bool = False

    class Config:
        populate_by_name = True