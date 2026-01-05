from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

# Request Body for Creating
class FolderCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

# Request Body for Renaming
class FolderUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

# Schema for the folder data inside the response
class FolderData(BaseModel):
    folder_id: str
    name: str
    created_at: datetime

# Standard Response Wrapper
class FolderResponse(BaseModel):
    status: str
    data: FolderData