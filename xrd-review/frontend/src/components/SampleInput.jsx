import React, { useState } from 'react'

/** 样品输入：粘贴 CSV / 上传文件 / 三个内置测试案例（单相、系统偏移、宽峰）。 */
export default function SampleInput({ references, onSample, onError }) {
  const [text, setText] = useState('')
  const [label, setLabel] = useState('')

  const parseCsv = (content, name) => {
    const tt = []
    const ii = []
    for (const line of content.split(/\r?\n/)) {
      const s = line.trim()
      if (!s || s.startsWith('#') || s.startsWith('//')) continue
      const parts = s.split(/[,\s;\t]+/).map(Number)
      if (parts.length >= 2 && parts.every((v) => Number.isFinite(v))) {
        tt.push(parts[0])
        ii.push(parts[1])
      }
    }
    if (tt.length < 10) {
      onError(`解析失败：有效数据点不足（${tt.length} < 10）。格式：每行 "2θ 强度"，逗号或空白分隔。`)
      return
    }
    onSample({ two_theta_deg: tt, intensity: ii, label: name })
  }

  const onFile = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    const reader = new FileReader()
    reader.onload = () => parseCsv(String(reader.result), f.name)
    reader.readAsText(f)
  }

  const findRef = (kw) => references.find((r) => r.name.includes(kw))

  const loadCase = async (kind) => {
    try {
      const ref = findRef('Quartz') || references[0]
      if (!ref) throw new Error('参考库为空')
      const cases = {
        single: { fwhm_deg: 0.08, zero_offset_deg: 0.0, tag: '单相合成谱' },
        offset: { fwhm_deg: 0.08, zero_offset_deg: 0.15, tag: '系统偏移 +0.15°' },
        broad: { fwhm_deg: 0.6, zero_offset_deg: 0.0, tag: '宽峰 FWHM=0.6°' },
      }
      const c = cases[kind]
      const { api } = await import('../api')
      const syn = await api.synthetic({
        reference_id: ref.id,
        fwhm_deg: c.fwhm_deg,
        zero_offset_deg: c.zero_offset_deg,
      })
      onSample({
        two_theta_deg: syn.two_theta_deg,
        intensity: syn.intensity,
        label: `${c.tag}（源：${ref.name}）`,
        caseKind: kind,
        genParams: c,
      })
    } catch (err) {
      onError(String(err))
    }
  }

  return (
    <div className="panel">
      <h2>样品谱输入</h2>
      <div className="row">
        <button className="secondary" onClick={() => loadCase('single')}>案例1 单相</button>
        <button className="secondary" onClick={() => loadCase('offset')}>案例2 系统偏移</button>
        <button className="secondary" onClick={() => loadCase('broad')}>案例3 宽峰</button>
      </div>
      <div className="hint">案例由后端按参考条目实时合成（高斯峰+背景+泊松噪声）。</div>
      <textarea
        rows={7}
        placeholder={'粘贴数据：每行 "2θ 强度"（逗号/空白分隔，# 为注释）\n20.00 512\n20.02 498\n...'}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="row">
        <button onClick={() => parseCsv(text, label || '粘贴数据')}>载入粘贴数据</button>
        <input type="file" accept=".csv,.txt,.xy,.dat" onChange={onFile} style={{ fontSize: 12 }} />
      </div>
      <input
        placeholder="样品标签（可选）"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        style={{ width: '100%', marginTop: 6, boxSizing: 'border-box', padding: 4, fontSize: 12 }}
      />
    </div>
  )
}
