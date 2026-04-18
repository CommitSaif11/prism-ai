import React, { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Send, Trash2, Bot, Copy, CheckCircle2,
  ChevronDown, ChevronUp, Shield, AlertTriangle, Radio, Wifi,
} from 'lucide-react'
import { useStore } from '../store/useStore.js'

// ─── Reusable sub-components ──────────────────────────────────────────────────

function Section({ title, icon: Icon, iconColor = 'var(--accent-bright)', children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden', marginBottom: '12px' }}>
      <button onClick={() => setOpen(!open)} style={{
        width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '11px 16px', background: 'var(--bg-elevated)', border: 'none', cursor: 'pointer',
        color: 'var(--text-secondary)', fontSize: '11px', fontFamily: 'var(--font-mono)',
        fontWeight: 700, letterSpacing: '0.07em',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {Icon && <Icon size={13} color={iconColor} />}
          {title}
        </div>
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>
      {open && <div style={{ padding: '14px 16px', background: 'var(--bg-card)' }}>{children}</div>}
    </div>
  )
}

function KV({ label, value, mono = false, color }) {
  if (value == null || value === '' || value === 'None' || value === 'null') return null
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      padding: '5px 0', borderBottom: '1px solid rgba(56,189,248,0.05)',
    }}>
      <span style={{ fontSize: '12px', color: 'var(--text-muted)', flexShrink: 0, marginRight: '16px' }}>{label}</span>
      <span style={{
        fontSize: '12px',
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)',
        color: color || 'var(--text-secondary)',
        textAlign: 'right', wordBreak: 'break-all',
      }}>
        {String(value)}
      </span>
    </div>
  )
}

function BandCard({ comp, prefix, specRef }) {
  const isLte     = prefix === 'E'
  const accentCol = isLte ? 'var(--accent-bright)' : 'var(--teal)'
  const bgColor   = isLte ? 'rgba(56,189,248,0.04)' : 'rgba(20,184,166,0.04)'

  return (
    <div style={{
      background: bgColor,
      borderRadius: 'var(--radius-sm)',
      padding: '12px 14px',
      border: `1px solid ${isLte ? 'rgba(56,189,248,0.2)' : 'rgba(20,184,166,0.2)'}`,
    }}>
      {/* Band header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isLte
            ? <Radio size={13} color={accentCol} />
            : <Wifi  size={13} color={accentCol} />}
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 700, color: accentCol }}>
            {isLte ? 'E-UTRA' : 'NR'} Band {comp.band}
          </span>
        </div>
        {specRef && (
          <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {specRef}
          </span>
        )}
      </div>

      {/* Parameters grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 14px' }}>
        {comp.bwClassDl   && <KV label="DL BW Class"  value={comp.bwClassDl.toUpperCase()} mono />}
        {comp.bwClassUl   && <KV label="UL BW Class"  value={comp.bwClassUl.toUpperCase()} mono />}
        {comp.mimoDl?.value  && <KV label="MIMO DL"   value={`${comp.mimoDl.value}×${comp.mimoDl.value}`} mono color="var(--teal)" />}
        {comp.mimoUl?.value  && <KV label="MIMO UL"   value={`${comp.mimoUl.value}×${comp.mimoUl.value}`} mono />}
        {comp.modulationDl?.value && <KV label="Mod DL" value={comp.modulationDl.value.toUpperCase()} mono color="var(--accent-bright)" />}
        {comp.modulationUl?.value && <KV label="Mod UL" value={comp.modulationUl.value.toUpperCase()} mono />}
        {comp.maxScs  && <KV label="Max SCS"   value={`${comp.maxScs} kHz`} mono />}
        {comp.maxBwDl?.value && <KV label="Max BW DL" value={`${comp.maxBwDl.value} MHz`} mono color="var(--teal)" />}
        {comp.powerClass && <KV label="Power Class" value={comp.powerClass} mono />}
      </div>

      {/* NR bandwidth table */}
      {comp.bandwidths && comp.bandwidths.length > 0 && (
        <div style={{ marginTop: '8px' }}>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '4px' }}>
            SUPPORTED BANDWIDTHS
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
            {comp.bandwidths.map((bw, i) => (
              <span key={i} style={{
                fontSize: '10px', fontFamily: 'var(--font-mono)',
                background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                borderRadius: '4px', padding: '2px 6px', color: 'var(--teal)',
              }}>
                SCS {bw.scs} kHz · {bw.bandwidthsDl?.join('/')} MHz
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ConfidenceBar({ value }) {
  if (value == null) return null
  const pct   = Math.round(value * 100)
  const color = value >= 0.85 ? 'var(--green)' : value >= 0.5 ? 'var(--amber)' : 'var(--red)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: '8px 0' }}>
      <div style={{ flex: 1, height: '6px', background: 'var(--bg-elevated)', borderRadius: '99px', overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', background: color,
          borderRadius: '99px', transition: 'width 0.8s ease',
        }} />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 700, color, minWidth: '38px' }}>
        {pct}%
      </span>
    </div>
  )
}

function ValidationBadge({ status }) {
  if (!status) return null
  const cfg = {
    PASS:    { color: 'var(--green)',  bg: 'rgba(34,197,94,0.12)',  icon: '✓ PASS' },
    FAIL:    { color: 'var(--red)',    bg: 'rgba(239,68,68,0.12)',  icon: '✗ FAIL' },
    WARN:    { color: 'var(--amber)',  bg: 'rgba(245,158,11,0.12)', icon: '⚠ WARN' },
    UNKNOWN: { color: 'var(--text-muted)', bg: 'transparent',      icon: '? UNKNOWN' },
  }
  const c = cfg[status] || cfg.UNKNOWN
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 700,
      color: c.color, background: c.bg, padding: '4px 12px',
      borderRadius: '999px', border: `1px solid ${c.color}`,
    }}>
      {c.icon}
    </span>
  )
}

function ChatBubble({ turn }) {
  const [copied, setCopied] = useState(false)
  const isLoading = turn.assistant === '...'
  const copy = (txt) => { navigator.clipboard.writeText(txt); setCopied(true); setTimeout(() => setCopied(false), 1500) }

  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
        <div style={{
          maxWidth: '80%', padding: '10px 14px',
          background: 'var(--accent)', borderRadius: '12px 12px 4px 12px',
          fontSize: '13px', lineHeight: '1.5', color: 'white',
        }}>{turn.user}</div>
      </div>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
        <div style={{ width: '28px', height: '28px', background: 'var(--bg-elevated)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Bot size={14} color="var(--teal)" />
        </div>
        <div style={{ flex: 1 }}>
          {isLoading ? (
            <div style={{ display: 'flex', gap: '4px', padding: '12px 14px', background: 'var(--bg-elevated)', borderRadius: '4px 12px 12px 12px' }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--text-muted)', animation: `pulse-glow 1.2s infinite ${i * 0.2}s` }} />
              ))}
            </div>
          ) : (
            <div>
              <div style={{
                padding: '10px 14px', background: 'var(--bg-elevated)',
                borderRadius: '4px 12px 12px 12px', fontSize: '13px',
                lineHeight: '1.6', color: 'var(--text-secondary)',
                border: '1px solid var(--border)',
              }}>
                {turn.assistant}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px', padding: '0 4px' }}>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{turn.timestamp}</span>
                <button onClick={() => copy(turn.assistant)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px' }}>
                  {copied ? <CheckCircle2 size={11} color="var(--green)" /> : <Copy size={11} />}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ComboDetail() {
  const { id }    = useParams()
  const navigate  = useNavigate()
  const comboId   = parseInt(id)
  const chatEndRef = useRef(null)
  const [question, setQuestion] = useState('')

  const { comboDetail, chatHistory, loading, selectCombo, sendChat, clearChat } = useStore(s => ({
    comboDetail:  s.comboDetail,
    chatHistory:  s.chatHistory,
    loading:      s.loading,
    selectCombo:  s.selectCombo,
    sendChat:     s.sendChat,
    clearChat:    s.clearChat,
  }))

  useEffect(() => { selectCombo(comboId) }, [comboId])
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [chatHistory[comboId]])

  const history = chatHistory[comboId] || []

  const handleSend = async () => {
    const q = question.trim()
    if (!q || loading.chat) return
    setQuestion('')
    await sendChat(comboId, q)
  }

  const QUICK_Q = [
    'What does this combination support?',
    'Explain the MRDC parameters',
    'What 3GPP spec applies here?',
    'What is the maximum throughput?',
  ]

  if (loading.detail && !comboDetail) {
    return (
      <div style={{ padding: '40px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '80vh', gap: '16px' }}>
        <div className="spinner" style={{ width: '40px', height: '40px', border: '3px solid var(--border)', borderTopColor: 'var(--accent)', borderRadius: '50%' }} />
        <div style={{ color: 'var(--text-muted)' }}>Loading combination {comboId}…</div>
      </div>
    )
  }

  if (!comboDetail) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', marginTop: '80px' }}>
        <div style={{ color: 'var(--text-muted)', marginBottom: '16px' }}>Combination not found</div>
        <button className="btn btn-ghost" onClick={() => navigate('/combinations')}>
          <ArrowLeft size={14} /> Back
        </button>
      </div>
    )
  }

  const d          = comboDetail
  const raw        = d.raw || {}
  const customData = raw.customData?.[0] || {}
  const isLteCA    = d.type === 'LTE-CA'
  const isNrCA     = d.type === 'NR-CA'
  const isMrdc     = d.type === 'MRDC'

  // Spec refs per band type
  const lteSpecRef = 'TS 36.306 §4.1'
  const nrSpecRef  = 'TS 38.306 §5.2'

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>

      {/* ── LEFT PANEL: Detail ────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '28px 24px' }}>

        {/* Back + header */}
        <div style={{ marginBottom: '20px' }}>
          <button className="btn btn-ghost" onClick={() => navigate('/combinations')} style={{ marginBottom: '14px', padding: '6px 12px', fontSize: '13px' }}>
            <ArrowLeft size={14} /> All Combinations
          </button>

          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                <span className={`badge badge-${d.type === 'LTE-CA' ? 'lte' : d.type === 'NR-CA' ? 'nr' : 'mrdc'}`}>
                  {d.type}
                </span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-muted)' }}>
                  #{String(comboId).padStart(3, '0')}
                </span>
                {d.validation_status && <ValidationBadge status={d.validation_status} />}
              </div>
              <h1 style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.02em', lineHeight: 1.3 }}>
                {d.bands_summary}
              </h1>
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '3px' }}>SPEC REF</div>
              <div style={{ fontSize: '11px', color: 'var(--accent-bright)', fontFamily: 'var(--font-mono)', lineHeight: 1.4 }}>
                {d.spec_reference}
              </div>
            </div>
          </div>
        </div>

        {/* ── AI Analysis block ────────────────────────────────────────────── */}
        {(d.ai_summary || d.ai_confidence != null) && (
          <div style={{
            marginBottom: '16px', padding: '14px 16px',
            background: 'linear-gradient(135deg, rgba(56,189,248,0.07), rgba(20,184,166,0.07))',
            border: '1px solid rgba(56,189,248,0.2)', borderRadius: 'var(--radius)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Bot size={14} color="var(--teal)" />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--teal)', fontWeight: 700, letterSpacing: '0.07em' }}>
                AI ANALYSIS · MISTRAL-7B
              </span>
            </div>
            {d.ai_summary && (
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: d.ai_confidence != null ? '10px' : 0 }}>
                {d.ai_summary}
              </p>
            )}
            {d.ai_confidence != null && (
              <div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '4px' }}>
                  AI CONFIDENCE
                </div>
                <ConfidenceBar value={d.ai_confidence} />
              </div>
            )}
          </div>
        )}

        {/* ── Band Components ──────────────────────────────────────────────── */}
        <Section title="BAND COMPONENTS" icon={Radio} iconColor="var(--accent-bright)">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {isLteCA && raw.components?.map((c, i) => (
              <BandCard key={i} comp={c} prefix="E" specRef={lteSpecRef} />
            ))}
            {isNrCA && raw.components?.map((c, i) => (
              <BandCard key={i} comp={c} prefix="NR" specRef={nrSpecRef} />
            ))}
            {isMrdc && <>
              {raw.componentsLte?.map((c, i) => <BandCard key={`lte-${i}`} comp={c} prefix="E"  specRef={lteSpecRef} />)}
              {raw.componentsNr?.map((c,  i) => <BandCard key={`nr-${i}`}  comp={c} prefix="NR" specRef={nrSpecRef}  />)}
            </>}
          </div>
        </Section>

        {/* ── MRDC / EN-DC Parameters ──────────────────────────────────────── */}
        {isMrdc && (
          <Section title="MRDC / EN-DC PARAMETERS" icon={Shield} iconColor="var(--purple)">
            <KV label="Feature Set Combination"          value={customData.featureSetCombination}          mono color="var(--accent-bright)" />
            <KV label="Dynamic Power Sharing ENDC"       value={customData.dynamicPowerSharingENDC}        mono color="var(--teal)" />
            <KV label="Simultaneous Rx/Tx Inter-band ENDC" value={customData.simultaneousRxTxInterBandENDC} mono />
            <KV label="Intra-band ENDC Support"          value={customData.intraBandENDC_Support || customData['intraBandENDC-Support']} mono />
            <KV label="Supported BW Combination Set"     value={customData.supportedBandwidthCombinationSet} mono />
            <KV label="BCS NR"                           value={raw.bcsNr?.value}   mono />
            <KV label="BCS EUTRA"                        value={raw.bcsEutra?.value} mono />
          </Section>
        )}

        {/* ── NR CA Parameters ────────────────────────────────────────────── */}
        {isNrCA && customData && Object.keys(customData).length > 0 && (
          <Section title="NR CA PARAMETERS" icon={Wifi} iconColor="var(--teal)">
            <KV label="Feature Set Combination"         value={customData.featureSetCombination}              mono color="var(--accent-bright)" />
            <KV label="Simultaneous Rx/Tx Inter-band CA" value={customData.simultaneousRxTxInterBandCA}       mono />
            <KV label="Parallel Tx SRS/PUCCH/PUSCH"    value={customData.parallelTxSRS_PUCCH_PUSCH || customData['parallelTxSRS-PUCCH-PUSCH']} mono />
            <KV label="Diff Numerology PUCCH"           value={customData.diffNumerologyWithinPUCCH_GroupSmallerSCS} mono />
            <KV label="Supported SRS Tx Port Switch"    value={customData.supportedSRS_TxPortSwitch || customData['supportedSRS-TxPortSwitch']} mono />
          </Section>
        )}

        {/* ── LTE CA Parameters ───────────────────────────────────────────── */}
        {isLteCA && (
          <Section title="LTE CA PARAMETERS" icon={Radio} iconColor="var(--accent-bright)">
            <KV label="BCS" value={raw.bcs != null ? JSON.stringify(raw.bcs) : null} mono />
          </Section>
        )}

        {/* ── Optional / Extra Fields ─────────────────────────────────────── */}
        {(() => {
          const extras = []
          if (customData.powerClass)              extras.push(['powerClass',                     customData.powerClass])
          if (customData['powerClass-v1530'])     extras.push(['powerClass-v1530',               customData['powerClass-v1530']])
          if (customData.supportedBandwidthCombinationSet) extras.push(['supportedBandwidthCombinationSet', customData.supportedBandwidthCombinationSet])
          if (customData.bandList)                extras.push(['bandList',                        customData.bandList])
          if (raw.extras)                         Object.entries(raw.extras).forEach(([k, v]) => v && extras.push([k, v]))
          if (extras.length === 0) return null
          return (
            <Section title="OPTIONAL FIELDS" defaultOpen={false}>
              {extras.map(([k, v]) => <KV key={k} label={k} value={typeof v === 'object' ? JSON.stringify(v) : v} mono />)}
            </Section>
          )
        })()}

        {/* ── AI Anomalies ─────────────────────────────────────────────────── */}
        <Section title="AI ANOMALIES & FLAGS" icon={AlertTriangle} iconColor="var(--amber)">
          {(!d.anomalies || d.anomalies.length === 0) ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--green)', fontSize: '13px' }}>
              <CheckCircle2 size={14} /> No anomalies detected
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {d.anomalies.map((a, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <AlertTriangle size={12} color="var(--amber)" style={{ marginTop: '1px', flexShrink: 0 }} />
                  <span>{a}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* ── 3GPP Spec References ─────────────────────────────────────────── */}
        <Section title="3GPP SPECIFICATION REFERENCES" icon={Shield} iconColor="var(--text-muted)" defaultOpen={false}>
          {/* AI-suggested spec refs */}
          {d.spec_refs && d.spec_refs.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '10px', color: 'var(--teal)', fontFamily: 'var(--font-mono)', marginBottom: '6px' }}>AI IDENTIFIED REFERENCES</div>
              {d.spec_refs.map((ref, i) => (
                <div key={i} style={{ fontSize: '12px', color: 'var(--text-secondary)', padding: '4px 0', borderBottom: '1px solid rgba(56,189,248,0.05)' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-bright)' }}>{ref}</span>
                </div>
              ))}
            </div>
          )}
          {/* Static spec refs */}
          {[
            { ref: 'TS 36.306', desc: 'LTE UE Radio Access Capabilities' },
            { ref: 'TS 36.331', desc: 'LTE RRC Protocol' },
            { ref: 'TS 38.306', desc: 'NR UE Radio Access Capabilities' },
            { ref: 'TS 38.331', desc: 'NR RRC Protocol' },
            { ref: 'TS 37.340', desc: 'NR Multi-connectivity — MRDC/EN-DC' },
          ].map(({ ref, desc }) => (
            <div key={ref} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid rgba(56,189,248,0.05)', fontSize: '12px' }}>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-bright)' }}>{ref}</span>
              <span style={{ color: 'var(--text-muted)' }}>{desc}</span>
            </div>
          ))}
        </Section>

        {/* ── Validation Summary ───────────────────────────────────────────── */}
        <div style={{
          marginTop: '4px', padding: '12px 16px',
          border: '1px solid var(--border)', borderRadius: 'var(--radius)',
          background: 'var(--bg-elevated)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '4px' }}>VALIDATION STATUS</div>
            <ValidationBadge status={d.validation_status || 'UNKNOWN'} />
          </div>
          {d.ai_confidence != null && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '4px' }}>AI CONFIDENCE</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '20px', fontWeight: 700,
                color: d.ai_confidence >= 0.85 ? 'var(--green)' : d.ai_confidence >= 0.5 ? 'var(--amber)' : 'var(--red)' }}>
                {Math.round(d.ai_confidence * 100)}%
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── RIGHT PANEL: AI Chat ──────────────────────────────────────────── */}
      <div style={{
        width: '360px', flexShrink: 0,
        borderLeft: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        background: 'var(--bg-surface)', height: '100vh',
      }}>
        {/* Chat header */}
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--teal)', animation: 'pulse-glow 2s infinite' }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                AI ASSISTANT
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Mistral-7B · Context: {d.type} #{comboId}
            </div>
          </div>
          <button className="btn btn-ghost" onClick={() => clearChat(comboId)} style={{ padding: '5px 8px', fontSize: '12px' }}>
            <Trash2 size={13} />
          </button>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '18px' }}>
          {history.length === 0 && (
            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
              <Bot size={28} color="var(--text-muted)" style={{ margin: '0 auto 10px' }} />
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.6', marginBottom: '18px' }}>
                Ask anything about <strong style={{ color: 'var(--text-secondary)' }}>{d.bands_summary}</strong>
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {QUICK_Q.map(q => (
                  <button key={q} onClick={() => setQuestion(q)} style={{
                    background: 'var(--bg-card)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)', padding: '7px 11px',
                    fontSize: '12px', color: 'var(--text-secondary)',
                    cursor: 'pointer', textAlign: 'left', transition: 'var(--transition)',
                  }}
                    onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                    onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {history.map((turn, i) => <ChatBubble key={i} turn={turn} />)}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div style={{ padding: '14px', borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              className="input"
              placeholder="Ask about this combination…"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              style={{ fontSize: '13px' }}
            />
            <button
              className="btn btn-primary"
              onClick={handleSend}
              disabled={!question.trim() || loading.chat}
              style={{ padding: '10px', flexShrink: 0 }}
            >
              {loading.chat
                ? <div className="spinner" style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%' }} />
                : <Send size={14} />}
            </button>
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '7px', fontFamily: 'var(--font-mono)', textAlign: 'center' }}>
            Context: {d.type} #{comboId} · {d.bands?.length || 0} bands
          </div>
        </div>
      </div>
    </div>
  )
}
