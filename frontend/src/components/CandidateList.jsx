import { useState } from 'react'

function ScoreRow({ label, value, hint }) {
  return (
    <div className="score-row" title={hint}>
      <span className="score-label">{label}</span>
      <span className="score-value">{typeof value === 'number' ? value.toFixed(3) : value}</span>
    </div>
  )
}

function PeakTable({ rows, columns, emptyText }) {
  if (!rows.length) return <div className="empty-note">{emptyText}</div>
  return (
    <table className="peak-table">
      <thead>
        <tr>{columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {columns.map((c) => (
              <td key={c.key}>{c.fmt ? c.fmt(r[c.key], r) : r[c.key]}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function CandidateList({ result }) {
  const [expanded, setExpanded] = useState(() => new Set([0]))
  const candidates = result.matching.candidates
  const summary = result.matching.summary

  const toggle = (i) => setExpanded((s) => {
    const n = new Set(s)
    n.has(i) ? n.delete(i) : n.add(i)
    return n
  })

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>候选对照（{summary.n_candidates_evaluated} 条参考全部列出，不做唯一结论）</h3>
      </div>
      <p className="note">
        排序依据：{summary.ordered_by}。{summary.no_unique_conclusion}
      </p>

      {result.matching.shift_scan.enabled && (
        <div className="shift-scan">
          <strong>系统偏移扫描（诊断，不自动应用）</strong>
          <table className="mini-table">
            <thead><tr><th>参考</th><th>零偏移命中</th><th>扫描最佳命中</th><th>建议偏移(°)</th></tr></thead>
            <tbody>
              {result.matching.shift_scan.per_reference.slice(0, 4).map((r) => (
                <tr key={r.reference_code} className={r.suggested_zero_shift_deg !== 0 ? 'warn' : ''}>
                  <td>{r.reference_code}</td>
                  <td>{r.hits_at_zero_shift}</td>
                  <td>{r.best_hits_under_scan}</td>
                  <td>{r.suggested_zero_shift_deg.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">{result.matching.shift_scan.note}</p>
        </div>
      )}

      {candidates.map((c, i) => {
        const open = expanded.has(i)
        const s = c.scores
        return (
          <div key={c.reference_code} className={`candidate ${c.passes_minimum_hits ? 'pass' : 'fail'}`}>
            <div className="candidate-head" onClick={() => toggle(i)}>
              <span className="caret">{open ? '▾' : '▸'}</span>
              <span className="rank">#{i + 1}</span>
              <span className="ref-code">{c.reference_code}</span>
              <span className="ref-name">{c.reference_name}</span>
              <span className={`badge ${c.passes_minimum_hits ? 'ok' : 'no'}`}>
                {c.passes_minimum_hits ? '达到最小命中数' : '未达最小命中数'}
              </span>
              <span className="overall">综合分 {s.overall_score.toFixed(3)}</span>
              <span className="hits">命中 {s.hit_count}</span>
            </div>

            {open && (
              <div className="candidate-body">
                <div className="scores-grid">
                  <ScoreRow label="参考峰被解释比例" value={s.fraction_reference_explained}
                    hint="命中峰数 / 该参考测量范围内的峰数" />
                  <ScoreRow label="样本峰被解释比例" value={s.fraction_sample_explained}
                    hint="命中峰数 / 样本检出峰数" />
                  <ScoreRow label="位置一致性" value={s.position_consistency}
                    hint="1 − 平均|Δ2θ|/平均容差" />
                  <ScoreRow label="RMS Δ2θ (°)" value={s.rms_delta_deg ?? '—'} />
                  <ScoreRow label="强度一致性" value={s.intensity_consistency ?? '—'}
                    hint="归一化相对强度平均吻合度（仅参考）" />
                  <ScoreRow label="范围内缺失峰" value={s.missing_in_range_count}
                    hint="参考有但样本未见，且位于测量角度范围内" />
                </div>

                <div className="prov">来源：{c.provenance}（λ={c.reference_wavelength_angstrom} Å）</div>

                <div className="three-col">
                  <div>
                    <h4 className="ok-text">✔ 命中峰位（{c.matched.length}）</h4>
                    <PeakTable
                      rows={c.matched}
                      columns={[
                        { key: 'sample_two_theta', label: '样本 2θ', fmt: (v) => v.toFixed(3) },
                        { key: 'reference_two_theta', label: '参考 2θ', fmt: (v) => v.toFixed(3) },
                        { key: 'delta', label: 'Δ°', fmt: (v) => v.toFixed(3) },
                        { key: 'reference_hkl', label: 'hkl' },
                        { key: 'reference_intensity_rel', label: '参考 I%' },
                      ]}
                      emptyText="无命中"
                    />
                  </div>
                  <div>
                    <h4 className="warn-text">△ 参考有、样本未见（范围内 {c.missing_in_range.length}）</h4>
                    <PeakTable
                      rows={c.missing_in_range}
                      columns={[
                        { key: 'reference_two_theta', label: '参考 2θ', fmt: (v) => v.toFixed(3) },
                        { key: 'reference_hkl', label: 'hkl' },
                        { key: 'reference_intensity_rel', label: 'I%' },
                      ]}
                      emptyText="范围内无缺失"
                    />
                    {c.missing_outside_measured_range.length > 0 && (
                      <p className="hint">另有 {c.missing_outside_measured_range.length} 个参考峰在测量范围之外。</p>
                    )}
                  </div>
                  <div>
                    <h4 className="err-text">✗ 样本未知峰（{c.unknown_sample_peaks.length}）</h4>
                    <PeakTable
                      rows={c.unknown_sample_peaks}
                      columns={[
                        { key: 'sample_two_theta', label: '样本 2θ', fmt: (v) => v.toFixed(3) },
                        { key: 'sample_fwhm_deg', label: 'FWHM°' },
                        { key: 'position_uncertainty_deg', label: '±°' },
                      ]}
                      emptyText="无未知峰"
                    />
                  </div>
                </div>

                {c.shift_diagnostic && (
                  <p className="shift-note">
                    偏移提示：若假设 zero_shift≈{c.shift_diagnostic.suggested_zero_shift_deg}°，
                    命中数 {c.shift_diagnostic.hits_without_shift} → {c.shift_diagnostic.hits_if_shift_applied}。
                    {c.shift_diagnostic.note}
                  </p>
                )}
                <p className="disclaimer-inline">{c.disclaimer}</p>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
