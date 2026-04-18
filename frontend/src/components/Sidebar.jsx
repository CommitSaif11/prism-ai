import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Upload, LayoutDashboard, List, BarChart2, Cpu, Radio } from 'lucide-react'
import { useStore } from '../store/useStore.js'

const NAV = [
  { to: '/upload',       icon: Upload,          label: 'Upload'       },
  { to: '/dashboard',    icon: LayoutDashboard,  label: 'Dashboard'    },
  { to: '/combinations', icon: List,             label: 'Combinations' },
  { to: '/analytics',    icon: BarChart2,        label: 'Analytics'    },
]

const styles = {
  sidebar: {
    position: 'fixed',
    left: 0, top: 0, bottom: 0,
    width: '240px',
    background: 'var(--bg-surface)',
    borderRight: '1px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    zIndex: 100,
  },
  logo: {
    padding: '24px 20px 20px',
    borderBottom: '1px solid var(--border)',
  },
  logoTop: {
    display: 'flex', alignItems: 'center', gap: '10px',
    marginBottom: '4px',
  },
  logoIcon: {
    width: '32px', height: '32px',
    background: 'linear-gradient(135deg, var(--accent), var(--teal))',
    borderRadius: '8px',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  logoName: {
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    fontSize: '15px',
    color: 'var(--text-primary)',
    letterSpacing: '0.02em',
  },
  logoSub: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    letterSpacing: '0.04em',
    fontFamily: 'var(--font-mono)',
  },
  nav: {
    flex: 1,
    padding: '16px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  navSection: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    letterSpacing: '0.1em',
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    padding: '8px 10px 4px',
  },
  footer: {
    padding: '16px 20px',
    borderTop: '1px solid var(--border)',
    fontSize: '11px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
}

export default function Sidebar() {
  const stats = useStore(s => s.stats)
  const totalCombos = useStore(s => s.totalCombos)

  return (
    <aside style={styles.sidebar}>
      {/* Logo */}
      <div style={styles.logo}>
        <div style={styles.logoTop}>
          <div style={styles.logoIcon}>
            <Radio size={16} color="white" />
          </div>
          <div>
            <div style={styles.logoName}>PRISM</div>
          </div>
        </div>
        <div style={styles.logoSub}>UE Capability Parser v3.0</div>
        <div style={{ marginTop: '4px', fontSize: '10px', color: 'var(--text-muted)' }}>
          Samsung R&D PRISM Project
        </div>
      </div>

      {/* Nav */}
      <nav style={styles.nav}>
        <div style={styles.navSection}>Navigation</div>
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '9px 12px',
              borderRadius: 'var(--radius)',
              textDecoration: 'none',
              fontSize: '14px',
              fontWeight: '500',
              transition: 'var(--transition)',
              color: isActive ? 'var(--accent-bright)' : 'var(--text-secondary)',
              background: isActive ? 'var(--accent-dim)' : 'transparent',
              borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
            })}
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}

        {/* Stats quick view */}
        {stats && (
          <>
            <div style={{ ...styles.navSection, marginTop: '16px' }}>Quick Stats</div>
            {[
              { label: 'LTE Bands',  val: stats.lte_bands, color: 'var(--accent-bright)' },
              { label: 'NR Bands',   val: stats.nr_bands,  color: 'var(--teal)' },
              { label: 'LTE CA',     val: stats.lte_ca,    color: 'var(--accent)' },
              { label: 'NR CA',      val: stats.nr_ca,     color: 'var(--teal)' },
              { label: 'MRDC',       val: stats.mrdc,      color: 'var(--purple)' },
            ].map(({ label, val, color }) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 12px', fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                <span style={{ color, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{val ?? '—'}</span>
              </div>
            ))}
          </>
        )}
      </nav>

      {/* Footer */}
      <div style={styles.footer}>
        <div style={{ marginBottom: '2px' }}>Mistral-7B via HuggingFace</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: stats ? 'var(--green)' : 'var(--amber)', animation: 'pulse-glow 2s infinite' }} />
          <span>{stats ? `${totalCombos || stats.total || 0} combos loaded` : 'No file uploaded'}</span>
        </div>
      </div>
    </aside>
  )
}
