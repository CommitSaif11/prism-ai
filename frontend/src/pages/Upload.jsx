import React, { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload as UploadIcon, FileText, CheckCircle, AlertTriangle, ArrowRight, Cpu, Zap, Shield } from 'lucide-react'
import { useStore } from '../store/useStore.js'

const STEPS = [
  { icon: FileText, label: 'Parse',    desc: 'Rule-based extraction of LTE/NR bands and CA combos' },
  { icon: Shield,   label: 'Validate', desc: 'Confidence scoring against 3GPP spec constraints' },
  { icon: Cpu,      label: 'Enrich',   desc: 'Mistral-7B AI adds explanations and spec references' },
  { icon: Zap,      label: 'Ready',    desc: 'Combinations indexed and ready for exploration' },
]

export default function Upload() {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState(null)
  const inputRef = useRef()
  const navigate = useNavigate()
  const { uploadFile, loading, error, uploadResult, clearError } = useStore(s => ({
    uploadFile: s.uploadFile,
    loading: s.loading.upload,
    error: s.error,
    uploadResult: s.uploadResult,
    clearError: s.clearError,
  }))

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }, [])

  const handleUpload = async () => {
    if (!file) return
    clearError()
    await uploadFile(file)
  }

  const confidence = uploadResult?.confidence
  const confColor = confidence >= 0.85 ? 'var(--green)' : confidence >= 0.5 ? 'var(--amber)' : 'var(--red)'

  return (
    <div style={{ minHeight: '100vh', padding: '40px', maxWidth: '900px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '40px', animationDelay: '0s' }} className="fade-up">
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: '8px' }}>
          SAMSUNG PRISM // UE CAPABILITY PARSER
        </div>
        <h1 style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em', marginBottom: '8px' }}>
          Upload UE Capability Log
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '15px' }}>
          Parse UE_Capa.txt files to extract LTE/NR band combinations with AI-powered enrichment.
        </p>
      </div>

      {/* Pipeline steps */}
      <div style={{ display: 'flex', gap: '0', marginBottom: '36px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)', overflow: 'hidden' }} className="fade-up">
        {STEPS.map(({ icon: Icon, label, desc }, i) => (
          <div key={i} style={{
            flex: 1,
            padding: '16px',
            borderRight: i < STEPS.length - 1 ? '1px solid var(--border)' : 'none',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            position: 'relative',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ padding: '6px', background: 'var(--accent-dim)', borderRadius: 'var(--radius-sm)' }}>
                <Icon size={14} color="var(--accent-bright)" />
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700, color: 'var(--accent-bright)' }}>{i + 1}. {label}</span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: '1.4' }}>{desc}</p>
          </div>
        ))}
      </div>

      {/* Drop zone */}
      <div
        className="fade-up"
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? 'var(--accent)' : file ? 'var(--green)' : 'var(--border)'}`,
          borderRadius: 'var(--radius-xl)',
          padding: '60px 40px',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragging ? 'var(--accent-dim)' : file ? 'var(--green-dim)' : 'var(--bg-card)',
          transition: 'var(--transition-lg)',
          marginBottom: '24px',
          animationDelay: '0.1s',
        }}
      >
        <input ref={inputRef} type="file" accept=".txt,.log" style={{ display: 'none' }} onChange={e => setFile(e.target.files[0])} />

        {file ? (
          <>
            <CheckCircle size={40} color="var(--green)" style={{ margin: '0 auto 16px' }} />
            <div style={{ fontSize: '18px', fontWeight: 600, marginBottom: '6px' }}>{file.name}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '13px', fontFamily: 'var(--font-mono)' }}>
              {(file.size / 1024).toFixed(1)} KB · Click to change
            </div>
          </>
        ) : (
          <>
            <UploadIcon size={40} color="var(--text-muted)" style={{ margin: '0 auto 16px' }} />
            <div style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>Drop UE_Capa.txt here</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>or click to browse · .txt / .log files</div>
          </>
        )}
      </div>

      {/* Error */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '14px 16px', background: 'var(--red-dim)', border: '1px solid var(--red)', borderRadius: 'var(--radius)', marginBottom: '16px', fontSize: '13px', color: 'var(--red)' }}>
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      {/* Action */}
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <button
          className="btn btn-primary"
          disabled={!file || loading}
          onClick={handleUpload}
          style={{ fontSize: '15px', padding: '12px 28px', opacity: (!file || loading) ? 0.5 : 1, minWidth: '160px', justifyContent: 'center' }}
        >
          {loading ? (
            <>
              <div className="spinner" style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%' }} />
              Processing…
            </>
          ) : 'Parse & Analyze'}
        </button>
        {uploadResult && (
          <button className="btn btn-ghost" onClick={() => navigate('/dashboard')} style={{ fontSize: '15px', padding: '12px 20px' }}>
            View Dashboard <ArrowRight size={16} />
          </button>
        )}
      </div>

      {/* Result summary */}
      {uploadResult && (
        <div className="fade-up" style={{ marginTop: '32px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', letterSpacing: '0.06em' }}>PARSE RESULT</div>
            <span className="badge" style={{ background: confidence >= 0.85 ? 'var(--green-dim)' : 'var(--amber-dim)', color: confColor, border: `1px solid ${confColor}40` }}>
              Confidence: {(confidence * 100).toFixed(0)}%
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0' }}>
            {[
              { label: 'LTE Bands',  val: uploadResult.summary.lte_bands, color: 'var(--accent-bright)' },
              { label: 'NR Bands',   val: uploadResult.summary.nr_bands,  color: 'var(--teal)' },
              { label: 'LTE CA',     val: uploadResult.summary.lte_ca,    color: 'var(--accent)' },
              { label: 'NR CA',      val: uploadResult.summary.nr_ca,     color: 'var(--teal)' },
              { label: 'MRDC',       val: uploadResult.summary.mrdc,      color: 'var(--purple)' },
            ].map(({ label, val, color }, i) => (
              <div key={i} style={{ padding: '20px 16px', textAlign: 'center', borderRight: i < 4 ? '1px solid var(--border)' : 'none' }}>
                <div style={{ fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color, marginBottom: '4px' }}>{val}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.05em' }}>{label}</div>
              </div>
            ))}
          </div>
          {uploadResult.flags?.length > 0 && (
            <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {uploadResult.flags.slice(0, 4).map((f, i) => (
                <span key={i} className="badge badge-warn" style={{ fontSize: '10px' }}>{f}</span>
              ))}
              {uploadResult.flags.length > 4 && <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>+{uploadResult.flags.length - 4} more</span>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
