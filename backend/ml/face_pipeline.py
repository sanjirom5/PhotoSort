import io
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
from sklearn.cluster import DBSCAN

from pillow_heif import register_heif_opener
register_heif_opener()


class FacePipeline:
    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        # MTCNN detects faces and returns aligned 160×160 crops
        self.mtcnn = MTCNN(
            image_size=160,
            margin=20,
            min_face_size=40,
            keep_all=True,
            device=self.device,
        )
        # InceptionResnetV1 pretrained on VGGFace2 → 512-dim embeddings
        self.resnet = InceptionResnetV1(pretrained="vggface2").eval().to(self.device)

    def extract_embeddings(self, image_bytes: bytes) -> Tuple[Optional[np.ndarray], int]:
        """
        Detect faces and return (embeddings [N, 512], face_count).
        Returns (None, 0) when no faces are found.
        """
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        faces = self.mtcnn(img)  # tensor [N,3,160,160] or None
        if faces is None:
            return None, 0
        if faces.ndim == 3:
            faces = faces.unsqueeze(0)
        faces = faces.to(self.device)
        with torch.no_grad():
            embeddings = self.resnet(faces).cpu().numpy()
        return embeddings, len(embeddings)

    def cluster_photos(
        self,
        photo_embeddings: Dict[str, np.ndarray],
        eps: float = 0.9,
        min_samples: int = 2,
    ) -> Dict[str, List[str]]:
        """
        Cluster face embeddings with DBSCAN.
        photo_embeddings: {photo_id: ndarray [N_faces, 512]}
        Returns: {"Person_1": [photo_ids], ..., "unknown": [photo_ids]}
        """
        all_embeddings: List[np.ndarray] = []
        photo_face_map: List[str] = []

        for photo_id, embs in photo_embeddings.items():
            for emb in embs:
                all_embeddings.append(emb)
                photo_face_map.append(photo_id)

        if not all_embeddings:
            return {}

        X = np.array(all_embeddings)
        labels = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean").fit_predict(X)

        cluster_to_photos: Dict[int, set] = {}
        for idx, label in enumerate(labels):
            cluster_to_photos.setdefault(label, set()).add(photo_face_map[idx])

        result: Dict[str, List[str]] = {}
        person_n = 1
        for label in sorted(cluster_to_photos):
            photo_set = cluster_to_photos[label]
            if label == -1:
                result.setdefault("unknown", []).extend(photo_set)
            else:
                result[f"Person_{person_n}"] = list(photo_set)
                person_n += 1

        return result

    def detect_group_photos(
        self,
        face_counts: Dict[str, int],
        min_faces: int = 2,
    ) -> List[str]:
        """Return photo_ids where detected face count >= min_faces."""
        return [pid for pid, count in face_counts.items() if count >= min_faces]
