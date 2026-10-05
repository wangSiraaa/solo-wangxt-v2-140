import { useState } from 'react'

/** 生成 Markdown 复核报告：物理约定、显式参数、候选依据、缺失/未知峰、未解释部分。 */
export function buildMarkdownReport(result, sampleName) {
  const c = result.convention
  const p = result.peaks
  const lines = []
  lines.push(`# XRD 离线复核报告`)
  lines.push('')
  lines.push(`- 样本：${sampleName || '未命名'}`)
  lines.push(`- 生成时间：${new Date().toLocaleString()}`)
  lines.push(`- 入射波长：**${c.wavelength} ${c.wavelength_unit}**（= ${c.wavelength_angstrom} Å）`)
  lines.push(`- 输入角度单位：${c.input_angle_unit}；内部统一：${c.internal_angle_unit}`)
  lines.push(`- 零点偏移：**${c.zero_shift_deg}°**（约定 ${c.zero_shift_convention}）`)
  const q = p.params
  lines.push(`- 仪器展宽 b_inst：**${q.instrument_fwhm_deg}°**；检测阈值：${q.prominence_sigma}σ` +
    `（噪声 σ=${p.noise_sigma}，绝对阈值=${p.prominence_threshold}）`)
  lines.push(`- FWHM 接受区间：${q.min_fwhm_deg}° – ${q.max_fwhm_deg}°；峰位不确定度系数：${q.uncertainty_fraction}`)
  lines.push('')
  lines.push(`## 检出峰（${p.peaks.length} 个，位置在零点校正后的角轴上读取）`)
  lines.push('')
  lines.push('| 2θ (°) | FWHM (°) | 本征 β (°) | 峰位 ± (°) | 净强度 |')
  lines.push('|---|---|---|---|---|')
  p.peaks.forEach((pk) => {
    lines.push(`| ${pk.two_theta.toFixed(4)} | ${pk.fwhm_deg.toFixed(3)} | ` +
      `${pk.broadening_resolved ? pk.intrinsic_fwhm_deg.toFixed(3) : '≤ 仪器展宽'} | ` +
      `${pk.position_uncertainty_deg.toFixed(3)} | ${pk.intensity_net.toFixed(1)} |`)
  })
  lines.push('')
  if (p.rejected_broad.length) {
    lines.push(`### 超 FWHM 上限（rejected_broad，${p.rejected_broad.length}）`)
    p.rejected_broad.forEach((r) =>
      lines.push(`- ${r.two_theta}°，FWHM=${r.fwhm_deg}°：${r.reason}`))
    lines.push('')
  }

  lines.push('## 候选依据（全部候选按综合分排序，非唯一结论）')
  result.matching.candidates.forEach((cand, i) => {
    const s = cand.scores
    lines.push('')
    lines.push(`### ${i + 1}. ${cand.reference_code} — ${cand.reference_name}` +
      `（${cand.passes_minimum_hits ? '达到' : '未达到'}最小命中数）`)
    lines.push(`- 来源：${cand.provenance}；参考波长 ${cand.reference_wavelength_angstrom} Å`)
    lines.push(`- 命中 **${s.hit_count}**；参考解释率 ${(s.fraction_reference_explained * 100).toFixed(0)}%；` +
      `样本解释率 ${(s.fraction_sample_explained * 100).toFixed(0)}%；` +
      `位置一致性 ${s.position_consistency}；RMS Δ2θ=${s.rms_delta_deg ?? '—'}°；` +
      `强度一致性 ${s.intensity_consistency ?? '—'}；综合分 ${s.overall_score}`)
    if (cand.matched.length) {
      lines.push('- 命中峰位：')
      lines.push('  | 样本 2θ | 参考 2θ | Δ° | hkl | 参考 I% |')
      lines.push('  |---|---|---|---|---|')
      cand.matched.forEach((m) =>
        lines.push(`  | ${m.sample_two_theta.toFixed(3)} | ${m.reference_two_theta.toFixed(3)} | ` +
          `${m.delta.toFixed(3)} | ${m.reference_hkl ?? ''} | ${m.reference_intensity_rel ?? ''} |`))
    }
    if (cand.missing_in_range.length) {
      lines.push(`- **参考有、样本未见（测量范围内 ${cand.missing_in_range.length} 个）：**`)
      cand.missing_in_range.forEach((m) =>
        lines.push(`  - ${m.reference_two_theta.toFixed(3)}° ${m.reference_hkl ?? ''} (I%=${m.reference_intensity_rel})`))
    }
    if (cand.missing_outside_measured_range.length) {
      lines.push(`- 另有 ${cand.missing_outside_measured_range.length} 个参考峰位于测量角度范围之外，无法判定。`)
    }
    if (cand.unknown_sample_peaks.length) {
      lines.push(`- **该候选解释不了的样本未知峰（${cand.unknown_sample_peaks.length} 个）：**`)
      cand.unknown_sample_peaks.forEach((u) =>
        lines.push(`  - ${u.sample_two_theta.toFixed(3)}° (FWHM=${u.sample_fwhm_deg}°, ±${u.position_uncertainty_deg}°)`))
    }
    if (cand.shift_diagnostic) {
      lines.push(`- ⚠ 偏移诊断：若 zero_shift≈${cand.shift_diagnostic.suggested_zero_shift_deg}°，` +
        `命中 ${cand.shift_diagnostic.hits_without_shift}→${cand.shift_diagnostic.hits_if_shift_applied}；` +
        `未自动应用，需人工确认。`)
    }
  })

  lines.push('')
  lines.push('## 未解释部分')
  if (result.unexplained_overall.length) {
    lines.push('以下样本峰不被任何达到最小命中数的候选解释：')
    result.unexplained_overall.forEach((u) =>
      lines.push(`- **${u.two_theta.toFixed(3)}°**（FWHM=${u.fwhm_deg}°，净强度=${u.intensity_net}）`))
    lines.push('')
    lines.push('可能原因：第二相/杂质、制样或仪器伪影、参考谱缺失、参数不当。')
  } else {
    lines.push('- 所有检出峰均至少被一个达标候选解释（但这不等于唯一物相结论）。')
  }
  const scan = result.matching.shift_scan
  if (scan.enabled) {
    const top = scan.per_reference[0]
    if (top && top.suggested_zero_shift_deg !== 0) {
      lines.push(`- 系统偏移扫描提示 ${top.reference_code} 在 zero_shift≈${top.suggested_zero_shift_deg}° 时命中最多` +
        `（${top.hits_at_zero_shift}→${top.best_hits_under_scan}），仅诊断、未自动应用。`)
    }
  }
  lines.push('')
  lines.push('---')
  lines.push(result.disclaimer)
  lines.push('本报告不声称自动完成真实材料鉴定。')
  return lines.join('\n')
}

export default function ReportPanel({ result, sampleName }) {
  const [copied, setCopied] = useState(false)
  if (!result) return null
  const md = buildMarkdownReport(result, sampleName)

  const copy = async () => {
    await navigator.clipboard.writeText(md)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  const download = () => {
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `xrd-review-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>复核报告（候选依据 + 未解释部分）</h3>
        <span>
          <button onClick={copy}>{copied ? '已复制 ✓' : '复制 Markdown'}</button>{' '}
          <button onClick={download}>下载 .md</button>
        </span>
      </div>
      <pre className="report-preview">{md}</pre>
    </div>
  )
}
