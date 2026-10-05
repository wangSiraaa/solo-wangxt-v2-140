import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'

/**
 * 原始谱与去背景谱并列（同图双纵轴式叠加 + 独立子图）。
 * 峰标记来自后端在角轴上检出的位置；归一化只影响视觉，不参与任何计算。
 */
export default function SpectrumPlot({ result }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!ref.current || !result) return
    const c = result.curves
    const x = c.two_theta_corrected
    const showNorm = true // 同时给原始/去背景的归一化轨迹（视觉对照）

    const traces = [
      {
        x, y: c.raw_intensity, type: 'scattergl', mode: 'lines',
        name: '原始谱', line: { color: '#1f5fa8', width: 1.4 },
        xaxis: 'x', yaxis: 'y',
      },
      {
        x, y: c.background, type: 'scattergl', mode: 'lines',
        name: 'SNIP 背景', line: { color: '#c0712c', width: 1.2, dash: 'dash' },
        xaxis: 'x', yaxis: 'y',
      },
      {
        x, y: c.net_intensity, type: 'scattergl', mode: 'lines',
        name: '去背景谱', line: { color: '#2e8b57', width: 1.4 },
        xaxis: 'x2', yaxis: 'y2',
      },
      {
        x, y: c.raw_normalized.map((v) => v * 100), type: 'scattergl', mode: 'lines',
        name: '原始(归一化×100，仅展示)', line: { color: '#8aa6c8', width: 0.9, dash: 'dot' },
        visible: showNorm ? true : 'legendonly',
        xaxis: 'x2', yaxis: 'y2',
      },
    ]

    const peakX = result.peaks.peaks.map((p) => p.two_theta)
    const peakY = result.peaks.peaks.map(() => Math.max(...c.net_intensity))
    traces.push({
      x: peakX, y: peakY, type: 'scattergl', mode: 'markers+text',
      name: `检出峰 (${peakX.length})`,
      marker: { symbol: 'triangle-down', size: 10, color: '#b3261e' },
      text: result.peaks.peaks.map((p) => p.two_theta.toFixed(2)),
      textposition: 'top center', textfont: { size: 9 },
      xaxis: 'x2', yaxis: 'y2',
      hovertemplate: '%{x:.3f}°<extra>检出峰</extra>',
    })

    // 最佳达标候选的参考峰杆：命中=绿（实），范围内缺失=橙（虚），样本未知峰=红菱形
    const topPass = result.matching.candidates.find((cc) => cc.passes_minimum_hits)
    if (topPass) {
      const netMax = Math.max(...c.net_intensity)
      const stems = (rows, posKey, color, dash, label) => {
        const sx = [], sy = []
        rows.forEach((r) => {
          const px = r[posKey]
          const amp = (Math.min(r.reference_intensity_rel ?? 60, 100) / 100) * netMax * 0.95
          sx.push(px, px, null); sy.push(0, amp, null)
        })
        return {
          x: sx, y: sy, type: 'scattergl', mode: 'lines', name: label,
          line: { color, width: 1.4, dash }, xaxis: 'x2', yaxis: 'y2', hoverinfo: 'skip',
        }
      }
      traces.push(stems(topPass.matched, 'reference_two_theta', '#1d7a46', 'solid',
        `${topPass.reference_code} 命中参考峰杆`))
      if (topPass.missing_in_range.length) {
        traces.push(stems(topPass.missing_in_range, 'reference_two_theta', '#d08a1f', 'dash',
          `${topPass.reference_code} 缺失参考峰（范围内）`))
      }
      if (topPass.unknown_sample_peaks.length) {
        traces.push({
          x: topPass.unknown_sample_peaks.map((u) => u.sample_two_theta),
          y: topPass.unknown_sample_peaks.map(() => netMax * 0.9),
          type: 'scattergl', mode: 'text',
          name: `${topPass.reference_code} 解释不了的样本未知峰`,
          text: topPass.unknown_sample_peaks.map(() => '?'),
          textfont: { size: 16, color: '#b3261e' },
          xaxis: 'x2', yaxis: 'y2', hovertemplate: '%{x:.3f}° 未知峰<extra></extra>',
        })
      }
    }

    const broadX = result.peaks.rejected_broad.map((p) => p.two_theta)
    if (broadX.length) {
      traces.push({
        x: broadX, y: broadX.map(() => Math.max(...c.raw_intensity) * 0.98),
        type: 'scattergl', mode: 'markers',
        name: `超宽上限/rejected_broad (${broadX.length})`,
        marker: { symbol: 'x', size: 12, color: '#8b0000', line: { width: 2 } },
        xaxis: 'x', yaxis: 'y',
      })
    }

    const layout = {
      height: 560,
      grid: { rows: 2, columns: 1, pattern: 'independent' },
      margin: { l: 60, r: 40, t: 30, b: 50 },
      hovermode: 'x unified',
      legend: { orientation: 'h', y: -0.12 },
      xaxis: { title: { text: '上图 2θ (°，已做显式零点校正)' } },
      yaxis: { title: { text: '原始强度 (counts)' } },
      xaxis2: { title: { text: '下图 2θ (°)' } },
      yaxis2: { title: { text: '去背景强度' } },
    }
    Plotly.react(ref.current, traces, layout, { responsive: true, scrollZoom: true })
  }, [result])

  return <div ref={ref} className="plot" />
}
