"""保有銘柄・ウォッチリストの永続化(ローカルJSON)。"""
import json
import os
from threading import Lock

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_LOCK = Lock()


def _path(name: str) -> str:
    return os.path.join(_DATA_DIR, f"{name}.json")


def load(name: str, default):
    """JSONを読み込む。存在しなければdefaultを返す。"""
    path = _path(name)
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save(name: str, data) -> None:
    """JSONへ保存する(簡易ロック付き)。"""
    os.makedirs(_DATA_DIR, exist_ok=True)
    with _LOCK:
        with open(_path(name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
