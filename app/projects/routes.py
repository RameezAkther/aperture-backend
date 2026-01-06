import uuid
import re
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, Body
from app.core.security import verify_access_token
from app.database.mongo import projects_collection, folders_collection
from app.projects.schemas import (
    ProjectCreateRequest, 
    ProjectResponse, 
    ProjectUpdateRequest, 
    AddFolderToProjectRequest
)

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])

# --- HELPER: Generate Unique Name ---
async def generate_project_name(user_id: str) -> str:
    """
    Generates names like "New Project", "New Project 1", "New Project 2"...
    based on what currently exists in the DB for this user.
    """
    base_name = "New Project"
    
    # Regex to find any project starting with "New Project"
    # This acts as a filter to minimize data fetched
    pattern = f"^{base_name}.*"
    cursor = projects_collection.find(
        {"user_id": user_id, "name": {"$regex": pattern}},
        {"name": 1}
    )
    existing_projects = await cursor.to_list(length=None)
    existing_names = {p["name"] for p in existing_projects}

    if base_name not in existing_names:
        return base_name

    counter = 1
    while True:
        candidate = f"{base_name} {counter}"
        if candidate not in existing_names:
            return candidate
        counter += 1


# --- 1. CREATE PROJECT ---
@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: ProjectCreateRequest = Body(default=None), # Body is optional
    payload: dict = Depends(verify_access_token)
):
    user_id = payload.get("user_id")
    
    # 1. Generate unique default name
    project_name = await generate_project_name(user_id)

    # 2. Handle initial folder if provided
    folder_ids = []
    if request and request.initial_folder_id:
        # verify folder exists and belongs to user
        folder = await folders_collection.find_one({
            "_id": request.initial_folder_id, 
            "user_id": user_id
        })
        if folder:
            folder_ids.append(request.initial_folder_id)

    # 3. Create Project Document
    new_project = {
        "_id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": project_name,
        "folder_ids": folder_ids, # List of grouped folders
        "is_initialized": False,
        "created_at": datetime.utcnow()
    }

    await projects_collection.insert_one(new_project)

    return new_project


# --- 2. UPDATE PROJECT (Rename) ---
@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    payload: dict = Depends(verify_access_token)
):
    user_id = payload.get("user_id")

    # Construct update fields
    update_data = {}
    if request.name is not None:
        # Check for duplicate name if renaming
        exists = await projects_collection.find_one({
            "user_id": user_id, 
            "name": request.name, 
            "_id": {"$ne": project_id}
        })
        if exists:
            raise HTTPException(status_code=409, detail="Project name already in use")
        update_data["name"] = request.name
        
    if request.is_initialized is not None:
        update_data["is_initialized"] = request.is_initialized

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    # Perform Update
    result = await projects_collection.find_one_and_update(
        {"_id": project_id, "user_id": user_id},
        {"$set": update_data},
        return_document=True
    )

    if not result:
        raise HTTPException(status_code=404, detail="Project not found")

    return result


# --- 3. ADD FOLDER TO PROJECT (Group Folder) ---
@router.post("/{project_id}/folders", response_model=ProjectResponse)
async def add_folder_to_project(
    project_id: str,
    request: AddFolderToProjectRequest,
    payload: dict = Depends(verify_access_token)
):
    user_id = payload.get("user_id")

    # 1. Verify Project Exists
    project = await projects_collection.find_one({"_id": project_id, "user_id": user_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Verify Folder Exists (and belongs to user)
    folder = await folders_collection.find_one({"_id": request.folder_id, "user_id": user_id})
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found or access denied")

    # 3. Add to set (prevents duplicate folder_ids in the list)
    updated_project = await projects_collection.find_one_and_update(
        {"_id": project_id},
        {"$addToSet": {"folder_ids": request.folder_id}},
        return_document=True
    )

    return updated_project


# --- 4. DELETE PROJECT ---
@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    payload: dict = Depends(verify_access_token)
):
    user_id = payload.get("user_id")

    # Check existence
    project = await projects_collection.find_one({"_id": project_id, "user_id": user_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete (Note: This deletes the grouping, but NOT the actual folders themselves, 
    # which is standard behavior for "grouping" containers)
    await projects_collection.delete_one({"_id": project_id})

    return None