import asyncio
import datetime
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .sessions.manager import SessionManager, SessionStatus, SortResults, ClusterInfo
from .drive.export import DriveService
from .bot.telegram_bot import run_bot, register_session

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── lazy globals ──────────────────────────────────────────────────────────────
_face_pipeline = None
_scene_classifier = None
_drive: Optional[DriveService] = None
_llm = None

sessions = SessionManager()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "photosortbot")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def get_drive() -> DriveService:
    global _drive
    if _drive is None:
        sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
        if not sa_file or not os.path.exists(sa_file):
            raise HTTPException(
                503,
                "Google Drive not configured — add GOOGLE_SERVICE_ACCOUNT_FILE to .env",
            )
        _drive = DriveService(sa_file)
    return _drive


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _llm
    if ANTHROPIC_KEY:
        from .llm.parser import LLMParser
        _llm = LLMParser(ANTHROPIC_KEY)
        logger.info("LLM parser ready")
    if BOT_TOKEN:
        asyncio.create_task(run_bot(BOT_TOKEN, get_drive()))
        logger.info("Telegram bot task created")
    yield


app = FastAPI(title="PhotoSort API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ───────────────────────────────────────────────────────────

class CreateSessionResponse(BaseModel):
    session_id: str
    drive_folder_link: str
    telegram_link: str


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    photo_count: int
    error: Optional[str] = None


class RenameRequest(BaseModel):
    text: str


class SearchRequest(BaseModel):
    query: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/session/create", response_model=CreateSessionResponse)
async def create_session():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_id, folder_link = get_drive().create_folder(f"PhotoSort_uploads_{ts}")
    session = sessions.create(folder_id, folder_link, BOT_USERNAME)
    register_session(session.id, folder_id)
    logger.info(f"Session {session.id} created, Drive folder {folder_id}")
    return CreateSessionResponse(
        session_id=session.id,
        drive_folder_link=folder_link,
        telegram_link=session.telegram_link,
    )


@app.get("/session/{session_id}/status", response_model=SessionStatusResponse)
async def get_status(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status == SessionStatus.COLLECTING:
        files = get_drive().list_photo_files(session.drive_folder_id)
        sessions.update_photo_count(session_id, len(files))
    return SessionStatusResponse(
        session_id=session.id,
        status=session.status,
        photo_count=session.photo_count,
        error=session.error,
    )


@app.post("/session/{session_id}/sort")
async def trigger_sort(session_id: str, background_tasks: BackgroundTasks):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status == SessionStatus.SORTING:
        raise HTTPException(409, "Sort already in progress")
    sessions.set_status(session_id, SessionStatus.SORTING)
    background_tasks.add_task(_run_sort_pipeline, session_id)
    return {"message": "Sort started"}


@app.get("/session/{session_id}/results")
async def get_results(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status == SessionStatus.ERROR:
        raise HTTPException(500, session.error or "Pipeline error")
    if session.status != SessionStatus.DONE:
        raise HTTPException(202, "Sort not complete yet")
    r = session.results
    return {
        "output_folder_link": r.output_folder_link,
        "people": [
            {
                "cluster_id": c.cluster_id,
                "label": c.label,
                "photo_count": len(c.photo_ids),
            }
            for c in r.people
        ],
        "scenes": {k: len(v) for k, v in r.scenes.items()},
        "uncategorized": len(r.uncategorized),
    }


@app.post("/session/{session_id}/rename")
async def rename_clusters(session_id: str, req: RenameRequest):
    session = sessions.get(session_id)
    if not session or not session.results:
        raise HTTPException(404, "Session or results not found")
    if not _llm:
        raise HTTPException(503, "LLM not configured — set ANTHROPIC_API_KEY in .env")
    current_labels = [c.label for c in session.results.people]
    mappings = _llm.parse_rename_commands(req.text, current_labels)
    renamed = []
    for old, new in mappings.items():
        if sessions.rename_cluster(session_id, old, new):
            renamed.append({"from": old, "to": new})
    return {"renamed": renamed}


@app.post("/session/{session_id}/search")
async def smart_search(session_id: str, req: SearchRequest):
    session = sessions.get(session_id)
    if not session or not session.results:
        raise HTTPException(404, "Session or results not found")
    if not _llm:
        raise HTTPException(503, "LLM not configured — set ANTHROPIC_API_KEY in .env")
    tags = _llm.extract_search_tags(req.query)
    result: dict = {"scenes": {}, "people": []}
    for scene in tags.get("scenes", []):
        ids = session.results.scenes.get(scene, [])
        if ids:
            result["scenes"][scene] = len(ids)
    for name in tags.get("people", []):
        for cluster in session.results.people:
            if name.lower() in cluster.label.lower():
                result["people"].append(
                    {"label": cluster.label, "count": len(cluster.photo_ids)}
                )
    return result


# ── Background ML pipeline ────────────────────────────────────────────────────

async def _run_sort_pipeline(session_id: str):
    global _face_pipeline, _scene_classifier
    session = sessions.get(session_id)
    if not session:
        return

    try:
        if _face_pipeline is None:
            logger.info("Loading ML models (first run, may take ~30 s)…")
            from .ml.face_pipeline import FacePipeline
            from .ml.scene_classifier import SceneClassifier
            _face_pipeline = FacePipeline()
            _scene_classifier = SceneClassifier()
            logger.info("ML models loaded")

        drive = get_drive()

        files = drive.list_photo_files(session.drive_folder_id)
        if not files:
            sessions.set_status(session_id, SessionStatus.ERROR, error="No photos found in Drive folder")
            return

        logger.info(f"[{session_id}] Downloading {len(files)} photos…")
        photo_bytes: dict = {}
        for f in files:
            photo_bytes[f["id"]] = drive.download_file(f["id"])

        photo_embeddings: dict = {}
        face_counts: dict = {}
        for photo_id, data in photo_bytes.items():
            embs, count = _face_pipeline.extract_embeddings(data)
            face_counts[photo_id] = count
            if embs is not None:
                photo_embeddings[photo_id] = embs

        person_clusters = _face_pipeline.cluster_photos(photo_embeddings)
        group_photo_ids = set(_face_pipeline.detect_group_photos(face_counts))
        scene_map = _scene_classifier.classify_batch(photo_bytes, face_counts)

        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        folders = drive.create_output_structure(date_str)
        categorized_ids: set = set()

        group_folder_id = folders["scene_folder_ids"]["Group Photos"]
        for pid in group_photo_ids:
            meta = next((f for f in files if f["id"] == pid), None)
            if meta:
                drive.copy_file(pid, meta["name"], group_folder_id)
                categorized_ids.add(pid)

        cluster_infos: list = []
        for person_label, photo_ids in person_clusters.items():
            if person_label == "unknown":
                continue
            person_folder_id, _ = drive.create_folder(person_label, folders["people_id"])
            for pid in photo_ids:
                meta = next((f for f in files if f["id"] == pid), None)
                if meta:
                    drive.copy_file(pid, meta["name"], person_folder_id)
                    categorized_ids.add(pid)
            cluster_infos.append(
                ClusterInfo(cluster_id=person_label, label=person_label, photo_ids=list(photo_ids))
            )

        scene_results: dict = {}
        for pid, scene in scene_map.items():
            scene_results.setdefault(scene, []).append(pid)
            if scene == "Group Photos":
                continue
            folder_id = folders["scene_folder_ids"].get(scene)
            if folder_id:
                meta = next((f for f in files if f["id"] == pid), None)
                if meta:
                    drive.copy_file(pid, meta["name"], folder_id)
                    categorized_ids.add(pid)

        uncat_ids = [f["id"] for f in files if f["id"] not in categorized_ids]
        for pid in uncat_ids:
            meta = next((f for f in files if f["id"] == pid), None)
            if meta:
                drive.copy_file(pid, meta["name"], folders["uncat_id"])

        results = SortResults(
            people=cluster_infos,
            scenes=scene_results,
            uncategorized=uncat_ids,
            output_folder_id=folders["root_id"],
            output_folder_link=folders["root_link"],
        )
        sessions.set_status(session_id, SessionStatus.DONE, results=results)
        logger.info(f"[{session_id}] Sort complete — {len(cluster_infos)} people clusters")

    except Exception as exc:
        logger.exception(f"[{session_id}] Sort pipeline error: {exc}")
        sessions.set_status(session_id, SessionStatus.ERROR, error=str(exc))
