import React, { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { RadialBarChart, RadialBar, ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts'
import { ArrowRight, Cpu, Shield, Radio, Wifi, AlertTriangle, CheckCircle2, Download } from 'lucide-react'
import { useStore } from '../store/useStore.js'

const COLORS = {
  'LTE-CA': 'var(--accent)',
  'NR-CA':  'var(--teal)',
  'MRDC':   'var(--purple)',
}

function StatCard({ label, value, sub, color = 'var(--accent-bright)', icon: Icon }) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ padding: '8px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
          <Icon size={18} color={color} />
        </div>
      </div>
      <div>
        <div style={{ fontSize: '32px', fontWeight: 700, fontFamily: 'var(--font-mono)', color, lineHeight: 1 }}>{value ?? '—'}</div>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '6px' }}>{label}</div>
        {sub && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>{sub}</div>}
      </div>
    </div>
  )
}

function ConfidenceGauge({ score = 0, decision = 'unknown' }) {
  const pct = Math.round(score * 100)
  const color = score >= 0.85 ? 'var(--green)' : score >= 0.5 ? 'var(--amber)' : 'var(--red)'
  const circumference = 2 * Math.PI * 48
  const dash = (score * circumference).toFixed(1)

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-muted)', textTransform: 'uppercase', width: '100%' }}>
        AI Confidence Score
      </div>
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="48" fill="none" stroke="var(--bg-elevated)" strokeWidth="10" />
        <circle cx="60" cy="60" r="48" fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={`${dash} ${circumference}`}
          strokeLinecap="round"
          transform="rotate(-90 60 60)"
          style={{ transition: 'stroke-dasharray 0.8s ease' }}
        />
        <text x="60" y="55" textAnchor="middle" fill={color} style={{ fontFamily: 'Space Mono, monospace', fontSize: '20px', fontWeight: 700 }}>{pct}%</text>
        <text x="60" y="72" textAnchor="middle" fill="var(--text-muted)" style={{ fontFamily: 'Space Mono, monospace', fontSize: '9px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>{decision}</text>
      </svg>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { stats, fetchStats, totalCombos, uploadResult } = useStore(s => ({
    stats: s.stats,
    fetchStats: s.fetchStats,
    totalCombos: s.totalCombos,
    uploadResult: s.uploadResult,
  }))

  useEffect(() => { fetchStats() }, [])

  if (!stats || stats.error) {
    return (
      <div style={{ padding: '40px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '80vh', gap: '16px', textAlign: 'center' }}>
        <Radio size={48} color="var(--text-muted)" />
        <h2 style={{ fontSize: '22px', fontWeight: 600 }}>No Data Loaded</h2>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '360px' }}>Upload a UE_Capa.txt file to parse LTE/NR capabilities and view the dashboard.</p>
        <button className="btn btn-primary" onClick={() => navigate('/upload')}>
          <ArrowRight size={16} /> Go to Upload
        </button>
      </div>
    )
  }

  const pieData = [
    { name: 'LTE-CA', value: stats.lte_ca  || 0 },
    { name: 'NR-CA',  value: stats.nr_ca   || 0 },
    { name: 'MRDC',   value: stats.mrdc    || 0 },
  ].filter(d => d.value > 0)

  return (
    <div style={{ padding: '40px', maxWidth: '1200px' }}>
      {/* Header */}
      <div style={{ marginBottom: '32px' }} className="fade-up">
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: '8px' }}>
          SAMSUNG PRISM // DASHBOARD
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 700, letterSpacing: '-0.02em' }}>Capability Overview</h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
              {stats.metadata?.source_file || 'Unknown file'} · RAT: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-bright)' }}>{stats.metadata?.rat_type?.toUpperCase() || '—'}</span>
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              className="btn btn-ghost"
              onClick={() => {
                const a = document.createElement('a')
                a.href = '/api/download'
                a.click()
              }}
              style={{ gap: '6px', fontSize: '13px' }}
              title="Download full parsed JSON"
            >
              <Download size={14} /> Export JSON
            </button>
            <button className="btn btn-ghost" onClick={() => navigate('/combinations')} style={{ gap: '8px' }}>
              View All Combinations <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Stat cards row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '14px', marginBottom: '24px' }} className="fade-up">
        <StatCard label="LTE Bands"  value={stats.lte_bands} icon={Radio}   color="var(--accent-bright)"  sub="EUTRA supported" />
        <StatCard label="NR Bands"   value={stats.nr_bands}  icon={Wifi}    color="var(--teal)"            sub="NR supported" />
        <StatCard label="LTE CA"     value={stats.lte_ca}    icon={Radio}   color="var(--accent)"          sub="CA combinations" />
        <StatCard label="NR CA"      value={stats.nr_ca}     icon={Wifi}    color="var(--teal)"            sub="NR combinations" />
        <StatCard label="MRDC"       value={stats.mrdc}      icon={Cpu}     color="var(--purple)"          sub="EN-DC combos" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '14px', marginBottom: '24px' }}>
        {/* Distribution pie */}
        <div className="card" style={{ gridColumn: 'span 2' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: '16px', textTransform: 'uppercase' }}>
            Combination Distribution
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
            <ResponsiveContainer width={180} height={180}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" strokeWidth={0}>
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={Object.values(COLORS)[i]} opacity={0.9} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px' }}
                  labelStyle={{ color: 'var(--text-primary)' }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ flex: 1 }}>
              {pieData.map((d, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '2px', background: Object.values(COLORS)[i] }} />
                    <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{d.name}</span>
                  </div>
                  <div>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '14px', color: Object.values(COLORS)[i] }}>{d.value}</span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '4px' }}>({Math.round(d.value / (stats.lte_ca + stats.nr_ca + stats.mrdc) * 100)}%)</span>
                  </div>
                </div>
              ))}
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0 0' }}>
                <span style={{ fontSize: '13px', fontWeight: 600 }}>Total</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '16px', color: 'var(--accent-bright)' }}>{totalCombos || stats.total}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Confidence gauge */}
        <ConfidenceGauge score={stats.confidence} decision={stats.decision} />
      </div>

      {/* Flags & Metadata */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
        {/* Validation flags */}
        <div className="card">
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: '16px', textTransform: 'uppercase' }}>
            Validation Flags
          </div>
          {stats.flags?.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--green)', fontSize: '13px' }}>
              <CheckCircle2 size={16} /> No issues detected
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '200px', overflowY: 'auto' }}>
              {stats.flags?.map((f, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <AlertTriangle size={13} color="var(--amber)" style={{ marginTop: '1px', flexShrink: 0 }} />
                  <span>{f}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Metadata */}
        <div className="card">
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: '16px', textTransform: 'uppercase' }}>
            File Metadata
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {[
              { k: 'Source File',    v: stats.metadata?.source_file },
              { k: 'RRC Release',    v: stats.metadata?.rrc_release },
              { k: 'Pkt Version',    v: stats.metadata?.pkt_version },
              { k: 'Physical Cell',  v: stats.metadata?.physical_cell_id },
              { k: 'Frequency',      v: stats.metadata?.freq },
              { k: 'RAT Type',       v: stats.metadata?.rat_type?.toUpperCase() },
              { k: 'Extraction',     v: stats.metadata?.extraction_method },
            ].map(({ k, v }) => v ? (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>{k}</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', maxWidth: '200px', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v}</span>
              </div>
            ) : null)}
          </div>
        </div>
      </div>
    </div>
  )
}
