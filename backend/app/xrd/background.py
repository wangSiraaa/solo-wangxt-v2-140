"""背景估计：SNIP（Statistics-sensitive Non-linear Iterative Peak-clipping）。

参数全部显式给出，不做隐藏默认之外的假设：
* window —— SNIP 迭代的最大窗口（单位：采样点），窗口越大背景越平滑；
* iterations —— 每个窗口尺度的迭代次数；
* smoothing —— 迭代前 LLS（对数-对数）平滑窗口（奇数个采样点）。

原始谱不会被修改；返回背景曲线与去背景谱（负值裁剪为 0）。
"""

from __future__ import annotations

import numpy as np


def snip_background(y, window: int = 40, iterations: int = 24, smoothing: int = 3) -> np.ndarray:
    """一维强度谱的 SNIP 背景估计。

    window/iterations 共同决定可被当作"峰"扣除的最大尺度；
    smoothing 为 LLS 变换前的简单滑动平均窗口（<=1 表示不平滑）。
    """
    y = np.asarray(y, dtype=float)
    n = y.size
    if n < 5:
        return np.zeros_like(y)
    window = max(1, int(window))
    iterations = max(1, int(iterations))

    # LLS（log-log-square）变换，压缩强峰动态范围
    offset = float(np.min(y))
    shifted = y - offset
    v = np.log(np.log(np.sqrt(np.maximum(shifted, 0) + 1.0) + 1.0) + 1.0)

    if smoothing and smoothing > 1:
        w = int(smoothing)
        if w % 2 == 0:
            w += 1
        kernel = np.ones(w) / w
        v = np.convolve(np.pad(v, w // 2, mode="edge"), kernel, mode="valid")

    # 窗口序列：1..window（可按 iterations 抽样）
    if iterations >= window:
        widths = np.arange(1, window + 1)
    else:
        widths = np.unique(np.linspace(1, window, iterations, dtype=int))

    # 边值用边缘常数填充，避免滚绕污染
    padded = np.pad(v, window, mode="edge")

    def _slice(offset: int) -> np.ndarray:
        return padded[window + offset : window + offset + n]

    for p in widths:
        candidate = 0.5 * (_slice(-p) + _slice(p))
        v = np.minimum(v, candidate)

    # 逆 LLS
    bg = (np.exp(np.exp(v) - 1.0) - 1.0) ** 2 - 1.0 + offset
    return np.minimum(bg, y)


def subtract_background(y, window: int = 40, iterations: int = 24, smoothing: int = 3):
    """返回 (background, net)。net 为去背景谱，负值裁剪到 0（不影响峰位）。"""
    y = np.asarray(y, dtype=float)
    bg = snip_background(y, window=window, iterations=iterations, smoothing=smoothing)
    net = np.maximum(y - bg, 0.0)
    return bg, net
