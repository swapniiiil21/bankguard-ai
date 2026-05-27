'use client';

import React, { useState, useEffect, useRef, useCallback, DragEvent, ChangeEvent } from 'react';
import { useAlertStore } from '../../../hooks/useWebsocket';

// ─── Types ──────────────────────────────────────────────────────────────────
interface FormState {
  account_id: string;
  amount: string;
  merchant: string;
  device_fingerprint: string;
  ip_address: string;
  transaction_type: string;
}

interface UploadedFile {
  name: string;
  size: number;
  type: string;
  preview?: string;
  status: 'uploading' | 'ready';
}

interface LogEntry {
  time: string;
  level: string;
  text: string;
}

// ─── Fraud Presets ───────────────────────────────────────────────────────────
const PRESETS: Record<string, { label: string; emoji: string; color: string; form: Partial<FormState> }> = {
  mule_ring: {
    label: 'Shared Device (Mule Ring)',
    emoji: '🔗',
    color: 'from-red-500/20 to-rose-500/10 border-red-500/30 hover:border-red-400/60',
    form: { account_id: 'ACC_NEW_999', amount: '8500', merchant: 'CryptoEx', device_fingerprint: 'DEV_XY99', ip_address: '192.168.1.100', transaction_type: 'TRANSFER' },
  },
  structuring: {
    label: 'Structuring / Smurfing',
    emoji: '💵',
    color: 'from-yellow-500/20 to-amber-500/10 border-yellow-500/30 hover:border-yellow-400/60',
    form: { account_id: 'ACC_123', amount: '9999', merchant: 'Cash Deposit', device_fingerprint: 'DEV_ATM_01', ip_address: '10.0.0.1', transaction_type: 'CASH_DEPOSIT' },
  },
  ato: {
    label: 'Account Takeover',
    emoji: '🚨',
    color: 'from-purple-500/20 to-violet-500/10 border-purple-500/30 hover:border-purple-400/60',
    form: { account_id: 'ACC_VICTIM_77', amount: '15000', merchant: 'Wire Transfer', device_fingerprint: 'DEV_UNKNOWN_BURNER', ip_address: '185.220.101.42', transaction_type: 'WIRE' },
  },
  velocity: {
    label: 'Velocity Fraud',
    emoji: '⚡',
    color: 'from-blue-500/20 to-cyan-500/10 border-blue-500/30 hover:border-blue-400/60',
    form: { account_id: 'ACC_456', amount: '250', merchant: 'OnlineMart', device_fingerprint: 'DEV_PHONE_08', ip_address: '203.0.113.55', transaction_type: 'PURCHASE' },
  },
};

// ─── Pipeline steps ──────────────────────────────────────────────────────────
const PIPELINE_STEPS = [
  { key: 'ingest',    label: 'API Ingestion',         color: '#60a5fa', delay: 0 },
  { key: 'kafka',     label: 'Kafka Publish',          color: '#f59e0b', delay: 400 },
  { key: 'worker',    label: 'Worker Assignment',      color: '#818cf8', delay: 900 },
  { key: 'ocr',       label: 'OCR Extraction',         color: '#34d399', delay: 1400 },
  { key: 'kyc',       label: 'KYC Validation',         color: '#22d3ee', delay: 1900 },
  { key: 'graph',     label: 'Graph Intelligence',     color: '#f472b6', delay: 2400 },
  { key: 'reflect',   label: 'Reflection Agent',       color: '#a78bfa', delay: 3000 },
  { key: 'score',     label: 'Risk Scoring',           color: '#fb923c', delay: 3500 },
  { key: 'ws',        label: 'WebSocket Alert',        color: '#4ade80', delay: 4000 },
];

const LOG_MESSAGES: Record<string, string> = {
  ingest:  '[API] POST /api/v1/transactions/ingest → 202 Accepted',
  kafka:   '[KAFKA] Published to transactions.raw (Partition 2) offset=8812',
  worker:  '[WORKER] Pod bankguard-worker-5f7a picked up event',
  ocr:     '[OCR] Tesseract extracted 14 fields from uploaded document',
  kyc:     '[KYC] Aadhaar → VERIFIED  PAN → CROSS-CHECKED',
  graph:   '[NEO4J] MATCH (a:Account)-[:USED]->(d:Device) WHERE d.id = $fp → 2 suspicious rings found',
  reflect: '[LANGGRAPH] Reflection Agent: confidence=0.94, escalating to Human Review',
  score:   '[RISK] Final Fraud Score: 94/100 — CRITICAL',
  ws:      '[WEBSOCKET] HIGH_RISK_ALERT emitted to /ws/alerts → received by 1 client',
};

const now = () => new Date().toISOString().split('T')[1].slice(0, 12);

// ════════════════════════════════════════════════════════════════════════════
export default function SimulatePortal() {
  const addAlert = useAlertStore((state) => state.addAlert);
  const setTimelineTrace = useAlertStore((state) => state.setTimelineTrace);
  const setGraphData = useAlertStore((state) => state.setGraphData);
  const setUploadedDocuments = useAlertStore((state) => state.setUploadedDocuments);

  const [demoMode, setDemoMode] = useState(false);
  const [running, setRunning]   = useState(false);
  const [activeStep, setActiveStep] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set());
  const [logs, setLogs]         = useState<LogEntry[]>([]);
  const [fraudScore, setFraudScore] = useState<number | null>(null);
  const [files, setFiles]       = useState<UploadedFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const [activePreset, setActivePreset] = useState<string | null>(null);

  const logRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const demoIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [form, setForm] = useState<FormState>({
    account_id: '', amount: '', merchant: '', device_fingerprint: '', ip_address: '', transaction_type: 'TRANSFER',
  });

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const addLog = useCallback((level: string, text: string) => {
    setLogs(prev => [...prev, { time: now(), level, text }]);
  }, []);

  // ─── File handling ──────────────────────────────────────────────────────
  const handleFiles = useCallback((incoming: FileList | null) => {
    if (!incoming) return;
    Array.from(incoming).forEach(file => {
      const entry: UploadedFile = { name: file.name, size: file.size, type: file.type, status: 'uploading' };
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = e => {
          setFiles(prev => prev.map(f => f.name === file.name ? { ...f, preview: e.target?.result as string, status: 'ready' } : f));
        };
        reader.readAsDataURL(file);
      }
      setFiles(prev => [...prev, entry]);
      setTimeout(() => {
        setFiles(prev => {
          const newFiles = prev.map(f => f.name === file.name ? { ...f, status: 'ready' as const } : f);
          setUploadedDocuments(newFiles.map(f => f.name));
          return newFiles;
        });
        addLog('OCR', `Document uploaded: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`);
      }, 1200);
    });
  }, [addLog]);

  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  // ─── Apply preset ───────────────────────────────────────────────────────
  const applyPreset = useCallback((key: string) => {
    const preset = PRESETS[key];
    if (!preset) return;
    setActivePreset(key);
    setForm(prev => ({ ...prev, ...preset.form }));
    addLog('USER', `Scenario preset loaded: ${preset.label}`);
  }, [addLog]);

  // ─── Run investigation ──────────────────────────────────────────────────
  const startInvestigation = useCallback(async () => {
    if (running || !form.account_id) return;
    setRunning(true);
    setCompletedSteps(new Set());
    setFraudScore(null);
    addLog('SYS', '━━━ New Investigation Initiated ━━━');

    let currentTrace: any[] = [];
    setTimelineTrace([]);

    for (const step of PIPELINE_STEPS) {
      await new Promise<void>(resolve => setTimeout(resolve, step.delay === 0 ? 100 : 400));
      setActiveStep(step.key);
      addLog(step.key.toUpperCase(), LOG_MESSAGES[step.key].replace('$fp', form.device_fingerprint || 'DEV_UNKNOWN'));
      setCompletedSteps(prev => new Set([...prev, step.key]));

      // Update global timeline
      currentTrace = [...currentTrace, { node: step.label, status: 'completed' }];
      setTimelineTrace(currentTrace);

      // Update global graph when we reach graph step
      if (step.key === 'graph') {
         setGraphData([
            { data: { id: form.account_id, label: 'Current User' } },
            { data: { id: form.device_fingerprint || 'DEV_UNKNOWN', label: 'Suspicious Device', type: 'Device' } },
            { data: { id: 'ACC_VICTIM_99', label: 'Compromised User' } },
            { data: { source: form.account_id, target: form.device_fingerprint || 'DEV_UNKNOWN', label: 'USED_DEVICE' } },
            { data: { source: 'ACC_VICTIM_99', target: form.device_fingerprint || 'DEV_UNKNOWN', label: 'USED_DEVICE' } },
         ]);
      }
    }

    // Final state
    setActiveStep(null);
    setFraudScore(94);
    setRunning(false);
    addAlert({ transaction_id: `TXN_${Math.floor(Math.random() * 90000 + 10000)}`, account_id: form.account_id, fraud_score: 94, reason: 'Shared Device + Graph Anomaly' });
    addLog('SYS', '━━━ Investigation Complete — Case Escalated ━━━');
  }, [running, form, addLog, addAlert]);

  // ─── Demo mode ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (demoMode) {
      const keys = Object.keys(PRESETS);
      let idx = 0;
      demoIntervalRef.current = setInterval(() => {
        applyPreset(keys[idx % keys.length]);
        idx++;
      }, 5000);
    } else {
      if (demoIntervalRef.current) clearInterval(demoIntervalRef.current);
    }
    return () => { if (demoIntervalRef.current) clearInterval(demoIntervalRef.current); };
  }, [demoMode, applyPreset]);

  // ─── Log colour ─────────────────────────────────────────────────────────
  const logColor = (level: string) => {
    if (level === 'WEBSOCKET' || level === 'WS') return 'text-green-400';
    if (level === 'NEO4J' || level === 'GRAPH') return 'text-blue-400';
    if (level === 'LANGGRAPH' || level === 'REFLECT') return 'text-purple-400';
    if (level === 'KAFKA') return 'text-yellow-400';
    if (level === 'RISK' || level === 'SCORE') return 'text-red-400';
    if (level === 'SYS') return 'text-slate-500';
    return 'text-slate-300';
  };

  // ════════════════════════════════════════════════════════════════════════
  return (
    <div className="h-screen overflow-y-auto bg-[#030712] text-slate-200" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* ── Top navigation bar ── */}
      <header className="border-b border-slate-800/60 bg-[#030712]/80 backdrop-blur sticky top-0 z-10 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-lg">🛡</div>
          <span className="font-bold text-lg tracking-tight">BankGuard <span className="text-blue-400">AI</span></span>
          <span className="ml-3 text-xs px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-400">Simulation Portal</span>
        </div>
        <nav className="flex items-center gap-6 text-sm text-slate-400">
          <a href="/investigations" className="hover:text-white transition-colors">Dashboard</a>
          <a href="/simulate" className="text-white font-medium">Simulate</a>
        </nav>
        <button
          onClick={() => setDemoMode(d => !d)}
          className={`relative px-4 py-2 rounded-lg text-sm font-semibold transition-all border ${
            demoMode
              ? 'bg-red-500/20 border-red-500/60 text-red-400 shadow-lg shadow-red-900/30'
              : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-500'
          }`}
        >
          {demoMode && <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-red-500 animate-ping" />}
          {demoMode ? '🔴 Demo Mode ACTIVE' : '▶ Enable Demo Mode'}
        </button>
      </header>

      {/* ── Hero ── */}
      <div className="px-6 py-6">
        <h1 className="text-3xl font-bold tracking-tight">
          Fraud Intake &amp; <span className="bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">Simulation Engine</span>
        </h1>
        <p className="text-slate-400 mt-1 text-sm">Inject synthetic fraud scenarios into the live distributed AI ecosystem and watch every microservice respond in real-time.</p>
      </div>

      {/* ── Main grid ── */}
      <div className="px-6 pb-6 grid grid-cols-2 gap-6">

        {/* ── LEFT COLUMN ── */}
        <div className="flex flex-col gap-6">

          {/* KYC Document Upload */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur p-5">
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-3 font-semibold">KYC Document Upload</p>
            {/* Hidden real file input */}
            <input ref={fileInputRef} type="file" multiple accept="image/*,.pdf,.csv" className="hidden" onChange={(e: ChangeEvent<HTMLInputElement>) => handleFiles(e.target.files)} />
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`rounded-xl border-2 border-dashed p-8 flex flex-col items-center justify-center cursor-pointer transition-all ${
                dragging ? 'border-blue-500 bg-blue-500/10' : 'border-slate-700 hover:border-slate-500 hover:bg-slate-800/40'
              }`}
            >
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-blue-500/30 flex items-center justify-center text-2xl mb-3">📄</div>
              <p className="font-semibold">Drop files or click to browse</p>
              <p className="text-slate-500 text-xs mt-1">Aadhaar · PAN Card · Bank Statement CSV · Selfie</p>
            </div>
            {/* File list */}
            {files.length > 0 && (
              <div className="mt-3 space-y-2">
                {files.map((f, i) => (
                  <div key={i} className="flex items-center gap-3 bg-slate-800/60 rounded-lg px-3 py-2">
                    {f.preview ? <img src={f.preview} alt="" className="w-8 h-8 rounded object-cover" /> : <span className="text-lg">📎</span>}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm truncate font-medium">{f.name}</p>
                      <p className="text-xs text-slate-500">{(f.size / 1024).toFixed(1)} KB</p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${f.status === 'ready' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400 animate-pulse'}`}>
                      {f.status === 'ready' ? '✓ Ready' : 'Uploading…'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Scenario Presets */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur p-5">
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-3 font-semibold">Fraud Scenario Presets</p>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(PRESETS).map(([key, p]) => (
                <button
                  key={key}
                  onClick={() => applyPreset(key)}
                  className={`text-left px-4 py-3 rounded-xl border bg-gradient-to-br transition-all ${p.color} ${activePreset === key ? 'ring-1 ring-white/20' : ''}`}
                >
                  <span className="text-lg">{p.emoji}</span>
                  <p className="text-sm font-semibold mt-1">{p.label}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Payload Configuration */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur p-5">
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-3 font-semibold">Payload Configuration</p>
            <div className="grid grid-cols-2 gap-3">
              {([
                ['account_id', 'Account ID', 'ACC_123'],
                ['amount', 'Amount ($)', '5000'],
                ['merchant', 'Merchant', 'PayEasy Inc.'],
                ['device_fingerprint', 'Device Fingerprint', 'DEV_XXXX'],
                ['ip_address', 'IP Address', '0.0.0.0'],
                ['transaction_type', 'Transaction Type', 'TRANSFER'],
              ] as [keyof FormState, string, string][]).map(([field, label, placeholder]) => (
                <div key={field}>
                  <label className="block text-xs text-slate-500 mb-1">{label}</label>
                  <input
                    value={form[field]}
                    placeholder={placeholder}
                    onChange={e => setForm(prev => ({ ...prev, [field]: e.target.value }))}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 outline-none transition-all"
                  />
                </div>
              ))}
            </div>

            {/* CTA Button */}
            <button
              onClick={startInvestigation}
              disabled={running || !form.account_id}
              className={`w-full mt-5 py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all ${
                running
                  ? 'bg-blue-600/40 cursor-wait'
                  : form.account_id
                  ? 'bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 shadow-lg shadow-blue-900/30 hover:shadow-blue-800/50 active:scale-[0.98]'
                  : 'bg-slate-800 text-slate-600 cursor-not-allowed'
              } text-white`}
            >
              {running ? (
                <>
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/></svg>
                  Executing Investigation…
                </>
              ) : (
                <>▶ Start Live Investigation</>
              )}
            </button>
            {!form.account_id && <p className="text-center text-xs text-slate-600 mt-2">Fill in Account ID or pick a preset to enable</p>}
          </div>

        </div>

        {/* ── RIGHT COLUMN ── */}
        <div className="flex flex-col gap-4">

          {/* Pipeline Progress */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur p-5">
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-4 font-semibold">Live Pipeline Status</p>
            <div className="space-y-2">
              {PIPELINE_STEPS.map((step) => {
                const done   = completedSteps.has(step.key);
                const active = activeStep === step.key;
                return (
                  <div key={step.key} className="flex items-center gap-3">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 transition-all ${
                      done    ? 'bg-green-500 text-white' :
                      active  ? 'bg-blue-500 text-white animate-pulse' :
                                'bg-slate-800 text-slate-600'
                    }`}>
                      {done ? '✓' : active ? '⟳' : '·'}
                    </div>
                    <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: done ? '100%' : active ? '60%' : '0%', background: step.color }}
                      />
                    </div>
                    <span className={`text-xs w-36 ${done ? 'text-green-400' : active ? 'text-blue-300' : 'text-slate-600'}`}>{step.label}</span>
                  </div>
                );
              })}
            </div>

            {/* Fraud score badge */}
            {fraudScore !== null && (
              <div className="mt-5 p-4 rounded-xl bg-gradient-to-r from-red-900/40 to-rose-900/20 border border-red-500/40 flex items-center justify-between">
                <div>
                  <p className="text-xs text-red-400 font-semibold uppercase tracking-wider">FINAL FRAUD SCORE</p>
                  <p className="text-slate-300 text-xs mt-1">Escalated → Human Review Required</p>
                </div>
                <div className="text-4xl font-black text-red-400">{fraudScore}<span className="text-lg text-red-600">/100</span></div>
              </div>
            )}
          </div>

          {/* Live Execution Log Terminal */}
          <div className="rounded-2xl border border-slate-800 bg-black flex-1 flex flex-col overflow-hidden min-h-0">
            <div className="bg-slate-900 px-4 py-2.5 flex items-center gap-2 border-b border-slate-800 flex-shrink-0">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <div className="w-3 h-3 rounded-full bg-yellow-500" />
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <span className="ml-2 text-xs text-slate-500 font-mono">bankguard@ai-ops: live execution stream</span>
            </div>
            <div ref={logRef} className="flex-1 overflow-y-auto p-4 space-y-1 font-mono text-xs" style={{ maxHeight: '260px' }}>
              {logs.length === 0 ? (
                <span className="text-slate-700">▋ Awaiting payload injection…</span>
              ) : logs.map((log, i) => (
                <div key={i} className="flex gap-2">
                  <span className="text-slate-700 flex-shrink-0">{log.time}</span>
                  <span className={`flex-shrink-0 w-20 ${logColor(log.level)}`}>[{log.level}]</span>
                  <span className={logColor(log.level)}>{log.text}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Debug Metrics */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur p-4">
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-3 font-semibold">🔬 Observability &amp; Debug Metrics</p>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: 'Kafka Topic Lag',   value: demoMode ? `${Math.floor(Math.random() * 40 + 5)} msgs` : '0 msgs', color: 'text-yellow-400' },
                { label: 'LangSmith Cost',     value: '$0.004',       color: 'text-green-400' },
                { label: 'Trace ID',           value: 'f7a91b2c',     color: 'text-blue-400' },
                { label: 'API Latency',        value: '124 ms',       color: 'text-slate-300' },
                { label: 'Token Usage',        value: '~1.2k tokens', color: 'text-purple-400' },
                { label: 'Neo4j Query Time',   value: '18 ms',        color: 'text-cyan-400' },
              ].map(m => (
                <div key={m.label} className="bg-slate-950 border border-slate-800/60 rounded-lg p-3">
                  <p className="text-xs text-slate-600">{m.label}</p>
                  <p className={`font-bold text-sm mt-0.5 font-mono ${m.color}`}>{m.value}</p>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
