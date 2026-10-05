import React, { useEffect, useState } from 'react'
import { api } from './api'
import SampleInput from './components/SampleInput'
import ParameterPanel from './components/ParameterPanel'
import SpectrumPlot from './components/SpectrumPlot'
import CandidatePanel from './components/CandidatePanel'
import ReportPanel from './components/ReportPanel'

const DEFAULT_PARAMS = {
  wavelength_angstrom: 1.5406,   // Cu Kα1
  zero_offset_deg: 0.0,
  instrument_fwhm_deg: 0.1,
  detection_threshold_rel: 1.0,
  noise_sigma_factor: 5.0,
  match_tolerance_deg: null,     // 自动
  bg_lam: 100000,
  bg_p: 0.01,
}

export default function App() {
  const [references, setReferences] = useState([])
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [sample, setSample] = useState(null)
  const [result, setResult] = useState(null)
  const [selected, setSelected] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.listReferences().then(setReferences).catch((e) => setError(String(e)))
  }, [])

  // 案例2（系统偏移）把生成偏移置 0.15°，提示用户用零点偏移参数校正；
  // 案例3（宽峰）需要把仪器展宽参数同步调大。
  const onSample = (s) => {
    setSample(s)
    setResult(null)
    setError('')
    if (s.caseKind === 'broad') {
      setParams((p) => ({ ...p, instrument_fwhm_deg: 0.6, detection_threshold_rel: 2.0 }))
    } else if (s.caseKind === 'offset') {
      setParams((p) => ({ ...p, zero_offset_deg: 0.0, instrument_fwhm_deg: 0.1 }))
    } else {
      setParams((p) => ({ ...p, instrument_fwhm_deg: 0.1, detection_threshold_rel: 1.0 }))
    }
  }

  const runAnalysis = async () => {
    if (!sample) return
    setBusy(true)
    setError('')
    try {
      const res = await api.analyze({
        two_theta_deg: sample.two_theta_deg,
        intensity: sample.intensity,
        params,
      })
      setResult(res)
      setSelected(0)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header>
        <h1>XRD 离线复核台（课程教学用）</h1>
        <div className="sub">
          对照样品谱与开放/自制参考条目 · 全部参数显式 · 不下唯一结论 · 不访问付费数据库
        </div>
      </header>
      <div className="layout">
        <div>
          <SampleInput references={references} onSample={onSample} onError={setError} />
          <ParameterPanel params={params} onChange={setParams} />
          <div className="panel">
            <button onClick={runAnalysis} disabled={!sample || busy}>
              {busy ? '分析中…' : '运行复核分析'}
            </button>
            {sample && <span className="hint">当前样品：{sample.label}</span>}
            {error && <div className="error">{error}</div>}
          </div>
          <div className="disclaimer">
            本工具仅用于课程教学中的谱线对照练习：匹配结果按透明规则排序并列出证据，
            不构成也不替代真实材料鉴定。参考数据为教科书公开值或自制示例。
          </div>
        </div>
        <div>
          {result ? (
            <>
              <div className="panel">
                <h2>原始谱 与 去背景谱（并列）</h2>
                <SpectrumPlot result={result} />
              </div>
              <CandidatePanel result={result} selected={selected} onSelect={setSelected} />
              <ReportPanel result={result} sampleLabel={sample?.label} />
            </>
          ) : (
            <div className="panel">
              <h2>结果区</h2>
              <div className="hint">
                选择左侧测试案例或粘贴/上传样品数据，然后点击"运行复核分析"。
                参考库共 {references.length} 个条目：
                {references.map((r) => r.name).join('、')}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
