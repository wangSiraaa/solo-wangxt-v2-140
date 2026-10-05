import React from 'react'
import createPlotlyComponent from 'react-plotly.js/factory'
import Plotly from 'plotly.js-dist-min'

const Plot = createPlotlyComponent(Plotly)

/** 原始谱（含背景曲线）与去背景谱（含检出峰标记）并列展示。 */
export default function SpectrumPlot({ result }) {
  if (!result) return null
  const x = result.raw.two_theta_deg
  const raw = result.raw.intensity
  const bg = result.background
  const sub = result.background_subtracted
  const peaks = result.peaks

  const traces = [
    { x, y: raw, name: '原始谱', type: 'scatter', mode: 'lines',
      line: { color: '#1f2a44', width: 1 }, xaxis: 'x', yaxis: 'y' },
    { x, y: bg, name: 'AsLS 背景', type: 'scatter', mode: 'lines',
      line: { color: '#d62728', width: 1, dash: 'dash' }, xaxis: 'x', yaxis: 'y' },
    { x, y: sub, name: '去背景谱', type: 'scatter', mode: 'lines',
      line: { color: '#2f6fed', width: 1 }, xaxis: 'x2', yaxis: 'y2' },
    {
      x: peaks.map((p) => p.two_theta_deg),
      y: peaks.map((p) => p.height_abs),
      name: `检出峰 (${peaks.length})`,
      type: 'scatter', mode: 'markers',
      marker: { color: '#1e7e34', size: 7, symbol: 'triangle-down' },
      xaxis: 'x2', yaxis: 'y2',
      text: peaks.map((p) =>
        `2θ=${p.two_theta_deg.toFixed(3)}° I=${p.intensity_norm.toFixed(1)} d=${p.d_angstrom.toFixed(3)}Å`),
      hoverinfo: 'text',
    },
  ]

  const layout = {
    height: 340,
    margin: { t: 30, r: 10, b: 40, l: 55 },
    showlegend: true,
    legend: { orientation: 'h', y: 1.12, font: { size: 11 } },
    xaxis: { domain: [0, 0.46], title: '2θ (deg)' },
    yaxis: { title: '原始强度 (counts)' },
    xaxis2: { domain: [0.54, 1], title: '2θ (deg)' },
    yaxis2: { title: '去背景强度 (counts)' },
  }

  return <Plot data={traces} layout={layout} style={{ width: '100%' }}
               config={{ displaylogo: false, responsive: true }} />
}
