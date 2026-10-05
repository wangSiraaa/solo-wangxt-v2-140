import { useRef, useState } from 'react'

const DEMO_CASES = [
  { case: 'single_clean', title: '单相合成谱：Cu（窄峰、无偏移）' },
  { case: 'systematic_shift', title: '系统偏移：Cu + 注入 +0.60°' },
  { case: 'broad_peaks', title: '宽峰：宽化 Si + 无定形鼓包' },
  { case: 'mixture', title: '两相混合：Cu + 弱 α-Fe' },
  { case: 'weak_unknown', title: 'Al + 两个未知杂质峰' },
]

export default function SpectrumInput({ onLoadDemo, onCsv, onAnalyzeText, currentName, busy }) {
  const fileRef = useRef(null)
  const [pasteOpen, setPasteOpen] = useState(false)
  const [text, setText] = useState('')

  const handleFile = (e) => {
    const f = e.target.files[0]
    if (!f) return
    const reader = new FileReader()
    reader.onload = () => onCsv(f.name, String(reader.result))
    reader.readAsText(f)
  }

  return (
    <div className="panel">
      <div className="panel-head"><h3>样本谱输入</h3></div>
      <div className="input-row">
        <label className="file-btn">
          载入 CSV/TSV（两列：角度, 强度）
          <input ref={fileRef} type="file" accept=".csv,.txt,.tsv,.xy,.raw" onChange={handleFile} hidden />
        </label>
        <button onClick={() => setPasteOpen((v) => !v)}>粘贴文本</button>
      </div>
      {pasteOpen && (
        <div className="paste-box">
          <textarea
            rows={6}
            placeholder={'# 示例：表头行会被跳过\n43.10,102\n43.12,98\n…'}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button className="primary" disabled={busy} onClick={() => onAnalyzeText(text)}>
            分析粘贴数据
          </button>
        </div>
      )}
      <div className="current-file">当前样本：<strong>{currentName}</strong></div>
      <div className="demo-list">
        <div className="demo-title">教学自检测试用例（合成谱，含 truth 供教师核对）：</div>
        {DEMO_CASES.map((d) => (
          <button key={d.case} className="demo-btn" disabled={busy} onClick={() => onLoadDemo(d.case)}>
            {d.title}
          </button>
        ))}
      </div>
      <p className="hint">
        注意：合成用例载入后会同时把建议参数（含零点偏移、容差、最大 FWHM 等）填入参数面板，
        你可以故意改成错误值观察缺失峰/未知峰的变化。
      </p>
    </div>
  )
}
