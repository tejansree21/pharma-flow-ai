import { useState, useRef, useEffect } from 'react'
import { api } from '../api'

// ── Starter questions ────────────────────────────────────────────────────────
const STARTERS = [
  "Which suppliers are highest risk right now?",
  "Are any drugs heading toward a shortage?",
  "Where should we buy Metformin to minimize risk?",
  "What price spikes should we act on this week?",
  "Any geopolitical disruptions affecting our supply chain?",
  "Which drugs need reordering urgently?",
]

// ── Source pill ──────────────────────────────────────────────────────────────
const SOURCE_LABELS = {
  supplier_risk:            { label: 'Supplier risk', color: '#ef4444' },
  price_forecast:           { label: 'Price forecast', color: '#f59e0b' },
  shortage_prediction:      { label: 'Shortage predictor', color: '#ef4444' },
  inventory_optimization:   { label: 'Inventory', color: '#f87171' },
  geopolitical_intelligence:{ label: 'Geo intel', color: '#a78bfa' },
  quality_anomaly:          { label: 'Quality anomaly', color: '#f59e0b' },
  purchase_optimization:    { label: 'Optimizer', color: '#60a5fa' },
}

function SourcePill({ source }) {
  const cfg = SOURCE_LABELS[source] || { label: source, color: '#9a9a9a' }
  return (
    <span style={{
      display: 'inline-block',
      fontSize: 9, fontWeight: 600, padding: '1px 6px',
      borderRadius: 4, marginRight: 4,
      background: `${cfg.color}18`,
      color: cfg.color,
      border: `1px solid ${cfg.color}30`,
      fontFamily: 'var(--mono)',
    }}>
      {cfg.label}
    </span>
  )
}

// ── Message bubble ───────────────────────────────────────────────────────────
function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 16,
    }}>
      {/* Label */}
      <div style={{
        fontSize: 10, fontWeight: 600, letterSpacing: '0.5px',
        color: 'var(--text-muted)', marginBottom: 4,
        textTransform: 'uppercase',
      }}>
        {isUser ? 'You' : 'PharmaFlow AI'}
      </div>

      {/* Bubble */}
      <div style={{
        maxWidth: '88%',
        padding: '10px 14px',
        borderRadius: isUser ? '12px 12px 2px 12px' : '2px 12px 12px 12px',
        background: isUser
          ? 'rgba(220,38,38,0.15)'
          : 'rgba(255,255,255,0.04)',
        border: isUser
          ? '1px solid rgba(239,68,68,0.25)'
          : '1px solid rgba(255,255,255,0.07)',
        fontSize: 13, lineHeight: 1.65,
        color: 'var(--text-primary)',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {msg.content}
      </div>

      {/* Source pills for assistant messages */}
      {!isUser && msg.sources?.length > 0 && (
        <div style={{ marginTop: 5, paddingLeft: 2 }}>
          {msg.sources.map((s, i) => <SourcePill key={i} source={s} />)}
        </div>
      )}
    </div>
  )
}

// ── Typing indicator ─────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 16 }}>
      <div style={{
        padding: '10px 16px',
        borderRadius: '2px 12px 12px 12px',
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', gap: 5, alignItems: 'center',
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#ef4444',
            animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
      </div>
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────
export default function AskPharmaFlow() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Focus input on open
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100)
  }, [open])

  const send = async (text) => {
    const question = (text || input).trim()
    if (!question || loading) return

    const userMsg = { role: 'user', content: question, id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      // Build history for API (last 6 turns)
      const history = messages.slice(-6).map(m => ({
        role: m.role,
        content: m.content,
      }))

      const res = await api.chat(question, history)

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          sources: res.sources || [],
          intents: res.intents || [],
          id: Date.now() + 1,
        },
      ])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I couldn\'t reach the AI service. Make sure ANTHROPIC_API_KEY is set on the backend.',
          sources: [],
          id: Date.now() + 1,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const clearChat = () => setMessages([])

  return (
    <>
      {/* Bounce keyframe injected once */}
      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);   opacity: 1; }
        }
        @keyframes slideOutRight {
          from { transform: translateX(0);   opacity: 1; }
          to   { transform: translateX(100%); opacity: 0; }
        }
        .chat-panel-enter { animation: slideInRight 0.25s ease; }
      `}</style>

      {/* Floating trigger button */}
      <button
        onClick={() => setOpen(o => !o)}
        title="Ask PharmaFlow AI"
        style={{
          position: 'fixed',
          bottom: 28, right: 28,
          zIndex: 300,
          width: 52, height: 52,
          borderRadius: '50%',
          background: open ? '#111' : '#dc2626',
          border: open
            ? '1px solid rgba(239,68,68,0.3)'
            : '1px solid rgba(255,255,255,0.1)',
          color: 'white',
          fontSize: open ? 20 : 22,
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: open
            ? '0 0 0 1px rgba(239,68,68,0.3)'
            : '0 0 24px rgba(220,38,38,0.4)',
          transition: 'all 0.2s ease',
        }}
      >
        {open ? '×' : '✦'}
      </button>

      {/* Chat panel */}
      {open && (
        <div
          className="chat-panel-enter"
          style={{
            position: 'fixed',
            bottom: 90, right: 28,
            width: 400,
            maxWidth: 'calc(100vw - 56px)',
            height: 580,
            maxHeight: 'calc(100vh - 120px)',
            zIndex: 299,
            background: '#0d0d0d',
            border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: 16,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            boxShadow: '0 24px 80px rgba(0,0,0,0.7), 0 0 40px rgba(220,38,38,0.08)',
          }}
        >
          {/* Header */}
          <div style={{
            padding: '14px 18px',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8,
                background: 'linear-gradient(135deg,#dc2626,#ef4444)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 14, flexShrink: 0,
                boxShadow: '0 0 14px rgba(220,38,38,0.3)',
              }}>
                ✦
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>
                  Ask PharmaFlow
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                  Powered by Claude · Live platform data
                </div>
              </div>
            </div>
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                style={{
                  background: 'none', border: 'none',
                  color: 'var(--text-muted)', cursor: 'pointer',
                  fontSize: 11, padding: '4px 8px',
                  borderRadius: 6,
                  border: '1px solid rgba(255,255,255,0.07)',
                }}
              >
                Clear
              </button>
            )}
          </div>

          {/* Messages */}
          <div style={{
            flex: 1, overflowY: 'auto',
            padding: '16px 18px 8px',
          }}>
            {messages.length === 0 ? (
              <div style={{ paddingTop: 8 }}>
                {/* Welcome */}
                <div style={{
                  fontSize: 13, color: 'var(--text-secondary)',
                  lineHeight: 1.6, marginBottom: 20,
                }}>
                  Ask me anything about your supply chain — supplier risks, price forecasts, shortage predictions, or what to buy and when.
                </div>
                {/* Starter questions */}
                <div style={{
                  fontSize: 11, fontWeight: 600, color: 'var(--text-muted)',
                  letterSpacing: '0.5px', textTransform: 'uppercase',
                  marginBottom: 10,
                }}>
                  Try asking
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {STARTERS.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => send(q)}
                      style={{
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid rgba(255,255,255,0.07)',
                        borderRadius: 8,
                        padding: '8px 12px',
                        color: 'var(--text-secondary)',
                        fontSize: 12,
                        cursor: 'pointer',
                        textAlign: 'left',
                        lineHeight: 1.4,
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={e => {
                        e.target.style.background = 'rgba(239,68,68,0.08)'
                        e.target.style.borderColor = 'rgba(239,68,68,0.2)'
                        e.target.style.color = '#fff'
                      }}
                      onMouseLeave={e => {
                        e.target.style.background = 'rgba(255,255,255,0.03)'
                        e.target.style.borderColor = 'rgba(255,255,255,0.07)'
                        e.target.style.color = 'var(--text-secondary)'
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map(msg => <Message key={msg.id} msg={msg} />)}
                {loading && <TypingIndicator />}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input */}
          <div style={{
            padding: '12px 14px',
            borderTop: '1px solid rgba(255,255,255,0.06)',
            flexShrink: 0,
          }}>
            <div style={{
              display: 'flex', gap: 8, alignItems: 'flex-end',
            }}>
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Ask about suppliers, prices, shortages…"
                rows={1}
                style={{
                  flex: 1,
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 10,
                  padding: '9px 12px',
                  color: 'var(--text-primary)',
                  fontSize: 13,
                  fontFamily: 'var(--font)',
                  resize: 'none',
                  outline: 'none',
                  lineHeight: 1.5,
                  maxHeight: 100,
                  overflowY: 'auto',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.target.style.borderColor = 'rgba(239,68,68,0.35)'}
                onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.08)'}
                onInput={e => {
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px'
                }}
              />
              <button
                onClick={() => send()}
                disabled={!input.trim() || loading}
                style={{
                  width: 38, height: 38, flexShrink: 0,
                  background: input.trim() && !loading ? '#dc2626' : 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 10,
                  color: input.trim() && !loading ? 'white' : 'var(--text-muted)',
                  cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 16,
                  transition: 'all 0.15s ease',
                  boxShadow: input.trim() && !loading
                    ? '0 0 14px rgba(220,38,38,0.25)' : 'none',
                }}
              >
                ↑
              </button>
            </div>
            <div style={{
              fontSize: 10, color: 'var(--text-muted)',
              marginTop: 6, textAlign: 'center',
            }}>
              Enter to send · Shift+Enter for new line
            </div>
          </div>
        </div>
      )}
    </>
  )
}
