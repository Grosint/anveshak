import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import { Button } from '../components/ui/Button'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await axios.post<{ access_token: string }>(
        '/api/v1/auth/login',
        { username, password },
      )
      login(data.access_token)
      navigate('/topics', { replace: true })
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setError('Invalid username or password.')
      } else {
        setError('Unable to reach the server. Try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-anveshak-bg px-4">
      <div className="w-full max-w-sm bg-anveshak-card border border-anveshak-border rounded-lg shadow-card p-8 animate-fade-in">
        {/* Brand */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">Anveshak</h1>
          <p className="text-sm text-text-muted mt-1">AI-Powered OSINT Analysis Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label htmlFor="username" className="block text-xs font-medium text-text-secondary mb-1.5">
              Username
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              required
              className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent transition-colors"
              placeholder="analyst"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-medium text-text-secondary mb-1.5">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent transition-colors"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && (
            <p role="alert" className="text-signal-high text-xs bg-signal-high/10 border border-signal-high/20 rounded px-3 py-2">
              {error}
            </p>
          )}

          <Button type="submit" loading={loading} className="w-full mt-2">
            Sign in
          </Button>
        </form>

        <p className="text-center text-xs text-text-muted mt-6">
          Sovereign deployment — data never leaves this system
        </p>
      </div>
    </div>
  )
}
