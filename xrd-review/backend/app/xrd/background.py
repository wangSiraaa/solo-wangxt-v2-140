"""背景扣除：非对称最小二乘 (AsLS, Eilers & Boelens 2005)。

lam 与 p 是显式参数，由请求传入并回显在报告里；
原始谱始终与去背景谱一并返回，前端并列展示。
"""
from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

DEFAULT_LAM = 1.0e5
DEFAULT_P = 0.01
DEFAULT_NITER = 10


def als_background(y: np.ndarray, lam: float = DEFAULT_LAM, p: float = DEFAULT_P,
                   niter: int = DEFAULT_NITER) -> np.ndarray:
    """返回估计的背景曲线（与 y 等长）。"""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 5:
        return np.zeros_like(y)
    # 二阶差分矩阵
    d = sparse.diags([1.0, -2.0, 1.0], [0, 1, 2], shape=(n - 2, n), format="csc")
    smooth = lam * (d.T @ d)
    w = np.ones(n)
    z = np.zeros(n)
    for _ in range(niter):
        w_mat = sparse.spdiags(w, 0, n, n)
        z = spsolve(w_mat + smooth, w * y)
        w = p * (y > z) + (1.0 - p) * (y <= z)
    return z
