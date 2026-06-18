import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import API from '../api/client'

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{status}</span>
}

export default function DashboardPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    API.get('/dashboard/').then(r => setData(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading">Loading dashboard...</div>
  if (!data) return <div className="error-msg">Failed to load dashboard</div>

  const { stats, recent_documents, upcoming_deadlines } = data

  function daysColor(days) {
    if (days <= 3) return 'days-urgent'
    if (days <= 14) return 'days-soon'
    return 'days-ok'
  }

  return (
    <div>
      <div className="section-header">
        <h1 className="section-title">Dashboard</h1>
        <Link to="/documents" className="btn btn-primary">+ Upload Document</Link>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Total Documents</div>
          <div className="stat-value">{stats.total_documents}</div>
          <div className="stat-sub">{stats.processed_documents} processed</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Text Chunks</div>
          <div className="stat-value">{stats.total_chunks}</div>
          <div className="stat-sub">Indexed for search</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Active Alerts</div>
          <div className="stat-value">{stats.active_alerts}</div>
          <div className="stat-sub">{stats.upcoming_alerts_7days} due this week</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Failed Docs</div>
          <div className="stat-value" style={{ color: stats.failed_documents > 0 ? '#dc2626' : '#1e293b' }}>{stats.failed_documents}</div>
          <div className="stat-sub">Need attention</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="section-header">
            <h2 style={{ fontSize: 15, fontWeight: 600 }}>Recent Documents</h2>
            <Link to="/documents" className="btn btn-sm btn-secondary">View all</Link>
          </div>
          {recent_documents.length === 0 ? (
            <div className="empty"><div className="empty-text">No documents yet</div></div>
          ) : (
            recent_documents.map(doc => (
              <Link to={`/documents/${doc.id}`} key={doc.id} style={{ textDecoration: 'none' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: '#1e293b' }}>{doc.filename}</div>
                    <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{new Date(doc.created_at).toLocaleDateString()}</div>
                  </div>
                  <StatusBadge status={doc.status} />
                </div>
              </Link>
            ))
          )}
        </div>

        <div className="card">
          <div className="section-header">
            <h2 style={{ fontSize: 15, fontWeight: 600 }}>Upcoming Deadlines</h2>
            <Link to="/alerts" className="btn btn-sm btn-secondary">View all</Link>
          </div>
          {upcoming_deadlines.length === 0 ? (
            <div className="empty"><div className="empty-text">No upcoming deadlines</div></div>
          ) : (
            upcoming_deadlines.map(d => (
              <div key={d.alert_id} className="alert-card" style={{ marginBottom: 8, padding: '12px 16px' }}>
                <div className="alert-info">
                  <div className="alert-title">{d.title}</div>
                  <div className="alert-meta">{d.document_name} · {new Date(d.deadline_date).toLocaleDateString()}</div>
                </div>
                <div className={`alert-days ${daysColor(d.days_until)}`}>{d.days_until}d</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}