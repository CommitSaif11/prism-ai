import React, { useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ScatterChart, Scatter, Cell, Legend
} from 'recharts'
import { useStore } from '../store/useStore.js'
import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

const TT_STYLE = {
  contentStyle: { background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px', fontFamily: 'Space Mono, monospace' },
  labelStyle: { color: 'var(--text-primary)' },
  itemStyle: { color: 'var(--text-secondary)' },
}

function ChartCard({ title, sub, children }) {
  return (
    <div className="card fade-up">
      <div style={{ marginBottom: '16px' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>{title}</div>
        {sub && <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{sub}</div>}
      </div>
      {children}
    </div>
  )
}

export default function Analytics() {
  const navigate = useNavigate()
  const { stats, combinations, fetchStats, fetchCombinations } = useStore(s => ({
    stats: s.stats,
    combinations: s.combinations,
    fetchStats: s.fetchStats,
    fetchCombinations: s.fetchCombinations,
  }))

  useEffect(() => {
    fetchStats()
    fetchCombinations(1, 'ALL')
  }, [])

  if (!stats || stats.error) {
    return (
      <div style={{ padding: '40px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '80vh', gap: '16px', textAlign: 'center' }}>
        <h2>No data to analyze</h2>
        <p style={{ color: 'var(--text-secondary)' }}>Upload a UE_Capa.txt file first to see analytics.</p>
        <button className="btn btn-primary" onClick={() => navigate('/upload')}><ArrowRight size={16} /> Upload File</button>
      </div>
    )
  }

  // Distribution bar chart
  const distData = [
    { name: 'LTE-CA', count: stats.lte_ca  || 0, fill: 'var(--accent)' },
    { name: 'NR-CA',  count: stats.nr_ca   || 0, fill: 'var(--teal)' },
    { name: 'MRDC',   count: stats.mrdc    || 0, fill: 'var(--purple)' },
  ]

  // Per-section confidence
  const perSection = stats.per_section || {}
  const sectionData = Object.entries(perSection).map(([k, v]) => ({
    subject: k.toUpperCase(),
    score: Math.round(v * 100),
    fullMark: 100,
  }))

  // Band frequency from combinations (top 20)
  const bandFreq = {}
  combinations.forEach(c => {
    (c.bands_summary || '').split(' + ').forEach(b => {
      bandFreq[b] = (bandFreq[b] || 0) + 1
    })
  })
  const bandData = Object.entries(bandFreq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 16)
    .map(([band, count]) => ({
      band: band.replace('E-B', 'LTE').replace('NR-B', 'NR'),
      count,
      fill: band.startsWith('E') ? 'var(--accent)' : band.startsWith('NR') ? 'var(--teal)' : 'var(--purple)',
    }))

  // Combo size distribution
  const sizeFreq = {}
  combinations.forEach(c => {
    const n = (c.bands_summary || '').split(' + ').length
    sizeFreq[n] = (sizeFreq[n] || 0) + 1
  })
  const sizeData = Object.entries(sizeFreq)
    .sort((a, b) => a[0] - b[0])
    .map(([size, count]) => ({ size: `${size}-band`, count }))

  // Feature set distribution
  const fscFreq = {}
  combinations.forEach(c => {
    const key = c.feature_set != null ? `FSC-${c.feature_set}` : 'None'
    fscFreq[key] = (fscFreq[key] || 0) + 1
  })
  const fscData = Object.entries(fscFreq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([fsc, count]) => ({ fsc, count }))

  return (
    <div style={{ padding: '40px', maxWidth: '1200px' }}>
      {/* Header */}
      <div style={{ marginBottom: '32px' }} className="fade-up">
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: '8px' }}>SAMSUNG PRISM // ANALYTICS</div>
        <h1 style={{ fontSize: '28px', fontWeight: 700, letterSpacing: '-0.02em' }}>Capability Analytics</h1>
        <p style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
          Visual breakdown of {stats.total || 0} extracted band combinations and validation scores.
        </p>
      </div>

      {/* Confidence radar */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
        <ChartCard title="Per-Section Confidence" sub="AI validation score per data category (0–100%)">
          {sectionData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart data={sectionData}>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'Space Mono, monospace' }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 9 }} />
                <Radar name="Confidence" dataKey="score" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.15} />
                <Tooltip {...TT_STYLE} formatter={v => [`${v}%`, 'Score']} />
              </RadarChart>
            </ResponsiveContainer>
          ) : <div style={{ height: '240px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>No data</div>}
        </ChartCard>

        {/* Combination type distribution */}
        <ChartCard title="Combination Type Distribution" sub="Count per combination type">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={distData} barCategoryGap="30%">
              <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 12, fontFamily: 'Space Mono, monospace' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...TT_STYLE} />
              <Bar dataKey="count" radius={[4,4,0,0]}>
                {distData.map((d, i) => <Cell key={i} fill={d.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Band frequency */}
      <ChartCard title="Band Frequency" sub="How many combinations each band appears in (top 16)">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={bandData} barCategoryGap="20%">
            <XAxis dataKey="band" tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'Space Mono, monospace' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip {...TT_STYLE} />
            <Bar dataKey="count" radius={[3,3,0,0]}>
              {bandData.map((d, i) => <Cell key={i} fill={d.fill} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div style={{ display: 'flex', gap: '16px', marginTop: '12px', justifyContent: 'center' }}>
          {[['LTE', 'var(--accent)'], ['NR', 'var(--teal)']].map(([label, color]) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '2px', background: color }} />
              {label} Band
            </div>
          ))}
        </div>
      </ChartCard>

      {/* Bottom row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '16px' }}>
        {/* Combo size distribution */}
        <ChartCard title="Combination Size" sub="Number of bands per combination">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={sizeData} barCategoryGap="30%">
              <XAxis dataKey="size" tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'Space Mono, monospace' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...TT_STYLE} />
              <Bar dataKey="count" fill="var(--amber)" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Feature set distribution */}
        <ChartCard title="Feature Set Distribution" sub="Top feature set combination IDs">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={fscData} layout="vertical" barCategoryGap="20%">
              <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis dataKey="fsc" type="category" width={60} tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'Space Mono, monospace' }} axisLine={false} tickLine={false} />
              <Tooltip {...TT_STYLE} />
              <Bar dataKey="count" fill="var(--purple)" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Summary table */}
      <div className="card fade-up" style={{ marginTop: '16px' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '16px' }}>
          Summary Statistics
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
          {[
            { label: 'Total Combinations',    val: stats.total || 0,       color: 'var(--accent-bright)' },
            { label: 'Unique LTE Bands',       val: stats.lte_bands || 0,  color: 'var(--accent)' },
            { label: 'Unique NR Bands',        val: stats.nr_bands || 0,   color: 'var(--teal)' },
            { label: 'MRDC Combos',            val: stats.mrdc || 0,       color: 'var(--purple)' },
            { label: 'Avg Bands/Combo',        val: combinations.length ? (combinations.reduce((s, c) => s + (c.bands_summary || '').split(' + ').length, 0) / combinations.length).toFixed(1) : '—', color: 'var(--amber)' },
            { label: 'With Feature Set',       val: combinations.filter(c => c.feature_set != null).length, color: 'var(--teal)' },
            { label: 'Confidence Score',       val: `${Math.round((stats.confidence || 0) * 100)}%`, color: stats.confidence >= 0.85 ? 'var(--green)' : 'var(--amber)' },
            { label: 'Validation Decision',    val: (stats.decision || '—').toUpperCase(), color: stats.decision === 'accept' ? 'var(--green)' : 'var(--amber)' },
          ].map(({ label, val, color }) => (
            <div key={label} style={{ textAlign: 'center', padding: '12px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius)' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '22px', fontWeight: 700, color, marginBottom: '4px' }}>{val}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
