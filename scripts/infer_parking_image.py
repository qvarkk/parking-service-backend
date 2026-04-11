from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services.parking_inference import count_parking_spots_from_image 

def main() -> None:
    p = argparse.ArgumentParser(description="YOLO: свободные/занятые места по фото")
    p.add_argument("image", type=Path, help="Путь к JPG/PNG")
    p.add_argument("--conf", type=float, default=None, help="Порог conf (иначе из .env)")
    args = p.parse_args()
    if not args.image.is_file():
        raise SystemExit(f"Файл не найден: {args.image}")

    r = count_parking_spots_from_image(args.image, conf=args.conf)
    print(
        json.dumps(
            {
                "free_spots": r.free_spots,
                "occupied_spots": r.occupied_spots,
                "unclassified": r.unclassified,
                "total_detections": r.total_detections,
                "total_parking_spots": r.total_parking_spots,
                "class_counts": r.class_counts,
                "model_class_names": {str(k): v for k, v in r.model_class_names.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
