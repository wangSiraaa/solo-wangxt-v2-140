import { useState } from 'react'

export default function ReferenceManager({ references, selected, onToggle, onReload, onSave, onDelete }) {
  const [showCustom, setShowCustom] = useState(false)
  const [mode, setMode] = useState('peaklist')
  const [form, setForm] = useState({
    code: '', name: '', structure: 'FCC', a_angstrom: 4.0,
    wavelength: 1.54056, wavelength_unit: 'angstrom',
    provenance: '', peaksText: '35.0,100,(111)\n50.0,60,(200)',
  })
  const [msg, setMsg] = useState('')

  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async () => {
    setMsg('')
    try {
      if (mode === 'peaklist') {
        const peaks = form.peaksText.split('\n').map((line) => {
          const parts = line.split(/[,\s]+/).filter(Boolean)
          if (parts.length < 2) return null
          return {
            two_theta: parseFloat(parts[0]),
            intensity_rel: parseFloat(parts[1]),
            hkl: parts[2] || null,
          }
        }).filter(Boolean)
        await onSave('peaklist', {
          code: form.code, name: form.name,
          wavelength: parseFloat(form.wavelength), wavelength_unit: form.wavelength_unit,
          provenance: form.provenance, peaks,
        })
      } else {
        await onSave('cubic', {
          code: form.code, name: form.name, structure: form.structure,
          a_angstrom: parseFloat(form.a_angstrom),
          wavelength: parseFloat(form.wavelength), wavelength_unit: form.wavelength_unit,
          provenance: form.provenance || '用户自定义立方结构合成谱（教学）',
        })
      }
      setMsg('已保存到 PostgreSQL')
      onReload()
    } catch (e) {
      setMsg('保存失败：' + e.message)
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>参考谱库（开放/自制，PostgreSQL）</h3>
        <button onClick={onReload}>刷新</button>
      </div>
      <p className="note">
        库内只保存由公开晶体学参数合成的教学谱或师生自制峰表，
        <strong>不访问 ICDD/PDF 等付费数据库</strong>。勾选条目参与本次对照（默认全部）。
      </p>
      <div className="ref-list">
        {references.map((r) => (
          <label key={r.code} className={`ref-item source-${r.source}`}>
            <input
              type="checkbox"
              checked={selected.has(r.code)}
              onChange={() => onToggle(r.code)}
            />
            <span className="ref-code">{r.code}</span>
            <span className="ref-name">{r.name}</span>
            <span className="ref-meta">{r.n_peaks} 峰 · λ={r.wavelength_angstrom} Å · {r.source}</span>
            {r.source !== 'builtin_synthetic' && (
              <button
                className="del-btn"
                onClick={(e) => { e.preventDefault(); onDelete(r.code) }}
              >
                删除
              </button>
            )}
            <span className="prov-mini" title={r.provenance}>ⓘ {r.provenance}</span>
          </label>
        ))}
      </div>

      <button className="expand-btn" onClick={() => setShowCustom((v) => !v)}>
        {showCustom ? '收起自制参考' : '＋ 新增自制参考'}
      </button>
      {showCustom && (
        <div className="custom-form">
          <div className="mode-switch">
            <label><input type="radio" checked={mode === 'peaklist'} onChange={() => setMode('peaklist')} /> 手输峰表（2θ°, I%）</label>
            <label><input type="radio" checked={mode === 'cubic'} onChange={() => setMode('cubic')} /> 立方结构参数合成</label>
          </div>
          <div className="form-grid">
            <label>code <input value={form.code} onChange={upd('code')} placeholder="USR-XXX" /></label>
            <label>名称 <input value={form.name} onChange={upd('name')} /></label>
            <label>波长 <input type="number" step="0.00001" value={form.wavelength} onChange={upd('wavelength')} /></label>
            <label>单位
              <select value={form.wavelength_unit} onChange={upd('wavelength_unit')}>
                <option value="angstrom">Å</option>
                <option value="nm">nm</option>
              </select>
            </label>
            {mode === 'cubic' && (
              <>
                <label>结构
                  <select value={form.structure} onChange={upd('structure')}>
                    {['SC', 'BCC', 'FCC', 'DIAMOND', 'NACL', 'CSCL', 'FLUORITE'].map((s) =>
                      <option key={s}>{s}</option>)}
                  </select>
                </label>
                <label>a (Å) <input type="number" step="0.0001" value={form.a_angstrom} onChange={upd('a_angstrom')} /></label>
              </>
            )}
            <label className="span2">
              来源/精度说明（必填，保证可追溯）
              <input value={form.provenance} onChange={upd('provenance')}
                placeholder="例如：课堂从公开教材图读取，角度精度约 0.1°" />
            </label>
            {mode === 'peaklist' && (
              <label className="span2">
                峰表（每行：2θ°, 相对强度, 可选 hkl）
                <textarea rows={5} value={form.peaksText} onChange={upd('peaksText')} />
              </label>
            )}
          </div>
          <button className="primary" onClick={submit}>保存到库</button>
          {msg && <span className="form-msg">{msg}</span>}
        </div>
      )}
    </div>
  )
}
