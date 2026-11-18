"use client";

import { useEffect, useState } from "react";
import {
  Activity, ArrowRight, BarChart3, BookOpen, Check, ChevronDown,
  CircleHelp, Clock3, CloudSun, Database, Download, Droplets, FlaskConical, Languages, Layers3, Leaf,
  MapPin, Menu, Satellite, Settings2, ShieldCheck,
  Sprout, Target, ThermometerSun, TrendingUp, X
} from "lucide-react";

const API = "/api";
const NOT_EVALUATED = "Not yet evaluated — Phase-II";
const fmt = (date) => new Date(date).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

async function request(path, options) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

function App() {
  const [page, setPage] = useState("Overview");
  const [mobileNav, setMobileNav] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [selectedModels, setSelectedModels] = useState(["prithvi", "satmae", "croma", "resnet"]);
  const [region, setRegion] = useState("punjab");
  const [crop, setCrop] = useState("Wheat");
  const [season, setSeason] = useState("Rabi 2025–26");
  const [dataset, setDataset] = useState("sentinel2");
  const [activeRun, setActiveRun] = useState(null);
  const [runs, setRuns] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [methodology, setMethodology] = useState(null);

  const load = async () => {
    try {
      setError("");
      const [dashboard, runData, datasetData, methodData] = await Promise.all([
        request("/dashboard"), request("/runs"), request("/datasets"), request("/methodology")
      ]);
      setData(dashboard);
      setRuns(runData);
      setDatasets(datasetData);
      setMethodology(methodData);
      setActiveRun((current) => current || runData[0] || null);
    } catch (e) {
      setError(`${e.message}. Start the API with: uvicorn apps.api.main:app --reload`);
    }
  };

  useEffect(() => { load(); }, []);

  const models = data?.models || [];
  const regions = data?.regions || [];
  const runComparison = async () => {
    if (selectedModels.length < 2) {
      setNotice("Select at least two models to compare.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const result = await request("/runs", {
        method: "POST",
        body: JSON.stringify({ model_ids: selectedModels, region_id: region, crop, season, dataset_id: dataset })
      });
      setActiveRun(result);
      setRuns((existing) => [result, ...existing]);
      setData((current) => current ? {
        ...current,
        run_count: current.run_count + 1,
        top_model: null,
        top_f1: null,
        latest_run: result
      } : current);
      setPage("Compare");
      setNotice("Comparison setup saved — no model inference was run.");
    } catch (e) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleModel = (id) => {
    setSelectedModels((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : current.length < 4 ? [...current, id] : current);
  };

  const addModelToComparison = (id) => {
    if (!selectedModels.includes(id) && selectedModels.length >= 4) {
      setNotice("A comparison supports up to four models. Remove one before adding another.");
    } else {
      setSelectedModels((current) => current.includes(id) ? current : [...current, id]);
      setNotice("");
    }
    setPage("Compare");
  };

  const selectRun = (run) => {
    setActiveRun(run);
    if (!run) return;
    setRegion(run.region_id);
    setCrop(run.crop);
    setSeason(run.season);
    setDataset(run.dataset_id);
    setSelectedModels(run.model_ids);
  };

  const nav = [
    { name: "Overview", icon: BarChart3 },
    { name: "Compare models", icon: FlaskConical },
    { name: "Farmer guide", icon: Sprout },
    { name: "Model library", icon: Layers3 },
    { name: "Datasets", icon: Database },
    { name: "Methodology", icon: BookOpen },
  ];

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Sprout size={22} strokeWidth={2.2} /></div>
          <div><strong>AgriFM<span> Compare</span></strong><small>RESEARCH WORKSPACE</small></div>
          <button className="mobile-close icon-button" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>
        <div className="workspace-label">PROJECT</div>
        <div className="project-card">
          <div className="project-icon"><Satellite size={16} /></div>
          <div><strong>Indian precision agri</strong><small>Major Project · 2026–27</small></div>
        </div>
        <div className="workspace-label nav-label">WORKSPACE</div>
        <nav className="nav-list" aria-label="Main navigation">
          {nav.map(({ name, icon: Icon }) => {
            const active = name === "Compare models" ? page === "Compare" : page === name;
            return <button key={name} className={`nav-item ${active ? "active" : ""}`} onClick={() => { setPage(name === "Compare models" ? "Compare" : name); setMobileNav(false); }}>
              <Icon size={17} /><span>{name}</span>{name === "Compare models" && <span className="nav-badge">NEW</span>}
            </button>;
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="status-card"><span className="status-dot" /><div><strong>Local research mode</strong><small>Seeded demo data enabled</small></div></div>
          <div className="student-card"><div className="avatar">PT</div><div><strong>Project team</strong><small>IILM University · Greater Noida</small></div></div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu size={20} /></button>
          <div className="breadcrumbs"><span>Research</span><span className="crumb-slash">/</span><strong>{page}</strong></div>
          <div className="top-actions"><span className="top-status"><span className="status-dot" />{data && !error ? " API connected" : error ? " API unavailable" : " Connecting…"}</span><button className="icon-button help-button" aria-label="Help" onClick={() => setPage("Methodology")}><CircleHelp size={18} /></button><div className="top-avatar">AG</div></div>
        </header>

        <div className="content">
          {error && <div className="error-banner"><CircleHelp size={17} /><span>{error}</span><button onClick={load}>Retry</button></div>}
          {notice && <div className="notice-banner"><Check size={16} /><span>{notice}</span><button aria-label="Dismiss" onClick={() => setNotice("")}><X size={15} /></button></div>}
          <div className="demo-banner" role="status"><strong>DEMO DATA</strong><span>Evaluation has not been run on ground-truth data. No model performance metrics are available.</span></div>
          {page === "Overview" && <Overview data={data} runs={runs} onCompare={() => setPage("Compare")} onRunSelect={(run) => { selectRun(run); setPage("Compare"); }} />}
          {page === "Compare" && <Compare models={models} regions={regions} datasets={datasets} selectedModels={selectedModels} toggleModel={toggleModel} region={region} setRegion={setRegion} crop={crop} setCrop={setCrop} season={season} setSeason={setSeason} dataset={dataset} setDataset={setDataset} onRun={runComparison} busy={busy} run={activeRun} runs={runs} onRunSelect={selectRun} />}
          {page === "Farmer guide" && <FarmerGuide regions={regions} crops={data?.crops || ["Wheat", "Rice", "Cotton", "Sugarcane", "Maize"]} />}
          {page === "Model library" && <ModelLibrary models={models} onCompare={() => setPage("Compare")} onAddModel={addModelToComparison} />}
          {page === "Datasets" && <Datasets datasets={datasets} />}
          {page === "Methodology" && <Methodology methodology={methodology} />}
          <footer className="footer"><div><strong>AgriFM Compare</strong><span> · Foundation Model for Precision Agriculture: A Comparative Study</span></div><span>Demo data only; no validated performance results. <span className="footer-sep">·</span> IILM University, Greater Noida · Session 2026–27</span></footer>
        </div>
      </main>
    </div>
  );
}

function PageHeading({ eyebrow, title, subtitle, action }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>;
}

function MetricCard({ label, value, note, icon: Icon, tone = "green", trend }) {
  const unavailable = value === NOT_EVALUATED;
  return <div className="metric-card"><div className="metric-top"><span>{label}</span><div className={`metric-icon ${tone}`}><Icon size={17} /></div></div><div className={`metric-value ${unavailable ? "metric-placeholder" : ""}`}>{value}</div><div className="metric-foot"><span>{trend && <TrendingUp size={13} />} {note}</span>{trend && <span className="trend-value">{trend}</span>}</div></div>;
}

function metricText(value) {
  return Number.isFinite(value) ? value : NOT_EVALUATED;
}

function Overview({ data, runs, onCompare, onRunSelect }) {
  const recent = runs.slice(0, 4);
  const latest = runs[0];
  const chartModels = (latest?.results || []).filter((result) => Number.isFinite(result.f1));
  const top = [...chartModels].sort((a, b) => b.f1 - a.f1)[0];
  return <>
    <PageHeading eyebrow="PROJECT DASHBOARD" title="Region-controlled study setup." subtitle="Prepare a consistent evaluation context across India's diverse agricultural regions." action={<button className="button primary" onClick={onCompare}><FlaskConical size={16} /> New comparison <ArrowRight size={15} /></button>} />
    <div className="hero-strip"><div className="hero-icon"><Leaf size={24} /></div><div className="hero-copy"><strong>A controlled setup. A clearer research path.</strong><span>Set the same crop, season, and region for each model, ready for a future evaluation.</span></div><button className="hero-link" onClick={onCompare}>Set up a run <ArrowRight size={15} /></button><div className="hero-decoration">agri<span>fm</span></div></div>
    <div className="metric-grid">
      <MetricCard label="Models in study" value={data?.model_count ?? "—"} note="3 foundation · 1 baseline" icon={Layers3} />
      <MetricCard label="Saved comparisons" value={data?.run_count ?? "—"} note="Runs stored locally" icon={Activity} tone="blue" />
      <MetricCard label="Regions covered" value={data?.region_count ?? "—"} note="Across 5 states" icon={MapPin} tone="amber" />
      <MetricCard label="Top F1 score" value={Number.isFinite(data?.top_f1) ? `${data.top_f1}%` : NOT_EVALUATED} note={data?.top_model || "No measured result"} icon={Target} tone="purple" />
    </div>
    <div className="dashboard-grid">
      <section className="panel performance-panel">
        <div className="panel-heading"><div><h2>Latest comparison</h2><p>{latest ? `${latest.crop} · ${latest.region_name || regionLabel(latest.region_id)} · ${latest.season}` : "Save a comparison setup to see it here"}</p></div><button className="text-button" onClick={onCompare}>Compare models <ArrowRight size={14} /></button></div>
        {chartModels.length ? <PerformanceChart results={chartModels} /> : <div className="empty-chart"><BarChart3 size={28} /><strong>{NOT_EVALUATED}</strong><span>No measured scores to chart.</span><button className="button secondary small" onClick={onCompare}>Set up a comparison</button></div>}
        <div className="chart-legend">{chartModels.map((r) => <span key={r.model_id}><i style={{ background: r.color }} />{r.model_name}</span>)}</div>
        <div className="chart-caption"><span><span className="dot-outline" /> F1 score (%)</span><span><span className="region-pill">{latest?.region_name || (latest ? regionLabel(latest.region_id) : "No run")}</span> Region controlled</span></div>
      </section>
      <section className="panel highlight-panel">
        <div className="panel-heading"><div><h2>Study snapshot</h2><p>Project evaluation context</p></div><span className="soft-icon"><Sprout size={17} /></span></div>
        <div className="highlight-stat"><div><span className="highlight-label">Current best performer</span><strong>{top?.model_name || NOT_EVALUATED}</strong><small>Ranking requires measured evaluation results</small></div><div className="score-orb">{top ? `${top.f1}%` : "—"}</div></div>
        <div className="highlight-divider" />
        <div className="study-detail"><span><MapPin size={14} /> Study focus</span><strong>Indian crop systems</strong></div>
        <div className="study-detail"><span><Satellite size={14} /> Primary imagery</span><strong>Sentinel-2 · 10 m</strong></div>
        <div className="study-detail"><span><ShieldCheck size={14} /> Comparison design</span><strong>Region-controlled</strong></div>
        <div className="caveat"><CircleHelp size={15} /><span>There are no measured research results. All model metrics remain unevaluated.</span></div>
      </section>
    </div>
    <section className="panel runs-panel">
      <div className="panel-heading"><div><h2>Recent comparisons</h2><p>Pick up where you left off</p></div><button className="text-button" onClick={onCompare}>View all <ArrowRight size={14} /></button></div>
      <div className="table-wrap"><table><thead><tr><th>RUN</th><th>REGION</th><th>CROP / SEASON</th><th>MODELS</th><th>TOP F1</th><th>DATE</th><th></th></tr></thead><tbody>
        {recent.map((run) => { const winner = [...run.results].filter((result) => Number.isFinite(result.f1)).sort((a, b) => b.f1 - a.f1)[0]; return <tr key={run.id}><td><button className="run-link" onClick={() => onRunSelect(run)}>#{run.id.slice(0, 8)}</button></td><td><span className="table-region"><MapPin size={13} />{run.region_name || regionLabel(run.region_id)}</span></td><td>{run.crop}<small className="sub-cell">{run.season}</small></td><td><div className="avatar-stack">{run.results.slice(0, 3).map((m) => <span title={m.model_name} key={m.model_id} style={{ background: m.color }}>{m.model_name.slice(0, 1)}</span>)}</div></td><td><span className={winner ? "table-score" : "not-evaluated"}>{winner ? `${winner.f1}%` : NOT_EVALUATED}</span>{winner && <small className="sub-cell">{winner.model_name}</small>}</td><td className="date-cell">{fmt(run.created_at)}</td><td><button className="icon-button row-open" onClick={() => onRunSelect(run)} aria-label="View run"><ArrowRight size={15} /></button></td></tr>; })}
        {!recent.length && <tr><td colSpan="7" className="empty-row">No saved comparisons yet. Start your first run above.</td></tr>}
      </tbody></table></div>
    </section>
  </>;
}

function PerformanceChart({ results }) {
  const top = 100;
  const bottom = 300;
  const y = (value) => bottom - ((value - 60) / 40) * (bottom - top);
  const x = (index) => 92 + index * 138;
  return <div className="chart-area">
    <div className="chart-y-label">F1 score (%)</div>
    <svg viewBox="0 0 720 330" role="img" aria-label="Bar chart comparing model F1 scores">
      {[60, 70, 80, 90, 100].map((tick) => <g key={tick}><line x1="58" x2="690" y1={y(tick)} y2={y(tick)} className="chart-gridline" /><text x="46" y={y(tick) + 4} textAnchor="end" className="chart-tick">{tick}</text></g>)}
      {results.map((r, i) => <g key={r.model_id}><rect x={x(i)} y={y(r.f1)} width="62" height={bottom - y(r.f1)} rx="8" fill={r.color} opacity=".92" /><text x={x(i) + 31} y={y(r.f1) - 12} textAnchor="middle" className="chart-value">{r.f1}</text><text x={x(i) + 31} y="322" textAnchor="middle" className="chart-name">{r.model_name.length > 14 ? `${r.model_name.slice(0, 13)}…` : r.model_name}</text></g>)}
    </svg>
  </div>;
}

function regionLabel(id) {
  return ({ punjab: "Punjab", up: "Western Uttar Pradesh", maharashtra: "Maharashtra", karnataka: "Karnataka", bihar: "Bihar" })[id] || id;
}

function FarmerGuide({ regions, crops }) {
  const [region, setRegion] = useState("punjab");
  const [crop, setCrop] = useState("Wheat");
  const [language, setLanguage] = useState("en");
  const [advisory, setAdvisory] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadGuidance = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await request("/farmer/advisory", {
        method: "POST",
        body: JSON.stringify({ region_id: region, crop, forecast_days: 7, language }),
      });
      setAdvisory(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return <>
    <PageHeading eyebrow="FARMER WEATHER GUIDE" title={language === "hi" ? "मौसम आधारित फसल योजना" : "Weather-based crop planning"} subtitle={language === "hi" ? "मौसम पूर्वानुमान को सरल रोज़मर्रा की योजना में बदलें।" : "Turn a 7-day public weather forecast into simple planning guidance."} />
    {error && <div className="error-banner"><CircleHelp size={17} /><span>{error}</span><button onClick={loadGuidance}>Retry</button></div>}
    <section className="panel farmer-controls">
      <div className="panel-heading">
        <div><h2>{language === "hi" ? "अपना विकल्प चुनें" : "Choose your context"}</h2><p>{language === "hi" ? "क्षेत्र और फसल के अनुसार जानकारी देखें" : "Get guidance for a region and crop"}</p></div>
        <Languages size={18} />
      </div>
      <div className="form-grid">
        <label className="field"><span>{language === "hi" ? "राज्य / क्षेत्र" : "State / region"}</span><div className="select-wrap"><MapPin size={15} /><select value={region} onChange={(e) => setRegion(e.target.value)}>{regions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><ChevronDown size={14} /></div></label>
        <label className="field"><span>{language === "hi" ? "फसल" : "Crop"}</span><div className="select-wrap"><Sprout size={15} /><select value={crop} onChange={(e) => setCrop(e.target.value)}>{crops.map((item) => <option key={item}>{item}</option>)}</select><ChevronDown size={14} /></div></label>
        <label className="field"><span>{language === "hi" ? "भाषा" : "Language"}</span><div className="select-wrap"><Languages size={15} /><select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="en">English</option><option value="hi">हिंदी</option></select><ChevronDown size={14} /></div></label>
      </div>
      <button className="button primary farmer-load" disabled={busy} onClick={loadGuidance}>{busy ? <><span className="spinner" /> {language === "hi" ? "पूर्वानुमान ले रहे हैं…" : "Loading forecast…"}</> : <><CloudSun size={16} /> {language === "hi" ? "7-दिन की सलाह देखें" : "Get 7-day guidance"}</>}</button>
    </section>
    {advisory && <>
      <div className="farmer-summary-grid">
        <section className="panel farmer-summary-card">
          <div className="farmer-summary-icon heat"><ThermometerSun size={20} /></div>
          <div><small>{language === "hi" ? "सबसे गर्म दिन" : "Hottest forecast"}</small><strong>{advisory.summary.hottest_day_c == null ? "—" : `${advisory.summary.hottest_day_c}°C`}</strong></div>
        </section>
        <section className="panel farmer-summary-card">
          <div className="farmer-summary-icon rain"><Droplets size={20} /></div>
          <div><small>{language === "hi" ? "कुल अनुमानित बारिश" : "Expected rainfall"}</small><strong>{advisory.summary.total_rainfall_mm == null ? "—" : `${advisory.summary.total_rainfall_mm} mm`}</strong></div>
        </section>
        <section className="panel farmer-summary-card">
          <div className="farmer-summary-icon region"><MapPin size={20} /></div>
          <div><small>{language === "hi" ? "क्षेत्र" : "Region"}</small><strong>{advisory.region_name}</strong></div>
        </section>
      </div>
      <section className="panel farmer-advice">
        <div className="panel-heading"><div><h2>{language === "hi" ? "सरल योजना सलाह" : "Simple planning advice"}</h2><p>{advisory.crop} · {advisory.source} · {advisory.forecast_days} {language === "hi" ? "दिन" : "days"}</p></div><span className="illustrative-tag">{language === "hi" ? "पूर्वानुमान" : "FORECAST"}</span></div>
        <div className="farmer-advice-list">{advisory.advisories.map((item, index) => <div key={item}><span>{String(index + 1).padStart(2, "0")}</span><p>{item}</p></div>)}</div>
        <div className="caveat"><ShieldCheck size={15} /><span>{advisory.disclaimer}</span></div>
      </section>
      <section className="panel farmer-forecast">
        <div className="panel-heading"><div><h2>{language === "hi" ? "7-दिन का मौसम" : "7-day weather"}</h2><p>{language === "hi" ? "दिनवार तापमान और बारिश" : "Daily temperature and rainfall"}</p></div></div>
        <div className="forecast-grid">{advisory.daily.map((day) => <article key={day.date} className="forecast-day"><strong>{fmt(day.date)}</strong><span>{day.condition}</span><div><ThermometerSun size={14} /> {day.temperature_max_c == null ? "—" : `${day.temperature_max_c}°`} / {day.temperature_min_c == null ? "—" : `${day.temperature_min_c}°`}</div><div><Droplets size={14} /> {day.precipitation_mm == null ? "—" : `${day.precipitation_mm} mm`}</div></article>)}</div>
      </section>
    </>}
  </>;
}

function Compare({ models, regions, datasets, selectedModels, toggleModel, region, setRegion, crop, setCrop, season, setSeason, dataset, setDataset, onRun, busy, run, runs, onRunSelect }) {
  const results = run?.results || [];
  const winner = [...results].filter((result) => Number.isFinite(result.f1)).sort((a, b) => b.f1 - a.f1)[0];
  return <>
    <PageHeading eyebrow="COMPARISON WORKSPACE" title="Compare foundation models" subtitle="Set a shared context for a future model evaluation; this prototype does not run inference." action={<div className="saved-select"><Clock3 size={15} /><select aria-label="Load saved comparison" value={run?.id || ""} onChange={(e) => onRunSelect(runs.find((r) => r.id === e.target.value))}><option value="">Saved runs</option>{runs.map((r) => <option value={r.id} key={r.id}>{r.crop} · {r.region_name || regionLabel(r.region_id)} · {fmt(r.created_at)}</option>)}</select><ChevronDown size={14} /></div>} />
    <div className="comparison-layout">
      <section className="panel setup-panel">
        <div className="panel-heading setup-heading"><div><span className="step-number">01</span><div><h2>Set your evaluation context</h2><p>Apply identical conditions to every model.</p></div></div><Settings2 size={17} className="muted" /></div>
        <div className="form-grid">
          <label className="field"><span>Study region</span><div className="select-wrap"><MapPin size={15} /><select value={region} onChange={(e) => setRegion(e.target.value)}>{regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select><ChevronDown size={14} /></div></label>
          <label className="field"><span>Target crop</span><div className="select-wrap"><Sprout size={15} /><select value={crop} onChange={(e) => setCrop(e.target.value)}>{["Wheat", "Rice", "Cotton", "Sugarcane", "Maize"].map((item) => <option key={item}>{item}</option>)}</select><ChevronDown size={14} /></div></label>
          <label className="field"><span>Growing season</span><div className="select-wrap"><Activity size={15} /><select value={season} onChange={(e) => setSeason(e.target.value)}>{["Rabi 2025–26", "Kharif 2025", "Rabi 2024–25", "Kharif 2024"].map((item) => <option key={item}>{item}</option>)}</select><ChevronDown size={14} /></div></label>
          <label className="field"><span>Imagery / dataset</span><div className="select-wrap"><Satellite size={15} /><select value={dataset} onChange={(e) => setDataset(e.target.value)}>{datasets.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><ChevronDown size={14} /></div></label>
        </div>
        <div className="model-select-head"><div><h3>Models to evaluate</h3><span>Select 2–4 models <span className="soft-count">{selectedModels.length} selected</span></span></div><button className="text-button" onClick={() => models.length && models.forEach((m) => { if (!selectedModels.includes(m.id)) toggleModel(m.id); })}><Check size={14} /> Select all</button></div>
        <div className="model-choice-list">{models.map((m) => {
          const checked = selectedModels.includes(m.id);
          return <button key={m.id} className={`model-choice ${checked ? "chosen" : ""}`} onClick={() => toggleModel(m.id)} aria-pressed={checked}><span className="model-check">{checked && <Check size={12} />}</span><span className="model-swatch" style={{ background: m.color }} /><span className="model-choice-name"><strong>{m.name}</strong><small>{m.provider} · {m.modality}</small></span><span className="model-type">{m.id === "resnet" ? "BASELINE" : "FOUNDATION"}</span></button>;
        })}</div>
        <div className="run-controls"><div className="run-notice"><ShieldCheck size={15} /><span>Controlled setup · same region, crop &amp; season for all models</span></div><button className="button primary run-button" disabled={busy || selectedModels.length < 2} onClick={onRun}>{busy ? <><span className="spinner" /> Saving…</> : <><Check size={15} /> Save comparison setup</>}</button></div>
      </section>
      <section className="panel result-panel">
        <div className="panel-heading"><div><h2>Evaluation results</h2><p>{run ? `${run.crop} · ${run.region_name || regionLabel(run.region_id)} · ${run.season}` : "Save a comparison setup to record the context"}</p></div>{run && <button className="icon-button export-button" aria-label="Download results as CSV" title="Download results as CSV" onClick={() => downloadCsv(run)}><Download size={16} /></button>}</div>
        {winner && <div className="winner-banner"><div className="winner-medal"><Target size={17} /></div><div><span>TOP PERFORMER · F1 SCORE</span><strong>{winner.model_name}</strong></div><span className="winner-score">{winner.f1}%</span></div>}
        {results.length ? <div className="result-table-wrap"><table className="result-table"><thead><tr><th>MODEL</th><th>F1 ↑</th><th>IoU</th><th>ACC.</th><th>KAPPA</th><th>MS/TILE</th></tr></thead><tbody>{[...results].sort((a, b) => Number(b.f1) - Number(a.f1)).map((r, i) => <tr key={r.model_id} className={winner && r.model_id === winner.model_id ? "top-row" : ""}><td><span className="result-model"><i style={{ background: r.color }} />{r.model_name}{winner && r.model_id === winner.model_id && <span className="best-tag">BEST</span>}</span></td><td className={Number.isFinite(r.f1) ? "strong-cell" : "not-evaluated"}>{metricText(r.f1)}</td><td className="not-evaluated">{metricText(r.iou)}</td><td className="not-evaluated">{metricText(r.accuracy)}</td><td className="not-evaluated">{metricText(r.kappa)}</td><td className="not-evaluated">{metricText(r.latency)}</td></tr>)}</tbody></table><div className="result-footnote"><CircleHelp size={13} /><span>Demo metadata only. Metrics remain unevaluated until Phase-II ground-truth validation.</span></div></div> : <div className="result-empty"><div className="empty-graphic"><BarChart3 size={26} /></div><strong>Results will appear here</strong><span>Select your models and save the comparison setup. No inference is run.</span><button className="text-button" onClick={() => onRun()}>Save current setup <ArrowRight size={14} /></button></div>}
        {results.length > 0 && (winner
          ? <div className="mini-bar-chart">{[...results].filter((result) => Number.isFinite(result.f1)).sort((a, b) => b.f1 - a.f1).map((r) => <div className="mini-bar-row" key={r.model_id}><span>{r.model_name}</span><div><i style={{ width: `${r.f1}%`, background: r.color }} /></div><strong>{r.f1}</strong></div>)}</div>
          : <div className="unmeasured-chart">{NOT_EVALUATED}</div>)}
      </section>
    </div>
    {run && <>
      <section className="panel context-panel">
        <div className="panel-heading"><div><h2>Run context</h2><p>Reproducibility details for the selected comparison</p></div><span className="run-id">RUN #{run.id.slice(0, 8)}</span></div>
        <div className="context-grid">
          <ContextItem icon={MapPin} label="Region" value={run.region_name || regionLabel(run.region_id)} />
          <ContextItem icon={Sprout} label="Crop" value={run.crop} />
          <ContextItem icon={Activity} label="Season" value={run.season} />
          <ContextItem icon={Satellite} label="Dataset" value={run.dataset_name || datasets.find((d) => d.id === run.dataset_id)?.name || "Sentinel-2 L2A"} />
          <ContextItem icon={Clock3} label="Created" value={new Date(run.created_at).toLocaleString("en-IN")} />
        </div>
        <div className="evaluation-blocked" role="alert">
          <strong>Evaluation blocked</strong>
          <span>{run.evaluation_reason || "The API did not provide an evaluation status or reason."}</span>
        </div>
      </section>
      <ProvenancePanel run={run} />
    </>}
    <div className="disclaimer"><CircleHelp size={15} /><span>No performance results are available. Model metrics will remain “{NOT_EVALUATED}” until a documented Phase-II evaluation is completed.</span></div>
  </>;
}

function ContextItem({ icon: Icon, label, value }) {
  return <div className="context-item"><Icon size={15} /><div><small>{label}</small><strong>{value}</strong></div></div>;
}

function ProvenancePanel({ run }) {
  const provenance = run.provenance || {};
  const fields = [
    ["dataset_release", "Dataset release"],
    ["label_source_version", "Label source / version"],
    ["acquisition_start", "Acquisition start"],
    ["acquisition_end", "Acquisition end"],
    ["split_id", "Evaluation split"],
    ["split_method", "Split method"],
    ["model_revisions", "Model revisions"],
    ["preprocessing", "Preprocessing"],
    ["input_resolution", "Input resolution"],
    ["metric_config", "Metric configuration"],
    ["random_seed", "Random seed"],
    ["code_revision", "Code revision"],
    ["hardware_runtime", "Hardware / runtime"],
  ];
  return <section className="panel provenance-panel">
    <div className="panel-heading"><div><h2>Evaluation provenance</h2><p>{run.provenance_status === "declared_unverified" ? "Declared values are unverified." : "No provenance was recorded because inference was not run."}</p></div><span className="run-id">{run.provenance_status === "declared_unverified" ? "UNVERIFIED" : "NOT RECORDED"}</span></div>
    <div className="provenance-grid">{fields.map(([key, label]) => {
      const value = provenance[key];
      const displayValue = value && typeof value === "object"
        ? Object.entries(value).map(([name, revision]) => `${name}: ${revision}`).join("; ")
        : value == null ? "Not recorded" : String(value);
      return <div className="context-item" key={key}><div><small>{label}</small><strong>{displayValue}</strong></div></div>;
    })}</div>
    <div className="result-footnote"><CircleHelp size={13} /><span>{run.provenance_reason || "The API did not provide a provenance status or reason."}</span></div>
  </section>;
}

function downloadCsv(run) {
  const provenance = run.provenance || {};
  const provenanceFields = [
    "dataset_release", "label_source_version", "acquisition_start", "acquisition_end",
    "split_id", "split_method", "model_revisions", "preprocessing", "input_resolution",
    "metric_config", "random_seed", "code_revision", "hardware_runtime",
  ];
  const rows = [[
    "model", "f1_percent", "iou_percent", "accuracy_percent", "kappa", "latency_ms_per_tile",
    "is_demo", "evaluation_status", "evaluation_reason", "provenance_status",
    ...provenanceFields,
  ], ...run.results.map((r) => [
    r.model_name,
    ...[r.f1, r.iou, r.accuracy, r.kappa, r.latency].map(metricText),
    true,
    run.evaluation_status || "not_reported",
    run.evaluation_reason || "The API did not provide an evaluation reason.",
    run.provenance_status || "not_reported",
    ...provenanceFields.map((key) => {
      const value = provenance[key];
      return value == null ? "Not recorded" : typeof value === "object" ? JSON.stringify(value) : value;
    }),
  ])];
  const csv = rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\n");
  const link = document.createElement("a");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  link.href = url;
  link.download = `agrifm-${run.id.slice(0, 8)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function ModelLibrary({ models, onCompare, onAddModel }) {
  return <>
    <PageHeading eyebrow="MODEL REGISTRY" title="Models in the study" subtitle="A consistent registry of geospatial foundation models and a supervised reference baseline." action={<button className="button primary" onClick={onCompare}><FlaskConical size={16} /> Compare models <ArrowRight size={15} /></button>} />
    <div className="library-intro"><div className="soft-icon"><Layers3 size={19} /></div><div><strong>Shared evaluation context</strong><span>Model descriptions are catalog metadata. No model has been evaluated in this prototype.</span></div><span className="illustrative-tag">DEMO DATA</span></div>
    <div className="model-card-grid">{models.map((m) => <article className="panel model-card" key={m.id}><div className="model-card-top"><div className="large-swatch" style={{ background: m.color }}>{m.name.slice(0, 1)}</div><span className={`model-type-badge ${m.id === "resnet" ? "baseline-badge" : ""}`}>{m.id === "resnet" ? "BASELINE" : "FOUNDATION"}</span></div><h2>{m.name}</h2><p className="model-provider">{m.provider}</p><p className="model-description">{m.description}</p><div className="model-tags"><span>{m.family}</span><span>{m.modality}</span></div><div className="model-facts"><div><small>Parameters</small><strong>{m.parameters}</strong></div><div><small>Evaluation</small><strong>Phase-II</strong></div><div><small>Status</small><strong>Not evaluated</strong></div></div><button className="card-link" onClick={() => onAddModel(m.id)}>Add to a comparison <ArrowRight size={14} /></button></article>)}</div>
  </>;
}

function Datasets({ datasets }) {
  return <>
    <PageHeading eyebrow="DATA CATALOG" title="Datasets & imagery" subtitle="Metadata catalog only; imagery has not been ingested or validated for evaluation." />
    <div className="dataset-summary"><div className="dataset-summary-icon"><Database size={20} /></div><div><strong>Data sources for a reproducible study</strong><span>This starter app catalogs representative sources. No imagery is downloaded or evaluated by the demo API.</span></div><span className="illustrative-tag">CATALOG ONLY</span></div>
    <section className="panel dataset-panel"><div className="panel-heading"><div><h2>Catalog entries</h2><p>Registry metadata only; no source is currently available for model evaluation.</p></div><span className="count-badge">{datasets.length} sources</span></div><div className="table-wrap"><table><thead><tr><th>DATASET</th><th>PROVIDER</th><th>SPATIAL SCALE</th><th>COVERAGE</th><th>DATA TYPE</th><th>STATUS</th></tr></thead><tbody>{datasets.map((d) => <tr key={d.id}><td><span className="dataset-name"><span className="dataset-mini-icon"><Satellite size={14} /></span><strong>{d.name}</strong></span></td><td>{d.provider}</td><td>{d.resolution}</td><td>{d.coverage}</td><td>{d.type}</td><td><span className={`data-status ${d.status === "Available for evaluation" ? "status-ready" : ""}`}><i />{d.status}</span></td></tr>)}</tbody></table></div></section>
    <div className="info-columns"><div className="panel info-card"><div className="info-icon blue"><Satellite size={17} /></div><h3>Optical imagery</h3><p>Sentinel-2 Level-2A provides multispectral surface reflectance at 10 m for visible, near-infrared, and selected shortwave-infrared bands.</p><span>Source: Copernicus Data Space Ecosystem</span></div><div className="panel info-card"><div className="info-icon purple"><Layers3 size={17} /></div><h3>Radar complement</h3><p>Sentinel-1 SAR can support observations through cloud cover and contribute a complementary signal to optical imagery.</p><span>Source: Copernicus Data Space Ecosystem</span></div><div className="panel info-card"><div className="info-icon amber"><ShieldCheck size={17} /></div><h3>Ground truth matters</h3><p>Model evaluation requires documented, spatially aligned labels and a held-out split that prevents geographic leakage.</p><span>Project recommendation</span></div></div>
  </>;
}

function Methodology({ methodology }) {
  const metrics = methodology?.metrics || [];
  const protocol = methodology?.protocol || [];
  return <>
    <PageHeading eyebrow="STUDY DESIGN" title="Methodology & evaluation" subtitle="A region-controlled framework for a fair, transparent comparison of geospatial models." />
    <div className="method-hero"><div className="method-hero-icon"><ShieldCheck size={24} /></div><div><span className="eyebrow">COMPARATIVE STUDY</span><h2>Control the context. Compare the models.</h2><p>Each run holds the selected crop, season, region, and imagery source constant across candidate models. This interface demonstrates the workflow; it does not run inference on imagery.</p></div></div>
    <div className="method-grid">
      <section className="panel method-panel"><div className="panel-heading"><div><h2>Evaluation protocol</h2><p>Recommended sequence for a valid comparison</p></div><span className="soft-icon"><FlaskConical size={17} /></span></div><div className="protocol-list">{protocol.map((step, i) => <div className="protocol-step" key={step}><span>{String(i + 1).padStart(2, "0")}</span><p>{step}</p></div>)}</div></section>
      <section className="panel method-panel"><div className="panel-heading"><div><h2>Metrics reported</h2><p>Common segmentation and runtime measures</p></div><span className="soft-icon"><Target size={17} /></span></div><div className="metric-def-list">{metrics.map((metric) => <div key={metric.name} className="metric-def"><div><strong>{metric.name}</strong><span>{metric.unit}</span></div><p>{metric.description}</p></div>)}</div></section>
    </div>
    <section className="panel research-notes"><div className="panel-heading"><div><h2>Research integrity notes</h2><p>Important boundaries of this prototype</p></div><span className="soft-icon"><BookOpen size={17} /></span></div><div className="notes-grid"><div><ShieldCheck size={16} /><p><strong>No measured scores.</strong> This prototype contains no model performance scores or rankings.</p></div><div><Database size={16} /><p><strong>Catalog is not a data pipeline.</strong> This prototype does not download imagery, prepare labels, train models, or execute model inference.</p></div><div><MapPin size={16} /><p><strong>Geographic splits are essential.</strong> Document sampling, label provenance, dates, and spatial train/test separation before interpreting metrics.</p></div></div></section>
    <section className="project-credits"><div className="credits-emblem"><Sprout size={22} /></div><div><span className="eyebrow">ABOUT THIS PROTOTYPE</span><h2>Foundation Model for Precision Agriculture: A Comparative Study</h2><p>B.Tech Major Project · IILM University, Greater Noida · School of Computer Science &amp; Engineering · Session 2026–27</p><div className="credit-people"><span><small>STATUS</small>Research workflow prototype · no inference pipeline connected</span><span><small>RESULTS</small>{NOT_EVALUATED}</span></div></div></section>
  </>;
}

export default App;
