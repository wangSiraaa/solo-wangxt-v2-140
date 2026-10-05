# 离线 XRD 复核台（教学用）

用一组衍射峰**复核**可能物相的课堂工具：把样本谱与开放/自制参考条目逐条对照，
列出命中、参考有而样本未见的缺失峰、样本有而参考解释不了的未知峰，
并给出多维度候选依据。

> **定位声明**：本工具是离线**复核台**，不是自动物相鉴定器。
> 它不输出"唯一物相"结论，不访问 ICDD/PDF 等付费数据库，
> 不声称自动完成真实材料鉴定。最终判断须由人结合化学背景与全部依据作出。

## 技术栈

| 部分 | 技术 |
|---|---|
| 前端 | React 18 + Plotly.js（Vite 构建），样本谱/去背景谱并列、候选依据表、Markdown 报告 |
| 后端 | FastAPI + SciPy（`find_peaks`、抛物线亚点修正、SNIP 背景、布拉格定律） |
| 数据库 | PostgreSQL（psycopg3），保存开放/自制参考谱与分析留档；无 DSN 时退化为内存库便于测试 |

## 目录

```
backend/
  app/
    xrd/units.py        波长(Å/nm)、角度(2θ°/θ°/弧度)、零点偏移的显式换算
    app/xrd/references.py  立方结构合成参考谱（SC/BCC/FCC/金刚石/NaCl/CsCl/萤石）
    app/xrd/background.py  SNIP 背景
    app/xrd/peaks.py    峰检测：阈值σ、最小/最大FWHM、仪器展宽反卷积
    app/xrd/matching.py 全候选对照 + 系统偏移扫描诊断（不自动应用）
    app/xrd/synthesize.py 教学合成谱（单相/偏移/宽峰/两相/未知峰）
    app/xrd/pipeline.py 总流水线（归一化谱仅展示，不参与检测/匹配）
    db.py schema.sql seed.py main.py service.py schemas.py
  tests/                pytest（算法 + API；真实 PG 联调单独开关）
frontend/               React + Plotly 界面
```

## 物理约定（在界面与每份结果中显式回显）

- 内部角度一律 **2θ 角度制**；输入支持 `2theta_deg / theta_deg / 2theta_rad / theta_rad`。
- 波长必须显式给出，支持 Å 与 nm（1 nm = 10 Å）；界面提供常见靶材快捷值但不隐藏默认。
- 零点偏移约定：**2θ_true = 2θ_measured − zero_shift**；只使用用户显式填入的值。
  "系统偏移扫描"只给诊断提示，即使能提高命中数也**绝不自动应用**。
- **峰强归一化不改峰位置**：检测与匹配使用未归一化数据；界面额外返回
  原始/去背景两条归一化曲线仅供视觉对照。
- 仪器展宽 `instrument_fwhm_deg` 只用于 β = √(B² − b_inst²) 的本征宽化估计，不改变峰位。
- 检测阈值显式：阈值 = `prominence_sigma × 1.4826 × MAD(去背景谱)`。
- 宽峰不静默丢弃：FWHM > `max_fwhm_deg` 的峰进入 `rejected_broad` 并说明原因。

## 候选如何呈现（不按命中数给唯一结论）

每个参考条目（无论是否达标）都返回：

- `matched`：样本 2θ / 参考 2θ / Δ / hkl / 参考相对强度；
- `missing_in_range`：**参考有、样本未见**且在测量角度范围内的峰；
- `missing_outside_measured_range`：范围外无法判定的参考峰；
- `unknown_sample_peaks`：**该候选解释不了的样本峰**；
- 六个独立量：参考解释率、样本解释率、位置一致性、RMS Δ2θ、强度一致性、范围内缺失数；
- 综合分只用于排序；未达 `minimum_hits` 的候选也完整保留。

另有跨候选的 `unexplained_overall`：任何达标候选都解释不了的样本峰，
在界面与 Markdown 报告中必须保留。

## 快速启动

需要 Python 3.11+ 与 Node 18+，PostgreSQL 13+（可选；不配置则后端用内存库）。

### 1. 后端

```bash
cd backend
python3 -m pip install -r requirements.txt
export DATABASE_URL="postgresql://USER@/DBNAME?host=/var/run/postgresql"  # 可选
python3 -m app.seed          # 建表并写入 8 条内置开放教学参考谱
uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173 ，/api 代理到 8000
```

打开页面 → 左侧选择教学用例（建议依次试"系统偏移""宽峰""未知峰"）。

## 测试

```bash
cd backend
python3 -m pytest tests/test_algorithm.py tests/test_api.py -q      # 内存库，无需 PG
# 真实 PostgreSQL 联调（需要 DATABASE_URL 指向可清空的库）：
DATABASE_URL="postgresql://xrd@/xrdbench?host=/tmp&port=55432" \
  python3 -m pytest tests/test_db_postgres.py -q
```

覆盖的教学案例：

| 用例 | 期望表现 |
|---|---|
| `single_clean` 单相 Cu | Cu 全命中，缺失/未知均为 0，其余候选不达标 |
| `systematic_shift` 注入 +0.60° | 不校正时命中下降，偏移扫描提示正值；显式填 0.60 后恢复 |
| `broad_peaks` 宽化 Si + 鼓包 | 鼓包残峰进入 `rejected_broad`，Si 本征 β 明显大于仪器展宽 |
| `mixture` Cu + 弱 Fe | 两个候选都达标，Fe 解释 Cu 解释不了的峰；不产生唯一结论 |
| `weak_unknown` Al + 两杂质峰 | 34.2°/57.6° 始终作为未知/未解释峰列出，不被最佳候选吸收 |

## 自制参考谱

界面右侧"新增自制参考"支持：

1. **手输峰表**（每行 `2θ°, 相对强度%, hkl?`），必须填来源/精度说明（provenance）；
2. **立方结构参数合成**（结构类型 + 晶格常数 + 显式波长，按消光规则生成）。

内置条目标 `builtin_synthetic` 不可删除；自制条目可删。所有条目都在
`provenance` 字段中注明"非 ICDD 数据"及近似来源。
