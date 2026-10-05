import React from 'react'

/** 文本报告：分析约定、候选依据、未解释部分、免责声明。 */
export default function ReportPanel({ result, sampleLabel }) {
  if (!result) return null
  const c = result.conventions
  const lines = []
  lines.push(`XRD 复核报告 —— ${sampleLabel || '未命名样品'}`)
  lines.push('='.repeat(56))
  lines.push('【分析约定（显式参数）】')
  lines.push(`  角度单位：${c.angle_unit}；波长：${c.wavelength_angstrom} Å`)
  lines.push(`  零点偏移约定：${c.zero_offset_convention}；本次取值：${c.zero_offset_deg}°`)
  lines.push(`  仪器展宽 FWHM：${c.instrument_fwhm_deg}°；检测阈值：${c.detection_threshold_rel}%（相对最大强度）`)
  lines.push(`  噪声下限倍数：${c.noise_sigma_factor ?? '默认'}；匹配容差：±${c.match_tolerance_deg.toFixed(3)}°`)
  lines.push(`  背景：AsLS (lam=${c.bg_lam}, p=${c.bg_p})；归一化：${c.normalization}`)
  lines.push(`  检出峰数：${result.peaks.length}`)
  lines.push('')
  lines.push('【候选物相与依据】（排序仅供对照，不构成鉴定结论）')
  result.candidates.forEach((cand, i) => {
    lines.push(`  ${i + 1}. ${cand.name} (${cand.formula})  综合分 ${cand.score.toFixed(3)}`)
    lines.push(`     覆盖率 ${(cand.coverage * 100).toFixed(0)}%，样品可解释 ${(cand.explained_fraction * 100).toFixed(0)}%，`
      + `命中 ${cand.n_matched} 峰，均|Δ2θ| = ${cand.mean_abs_delta_deg == null ? '—' : cand.mean_abs_delta_deg.toFixed(3) + '°'}`)
    if (cand.missing_ref_peaks.length) {
      lines.push(`     参考有而样品未见：${cand.missing_ref_peaks.map((p) => `${p.two_theta_deg.toFixed(2)}°`).join(', ')}`)
    }
    if (cand.unexplained_sample_peaks.length) {
      lines.push(`     本候选解释不了的样品峰：${cand.unexplained_sample_peaks.map((p) => `${p.two_theta_deg.toFixed(2)}°`).join(', ')}`)
    }
  })
  lines.push('')
  lines.push('【未解释部分】')
  const top = result.candidates[0]
  if (top && top.unexplained_sample_peaks.length) {
    lines.push(`  即使按排名第一的 ${top.name}，仍有 ${top.unexplained_sample_peaks.length} 个样品峰未解释，`)
    lines.push('  可能来自第二相、择优取向、仪器伪峰或参考条目不全，需人工核查。')
  } else {
    lines.push('  排名第一的候选可解释全部检出峰；仍不排除参考库外物相。')
  }
  lines.push('')
  lines.push('【声明】')
  lines.push(`  ${result.disclaimer}`)

  const text = lines.join('\n')
  const download = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'xrd_review_result.json'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="panel">
      <h2>复核报告</h2>
      <pre className="report">{text}</pre>
      <button className="secondary" onClick={download}>下载完整 JSON 结果</button>
    </div>
  )
}
