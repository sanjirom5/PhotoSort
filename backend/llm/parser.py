import json
import re
from typing import Dict, List

import anthropic

_MODEL = "claude-sonnet-4-6"


class LLMParser:
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def _ask(self, system: str, user: str, max_tokens: int = 512) -> str:
        msg = self._client.messages.create(
            model=_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()

    def _extract_json(self, text: str) -> dict:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {}

    def parse_rename_commands(self, text: str, current_labels: List[str]) -> Dict[str, str]:
        """
        Parse "Person_1 это Саня, Person_2 это Диас" → {"Person_1": "Саня", "Person_2": "Диас"}.
        old_label keys must match entries in current_labels.
        """
        system = (
            "You parse photo cluster rename commands. "
            f"Current cluster labels: {', '.join(current_labels)}. "
            "Return ONLY a JSON object mapping old label → new name. "
            'Example: {"Person_1": "Саня", "Person_2": "Диас"}. '
            "old keys must match current labels exactly."
        )
        raw = self._ask(system, text)
        return self._extract_json(raw)

    def extract_search_tags(self, query: str) -> Dict[str, List[str]]:
        """
        Parse a natural-language photo search into filter tags.
        Returns {"scenes": [...], "people": [...]}.
        Valid scene values: Nature, Food, City, Landmarks, Group Photos, Portrait.
        """
        system = (
            "Parse a photo search query into filter tags. "
            "Valid scene values: Nature, Food, City, Landmarks, Group Photos, Portrait. "
            'Return ONLY JSON: {"scenes": [], "people": []}. '
            "people is a list of names/labels mentioned. scenes is a list of matching scene categories."
        )
        raw = self._ask(system, query, max_tokens=256)
        result = self._extract_json(raw)
        result.setdefault("scenes", [])
        result.setdefault("people", [])
        return result

    def generate_album_title(self, scenes: List[str], exif_info: Dict) -> str:
        """Generate a short Russian album title from detected scenes and EXIF metadata."""
        scene_summary = ", ".join(set(scenes)) if scenes else "разные"
        location = exif_info.get("location", "")
        date = exif_info.get("date", "")
        prompt = (
            f"Scenes in photos: {scene_summary}. "
            f"Location hint: {location or 'unknown'}. "
            f"Date: {date or 'unknown'}. "
            "Generate a short evocative album title in Russian (max 8 words). "
            "Return only the title, no quotes."
        )
        return self._ask("", prompt, max_tokens=64)
