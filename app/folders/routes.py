import os
import shutil
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from app.core.security import verify_access_token
from app.core.config import settings
from app.database.mongo import folders_collection
from app.folders.schemas import FolderCreateRequest, FolderResponse, FolderUpdateRequest

router = APIRouter(prefix="/api/v1/folders", tags=["Folders"])

# Helper to get safe paths
def get_user_storage_path(user_id: str):
    return os.path.join(settings.DATA_DIR, user_id)

def get_folder_path(user_id: str, folder_name: str):
    return os.path.join(get_user_storage_path(user_id), folder_name)


# --- 1. CREATE FOLDER ---
@router.post("", response_model=FolderResponse, status_code=201)
async def create_folder(
    request: FolderCreateRequest,
    payload: dict = Depends(verify_access_token)
):
    user_id = payload.get("user_id")
    
    # 1. Sanitize Folder Name (Prevent ".." or slashes)
    safe_name = "".join([c for c in request.name if c.isalnum() or c in (' ', '_', '-')]).strip()
    if not safe_name:
         raise HTTPException(status_code=400, detail="Invalid folder name")

    # 2. Check DB for duplicates
    existing_folder = await folders_collection.find_one({
        "user_id": user_id, 
        "name": safe_name
    })
    if existing_folder:
        raise HTTPException(status_code=409, detail="Folder with this name already exists")

    # 3. Create Physical Directory
    full_path = get_folder_path(user_id, safe_name)
    try:
        os.makedirs(full_path, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"File system error: {str(e)}")

    # 4. Insert into MongoDB
    new_folder = {
        "_id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": safe_name,
        "created_at": datetime.utcnow()
    }
    await folders_collection.insert_one(new_folder)

    # 5. Return Response
    return {
        "status": "success",
        "data": {
            "folder_id": new_folder["_id"],
            "name": new_folder["name"],
            "created_at": new_folder["created_at"]
        }
    }


# --- 2. RENAME FOLDER ---
@router.put("/{folder_id}", response_model=FolderResponse)
async def rename_folder(
    folder_id: str,
    request: FolderUpdateRequest,
    payload: dict = Depends(verify_access_token)
):
    user_id = payload.get("user_id")
    new_safe_name = "".join([c for c in request.name if c.isalnum() or c in (' ', '_', '-')]).strip()

    # 1. Find existing folder
    folder = await folders_collection.find_one({"_id": folder_id, "user_id": user_id})
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    old_name = folder["name"]
    
    # If name hasn't changed, just return
    if old_name == new_safe_name:
         return {"status": "success", "data": {"folder_id": folder_id, "name": old_name, "created_at": folder["created_at"]}}

    # 2. Check if new name is already taken
    duplicate_check = await folders_collection.find_one({"user_id": user_id, "name": new_safe_name})
    if duplicate_check:
        raise HTTPException(status_code=409, detail="Folder name already in use")

    # 3. Rename on File System
    old_path = get_folder_path(user_id, old_name)
    new_path = get_folder_path(user_id, new_safe_name)

    try:
        if os.path.exists(old_path):
            os.rename(old_path, new_path)
        else:
            # Logic fallback: If DB record exists but folder is missing, create it
            os.makedirs(new_path, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"File system error: {str(e)}")

    # 4. Update MongoDB
    await folders_collection.update_one(
        {"_id": folder_id}, 
        {"$set": {"name": new_safe_name}}
    )

    return {
        "status": "success",
        "data": {
            "folder_id": folder_id,
            "name": new_safe_name,
            "created_at": folder["created_at"]
        }
    }


# --- 3. DELETE FOLDER ---
@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: str,
    payload: dict = Depends(verify_access_token)
):
    user_id = payload.get("user_id")

    # 1. Find folder
    folder = await folders_collection.find_one({"_id": folder_id, "user_id": user_id})
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # 2. Delete Physical Directory
    folder_path = get_folder_path(user_id, folder["name"])
    
    try:
        if os.path.exists(folder_path):
            # shutil.rmtree removes the folder and all contents
            shutil.rmtree(folder_path)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"File system error: {str(e)}")

    # 3. Delete from MongoDB
    await folders_collection.delete_one({"_id": folder_id})

    return {
        "status": "success", 
        "message": "Folder deleted successfully"
    }