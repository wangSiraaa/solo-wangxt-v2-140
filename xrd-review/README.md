# XRD 离线复核台（课程教学用）

用一组衍射峰对照样品谱与参考条目，给出**带证据的候选列表**而非唯一结论。
全离线运行：React + Plotly.js 前端、FastAPI + SciPy 分析后端、PostgreSQL 存
放开放/自制示例参考谱，**不访问任何付费数据库**。

> 本工具仅用于课程教学中的谱线对照练习，不构成也不替代真实材料鉴定。
> 参考数据为教科书公开值或自制示例，未做精度核验。

## 快速开始

```bash
docker compose up --build      # 打开 http://localhost:8000
```

本地开发（无需 Docker）：

```bash
# 后端（默认连 PostgreSQL；本地试用可指定 SQLite）
cd backend
pip install -r requirements.txt
DATABASE_URL="sqlite:///./xrd_dev.db" uvicorn app.main:app --reload

# 前端（另开终端，代理到 :8000）
cd frontend && npm install && npm run dev   # http://localhost:5173

# 测试（三类必需案例 + 不变量）
cd backend && DATABASE_URL="sqlite:///:memory:" python3 -m pytest tests/ -q
```

## 显式约定（界面与报告中均回显）

| 约定 | 取值 |
|---|---|
| 角度单位 | 度（°），扫描轴 2θ |
| 波长 | Å，默认 Cu Kα1 = 1.5406，可改 |
| 零点偏移 | `校正后2θ = 测量值 − zero_offset_deg` |
| 强度归一化 | 只缩放强度（最高=100），**峰位不变**（有测试保证） |
| 仪器展宽 | FWHM（°2θ），显式参数，影响最小峰宽与自动容差 |
| 检测阈值 | 相对去背景最大值的百分比 + k·σ 噪声下限（σ=c·√N 局部曲线，MAD 标定） |
| 匹配容差 | 显式参数；留空自动取 `max(0.05°, 0.5×FWHM)` |

## 分析流水线

原始谱 → 零点偏移校正（平移角度轴）→ AsLS 背景估计（λ、p 显式）→
去背景谱上寻峰（Savitzky-Golay 平滑仅用于定位，峰位/峰高取自未平滑谱，
抛物线亚步长细化）→ 归一化 → 与库内**全部**参考条目逐一做匈牙利一对一配峰。

每个候选返回：命中峰对（含 Δ2θ）、**参考有而样品未见的峰**、
**样品中该候选解释不了的峰**、覆盖率、可解释分数、综合分
（0.5×覆盖率+0.5×可解释，仅用于排序）。候选不裁剪、不下唯一结论。
原始谱与去背景谱在前端并列展示。

## 三类测试案例（`backend/tests/test_xrd.py`）

1. **单相合成谱**：由参考条目合成（高斯峰+背景+泊松噪声），该条目须排首位，
   覆盖率>0.9，峰位误差<0.02°；
2. **系统偏移**：峰位整体 +0.15°，不校正时残差≈0.15°、匹配崩溃；
   设 `zero_offset_deg=0.15` 后恢复（残差<0.02°）；
3. **宽峰**：FWHM=0.6°，显式传入仪器展宽后自动容差放大为 0.3°，仍正确匹配。

另验证：归一化不改峰位；缺失峰与未解释峰必须列出；API 端到端一致。

## API 摘要

- `GET  /api/references` — 参考条目列表（含 d–I 峰表、来源标注）
- `POST /api/references` — 添加自制参考条目
- `POST /api/analyze` — 样品谱 + 全部显式参数 → 峰表 + 候选证据 + 约定回显
- `POST /api/synthetic` — 由参考条目合成测试谱（可注入偏移/宽峰/噪声）
- `GET  /api/health` — 约定与免责声明

## 目录

```
backend/app/xrd/    units(约定) background(AsLS) peaks(寻峰) matching(匹配) synthetic(合成)
backend/tests/      三类案例与不变量测试
frontend/src/       React + Plotly 界面（参数面板/并列谱图/候选证据/报告）
docker-compose.yml  PostgreSQL + 应用（前端构建进同一镜像）
```
