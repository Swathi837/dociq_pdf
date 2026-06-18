import { useState } from 'react'
import API from '../api/client'

export default function LoginPage() {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('swathi@dociq.com')
  const [password, setPassword] = useState('swathi837')
  const [fullName, setFullName] = useState('Swathi')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')

    try {
      const endpoint = mode === 'login' ? '/auth/login' : '/auth/register'
      const payload = mode === 'login'
        ? { email, password }
        : { email, password, full_name: fullName }
      const { data } = await API.post(endpoint, payload)

      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user || { email, full_name: fullName }))
      window.location.href = '/'
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to sign in. Please check your details and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div>
          <div className="auth-logo">Doc<span>IQ</span></div>
          <h1>{mode === 'login' ? 'Welcome back' : 'Create your workspace'}</h1>
          <p>Sign in to review documents, deadlines, alerts, and extracted intelligence.</p>
        </div>

        <form onSubmit={submit} className="auth-form">
          {mode === 'register' && (
            <label>
              Full name
              <input value={fullName} onChange={(event) => setFullName(event.target.value)} required />
            </label>
          )}
          <label>
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>

          {error && <div className="form-error">{error}</div>}

          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <button className="link-button" type="button" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Need an account? Register' : 'Already have an account? Sign in'}
        </button>
      </section>
    </main>
  )
}
