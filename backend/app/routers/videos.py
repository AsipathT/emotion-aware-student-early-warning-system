"""
backend/app/routers/videos.py

Feature: Lecture Video Management, 10MB Size Limit, Video Streaming, and Student Watch Telemetry.
Provides:
  - POST /api/v1/courses/{course_id}/videos: Upload video (Lecturer/Admin only, <= 10MB)
  - GET  /api/v1/courses/{course_id}/videos: List videos with watch analytics
  - DELETE /api/v1/courses/{course_id}/videos/{video_id}: Delete video & records (Lecturer/Admin only)
  - GET  /api/v1/videos/{video_id}/stream: Stream video supporting HTTP 206 Partial Content
  - POST /api/v1/videos/{video_id}/watch: Record student watch duration and telemetry
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Header,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.privacy import pseudonymize
from app.core.schema_mapping import (
    CANONICAL_COURSES,
    CANONICAL_USERS,
    check_course_ownership,
    check_student_enrolled,
)
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.db import collections as col
from app.models.user import User
from app.services.event_week import resolve_event_week

router = APIRouter(tags=["videos"])

# Maximum allowed video file size: 10 MB (in bytes)
MAX_VIDEO_SIZE = 10 * 1024 * 1024  # 10,485,760 bytes

# Directory to store uploaded video files
UPLOAD_BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "videos"
)
os.makedirs(UPLOAD_BASE_DIR, exist_ok=True)

COL_COURSE_VIDEOS = "course_videos"
COL_VIDEO_WATCH_RECORDS = "video_watch_records"

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_stream_user(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> User:
    """
    Authenticates user for video streaming via either Authorization header or ?token= query parameter.
    """
    raw_token = None
    if credentials:
        raw_token = credentials.credentials
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required to stream video.",
        )

    try:
        payload = decode_token(raw_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token subject.",
        )

    user_doc = await db[CANONICAL_USERS].find_one({"_id": user_id})
    if not user_doc:
        user_doc = await db[CANONICAL_USERS].find_one({"id": user_id})

    if not user_doc or not user_doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    return User(**user_doc)


class WatchHeartbeatPayload(BaseModel):
    watched_seconds: float = Field(..., ge=0, le=300)
    current_time: float = Field(default=0.0, ge=0)
    completed: bool = False


# ── 1. Upload Video (Lecturer / Admin) ──────────────────────────────────────────
@router.post("/api/v1/courses/{course_id}/videos", status_code=status.HTTP_201_CREATED)
async def upload_course_video(
    course_id: str,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Uploads a course lecture video.
    Strictly verifies:
      - Course lecturer or admin role.
      - Maximum file size <= 10MB.
    """
    # Verify course ownership
    await check_course_ownership(db, course_id, current_user)

    if not title or not title.trim() if hasattr(title, "trim") else not title.strip():
        raise HTTPException(status_code=400, detail="Video title is required.")

    # Validate filename extension / mime
    filename = file.filename or "video.mp4"
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = {".mp4", ".webm", ".ogg", ".mov", ".m4v", ".mkv"}
    if ext and ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format '{ext}'. Allowed formats: MP4, WebM, OGG, MOV.",
        )

    # Prepare course storage directory
    course_upload_dir = os.path.join(UPLOAD_BASE_DIR, str(course_id))
    os.makedirs(course_upload_dir, exist_ok=True)

    video_id = str(uuid.uuid4())
    safe_filename = f"{video_id}_{filename.replace(' ', '_')}"
    target_path = os.path.join(course_upload_dir, safe_filename)

    # Stream file to disk while enforcing <= 10MB limit
    total_bytes = 0
    chunk_size = 1024 * 128  # 128 KB chunks

    try:
        with open(target_path, "wb") as f_out:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_VIDEO_SIZE:
                    # Exceeded 10MB limit: delete partial file and reject
                    f_out.close()
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Video file exceeds maximum allowed size of 10MB "
                            f"(received > {(total_bytes / (1024*1024)):.2f}MB). Upload aborted."
                        ),
                    )
                f_out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        if os.path.exists(target_path):
            os.remove(target_path)
        raise HTTPException(
            status_code=500, detail=f"Failed to save video file: {str(exc)}"
        )
    finally:
        await file.close()

    now = datetime.now(timezone.utc)
    uploader_name = current_user.full_name or current_user.email

    video_doc = {
        "_id": video_id,
        "id": video_id,
        "course_id": str(course_id),
        "title": title.strip(),
        "description": description.strip() if description else "",
        "filename": filename,
        "file_path": target_path,
        "file_size": total_bytes,
        "content_type": file.content_type or "video/mp4",
        "uploader_id": str(current_user.id),
        "uploader_name": uploader_name,
        "created_at": now,
        "updated_at": now,
    }

    await db[COL_COURSE_VIDEOS].insert_one(video_doc)

    return {
        "id": video_id,
        "course_id": str(course_id),
        "title": video_doc["title"],
        "description": video_doc["description"],
        "filename": filename,
        "file_size": total_bytes,
        "uploader_name": uploader_name,
        "created_at": now.isoformat(),
        "unique_viewers": 0,
        "total_watch_minutes": 0.0,
    }


# ── 2. List Course Videos with Watch Analytics ─────────────────────────────────
@router.get("/api/v1/courses/{course_id}/videos")
async def list_course_videos(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns list of all videos uploaded for this course along with aggregated watch analytics:
      - unique_viewers (number of distinct students who watched)
      - total_watch_minutes (cumulative duration watched across all students)
      - viewers breakdown (for lecturer/admin)
      - my_watch_minutes (for current student)
    """
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    is_lecturer_or_admin = role_val in ("lecturer", "admin")

    # If student, verify course enrollment
    if not is_lecturer_or_admin:
        is_enrolled = await check_student_enrolled(db, course_id, current_user)
        if not is_enrolled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in this course to access its lecture videos.",
            )

    cursor = db[COL_COURSE_VIDEOS].find({"course_id": str(course_id)}).sort("created_at", -1)
    videos = await cursor.to_list(length=100)

    current_user_id = str(current_user.id)
    results = []

    for v in videos:
        vid = str(v["_id"])

        # Fetch watch records for this video
        records_cursor = db[COL_VIDEO_WATCH_RECORDS].find({"video_id": vid})
        watch_records = await records_cursor.to_list(length=500)

        total_watch_seconds = sum(r.get("total_watch_seconds", 0) for r in watch_records)
        unique_viewers = len(watch_records)

        my_seconds = 0
        viewers_list = []

        for r in watch_records:
            w_secs = r.get("total_watch_seconds", 0)
            if r.get("student_id") == current_user_id:
                my_seconds = w_secs

            if is_lecturer_or_admin:
                viewers_list.append({
                    "student_id": r.get("student_id"),
                    "student_name": r.get("student_name", "Student"),
                    "student_email": r.get("student_email", ""),
                    "total_watch_seconds": round(w_secs, 1),
                    "total_watch_minutes": round(w_secs / 60, 1),
                    "last_watched_at": r.get("last_watched_at").isoformat() if r.get("last_watched_at") else None,
                    "completed": r.get("completed", False),
                })

        item: Dict[str, Any] = {
            "id": vid,
            "course_id": v["course_id"],
            "title": v.get("title", "Lecture Video"),
            "description": v.get("description", ""),
            "filename": v.get("filename", ""),
            "file_size": v.get("file_size", 0),
            "content_type": v.get("content_type", "video/mp4"),
            "uploader_name": v.get("uploader_name", "Instructor"),
            "created_at": v.get("created_at").isoformat() if v.get("created_at") else None,
            "unique_viewers": unique_viewers,
            "total_watch_seconds": round(total_watch_seconds, 1),
            "total_watch_minutes": round(total_watch_seconds / 60, 1),
            "my_watch_seconds": round(my_seconds, 1),
            "my_watch_minutes": round(my_seconds / 60, 1),
        }

        if is_lecturer_or_admin:
            item["viewers"] = viewers_list

        results.append(item)

    return results


# ── 3. Delete Video (Lecturer / Admin) ─────────────────────────────────────────
@router.delete("/api/v1/courses/{course_id}/videos/{video_id}")
async def delete_course_video(
    course_id: str,
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Deletes a lecture video and its associated watch records and local file.
    Restricted to Course Lecturer or Admin.
    """
    await check_course_ownership(db, course_id, current_user)

    video = await db[COL_COURSE_VIDEOS].find_one({"_id": video_id, "course_id": str(course_id)})
    if not video:
        video = await db[COL_COURSE_VIDEOS].find_one({"id": video_id, "course_id": str(course_id)})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")

    # Remove file from disk
    file_path = video.get("file_path")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    # Remove database entries
    await db[COL_COURSE_VIDEOS].delete_one({"_id": video["_id"]})
    await db[COL_VIDEO_WATCH_RECORDS].delete_many({"video_id": video_id})

    return {"status": "deleted", "video_id": video_id}


# ── 4. Stream Video (HTTP 206 Partial Content Range Support) ───────────────────
@router.get("/api/v1/videos/{video_id}/stream")
async def stream_video(
    video_id: str,
    request: Request,
    user: User = Depends(get_stream_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Streams the video file with HTTP Range support for smooth HTML5 video scrubbing and playback.
    """
    video = await db[COL_COURSE_VIDEOS].find_one({"_id": video_id})
    if not video:
        video = await db[COL_COURSE_VIDEOS].find_one({"id": video_id})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")

    file_path = video.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file is missing from storage.")

    file_size = os.path.getsize(file_path)
    content_type = video.get("content_type") or "video/mp4"

    range_header = request.headers.get("range")

    if not range_header:
        def iter_full():
            with open(file_path, "rb") as f:
                while chunk := f.read(1024 * 256):
                    yield chunk

        return StreamingResponse(
            iter_full(),
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            },
        )

    # Parse byte range header, e.g. "bytes=0-1048575"
    range_str = range_header.replace("bytes=", "").strip()
    parts = range_str.split("-")
    start = int(parts[0]) if parts[0] else 0
    end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1

    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Requested Range Not Satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_length = end - start + 1

    def iter_range():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = chunk_length
            while remaining > 0:
                read_amount = min(remaining, 1024 * 128)
                data = f.read(read_amount)
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iter_range(),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=content_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_length),
        },
    )


# ── 5. Record Student Watch Telemetry ──────────────────────────────────────────
@router.post("/api/v1/videos/{video_id}/watch")
async def record_video_watch(
    video_id: str,
    payload: WatchHeartbeatPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Logs student video watch time heartbeat and updates aggregate video analytics.
    Also logs activity event to col.ACTIVITY_EVENTS for Feature 9/19 clickstream integration.
    """
    video = await db[COL_COURSE_VIDEOS].find_one({"_id": video_id})
    if not video:
        video = await db[COL_COURSE_VIDEOS].find_one({"id": video_id})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")

    student_id = str(current_user.id)
    student_name = current_user.full_name or current_user.email
    student_email = current_user.email
    student_ref = current_user.student_id or student_id
    pid = getattr(current_user, "pid", None) or pseudonymize(student_ref)

    now = datetime.now(timezone.utc)

    # 1. Update or create student's watch record for this video
    record = await db[COL_VIDEO_WATCH_RECORDS].find_one({
        "video_id": video_id,
        "student_id": student_id,
    })

    if not record:
        new_record = {
            "_id": str(uuid.uuid4()),
            "video_id": video_id,
            "course_id": video["course_id"],
            "student_id": student_id,
            "student_name": student_name,
            "student_email": student_email,
            "pid": pid,
            "total_watch_seconds": payload.watched_seconds,
            "last_position_seconds": payload.current_time,
            "completed": payload.completed,
            "first_watched_at": now,
            "last_watched_at": now,
        }
        await db[COL_VIDEO_WATCH_RECORDS].insert_one(new_record)
        total_student_seconds = payload.watched_seconds
    else:
        update_doc: Dict[str, Any] = {
            "$inc": {"total_watch_seconds": payload.watched_seconds},
            "$set": {
                "last_position_seconds": payload.current_time,
                "last_watched_at": now,
            },
        }
        if payload.completed:
            update_doc["$set"]["completed"] = True

        await db[COL_VIDEO_WATCH_RECORDS].update_one(
            {"_id": record["_id"]},
            update_doc,
        )
        total_student_seconds = record.get("total_watch_seconds", 0) + payload.watched_seconds

    # 2. Log activity clickstream event in col.ACTIVITY_EVENTS for downstream ML
    event_id = str(uuid.uuid4())
    event_doc = {
        "_id": event_id,
        "id": event_id,
        "schema_version": 1,
        "pid": pid,
        "course_id": video["course_id"],
        "week_index": await resolve_event_week(db, video["course_id"], now, 1),
        "event_type": "video_watch",
        "event_payload": {
            "video_id": video_id,
            "video_title": video.get("title"),
            "watched_seconds": payload.watched_seconds,
            "current_time": payload.current_time,
            "completed": payload.completed,
        },
        "clicks": 1,
        "timestamp": now,
        "ingested_at": now,
    }
    await db[col.ACTIVITY_EVENTS].insert_one(event_doc)

    return {
        "status": "recorded",
        "video_id": video_id,
        "student_watch_seconds": round(total_student_seconds, 1),
        "student_watch_minutes": round(total_student_seconds / 60, 1),
    }
