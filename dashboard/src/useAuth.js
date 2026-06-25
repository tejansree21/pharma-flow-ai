import { useState, useEffect, createContext, useContext } from 'react'

const DEMO_USERS = {
  'cpo@pharmaflow.ai':    { password: 'pharma123', role: 'CPO',                  name: 'Chief Procurement Officer', initials: 'CP' },
  'pm@pharmaflow.ai':     { password: 'pharma123', role: 'Procurement Manager',  name: 'Procurement Manager',       initials: 'PM' },
  'qa@pharmaflow.ai':     { password: 'pharma123', role: 'QA Lead',              name: 'Quality Assurance Lead',    initials: 'QA' },
  'buyer@pharmaflow.ai':  { password: 'pharma123', role: 'Buyer',                name: 'Buyer / Analyst',           initials: 'BY' },
}

export const ROLE_PERMISSIONS = {
  'CPO': [
    'overview', 'forecast', 'shortage', 'geo', 'demand',
    'benchmark', 'counterfeit',
    'suppliers', 'inventory', 'scenarios',
    'supplychain', 'compliance', 'esg',
  ],
  'Procurement Manager': [
    'overview', 'forecast', 'shortage', 'geo', 'demand',
    'benchmark', 'suppliers', 'inventory', 'scenarios',
    'supplychain',
  ],
  'QA Lead': [
    'overview', 'suppliers', 'counterfeit', 'compliance',
  ],
  'Buyer': [
    'overview', 'forecast', 'inventory',
  ],
}

const STORAGE_KEY = 'pharmaflow_user'
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) setUser(JSON.parse(stored))
    } catch (_) {}
    setReady(true)
  }, [])

  const login = (email, password) => {
    const demo = DEMO_USERS[email.toLowerCase().trim()]
    if (!demo || demo.password !== password) {
      throw new Error('Invalid email or password. Use the demo credentials shown below.')
    }
    const userData = { email: email.toLowerCase().trim(), role: demo.role, name: demo.name, initials: demo.initials }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(userData))
    setUser(userData)
    return userData
  }

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY)
    setUser(null)
  }

  const hasAccess = (pageId) => {
    if (!user) return false
    return (ROLE_PERMISSIONS[user.role] || []).includes(pageId)
  }

  return (
    <AuthContext.Provider value={{ user, ready, login, logout, hasAccess }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
