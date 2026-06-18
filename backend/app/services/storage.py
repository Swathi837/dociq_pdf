import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
LOCAL_UPLOAD_DIR = os.getenv("LOCAL_UPLOAD_DIR", "/app/uploads")


# ─────────────────────────────────────────────
# Ensure local upload directory exists
# ─────────────────────────────────────────────
def ensure_upload_dir():
    Path(LOCAL_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# Upload file — local or R2
# ─────────────────────────────────────────────
async def upload_file(file: UploadFile, workspace_id: str) -> dict:
    """
    Upload a file and return storage metadata.
    Returns: { s3_key, file_size_bytes }
    """
    file_ext = Path(file.filename).suffix.lower()
    unique_name = f"{uuid.uuid4()}{file_ext}"
    s3_key = f"{workspace_id}/{unique_name}"

    if STORAGE_BACKEND == "local":
        return await _upload_local(file, s3_key)
    else:
        return await _upload_r2(file, s3_key)


async def _upload_local(file: UploadFile, s3_key: str) -> dict:
    ensure_upload_dir()
    dest_path = Path(LOCAL_UPLOAD_DIR) / s3_key
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    return {
        "s3_key": s3_key,
        "file_size_bytes": len(content),
    }


async def _upload_r2(file: UploadFile, s3_key: str) -> dict:
    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("R2_SECRET_KEY"),
    )
    content = await file.read()
    s3.put_object(
        Bucket=os.getenv("R2_BUCKET", "dociq-documents"),
        Key=s3_key,
        Body=content,
        ContentType="application/pdf",
    )
    return {
        "s3_key": s3_key,
        "file_size_bytes": len(content),
    }


# ─────────────────────────────────────────────
# Get file path (for local serving)
# ─────────────────────────────────────────────
def get_local_path(s3_key: str) -> Path:
    return Path(LOCAL_UPLOAD_DIR) / s3_key


# ─────────────────────────────────────────────
# Delete file
# ─────────────────────────────────────────────
async def delete_file(s3_key: str):
    if STORAGE_BACKEND == "local":
        path = get_local_path(s3_key)
        if path.exists():
            path.unlink()
    else:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("R2_SECRET_KEY"),
        )
        s3.delete_object(Bucket=os.getenv("R2_BUCKET"), Key=s3_key)