"""
原子文件写入工具。

直接 `open(path, "w")` + `json.dump` 会在写入中途失败（磁盘满、进程被杀、
序列化异常）时留下**被截断的半个 JSON**，该文件永久不可读。这里改为先写同目录
临时文件、flush+fsync 后再 `os.replace` 原子替换 —— 读方要么看到旧内容，要么
看到完整新内容，不会看到中间态。
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any


def atomic_write_json(path: Any, payload: Any, *, indent: int = 2) -> None:
    target = Path(path)
    tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    finally:
        # os.replace 成功后 tmp 已不存在；失败时清掉残留，避免污染目录列表
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
