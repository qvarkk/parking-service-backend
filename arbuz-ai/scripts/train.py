"""
Алгоритм обучения детектора (YOLOv8 через Ultralytics).

Google Colab (пример):
    !pip install -q ultralytics pyyaml
    # Распакуйте/клонируйте проект так, чтобы рядом были каталоги train/ и configs/
    %cd /path/to/arbuz-ai
    !python scripts/train.py --root /path/to/arbuz-ai
    # Либо без --root, если текущая папка уже корень проекта (есть train/ и configs/).
    # Из Google Drive:
    #   import os; os.environ["ARBUZ_AI_ROOT"] = "/content/drive/MyDrive/arbuz-ai"
    #   !python scripts/train.py

Корень проекта (где лежат train/, configs/): аргумент --root, переменная ARBUZ_AI_ROOT,
в Colab — авто-поиск по cwd и /content/...; локально — родитель каталога scripts/.

1. Подготовка данных: структура датасета YOLO
   dataset/
     train/images, train/labels
     val/images, val/labels
   Метки — txt на каждое изображение (class cx cy w h в нормализованных координатах).

2. Конфигурация: create_dataset_yaml() формирует data.yaml (path, train, val, nc, names).

3. Инициализация модели: загрузка весов model_name (.pt), опционально предобученные.

4. Обучение: model.train() — по эпохам: прямой проход, лосс, обратное распространение,
   валидация на val, логирование метрик, сохранение весов и чекпоинтов; при отсутствии
   улучшения val-метрик patience эпох подряд — early stopping (если включён).

5. Оценка: validate_model() — mAP50, mAP50-95, precision, recall на val.

6. (Опционально) export_model() — экспорт лучших весов в ONNX/TFLite и др.

7. (Опционально) test_prediction() — инференс на изображениях с порогами conf/iou.
"""
from __future__ import annotations

import argparse
import os
import random
import shutil
from pathlib import Path
from typing import Any

import yaml
from ultralytics import YOLO


def repo_root(explicit: str | None = None) -> str:
    """Корень arbuz-ai: явный путь, ARBUZ_AI_ROOT, Colab (cwd/content), либо каталог с scripts/."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_dir():
            raise NotADirectoryError(f"Некорректный --root (нет каталога): {p}")
        return str(p)

    env = os.environ.get("ARBUZ_AI_ROOT", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if not p.is_dir():
            raise NotADirectoryError(f"ARBUZ_AI_ROOT не указывает на каталог: {p}")
        return str(p)

    if os.environ.get("COLAB_RELEASE_TAG"):
        candidates = [
            Path.cwd().resolve(),
            Path("/content") / "arbuz-ai",
            Path("/content") / "drive" / "MyDrive" / "arbuz-ai",
            Path("/content") / "drive" / "MyDrive" / "parking-service-backend" / "arbuz-ai",
        ]
        for c in candidates:
            if (c / "train").is_dir() and (c / "configs").is_dir():
                return str(c.resolve())

    try:
        return str(Path(__file__).resolve().parent.parent)
    except NameError:
        return str(Path.cwd().resolve())


def resolve_path(path: str | None, root: str) -> str | None:
    if path is None:
        return None
    p = str(path).strip()
    if not p:
        return None
    if os.path.isabs(p):
        return os.path.normpath(p)
    return os.path.normpath(os.path.join(root, p))


def resolve_training_device(device_cfg: str | None) -> str:
    """Ultralytics: \"0\" / [0,1] — CUDA; \"cpu\"; \"mps\" — Apple. gpu/auto — первая CUDA или cpu."""
    if device_cfg is None or not str(device_cfg).strip():
        device_cfg = "0"
    d = str(device_cfg).strip().lower()
    if d in ("gpu", "cuda", "auto"):
        try:
            import torch

            if torch.cuda.is_available():
                return "0"
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        print("⚠ CUDA/MPS недоступны, обучение на CPU.")
        return "cpu"
    return str(device_cfg).strip()


def resolve_model_path(model_name: str, root: str) -> str:
    if os.path.isabs(model_name) and os.path.isfile(model_name):
        return model_name
    if os.path.isfile(model_name):
        return os.path.abspath(model_name)
    for base in (root, str(Path(root).resolve().parent)):
        candidate = os.path.join(base, model_name)
        if os.path.isfile(candidate):
            return candidate
    return model_name


def load_training_config(config_path: str) -> dict[str, Any]:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Ожидался YAML-словарь в конфиге: {config_path}")
    return cfg


def resolve_data_yaml(cfg: dict[str, Any], root: str) -> str:
    if cfg.get("arbuz_repo_dataset"):
        split_seed = cfg.get("dataset_split_seed", cfg.get("seed", 42))
        return prepare_arbuz_repo_dataset(
            root,
            val_ratio=float(cfg.get("val_ratio", 0.15)),
            seed=int(split_seed),
        )

    data_yaml = resolve_path(cfg.get("data_yaml"), root)
    if data_yaml and os.path.isfile(data_yaml):
        return data_yaml

    dataset_path = resolve_path(cfg.get("dataset_path"), root)
    classes = cfg.get("classes")
    if dataset_path and isinstance(classes, list) and len(classes) > 0:
        return create_dataset_yaml(dataset_path, list(classes))

    raise ValueError(
        "Укажите в train_data.yaml: arbuz_repo_dataset: true, либо data_yaml, "
        "либо dataset_path и classes для генерации data.yaml."
    )


def prepare_arbuz_repo_dataset(root: str, val_ratio: float = 0.15, seed: int = 42) -> str:
    """Собирает train/val из папки arbuz-ai/train (каждый .jpg с одноимённым .txt рядом).

    Папка arbuz-ai/test без разметки для YOLO не подходит как val — валидация выделяется из train.
    Пишет configs/data/train_images.txt, val_images.txt и configs/data/arbuz_data.yaml.
    """
    root_p = Path(root).resolve()
    train_dir = root_p / "train"
    if not train_dir.is_dir():
        raise FileNotFoundError(f"Нет каталога train: {train_dir}")

    images: list[Path] = []
    for jpg in train_dir.rglob("*.jpg"):
        if jpg.with_suffix(".txt").is_file():
            images.append(jpg.resolve())

    images.sort()
    if not images:
        raise FileNotFoundError(
            f"Не найдено пар изображение+разметка (.jpg + рядом .txt) под {train_dir}"
        )

    rng = random.Random(int(seed))
    rng.shuffle(images)
    n_val = max(1, int(len(images) * float(val_ratio)))
    val_paths = images[:n_val]
    train_paths = images[n_val:]

    out_dir = root_p / "configs" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    train_txt = out_dir / "train_images.txt"
    val_txt = out_dir / "val_images.txt"
    train_txt.write_text("\n".join(str(p) for p in train_paths), encoding="utf-8")
    val_txt.write_text("\n".join(str(p) for p in val_paths), encoding="utf-8")

    yaml_path = out_dir / "arbuz_data.yaml"
    rel_train = train_txt.relative_to(root_p).as_posix()
    rel_val = val_txt.relative_to(root_p).as_posix()
    data_cfg = {
        "path": str(root_p),
        "train": rel_train,
        "val": rel_val,
        "nc": 2,
        "names": ["vacant", "occupied"],
    }
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data_cfg, f, default_flow_style=False, allow_unicode=True)

    print(f"✅ arbuz-ai/train: train={len(train_paths)} val={len(val_paths)} → {yaml_path}")
    return str(yaml_path)


def create_dataset_yaml(dataset_path: str, classes: list) -> str:

    data_config = {
        'path': dataset_path,
        'train': os.path.join(dataset_path, 'train/images'),
        'val': os.path.join(dataset_path, 'val/images'),
        'nc': len(classes),  # number of classes
        'names': classes  # class names
    }

    yaml_path = os.path.join(dataset_path, 'data.yaml')

    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(data_config, f, default_flow_style=False, allow_unicode=True)

    print(f"✅ Создан файл конфигурации: {yaml_path}")
    return yaml_path


def train_yolo(
    data_yaml: str,
    model_name: str = "yolov8n.pt",
    epochs: int = 100,
    imgsz: int = 640,
    batch: int = 16,
    device: str = "0",
    project: str = "runs/detect",
    experiment_name: str = "my_experiment",
    *,
    exist_ok: bool = True,
    patience: int = 50,
    save_period: int = 10,
    seed: int = 42,
    save_original_weights: bool = True,
    original_weights_filename: str = "original_pretrained.pt",
    repo: str | None = None,
    workers: int | None = None,
):
    root = repo or repo_root()
    model_path = resolve_model_path(model_name, root)
    project_dir = resolve_path(project, root) or project

    print("🚀 Загрузка модели...")
    model = YOLO(model_path)
    pretrained_src = getattr(model, "ckpt_path", None)

    print(f"📊 Начало обучения на {epochs} эпохах...")

    train_kw: dict[str, Any] = dict(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=project_dir,
        name=experiment_name,
        patience=patience,
        save=True,
        save_period=save_period,
        pretrained=True,
        optimizer="auto",
        verbose=True,
        seed=seed,
        val=True,
        plots=True,
        exist_ok=exist_ok,
    )
    if workers is not None:
        train_kw["workers"] = int(workers)
    model.train(**train_kw)

    save_dir = getattr(getattr(model, "trainer", None), "save_dir", None)
    if save_original_weights and pretrained_src:
        src = Path(pretrained_src)
        if src.is_file() and save_dir:
            dest = Path(save_dir) / "weights" / original_weights_filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"💾 Исходная модель (чекпоинт до обучения) сохранена: {dest}")

    print("✅ Обучение завершено!")
    return model


def best_weights_path(model: YOLO) -> str | None:
    save_dir = getattr(getattr(model, "trainer", None), "save_dir", None)
    if not save_dir:
        return None
    p = Path(save_dir) / "weights" / "best.pt"
    return str(p) if p.is_file() else None


def export_model(model_path: str, export_formats: list = None):

    if export_formats is None:
        export_formats = ['onnx']  # ONNX по умолчанию

    model = YOLO(model_path)

    for fmt in export_formats:
        print(f"📦 Экспорт в формат {fmt}...")
        try:
            model.export(format=fmt)
            print(f"✅ Модель экспортирована в {fmt}")
        except Exception as e:
            print(f"❌ Ошибка экспорта в {fmt}: {e}")


def validate_model(model_path: str, data_yaml: str):

    model = YOLO(model_path)
    metrics = model.val(data=data_yaml)

    print("\n📈 Метрики модели:")
    print(f"   mAP50: {metrics.box.map50:.4f}")
    print(f"   mAP50-95: {metrics.box.map:.4f}")
    print(f"   Precision: {metrics.box.mp:.4f}")
    print(f"   Recall: {metrics.box.mr:.4f}")

    return metrics


def test_prediction(model_path: str, image_path: str, save_results: bool = True, show: bool = False):

    model = YOLO(model_path)
    results = model.predict(
        source=image_path,
        save=save_results,
        show=show,
        conf=0.25,  # Порог уверенности
        iou=0.45,  # Порог IoU для NMS
    )

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Обучение YOLO (локально или Google Colab). См. docstring в train.py."
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Корень проекта arbuz-ai (каталоги train/, configs/). В Colab задайте явно, если cwd другой.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Путь к train_data.yaml (абсолютный или относительно --root)",
    )
    args = parser.parse_args()

    root = repo_root(args.root)
    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.is_absolute():
            cfg_path = Path(root) / cfg_path
        config_path = str(cfg_path.resolve())
    else:
        config_path = str(Path(root) / "configs" / "train" / "train_data.yaml")

    if not Path(config_path).is_file():
        raise FileNotFoundError(f"Нет файла конфигурации: {config_path}")

    print(f"📁 Корень проекта: {root}")
    print(f"📄 Конфиг: {config_path}")

    cfg = load_training_config(config_path)
    data_yaml = resolve_data_yaml(cfg, root)

    model_name = str(cfg.get("model_name") or "yolov8n.pt")
    epochs = int(cfg.get("epochs") or 100)
    imgsz = int(cfg.get("imgsz") or 640)
    batch = int(cfg.get("batch") or 8)
    device = resolve_training_device(cfg.get("device"))
    print(f"🖥 Устройство обучения: {device}")
    project = str(cfg.get("project") or "outputs/runs")
    experiment_name = str(cfg.get("experiment_name") or "exp")
    exist_ok = bool(cfg.get("exist_ok", True))
    patience = int(cfg.get("patience") or 50)
    save_period = int(cfg.get("save_period") or 10)
    seed = int(cfg.get("seed") or 42)
    save_original = bool(cfg.get("save_original_weights", True))
    orig_name = str(cfg.get("original_weights_filename") or "original_pretrained.pt")
    workers_raw = cfg.get("workers")
    workers = int(workers_raw) if workers_raw is not None and str(workers_raw).strip() != "" else None

    trained = train_yolo(
        data_yaml=data_yaml,
        model_name=model_name,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=project,
        experiment_name=experiment_name,
        exist_ok=exist_ok,
        patience=patience,
        save_period=save_period,
        seed=seed,
        save_original_weights=save_original,
        original_weights_filename=orig_name,
        repo=root,
        workers=workers,
    )

    best_model_path = best_weights_path(trained)
    if best_model_path:
        validate_model(best_model_path, data_yaml)
        export_list = cfg.get("export_formats")
        if isinstance(export_list, list) and len(export_list) > 0:
            export_model(best_model_path, export_formats=export_list)
        print(f"\n🎉 Готово! Лучшая модель: {best_model_path}")
    else:
        print("\n⚠ Не удалось определить путь к best.pt (проверьте логи обучения).")