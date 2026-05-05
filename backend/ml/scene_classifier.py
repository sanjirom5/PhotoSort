import io
from typing import Dict

import torch
from PIL import Image
from torchvision import models

SCENE_CATEGORIES = ["Nature", "Food", "City", "Landmarks", "Group Photos", "Portrait"]

# Rough keyword→scene mapping based on ImageNet class labels
_KEYWORD_MAP = {
    # Nature
    "valley": "Nature", "cliff": "Nature", "coral reef": "Nature",
    "mountain": "Nature", "lakeside": "Nature", "seashore": "Nature",
    "volcano": "Nature", "sandbar": "Nature", "geyser": "Nature",
    # Food
    "pizza": "Food", "hotdog": "Food", "hamburger": "Food",
    "ice cream": "Food", "burrito": "Food", "pretzel": "Food",
    "espresso": "Food", "cup": "Food", "chocolate": "Food",
    # City
    "street sign": "City", "traffic light": "City", "crosswalk": "City",
    "skyscraper": "City", "parking meter": "City",
    # Landmarks (monumental structures)
    "church": "Landmarks", "mosque": "Landmarks", "palace": "Landmarks",
    "castle": "Landmarks", "bridge": "Landmarks", "monastery": "Landmarks",
}


class SceneClassifier:
    def __init__(self, device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        weights = models.EfficientNet_B3_Weights.IMAGENET1K_V1
        self.model = models.efficientnet_b3(weights=weights).eval().to(self.device)
        self.preprocess = weights.transforms()
        self._labels = weights.meta["categories"]

    @torch.no_grad()
    def classify(self, image_bytes: bytes, face_count: int = 0) -> str:
        """
        Classify one image into a SCENE_CATEGORY.
        face_count from the face pipeline takes priority for Group Photos / Portrait.
        """
        if face_count >= 2:
            return "Group Photos"
        if face_count == 1:
            return "Portrait"

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = self.preprocess(img).unsqueeze(0).to(self.device)
        logits = self.model(tensor)
        probs = torch.softmax(logits, dim=1)[0]
        top5_idx = probs.topk(5).indices.tolist()

        for idx in top5_idx:
            label_lower = self._labels[idx].lower()
            for keyword, scene in _KEYWORD_MAP.items():
                if keyword in label_lower:
                    return scene

        return "Nature"  # fallback

    def classify_batch(
        self,
        photo_bytes_map: Dict[str, bytes],
        face_counts: Dict[str, int],
    ) -> Dict[str, str]:
        """Returns {photo_id: scene_category} for all photos."""
        return {
            pid: self.classify(data, face_counts.get(pid, 0))
            for pid, data in photo_bytes_map.items()
        }
