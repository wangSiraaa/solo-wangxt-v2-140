import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import SpectrumInput from './components/SpectrumInput'
import ParameterPanel from './components/ParameterPanel'
import SpectrumPlot from './components/SpectrumPlot'
import CandidateList from './components/CandidateList'
import ReferenceManager from './components/ReferenceManager'
import ReportPanel from './components/ReportPanel'
import './styles.css'

const DEFAULT_PARAMS = {
  wavelength: 1.54056,
  wavelength_unit: 'angstrom',
  angle_unit: '2theta_deg',
  zero_shift: 0.0,
  bg_window: 40,
  bg_iterations: 24,
  bg_smoothing: 3,
  prominence_sigma: 5.0,
  min_separation_deg: 0.05,
  min_fwhm_deg: 0.03,
  max_fwhm_deg: 3.0,
  instrument_fwhm_deg: 0.08,
  uncertainty_fraction: 0.1,
  tolerance_deg: 0.15,
  minimum_hits: 2,
  shift_scan_max: 2.0,
  shift_scan_step: 0.02,
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [constants, setConstants] = useState(null)
  const [references, setReferences] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [spectrum, setSpectrum] = useState(null) // {two_theta, intensity, name, truth}
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError('后端不可达：' + e.message))
    api.constants().then(setConstants)
    reloadRefs()
  }, [])

  const reloadRefs = async () => {
    const r = await api.listReferences()
    setReferences(r.references)
    setSelected(new Set(r.references.map((x) => x.code)))
  }

  const changeParam = (key, value) => setParams((p) => ({ ...p, [key]: value }))

  const runAnalyze = async (spectrumArg = spectrum, paramOverrides = {}) => {
    if (!spectrumArg) {
      setError('请先载入样本谱或生成测试用例')
      return
    }
    setBusy(true)
    setError('')
    try {
      const body = {
        two_theta: spectrumArg.two_theta,
        intensity: spectrumArg.intensity,
        reference_codes: [...selected],
        ...params,
        ...paramOverrides,
      }
      const r = await api.analyze(body)
      setResult(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const loadDemo = async (caseName) => {
    setBusy(true)
    setError('')
    try {
      const d = await api.generateDemo(caseName)
      setSpectrum({
        two_theta: d.spectrum.two_theta,
        intensity: d.spectrum.intensity,
        name: d.title,
        truth: d.truth,
      })
      const sp = d.truth.suggested_params || {}
      const nextParams = {
        ...DEFAULT_PARAMS,
        wavelength: d.wavelength,
        wavelength_unit: d.wavelength_unit,
        ...sp,
      }
      setParams(nextParams)
      const r = await api.analyze({
        two_theta: d.spectrum.two_theta,
        intensity: d.spectrum.intensity,
        reference_codes: [...selected],
        ...nextParams,
      })
      setResult(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const loadCsv = (name, text) => {
    const parse = (t) => {
      const xs = [], ys = []
      t.split(/\r?\n/).forEach((line) => {
        const m = line.match(/^\s*([-0-9.eE]+)[,\s;]+([-0-9.eE]+)/)
        if (m) { xs.push(parseFloat(m[1])); ys.push(parseFloat(m[2])) }
      })
      return { xs, ys }
    }
    const { xs, ys } = parse(text)
    if (xs.length < 5) {
      setError(`CSV 解析有效点不足（${xs.length} 个），需要两列数值`)
      return
    }
    setSpectrum({ two_theta: xs, intensity: ys, name, truth: null })
    setError('')
  }

  const analyzeText = (text) => {
    const xs = [], ys = []
    text.split(/\r?\n/).forEach((line) => {
      const m = line.match(/^\s*([-0-9.eE]+)[,\s;]+([-0-9.eE]+)/)
      if (m) { xs.push(parseFloat(m[1])); ys.push(parseFloat(m[2])) }
    })
    if (xs.length < 5) { setError('粘贴数据有效点不足 5 个'); return }
    const spec = { two_theta: xs, intensity: ys, name: '粘贴文本', truth: null }
    setSpectrum(spec)
    runAnalyze(spec)
  }

  const toggleRef = (code) => setSelected((s) => {
    const n = new Set(s)
    n.has(code) ? n.delete(code) : n.add(code)
    return n
  })

  const saveReference = async (kind, body) => {
    if (kind === 'peaklist') await api.savePeakList(body)
    else await api.saveCubic(body)
  }

  const deleteReference = async (code) => {
    await api.deleteReference(code)
    reloadRefs()
  }

  const truthBanner = useMemo(() => {
    if (!spectrum?.truth) return null
    const t = spectrum.truth
    return (
      <div className="truth-banner">
        <strong>教学用例 truth（分析接口不读取，仅供核对）：</strong>
        <span>物相={t.phases.join(' + ')}</span>
        <span>注入零点偏移={t.zero_shift_deg}°</span>
        {t.amorphous_humps?.map((h, i) => (
          <span key={i}>无定形鼓包≈{h.center_deg}° (FWHM {h.fwhm_deg}°)</span>
        ))}
        {t.unknown_injected_peaks && <span>注入未知峰={t.unknown_injected_peaks.join('、')}°</span>}
        <span className="expect">{t.expected_behaviour}</span>
      </div>
    )
  }, [spectrum])

  return (
    <div className="app">
      <header>
        <h1>离线 XRD 复核台</h1>
        <div className="sub">
          React + Plotly.js 谱图对照 · FastAPI + SciPy 峰位与候选匹配 · PostgreSQL 开放/自制参考谱
        </div>
        <div className="health">
          {health && (
            <>
              <span className={`dot ${health.status === 'ok' ? 'green' : 'red'}`} />
              后端：{health.status} · 存储：{health.storage} · 参考 {health.n_references} 条 ·
              付费数据库访问：{health.paid_databases_accessed ? '是' : '否（仅开放/自制数据）'}
            </>
          )}
        </div>
        <div className="warning-bar">
          本工具只做离线复核与候选依据展示，<strong>不声称自动完成真实材料鉴定</strong>；
          最终物相判断须结合化学背景、缺失峰、未知峰与强度由人工完成。
        </div>
      </header>

      {error && <div className="error-bar" onClick={() => setError('')}>⚠ {error}（点击关闭）</div>}
      {truthBanner}

      <div className="layout">
        <aside className="left">
          <SpectrumInput
            onLoadDemo={loadDemo}
            onCsv={loadCsv}
            onAnalyzeText={analyzeText}
            currentName={spectrum?.name || '尚未载入'}
            busy={busy}
          />
          <ParameterPanel
            params={params}
            onChange={changeParam}
            onAnalyze={() => runAnalyze()}
            busy={busy}
            targets={constants?.common_targets_angstrom}
            onPickTarget={(wl) => changeParam('wavelength', wl)}
          />
        </aside>

        <main className="center">
          {result ? (
            <>
              <ConventionBar result={result} params={params} />
              <SpectrumPlot result={result} />
              <PeakSummary result={result} />
              <CandidateList result={result} />
              <ReportPanel result={result} sampleName={spectrum?.name} />
            </>
          ) : (
            <div className="placeholder">
              <h2>开始方式</h2>
              <ol>
                <li>在左侧选择一个教学测试用例（建议先试"系统偏移"和"宽峰"）；</li>
                <li>或载入自己的 CSV（两列：2θ、强度），确认上方波长/角度单位；</li>
                <li>检查①物理约定、③检测阈值与仪器展宽是否符合你的仪器；</li>
                <li>点击"运行复核"，查看原始谱/去背景谱并列图与候选依据。</li>
              </ol>
              <p>所有物理量（波长、角度单位、零点偏移、展宽、阈值、容差）均为显式参数，
                结果里会原样回显；峰强归一化仅用于展示，不参与峰位与匹配。</p>
            </div>
          )}
        </main>

        <aside className="right">
          <ReferenceManager
            references={references}
            selected={selected}
            onToggle={toggleRef}
            onReload={reloadRefs}
            onSave={saveReference}
            onDelete={deleteReference}
          />
        </aside>
      </div>
    </div>
  )
}

function ConventionBar({ result, params }) {
  const c = result.convention
  return (
    <div className="convention-bar">
      <span>内部角度：<b>{c.internal_angle_unit}</b></span>
      <span>输入单位：{c.input_angle_unit}</span>
      <span>波长：<b>{c.wavelength}</b> {c.wavelength_unit}（= {c.wavelength_angstrom} Å）</span>
      <span>零点偏移：<b>{c.zero_shift_deg}°</b>（{c.zero_shift_convention}）</span>
      <span>仪器展宽：{params.instrument_fwhm_deg}°</span>
      <span>检测阈值：{params.prominence_sigma}σ（实测噪声 σ={result.peaks.noise_sigma}，阈值={result.peaks.prominence_threshold}）</span>
      <span>匹配容差：{params.tolerance_deg}°</span>
    </div>
  )
}

function PeakSummary({ result }) {
  const p = result.peaks
  return (
    <div className="panel">
      <div className="panel-head"><h3>检出峰与未解释部分</h3></div>
      <div className="peak-summary-row">
        <span>检出 <b>{p.peaks.length}</b> 个峰</span>
        <span>超宽上限列入 rejected_broad：<b className="err-text">{p.rejected_broad.length}</b></span>
        <span>过窄（噪声尖峰）剔除：<b>{p.rejected_narrow_count ?? 0}</b></span>
        <span>全部达标候选都解释不了的峰：<b className="err-text">{result.unexplained_overall.length}</b></span>
      </div>
      <table className="peak-table">
        <thead>
          <tr>
            <th>2θ_corrected (°)</th><th>实测 FWHM (°)</th><th>本征 β (°)</th>
            <th>峰位 ± (°)</th><th>去背景强度</th>
          </tr>
        </thead>
        <tbody>
          {p.peaks.map((pk, i) => (
            <tr key={i} className={result.unexplained_overall.some((u) => u.two_theta === pk.two_theta) ? 'unexplained' : ''}>
              <td>{pk.two_theta.toFixed(4)}</td>
              <td>{pk.fwhm_deg.toFixed(3)}</td>
              <td>{pk.broadening_resolved ? pk.intrinsic_fwhm_deg.toFixed(3) : '≤ 仪器展宽'}</td>
              <td>{pk.position_uncertainty_deg.toFixed(3)}</td>
              <td>{pk.intensity_net.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {p.rejected_broad.length > 0 && (
        <div className="rejected-box">
          {p.rejected_broad.map((r, i) => (
            <div key={i} className="rejected-item">
              ⚠ {r.two_theta.toFixed(3)}°：{r.reason}（净强度 {r.intensity_net}）
            </div>
          ))}
        </div>
      )}
      {result.unexplained_overall.length > 0 && (
        <div className="rejected-box unexplained-box">
          <strong>未解释峰（任何达标候选都对不上）：</strong>
          {result.unexplained_overall.map((u, i) => (
            <span key={i} className="unknown-chip">{u.two_theta.toFixed(3)}°</span>
          ))}
          <div className="hint">这些峰必须在报告中保留，可能是第二相、杂质、制样伪影或未知结构。</div>
        </div>
      )}
    </div>
  )
}
