import json
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

from app.config import settings
from app.schemas import CropRule


def _normalize_text(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


class CropCatalog:
    """Loads and resolves FAO-based crop rules from fao_crops_rules.json."""

    def __init__(self, rules_path: Optional[str] = None) -> None:
        path = Path(rules_path or settings.fao_rules_path)
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        self.metadata: Dict = raw.get("metadata", {})
        self.crops: List[CropRule] = [CropRule(**item) for item in raw.get("crops", [])]
        self._by_id: Dict[str, CropRule] = {_normalize_text(c.id): c for c in self.crops}
        self._aliases: Dict[str, CropRule] = {}
        for crop in self.crops:
            self._aliases[_normalize_text(crop.id)] = crop
            self._aliases[_normalize_text(crop.name)] = crop
            for part in _normalize_text(crop.name).split("/"):
                self._aliases[part.strip()] = crop

    def list_crops(self) -> List[CropRule]:
        return list(self.crops)

    def resolve(self, crop_query: str) -> Optional[CropRule]:
        key = _normalize_text(crop_query)
        if key in self._aliases:
            return self._aliases[key]
        for alias, crop in self._aliases.items():
            if key in alias or alias in key:
                return crop
        return None
