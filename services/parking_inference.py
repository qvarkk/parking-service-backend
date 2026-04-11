from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Dict, Mapping, Optional, Union

from config import settings

logger = logging.getLogger(__name__)

ImageSource = Union[str, Path, bytes, bytearray, BinaryIO, Any]

_model = None
_model_path_resolved: Optional[Path] = None


def _require_ultralytics():
    try:
        from ultralytics import YOLO
    except ImportError as e:
        raise ImportError(
            "Нужны пакеты torch и ultralytics: pip install torch ultralytics"
        ) from e
    return YOLO


def _resolve_weights_path() -> Path:
    raw = (settings.PARKING_YOLO_WEIGHTS or "best.pt").strip()
    p = Path(raw)
    if p.is_file():
        return p.resolve()
    root = Path(__file__).resolve().parent.parent
    cand = root / raw
    if cand.is_file():
        return cand.resolve()
    raise FileNotFoundError(f"Веса YOLO не найдены: {raw} (искали также {cand})")


def _load_model():
    global _model, _model_path_resolved
    YOLO = _require_ultralytics()
    path = _resolve_weights_path()
    if _model is None or _model_path_resolved != path:
        logger.info("Загрузка YOLO: %s", path)
        _model = YOLO(str(path))
        _model_path_resolved = path
    return _model


def _parse_class_ids(s: Optional[str]) -> Optional[set[int]]:
    if not s or not str(s).strip():
        return None
    out: set[int] = set()
    for part in str(s).split(","):
        part = part.strip()
        if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
            out.add(int(part))
    return out or None


def _coerce_image(source: ImageSource) -> Any:
    if isinstance(source, (str, Path)):
        return str(Path(source).expanduser())
    if isinstance(source, (bytes, bytearray)):
        from PIL import Image

        return Image.open(io.BytesIO(source)).convert("RGB")
    if hasattr(source, "read"):
        data = source.read()
        from PIL import Image

        return Image.open(io.BytesIO(data)).convert("RGB")
    return source


_FREE_PATTERNS = re.compile(
    r"free|empty|vacant|available|свобод|пуст", re.IGNORECASE
)
_OCC_PATTERNS = re.compile(
    r"occupy|occupied|busy|taken|full|car|занят|занято|машин", re.IGNORECASE
)


def _counts_from_names(
    names: Mapping[int, str], class_ids: list[int]
) -> tuple[Dict[str, int], int, int, int]:
    from collections import Counter

    cnt: Counter[int] = Counter(int(c) for c in class_ids)
    by_name: Dict[str, int] = {}
    for cid, k in sorted(cnt.items()):
        label = str(names.get(int(cid), str(int(cid))))
        by_name[label] = k

    free_ids = _parse_class_ids(settings.PARKING_YOLO_FREE_CLASS_IDS)
    occ_ids = _parse_class_ids(settings.PARKING_YOLO_OCCUPIED_CLASS_IDS)

    free = occ = uncl = 0
    if free_ids is not None or occ_ids is not None:
        free_ids = free_ids or set()
        occ_ids = occ_ids or set()
        for cid, k in cnt.items():
            if cid in free_ids:
                free += k
            elif cid in occ_ids:
                occ += k
            else:
                uncl += k
        return by_name, free, occ, uncl

    for cid, k in cnt.items():
        label = names.get(int(cid), str(cid))
        if _FREE_PATTERNS.search(label):
            free += k
        elif _OCC_PATTERNS.search(label):
            occ += k
        else:
            uncl += k
    return by_name, free, occ, uncl


@dataclass
class ParkingSpotCountResult:

    free_spots: int
    occupied_spots: int
    unclassified: int
    total_detections: int
    class_counts: Dict[str, int] = field(default_factory=dict)
    model_class_names: Dict[int, str] = field(default_factory=dict)

    @property
    def total_parking_spots(self) -> int:
        return self.free_spots + self.occupied_spots


def count_parking_spots_from_image(
    image: ImageSource,
    *,
    conf: Optional[float] = None,
) -> ParkingSpotCountResult:
    model = _load_model()
    conf_f = float(conf if conf is not None else settings.PARKING_YOLO_CONF)
    src = _coerce_image(image)

    results = model.predict(source=src, conf=conf_f, verbose=False)
    r0 = results[0]
    names: Dict[int, str] = dict(r0.names) if r0.names is not None else {}

    if r0.boxes is None or len(r0.boxes) == 0:
        return ParkingSpotCountResult(
            free_spots=0,
            occupied_spots=0,
            unclassified=0,
            total_detections=0,
            class_counts={},
            model_class_names=names,
        )

    cls_list = r0.boxes.cls.cpu().numpy().astype(int).tolist()
    by_name, free, occ, uncl = _counts_from_names(names, cls_list)

    return ParkingSpotCountResult(
        free_spots=free,
        occupied_spots=occ,
        unclassified=uncl,
        total_detections=len(cls_list),
        class_counts=by_name,
        model_class_names=names,
    )
