from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder


@dataclass(frozen=True)
class DatasetBundle:
    x: np.ndarray
    y: np.ndarray
    meta: pd.DataFrame
    classes: np.ndarray


def _cache_key(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def load_moabb_dataset(
    *,
    moabb_class: str,
    events: list[str],
    subjects: list[int] | None,
    fmin: float,
    fmax: float,
    tmin: float,
    tmax: float,
    resample: float | None,
    drop_eog: bool,
    scale: float,
    cache_dir: Path,
) -> DatasetBundle:
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "moabb_class": moabb_class,
        "events": events,
        "subjects": subjects,
        "fmin": fmin,
        "fmax": fmax,
        "tmin": tmin,
        "tmax": tmax,
        "resample": resample,
        "drop_eog": drop_eog,
        "scale": float(scale),
    }
    key = _cache_key(
        {
            **payload,
        }
    )
    npz_path = cache_dir / f"{key}.npz"
    meta_path = cache_dir / f"{key}_meta.csv"
    classes_path = cache_dir / f"{key}_classes.json"

    if npz_path.exists() and meta_path.exists() and classes_path.exists():
        data = np.load(npz_path, allow_pickle=False)
        x = data["x"]
        y = data["y"]
        meta = pd.read_csv(meta_path)
        classes = np.asarray(json.loads(classes_path.read_text(encoding="utf-8")))
        return DatasetBundle(x=x, y=y, meta=meta, classes=classes)

    # Backward-compatible cache reuse: older cache keys didn't include `scale`.
    legacy_payload = {k: v for k, v in payload.items() if k != "scale"}
    legacy_key = _cache_key(legacy_payload)
    legacy_npz = cache_dir / f"{legacy_key}.npz"
    legacy_meta = cache_dir / f"{legacy_key}_meta.csv"
    legacy_classes = cache_dir / f"{legacy_key}_classes.json"
    if legacy_npz.exists() and legacy_meta.exists() and legacy_classes.exists():
        data = np.load(legacy_npz, allow_pickle=False)
        x = data["x"] * float(scale)
        y = data["y"]
        meta = pd.read_csv(legacy_meta)
        classes = np.asarray(json.loads(legacy_classes.read_text(encoding="utf-8")))

        np.savez_compressed(npz_path, x=x, y=y)
        meta.to_csv(meta_path, index=False)
        classes_path.write_text(json.dumps(classes.tolist(), ensure_ascii=False), encoding="utf-8")
        return DatasetBundle(x=x, y=y, meta=meta, classes=classes)

    from moabb import datasets as moabb_datasets  # heavy import
    from moabb.paradigms import MotorImagery

    dataset_cls = getattr(moabb_datasets, moabb_class, None)
    if dataset_cls is None:
        raise ValueError(f"Unknown MOABB dataset class: {moabb_class}")
    dataset = dataset_cls()

    paradigm = MotorImagery(
        n_classes=len(events),
        events=events,
        fmin=float(fmin),
        fmax=float(fmax),
        tmin=float(tmin),
        tmax=float(tmax),
        resample=resample,
    )

    if drop_eog:
        epochs, y, meta = paradigm.get_data(dataset=dataset, subjects=subjects, return_epochs=True)
        epochs = epochs.copy().pick_types(eeg=True, eog=False, stim=False)
        x = epochs.get_data(copy=False)
    else:
        x, y, meta = paradigm.get_data(dataset=dataset, subjects=subjects)

    x = x * float(scale)
    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    # MOABB meta usually contains: subject, session, run, etc.
    if "subject" not in meta.columns:
        raise RuntimeError("MOABB meta must include 'subject' column for LOSO protocol")

    classes = le.classes_

    np.savez_compressed(npz_path, x=x, y=y_enc)
    meta.to_csv(meta_path, index=False)
    classes_path.write_text(json.dumps(classes.tolist(), ensure_ascii=False), encoding="utf-8")

    return DatasetBundle(x=x, y=y_enc, meta=meta, classes=classes)
