-- 离线 XRD 复核台：参考谱库 schema
-- PostgreSQL 13+。参考条目只保存开放/自制教学数据，不含任何付费数据库内容。

CREATE TABLE IF NOT EXISTS reference_entries (
    code            TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    structure       TEXT,                       -- SC/BCC/FCC/DIAMOND/NACL/CSCL/FLUORITE/CUSTOM
    a_angstrom      DOUBLE PRECISION,
    wavelength_angstrom DOUBLE PRECISION NOT NULL,
    source          TEXT NOT NULL DEFAULT 'builtin_synthetic',
                        -- builtin_synthetic | user_peaklist | user_cubic
    provenance      TEXT NOT NULL,
    params_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reference_peaks (
    id              BIGSERIAL PRIMARY KEY,
    reference_code  TEXT NOT NULL REFERENCES reference_entries(code) ON DELETE CASCADE,
    two_theta       DOUBLE PRECISION NOT NULL,
    intensity_rel   DOUBLE PRECISION NOT NULL DEFAULT 0,
    hkl             TEXT,
    d_angstrom      DOUBLE PRECISION,
    multiplicity    INTEGER,
    ord             INTEGER NOT NULL DEFAULT 0,
    UNIQUE (reference_code, ord)
);

CREATE INDEX IF NOT EXISTS idx_ref_peaks_code ON reference_peaks(reference_code);

-- 分析留档（可选功能；不用于"自动鉴定"，只保存师生的复核记录与所用显式参数）
CREATE TABLE IF NOT EXISTS analysis_runs (
    id              BIGSERIAL PRIMARY KEY,
    label           TEXT,
    request_json    JSONB NOT NULL,
    result_json     JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
