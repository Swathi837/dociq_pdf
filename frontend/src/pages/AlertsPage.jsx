import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import API from '../api/client'

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('all')
  const [testEmailMsg, setTestEmailMsg] = useState('')
  const [sendingTestEmail, setSendingTestEmail] = useState(false)

  useEffect(() => { loadAlerts() }, [])

  async function loadAlerts() {
    try {
      const res = await API.get('/alerts/')
      setAlerts(res.data)
    } finally {
      setLoading(false)
    }
  }

  async function dismiss(id) {
    await API.put(`/alerts/${id}`, { status: 'dismissed' })
    loadAlerts()
  }

  async function deleteAlert(id) {
    if (!confirm('Delete this alert?')) return
    await API.delete(`/alerts/${id}`)
    loadAlerts()
  }

  async function sendTestEmail() {
    setSendingTestEmail(true)
    setTestEmailMsg('')
    try {
      const res = await API.post('/alerts/test-email')
      setTestEmailMsg(`${res.data.message} to ${res.data.to_email}`)
    } catch (e) {
      setTestEmailMsg(e.response?.data?.detail || 'Test email failed. Check backend logs.')
    } finally {
      setSendingTestEmail(false)
    }
  }

  function daysColor(days) {
    if (days === undefined || days === null) return ''
    if (days <= 3) return 'days-urgent'
    if (days <= 14) return 'days-soon'
    return 'days-ok'
  }

  const filtered = tab === 'all' ? alerts : alerts.filter(a => a.status === tab)

  return (
    <div>
      <div className="section-header">
        <h1 className="section-title">Deadline Alerts</h1>
        <div className="flex-center">
          <button onClick={sendTestEmail} className="btn btn-secondary" disabled={sendingTestEmail}>
            {sendingTestEmail ? 'Sending...' : 'Send test email'}
          </button>
          <Link to="/documents" className="btn btn-primary">+ Add from Document</Link>
        </div>
      </div>

      {testEmailMsg && (
        <div className={testEmailMsg.toLowerCase().includes('failed') ? 'error-msg' : 'success-msg'}>
          {testEmailMsg}
        </div>
      )}

      <div className="tabs">
        {['all', 'active', 'triggered', 'dismissed'].map(t => (
          <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
            {t === 'all' ? ` (${alerts.length})` : ` (${alerts.filter(a => a.status === t).length})`}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading">Loading alerts...</div>
      ) : filtered.length === 0 ? (
        <div className="empty">
          <div className="empty-icon">🔔</div>
          <div className="empty-text">No {tab === 'all' ? '' : tab} alerts</div>
          <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 8 }}>
            Open a document and create alerts from its deadline dates
          </div>
        </div>
      ) : (
        filtered.map(alert => (
          <div key={alert.id} className="alert-card">
            <div className="alert-info">
              <div className="alert-title">{alert.title}</div>
              <div className="alert-meta">
                📅 {new Date(alert.deadline_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}
                {' · '}Notify {alert.notify_days_before} days before
                {alert.notify_email ? ' · 📧 Email' : ''}
              </div>
              <span className={`badge badge-${alert.status}`} style={{ marginTop: 6 }}>{alert.status}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {alert.days_until_deadline !== null && alert.status === 'active' && (
                <div className={`alert-days ${daysColor(alert.days_until_deadline)}`}>
                  {alert.days_until_deadline === 0 ? 'Today!' : `${alert.days_until_deadline}d left`}
                </div>
              )}
              <div className="flex-center">
                {alert.status === 'active' && (
                  <button onClick={() => dismiss(alert.id)} className="btn btn-sm btn-secondary">Dismiss</button>
                )}
                <button onClick={() => deleteAlert(alert.id)} className="btn btn-sm btn-danger">Delete</button>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
