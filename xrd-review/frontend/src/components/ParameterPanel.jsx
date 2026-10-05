import React from 'react'

const FIELDS = [
  { key: 'wavelength_angstrom', label: '波长 λ (Å)', step: '0.0001' },
  { key: 'zero_offset_deg', label: '零点偏移 (°2θ)', step: '0.01' },
  { key: 'instrument_fwhm_deg', label: '仪器展宽 FWHM (°2θ)', step: '0.01' },
  { key: 'detection_threshold_rel', label: '检测阈值 (%最大值)', step: '0.1' },
  { key: 'noise_sigma_factor', label: '噪声下限倍数 k·σ', step: '0.5' },
  { key: 'match_tolerance_deg', label: '匹配容差 (°2θ，空=自动)', step: '0.01' },
  { key: 'bg_lam', label: '背景刚度 λ (AsLS)', step: '10000' },
  { key: 'bg_p', label: '背景不对称 p (AsLS)', step: '0.001' },
]

/** 全部分析参数显式列出；角度单位固定为度(2θ)，在标题注明。 */
export default function ParameterPanel({ params, onChange }) {
  const set = (key, raw) => {
    if (key === 'match_tolerance_deg' && raw === '') {
      onChange({ ...params, [key]: null })
      return
    }
    const v = parseFloat(raw)
    if (!Number.isNaN(v)) onChange({ ...params, [key]: v })
  }
  return (
    <div className="panel">
      <h2>分析参数（角度单位：度，2θ）</h2>
      <div className="param-grid">
        {FIELDS.map((f) => (
          <React.Fragment key={f.key}>
            <label>{f.label}</label>
            <input
              type="number"
              step={f.step}
              value={params[f.key] ?? ''}
              onChange={(e) => set(f.key, e.target.value)}
            />
          </React.Fragment>
        ))}
      </div>
      <div className="hint">
        零点偏移约定：校正后2θ = 测量值 − 偏移值。归一化只缩放强度，不动峰位。
        匹配容差留空 = 自动时取 max(0.05°, 0.5×FWHM)。
      </div>
    </div>
  )
}
