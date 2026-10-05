import { useState } from 'react'

const FIELD_DEFS = [
  // 物理约定
  { key: 'wavelength', label: '波长 λ', type: 'number', step: 0.00001, group: 'convention' },
  { key: 'wavelength_unit', label: '波长单位', type: 'select', options: ['angstrom', 'nm'], group: 'convention' },
  { key: 'angle_unit', label: '角度单位', type: 'select',
    options: ['2theta_deg', 'theta_deg', '2theta_rad', 'theta_rad'], group: 'convention' },
  { key: 'zero_shift', label: '零点偏移 (°)', type: 'number', step: 0.01, group: 'convention',
    hint: '约定：2θ_true = 2θ_measured − zero_shift；只使用显式值' },
  // 背景
  { key: 'bg_window', label: 'SNIP 窗口(点)', type: 'number', step: 1, group: 'background' },
  { key: 'bg_iterations', label: 'SNIP 迭代', type: 'number', step: 1, group: 'background' },
  { key: 'bg_smoothing', label: '平滑窗口(点)', type: 'number', step: 2, group: 'background' },
  // 检测
  { key: 'prominence_sigma', label: '检测阈值 (σ 倍数)', type: 'number', step: 0.5, group: 'detection',
    hint: '阈值 = prominence_sigma × 1.4826 × MAD(去背景谱)' },
  { key: 'min_separation_deg', label: '最小峰间距 (°)', type: 'number', step: 0.01, group: 'detection' },
  { key: 'min_fwhm_deg', label: '最小 FWHM (°)', type: 'number', step: 0.01, group: 'detection' },
  { key: 'max_fwhm_deg', label: '最大 FWHM (°)', type: 'number', step: 0.1, group: 'detection',
    hint: '超过此宽的峰进入 rejected_broad 显式列出，不静默丢弃' },
  { key: 'instrument_fwhm_deg', label: '仪器展宽 b_inst (°)', type: 'number', step: 0.01, group: 'detection',
    hint: '仅用于反卷积估计本征宽化 β=√(B²−b_inst²)，不改变峰位' },
  { key: 'uncertainty_fraction', label: '峰位不确定度系数', type: 'number', step: 0.01, group: 'detection' },
  // 匹配
  { key: 'tolerance_deg', label: '匹配容差 Δ2θ (°)', type: 'number', step: 0.01, group: 'matching' },
  { key: 'minimum_hits', label: '最小命中数', type: 'number', step: 1, group: 'matching' },
  { key: 'shift_scan_max', label: '偏移扫描范围 (°)', type: 'number', step: 0.1, group: 'matching' },
  { key: 'shift_scan_step', label: '偏移扫描步长 (°)', type: 'number', step: 0.01, group: 'matching' },
]

const GROUP_LABELS = {
  convention: '① 物理约定（必须明确）',
  background: '② 去背景参数（SNIP）',
  detection: '③ 检测阈值与仪器展宽（显式）',
  matching: '④ 匹配参数',
}

export default function ParameterPanel({ params, onChange, onAnalyze, busy, targets, onPickTarget }) {
  const [openGroup, setOpenGroup] = useState({ convention: true, background: true, detection: true, matching: true })
  const groups = ['convention', 'background', 'detection', 'matching']

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>分析参数</h3>
        <button className="primary" onClick={onAnalyze} disabled={busy}>
          {busy ? '分析中…' : '运行复核'}
        </button>
      </div>
      {groups.map((g) => (
        <div key={g} className="param-group">
          <div className="group-title" onClick={() => setOpenGroup((s) => ({ ...s, [g]: !s[g] }))}>
            <span>{openGroup[g] ? '▾' : '▸'}</span> {GROUP_LABELS[g]}
          </div>
          {openGroup[g] && (
            <div className="group-body">
              {FIELD_DEFS.filter((f) => f.group === g).map((f) => (
                <label key={f.key} className="field">
                  <span className="field-label">{f.label}</span>
                  {f.type === 'select' ? (
                    <select
                      value={params[f.key]}
                      onChange={(e) => onChange(f.key, e.target.value)}
                    >
                      {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      type="number"
                      step={f.step}
                      value={params[f.key]}
                      onChange={(e) => onChange(f.key, parseFloat(e.target.value))}
                    />
                  )}
                  {f.key === 'wavelength' && targets && (
                    <span className="targets">
                      {Object.entries(targets).map(([name, wl]) => (
                        <button
                          key={name}
                          type="button"
                          className="chip"
                          title={`${name} = ${wl} Å`}
                          onClick={() => onPickTarget(wl)}
                        >
                          {name.replace('_', ' ')}
                        </button>
                      ))}
                    </span>
                  )}
                  {f.hint && <span className="hint">{f.hint}</span>}
                </label>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
