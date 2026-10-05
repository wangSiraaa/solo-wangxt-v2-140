"""谱数据解析：支持 CSV/TSV 文本（两列：角度、强度）。

规则显式且宽容：
* 分隔符支持逗号、空白、制表符、分号；
* 以 # 开头或首字段无法解析为数字的行视为表头/注释并跳过；
* 单位由调用方显式传入，解析器不猜测单位。
"""

from __future__ import annotations

import io
import re

import numpy as np


def parse_spectrum_text(text: str) -> dict:
    angles, intensities = [], []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p for p in re.split(r"[,\s;]+", line) if p]
        if len(parts) < 2:
            raise ValueError(f"第 {lineno} 行无法解析为两列：{line!r}")
        try:
            a, i = float(parts[0]), float(parts[1])
        except ValueError:
            # 表头行，静默跳过
            continue
        angles.append(a)
        intensities.append(i)
    if len(angles) < 5:
        raise ValueError("有效数据点不足 5 个，无法进行峰分析")
    order = np.argsort(angles)
    return {
        "two_theta": [angles[k] for k in order],
        "intensity": [intensities[k] for k in order],
        "n_points": len(angles),
    }
