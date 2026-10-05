import React from 'react'
import createPlotlyComponent from 'react-plotly.js/factory'
import Plotly from 'plotly.js-dist-min'

const Plot = createPlotlyComponent(Plotly)

/** 候选列表 + 选中候选的证据明细（命中/缺失/未解释）+ 峰位对照棒图。 */
export default function CandidatePanel({ result, selected, onSelect }) {
  if (!result) return null
  const cands = result.candidates
  const sel = cands[selected]

  return (
    <div className="panel">
      <h2>候选物相（按综合分排序，非唯一结论）</h2>
      <table>
        <thead>
          <tr>
            <th>物相</th><th>化学式</th><th>综合分</th><th>覆盖率</th>
            <th>可解释</th><th>命中数</th><th>缺失</th><th>未解释</th><th>均|Δ2θ|</th>
          </tr>
        </thead>
        <tbody>
          {cands.map((c, i) => (
            <tr key={c.reference_id}
                className={`clickable ${i === selected ? 'selected' : ''}`}
                onClick={() => onSelect(i)}>
              <td>{c.name}</td>
              <td>{c.formula}</td>
              <td>{c.score.toFixed(3)}</td>
              <td>{(c.coverage * 100).toFixed(0)}%</td>
              <td>{(c.explained_fraction * 100).toFixed(0)}%</td>
              <td>{c.n_matched}</td>
              <td>{c.missing_ref_peaks.length}</td>
              <td>{c.unexplained_sample_peaks.length}</td>
              <td>{c.mean_abs_delta_deg == null ? '—' : c.mean_abs_delta_deg.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="hint">
        综合分 = 0.5×覆盖率 + 0.5×可解释分数（覆盖率=命中参考峰强度占比，可解释=样品峰被解释强度占比），仅用于排序。
      </div>
      {sel && <CandidateDetail cand={sel} />}
    </div>
  )
}

function CandidateDetail({ cand }) {
  const stickTraces = [
    {
      x: cand.matched.map((m) => m.sample_two_theta),
      y: cand.matched.map((m) => m.sample_intensity),
      type: 'bar', name: '样品峰（已匹配）', marker: { color: '#2f6fed' }, width: 0.08,
    },
    {
      x: cand.matched.map((m) => m.ref_two_theta),
      y: cand.matched.map((m) => -m.ref_intensity),
      type: 'bar', name: '参考峰（已命中）', marker: { color: '#1e7e34' }, width: 0.08,
    },
    {
      x: cand.missing_ref_peaks.map((p) => p.two_theta_deg),
      y: cand.missing_ref_peaks.map((p) => -p.intensity_rel),
      type: 'bar', name: '参考有·样品未见', marker: { color: '#c62828' }, width: 0.08,
    },
    {
      x: cand.unexplained_sample_peaks.map((p) => p.two_theta_deg),
      y: cand.unexplained_sample_peaks.map((p) => p.intensity_norm),
      type: 'bar', name: '样品未解释峰', marker: { color: '#b26a00' }, width: 0.08,
    },
  ]
  const layout = {
    height: 260, margin: { t: 10, r: 10, b: 40, l: 50 },
    barmode: 'overlay',
    legend: { orientation: 'h', y: 1.18, font: { size: 11 } },
    xaxis: { title: '2θ (deg)' },
    yaxis: { title: '样品 + / 参考 −' },
  }

  return (
    <div style={{ marginTop: 10 }}>
      <h2 style={{ fontSize: 13 }}>
        证据明细：{cand.name}（容差 ±{cand.tolerance_deg.toFixed(3)}°）
        <span className="badge hit">命中 {cand.n_matched}</span>
        <span className="badge miss">缺失 {cand.missing_ref_peaks.length}</span>
        <span className="badge unknown">未解释 {cand.unexplained_sample_peaks.length}</span>
      </h2>
      <Plot data={stickTraces} layout={layout} style={{ width: '100%' }}
            config={{ displaylogo: false, responsive: true }} />
      <table>
        <thead>
          <tr><th>样品 2θ</th><th>参考 2θ</th><th>Δ2θ</th><th>样品 I</th><th>参考 I</th></tr>
        </thead>
        <tbody>
          {cand.matched.map((m, i) => (
            <tr key={i}>
              <td>{m.sample_two_theta.toFixed(3)}</td>
              <td>{m.ref_two_theta.toFixed(3)}</td>
              <td>{m.delta_two_theta >= 0 ? '+' : ''}{m.delta_two_theta.toFixed(3)}</td>
              <td>{m.sample_intensity.toFixed(1)}</td>
              <td>{m.ref_intensity.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {cand.missing_ref_peaks.length > 0 && (
        <div className="hint">
          参考有而样品未见（2θ / d Å / 相对强度）：
          {cand.missing_ref_peaks.map((p) =>
            ` ${p.two_theta_deg.toFixed(2)}°(${p.d_angstrom.toFixed(3)}Å,${p.intensity_rel})`).join('；')}
        </div>
      )}
      {cand.unexplained_sample_peaks.length > 0 && (
        <div className="hint">
          样品中本候选解释不了的峰（2θ / 归一强度）：
          {cand.unexplained_sample_peaks.map((p) =>
            ` ${p.two_theta_deg.toFixed(2)}°(${p.intensity_norm.toFixed(1)})`).join('；')}
        </div>
      )}
    </div>
  )
}
