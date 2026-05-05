import io
from typing import Dict, List, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

PHOTO_MIMES = (
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
)


class DriveService:
    def __init__(self, service_account_file: str):
        creds = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        self._svc = build("drive", "v3", credentials=creds)

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Tuple[str, str]:
        """Create a Drive folder. Returns (folder_id, web_view_link)."""
        meta: Dict = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            meta["parents"] = [parent_id]
        folder = self._svc.files().create(body=meta, fields="id,webViewLink").execute()
        folder_id: str = folder["id"]
        # Allow anyone with the link to upload files
        self._svc.permissions().create(
            fileId=folder_id,
            body={"type": "anyone", "role": "writer"},
        ).execute()
        return folder_id, folder.get("webViewLink", "")

    def list_photo_files(self, folder_id: str) -> List[Dict]:
        """Return all image files directly inside folder_id."""
        q_mimes = " or ".join(f"mimeType='{m}'" for m in PHOTO_MIMES)
        query = f"'{folder_id}' in parents and ({q_mimes}) and trashed=false"
        result = (
            self._svc.files()
            .list(q=query, fields="files(id,name,mimeType,size)", pageSize=1000)
            .execute()
        )
        return result.get("files", [])

    def download_file(self, file_id: str) -> bytes:
        request = self._svc.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()

    def upload_file(self, name: str, data: bytes, mime_type: str, parent_id: str) -> str:
        """Upload raw bytes as a new file. Returns new file_id."""
        meta = {"name": name, "parents": [parent_id]}
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type)
        f = self._svc.files().create(body=meta, media_body=media, fields="id").execute()
        return f["id"]

    def copy_file(self, file_id: str, name: str, parent_id: str) -> str:
        """Copy an existing Drive file into parent_id. Returns new file_id."""
        body = {"name": name, "parents": [parent_id]}
        f = self._svc.files().copy(fileId=file_id, body=body, fields="id").execute()
        return f["id"]

    def create_output_structure(self, session_date: str) -> Dict:
        """
        Build the PhotoSort output folder tree and return a dict of folder IDs:
          root_id, root_link, people_id, uncat_id,
          scene_folder_ids: {scene_name: folder_id}
        """
        root_id, root_link = self.create_folder(f"PhotoSort_{session_date}")
        people_id, _ = self.create_folder("People", root_id)
        scenes_id, _ = self.create_folder("Scenes", root_id)
        uncat_id, _ = self.create_folder("Uncategorized", root_id)

        scene_folder_ids: Dict[str, str] = {}
        for scene in ("Nature", "Food", "City", "Landmarks", "Group Photos"):
            fid, _ = self.create_folder(scene, scenes_id)
            scene_folder_ids[scene] = fid

        return {
            "root_id": root_id,
            "root_link": root_link,
            "people_id": people_id,
            "uncat_id": uncat_id,
            "scene_folder_ids": scene_folder_ids,
        }
