import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, ChevronLeft, ChevronRight, ArrowUpRight, CheckCircle2, XCircle, AlertTriangle, Download } from 'lucide-react'
import { useStore } from '../store/useStore.js'

const TYPE_FILTERS = ['ALL', 'LTE-CA', 'NR-CA', 'MRDC']

function TypeBadge({ type }) {
  const map = {
    'LTE-CA': { cls: 'badge-lte',  label: 'LTE-CA' },
    'NR-CA':  { cls: 'badge-nr',   label: 'NR-CA'  },
    'MRDC':   { cls: 'badge-mrdc', label: 'MRDC'   },
  }
  const { cls, label } = map[type] || { cls: '', label: type }
  return <span className={`badge ${cls}`}>{label}</span>
}

function ValidationBadge({ status }) {
  if (!status) return <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>—</span>
  const cfg = {
    PASS:    { color: 'var(--green)',  bg: 'rgba(34,197,94,0.12)',  icon: '✓' },
    FAIL:    { color: 'var(--red)',    bg: 'rgba(239,68,68,0.12)',  icon: '✗' },
    WARN:    { color: 'var(--amber)',  bg: 'rgba(245,158,11,0.12)', icon: '⚠' },
    UNKNOWN: { color: 'var(--text-muted)', bg: 'transparent',      icon: '?' },
  }
  const c = cfg[status] || cfg.UNKNOWN
  return (
    <span style={{
      fontSize: '10px', fontFamily: 'var(--font-mono)', fontWeight: 700,
      color: c.color, background: c.bg, padding: '2px 7px',
      borderRadius: '999px', border: `1px solid ${c.color}`,
    }}>
      {c.icon} {status}
    </span>
  )
}

function ConfidenceBar({ value }) {
  if (value == null) return <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>—</span>
  const pct  = Math.round(value * 100)
  const color = value >= 0.85 ? 'var(--green)' : value >= 0.5 ? 'var(--amber)' : 'var(--red)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{ width: '52px', height: '5px', background: 'var(--bg-elevated)', borderRadius: '99px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '99px', transition: 'width 0.5s ease' }} />
      </div>
      <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color, minWidth: '30px' }}>{pct}%</span>
    </div>
  )
}

export default function Combinations() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const {
    combinations, totalCombos, page, pages, loading, typeFilter,
    fetchCombinations, selectCombo, setFilter, setPage,
  } = useStore(s => ({
    combinations:      s.combinations,
    totalCombos:       s.totalCombos,
    page:              s.page,
    pages:             s.pages,
    loading:           s.loading.combos,
    typeFilter:        s.typeFilter,
    fetchCombinations: s.fetchCombinations,
    selectCombo:       s.selectCombo,
    setFilter:         s.setFilter,
    setPage:           s.setPage,
  }))

  useEffect(() => { fetchCombinations(1, typeFilter) }, [])

  const filtered = search
    ? combinations.filter(c => c.bands_summary.toLowerCase().includes(search.toLowerCase()))
    : combinations

  const handleRowClick = async (combo) => {
    await selectCombo(combo.id)
    navigate(`/combinations/${combo.id}`)
  }

  return (
    <div style={{ padding: '40px', maxWidth: '1200px' }}>
      {/* Header */}
      <div style={{ marginBottom: '28px' }} className="fade-up">
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: '8px' }}>
          SAMSUNG PRISM // COMBINATIONS
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 700, letterSpacing: '-0.02em' }}>Band Combinations</h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
              {totalCombos} total combinations · Click any row to view full detail and AI analysis
            </p>
          </div>
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
        </div>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center' }} className="fade-up">
        {/* Search */}
        <div style={{ position: 'relative', flex: 1, maxWidth: '320px' }}>
          <Search size={14} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
          <input
            className="input"
            placeholder="Search bands..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ paddingLeft: '36px' }}
          />
        </div>

        {/* Type filter tabs */}
        <div style={{ display: 'flex', gap: '4px', background: 'var(--bg-surface)', padding: '4px', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          {TYPE_FILTERS.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '5px 12px', borderRadius: 'var(--radius-sm)', border: 'none',
                fontSize: '12px', fontWeight: 600, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                transition: 'var(--transition)',
                background: typeFilter === f ? 'var(--accent)' : 'transparent',
                color:      typeFilter === f ? 'white' : 'var(--text-muted)',
              }}
            >
              {f}
            </button>
          ))}
        </div>

        <div style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          Page {page} of {pages}
        </div>
      </div>

      {/* Table */}
      <div className="card fade-up" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center' }}>
            <div className="spinner" style={{ width: '32px', height: '32px', border: '3px solid var(--border)', borderTopColor: 'var(--accent)', borderRadius: '50%', margin: '0 auto 16px' }} />
            <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Loading combinations…</div>
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '14px' }}>
            {totalCombos === 0 ? 'No file uploaded yet. Go to Upload to get started.' : 'No combinations match your search.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '60px' }}>#</th>
                  <th style={{ width: '90px' }}>Type</th>
                  <th>Band Combination</th>
                  <th style={{ width: '100px' }}>Feature Set</th>
                  <th style={{ width: '70px' }}>MRDC</th>
                  <th style={{ width: '120px' }}>AI Confidence</th>
                  <th style={{ width: '110px' }}>Validation</th>
                  <th style={{ width: '50px' }}></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((combo, idx) => (
                  <tr
                    key={combo.id}
                    onClick={() => handleRowClick(combo)}
                    style={{ animationDelay: `${idx * 0.02}s`, cursor: 'pointer' }}
                    className="fade-up"
                  >
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-muted)' }}>
                      {String(combo.id).padStart(3, '0')}
                    </td>
                    <td><TypeBadge type={combo.type} /></td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', letterSpacing: '0.02em', color: 'var(--text-primary)' }}>
                      {combo.bands_summary}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {combo.feature_set != null ? `FSC-${combo.feature_set}` : '—'}
                    </td>
                    <td>
                      {combo.has_mrdc
                        ? <CheckCircle2 size={14} color="var(--green)" />
                        : <XCircle     size={14} color="var(--text-muted)" />}
                    </td>
                    <td>
                      <ConfidenceBar value={combo.ai_confidence} />
                    </td>
                    <td>
                      <ValidationBadge status={combo.validation_status} />
                    </td>
                    <td>
                      <ArrowUpRight size={14} color="var(--text-muted)" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '20px', alignItems: 'center' }}>
          <button className="btn btn-ghost" onClick={() => setPage(page - 1)} disabled={page <= 1} style={{ padding: '6px 10px' }}>
            <ChevronLeft size={16} />
          </button>
          {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
            const p = pages <= 7 ? i + 1 : page <= 4 ? i + 1 : page >= pages - 3 ? pages - 6 + i : page - 3 + i
            return (
              <button key={p} className="btn" onClick={() => setPage(p)} style={{
                padding: '6px 12px', fontSize: '13px',
                background: p === page ? 'var(--accent)' : 'transparent',
                color:      p === page ? 'white' : 'var(--text-secondary)',
                border: '1px solid ' + (p === page ? 'var(--accent)' : 'var(--border)'),
              }}>{p}</button>
            )
          })}
          <button className="btn btn-ghost" onClick={() => setPage(page + 1)} disabled={page >= pages} style={{ padding: '6px 10px' }}>
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  )
}
