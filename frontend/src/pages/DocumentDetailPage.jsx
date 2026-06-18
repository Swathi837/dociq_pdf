import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import API from '../api/client'

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{status}</span>
}

export default function DocumentDetailPage() {
  const { id } = useParams()
  const [doc, setDoc] = useState(null)
  const [extraction, setExtraction] = useState(null)
  const [tab, setTab] = useState('summary')
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [alertForm, setAlertForm] = useState({ title: '', deadline_date: '', notify_days_before: 7 })
  const [alertMsg, setAlertMsg] = useState('')
  const msgEnd = useRef(null)

  useEffect(() => {
    API.get(`/documents/${id}`).then(r => setDoc(r.data))
    API.get(`/chat/${id}/extraction`).then(r => setExtraction(r.data)).catch(() => {})
  }, [id])

  useEffect(() => {
    if (!doc || (doc.status !== 'pending' && doc.status !== 'processing')) return
    const timer = setInterval(() => {
      API.get(`/documents/${id}`).then(r => setDoc(r.data))
      API.get(`/chat/${id}/extraction`).then(r => setExtraction(r.data)).catch(() => {})
    }, 3000)
    return () => clearInterval(timer)
  }, [doc, id])

  useEffect(() => {
    msgEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function askQuestion(e) {
    e.preventDefault()
    if (!question.trim() || chatLoading) return
    const q = question.trim()
    setQuestion('')
    setMessages(m => [...m, { role: 'user', content: q }])
    setChatLoading(true)
    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }))
      const res = await API.post(`/chat/${id}/ask`, { question: q, history })
      setMessages(m => [...m, {
        role: 'assistant',
        content: res.data.answer,
        sources: res.data.sources
      }])
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'Sorry, I could not answer that question.' }])
    } finally {
      setChatLoading(false)
    }
  }

  async function createAlert(e) {
    e.preventDefault()
    setAlertMsg('')
    try {
      await API.post('/alerts/', {
        document_id: id,
        title: alertForm.title,
        deadline_date: new Date(alertForm.deadline_date).toISOString(),
        notify_days_before: parseInt(alertForm.notify_days_before),
        notify_email: true,
      })
      setAlertMsg('Alert created successfully!')
      setAlertForm({ title: '', deadline_date: '', notify_days_before: 7 })
    } catch (e) {
      setAlertMsg('Failed to create alert: ' + (e.response?.data?.detail || 'error'))
    }
  }

  async function autoDetect() {
    try {
      const res = await API.post(`/alerts/${id}/auto-detect`)
      setAlertMsg(res.data.length > 0 ? `Created ${res.data.length} alert(s) from document dates!` : 'No future dates detected in this document.')
    } catch {
      setAlertMsg('Auto-detect failed')
    }
  }

  async function retryProcessing() {
    setAlertMsg('')
    try {
      const res = await API.post(`/documents/${id}/retry`)
      setDoc(res.data)
    } catch (e) {
      setAlertMsg('Retry failed: ' + (e.response?.data?.detail || 'error'))
    }
  }

  if (!doc) return <div className="loading">Loading document...</div>

  return (
    <div>
      <div className="section-header">
        <div>
          <Link to="/documents" style={{ color: '#64748b', textDecoration: 'none', fontSize: 13 }}>← Documents</Link>
          <h1 className="section-title" style={{ marginTop: 4 }}>📄 {doc.filename}</h1>
        </div>
        <div className="flex-center">
          <StatusBadge status={doc.status} />
          <span className="text-muted">{doc.page_count ? `${doc.page_count} page(s)` : ''}</span>
        </div>
      </div>

      {doc.status !== 'processed' && (
        <div className="error-msg" style={{ background: '#fef9c3', color: '#92400e' }}>
          ⏳ Document is {doc.status} — AI features will be available once processing completes.
          {doc.status === 'failed' && doc.error_message && (
            <div className="failure-detail">{doc.error_message}</div>
          )}
          {doc.status === 'failed' && (
            <button onClick={retryProcessing} className="btn btn-sm btn-secondary" style={{ marginTop: 10 }}>
              Retry processing
            </button>
          )}
        </div>
      )}

      <div className="tabs">
        {['summary', 'extraction', 'chat', 'alerts'].map(t => (
          <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t === 'summary' ? '📝 Summary' : t === 'extraction' ? '🔍 Extraction' : t === 'chat' ? '💬 Q&A Chat' : '🔔 Alerts'}
          </button>
        ))}
      </div>

      {/* SUMMARY */}
      {tab === 'summary' && (
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Document Summary</h3>
          {extraction?.summary ? (
            <div className="summary-box">{extraction.summary}</div>
          ) : (
            <div className="empty"><div className="empty-text">Summary not available yet</div></div>
          )}
        </div>
      )}

      {/* EXTRACTION */}
      {tab === 'extraction' && (
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Extracted Information</h3>
          {extraction?.extracted_data ? (
            <div className="extraction-grid">
              {[
                ['Document Type', extraction.extracted_data.document_type],
                ['Parties', (extraction.extracted_data.parties || []).join(', ') || '—'],
                ['Effective Date', extraction.extracted_data.effective_date || '—'],
                ['Expiry Date', extraction.extracted_data.expiry_date || '—'],
                ['Payment Terms', extraction.extracted_data.payment_terms || '—'],
                ['Jurisdiction', extraction.extracted_data.jurisdiction || '—'],
              ].map(([label, value]) => (
                <div key={label} className="extraction-item">
                  <div className="extraction-label">{label}</div>
                  <div className="extraction-value">{value || '—'}</div>
                </div>
              ))}
              {extraction.extracted_data.key_clauses?.length > 0 && (
                <div className="extraction-item" style={{ gridColumn: '1 / -1' }}>
                  <div className="extraction-label">Key Clauses</div>
                  {extraction.extracted_data.key_clauses.map((c, i) => (
                    <div key={i} className="extraction-value" style={{ marginBottom: 6, paddingLeft: 12, borderLeft: '2px solid #e2e8f0' }}>{c}</div>
                  ))}
                </div>
              )}
              {extraction.extracted_data.amounts?.length > 0 && (
                <div className="extraction-item" style={{ gridColumn: '1 / -1' }}>
                  <div className="extraction-label">Amounts</div>
                  {extraction.extracted_data.amounts.map((a, i) => (
                    <div key={i} className="extraction-value">{a.label}: {a.amount}</div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="empty"><div className="empty-text">Extraction not available yet</div></div>
          )}
        </div>
      )}

      {/* CHAT */}
      {tab === 'chat' && (
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Ask Questions About This Document</h3>
          <div className="chat-wrap">
            <div className="chat-messages">
              {messages.length === 0 && (
                <div className="empty" style={{ padding: 40 }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>💬</div>
                  <div className="empty-text">Ask anything about this document</div>
                  <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 8 }}>
                    Try: "What is this document about?" or "What are the key dates?"
                  </div>
                </div>
              )}
              {messages.map((m, i) => (
                <div key={i} className={`msg msg-${m.role === 'user' ? 'user' : 'ai'}`}>
                  {m.content}
                  {m.sources?.length > 0 && (
                    <div className="msg-sources">
                      📍 {m.sources.map(s => `Page ${s.page_num}`).join(', ')}
                    </div>
                  )}
                </div>
              ))}
              {chatLoading && <div className="msg msg-ai">Thinking...</div>}
              <div ref={msgEnd} />
            </div>
            <form onSubmit={askQuestion} className="chat-input-wrap">
              <input
                className="chat-input"
                value={question}
                onChange={e => setQuestion(e.target.value)}
                placeholder="Ask a question about this document..."
                disabled={chatLoading || doc.status !== 'processed'}
              />
              <button type="submit" className="btn btn-primary" disabled={chatLoading || doc.status !== 'processed'}>Send</button>
            </form>
          </div>
        </div>
      )}

      {/* ALERTS */}
      {tab === 'alerts' && (
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Deadline Alerts</h3>
          {alertMsg && (
            <div className={alertMsg.includes('Failed') ? 'error-msg' : 'success-msg'}>{alertMsg}</div>
          )}
          <button onClick={autoDetect} className="btn btn-secondary" style={{ marginBottom: 20 }}>
            🔍 Auto-detect dates from document
          </button>
          <h4 style={{ fontSize: 14, fontWeight: 500, marginBottom: 12 }}>Create manual alert</h4>
          <form onSubmit={createAlert}>
            <div className="form-group">
              <label>Alert title</label>
              <input value={alertForm.title} onChange={e => setAlertForm({ ...alertForm, title: e.target.value })} placeholder="e.g. Contract renewal deadline" required />
            </div>
            <div className="form-group">
              <label>Deadline date</label>
              <input type="datetime-local" value={alertForm.deadline_date} onChange={e => setAlertForm({ ...alertForm, deadline_date: e.target.value })} required />
            </div>
            <div className="form-group">
              <label>Notify me (days before)</label>
              <input type="number" min={1} max={90} value={alertForm.notify_days_before} onChange={e => setAlertForm({ ...alertForm, notify_days_before: e.target.value })} />
            </div>
            <button type="submit" className="btn btn-primary">Create Alert</button>
          </form>
        </div>
      )}
    </div>
  )
}
