import { useState } from 'react'
import { useAuth } from '../useAuth.jsx'

const DEMO_CREDENTIALS = [
  { email: 'cpo@pharmaflow.ai',   role: 'CPO',                 access: 'All modules' },
  { email: 'pm@pharmaflow.ai',    role: 'Procurement Manager', access: 'Intelligence + Operations' },
  { email: 'qa@pharmaflow.ai',    role: 'QA Lead',             access: 'Dashboard + Suppliers + Counterfeit' },
  { email: 'buyer@pharmaflow.ai', role: 'Buyer',               access: 'Dashboard + Forecast + Inventory' },
]

export default function Login({ onLogin }) {
  const { login }           = useAuth()
  const [email, setEmail]   = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]   = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email || !password) { setError('Please enter email and password.'); return }
    setLoading(true); setError('')
    try {
      const user = login(email, password)
      onLogin?.(user)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const quickLogin = (demoEmail) => {
    setEmail(demoEmail)
    setPassword('pharma123')
    setError('')
  }

  return (
    <div style={{
      minHeight: '100vh', background: '#080808',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '24px', fontFamily: 'var(--font)',
    }}>
      {/* Ambient background */}
      <div style={{
        position: 'fixed', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse 60% 40% at 30% 20%, rgba(220,38,38,0.06) 0%, transparent 60%)',
      }} />

      <div style={{ width: '100%', maxWidth: 440, position: 'relative', zIndex: 1 }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 14,
            background: 'linear-gradient(135deg,#dc2626,#ef4444)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px', fontSize: 24,
            boxShadow: '0 0 28px rgba(220,38,38,0.3)',
          }}>
            ⚕️
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#fff', marginBottom: 4 }}>
            PharmaFlow AI
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', letterSpacing: '0.5px' }}>
            SUPPLY CHAIN INTELLIGENCE
          </div>
        </div>

        {/* Login card */}
        <div style={{
          background: '#0d0d0d',
          border: '1px solid rgba(239,68,68,0.15)',
          borderRadius: 16, padding: '32px',
          boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
        }}>
          <div style={{ fontSize: 18, fontWeight: 600, color: '#fff', marginBottom: 8 }}>
            Sign in
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 24, lineHeight: 1.5 }}>
            Enter your credentials or click a demo role below.
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6, letterSpacing: '0.3px' }}>
                EMAIL
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@pharmaflow.ai"
                style={{
                  width: '100%', padding: '10px 14px',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 10, color: '#fff',
                  fontFamily: 'var(--font)', fontSize: 13,
                  outline: 'none', boxSizing: 'border-box',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.target.style.borderColor = 'rgba(239,68,68,0.4)'}
                onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.08)'}
              />
            </div>

            <div>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6, letterSpacing: '0.3px' }}>
                PASSWORD
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{
                  width: '100%', padding: '10px 14px',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 10, color: '#fff',
                  fontFamily: 'var(--font)', fontSize: 13,
                  outline: 'none', boxSizing: 'border-box',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.target.style.borderColor = 'rgba(239,68,68,0.4)'}
                onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.08)'}
              />
            </div>

            {error && (
              <div style={{
                padding: '8px 12px', borderRadius: 8,
                background: 'rgba(239,68,68,0.08)',
                border: '1px solid rgba(239,68,68,0.2)',
                fontSize: 12, color: '#ef4444',
              }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '11px', background: loading ? 'rgba(220,38,38,0.4)' : '#dc2626',
                border: 'none', borderRadius: 10,
                color: '#fff', fontWeight: 600, fontSize: 14,
                cursor: loading ? 'not-allowed' : 'pointer',
                fontFamily: 'var(--font)',
                boxShadow: loading ? 'none' : '0 0 20px rgba(220,38,38,0.3)',
                transition: 'all 0.2s ease',
                marginTop: 4,
              }}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          {/* Demo credentials */}
          <div style={{ marginTop: 28 }}>
            <div style={{
              fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.3px',
              marginBottom: 12, textAlign: 'center',
            }}>
              DEMO ACCOUNTS — all use password: <code style={{ color: '#f59e0b', fontFamily: 'var(--mono)' }}>pharma123</code>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {DEMO_CREDENTIALS.map(({ email: de, role, access }) => (
                <div
                  key={de}
                  onClick={() => quickLogin(de)}
                  style={{
                    padding: '8px 12px', borderRadius: 8,
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    cursor: 'pointer', transition: 'all 0.15s ease',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.06)'; e.currentTarget.style.borderColor = 'rgba(239,68,68,0.18)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)' }}
                >
                  <div>
                    <div style={{ fontSize: 12, color: '#fff', fontWeight: 500 }}>{role}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>{de}</div>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textAlign: 'right', maxWidth: 140 }}>
                    {access}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div style={{ textAlign: 'center', marginTop: 20, fontSize: 11, color: 'var(--text-muted)' }}>
          Demo auth — client-side only · Backend secured via API key
        </div>
      </div>
    </div>
  )
}
