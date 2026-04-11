#!/usr/bin/env python3
"""
Проверка инференса YOLO: best.pt + тестовое фото в корне репозитория.

  python scripts/test_parking_inference.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

TEST_IMAGE = _ROOT / "5393519222383644680.jpg"


def main() -> int:
    if not TEST_IMAGE.is_file():
        print(f"FAIL: нет тестовой картинки {TEST_IMAGE}", file=sys.stderr)
        return 1

    try:
        from services.parking_inference import count_parking_spots_from_image
    except ImportError as e:
        print(
            "FAIL: не установлены зависимости (torch, ultralytics):",
            e,
            file=sys.stderr,
        )
        return 1

    try:
        result = count_parking_spots_from_image(TEST_IMAGE)
    except FileNotFoundError as e:
        print("FAIL: веса YOLO не найдены:", e, file=sys.stderr)
        return 1
    except Exception as e:
        print("FAIL: инференс упал:", e, file=sys.stderr)
        raise

    payload = {
        "image": str(TEST_IMAGE),
        "free_spots": result.free_spots,
        "occupied_spots": result.occupied_spots,
        "unclassified": result.unclassified,
        "total_detections": result.total_detections,
        "total_parking_spots": result.total_parking_spots,
        "class_counts": result.class_counts,
        "model_class_names": {str(k): v for k, v in result.model_class_names.items()},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    # Минимальные проверки: модель ответила структурой, числа неотрицательные
    assert result.total_detections >= 0
    assert result.free_spots >= 0 and result.occupied_spots >= 0
    assert result.unclassified >= 0
    assert result.free_spots + result.occupied_spots + result.unclassified == result.total_detections

    print("OK: инференс прошёл, счётчики согласованы с числом боксов.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
