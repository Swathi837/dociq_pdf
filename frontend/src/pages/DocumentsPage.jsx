import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import API from '../api/client'

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{status}</span>
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function loadDocs() {
    try {
      const res = await API.get('/documents/')
      setDocs(res.data)
    } catch (e) {
      setError('Failed to load documents')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadDocs() }, [])

  useEffect(() => {
    if (!docs.some(doc => doc.status === 'pending' || doc.status === 'processing')) return
    const timer = setInterval(loadDocs, 3000)
    return () => clearInterval(timer)
  }, [docs])

  const onDrop = useCallback(async (files) => {
    if (!files.length) return
    const file = files[0]
    if (file.type !== 'application/pdf') {
      setError('Only PDF files are allowed')
      return
    }
    setUploading(true)
    setError('')
    setSuccess('')
    const form = new FormData()
    form.append('file', file)
    try {
      await API.post('/documents/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setSuccess(`"${file.name}" uploaded! AI is processing it...`)
      setTimeout(loadDocs, 3000)
    } catch (e) {
      setError(e.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { 'application/pdf': ['.pdf'] }, maxFiles: 1
  })

  async function deleteDoc(id, name, e) {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm(`Delete "${name}"?`)) return
    await API.delete(`/documents/${id}`)
    loadDocs()
  }

  async function retryDoc(id, e) {
    e.preventDefault()
    e.stopPropagation()
    setError('')
    setSuccess('')
    try {
      await API.post(`/documents/${id}/retry`)
      setSuccess('Document queued for processing again.')
      loadDocs()
    } catch (err) {
      setError(err.response?.data?.detail || 'Retry failed')
    }
  }

  return (
    <div>
      <div className="section-header">
        <h1 className="section-title">Documents</h1>
        <span className="text-muted">{docs.length} document{docs.length !== 1 ? 's' : ''}</span>
      </div>

      {error && <div className="error-msg">{error}</div>}
      {success && <div className="success-msg">{success}</div>}

      <div className="card" style={{ marginBottom: 24 }}>
        <div {...getRootProps()} className={`upload-zone ${isDragActive ? 'active' : ''}`}>
          <input {...getInputProps()} />
          <div className="upload-icon">{uploading ? '⏳' : '📎'}</div>
          <div className="upload-text">
            {uploading ? 'Uploading...' : isDragActive ? 'Drop your PDF here' : 'Drag & drop a PDF, or click to browse'}
          </div>
          <div className="upload-sub">Max 50MB · PDF only</div>
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading documents...</div>
      ) : docs.length === 0 ? (
        <div className="empty">
          <div className="empty-icon">📂</div>
          <div className="empty-text">No documents yet — upload your first PDF above</div>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Status</th>
                  <th>Pages</th>
                  <th>Size</th>
                  <th>Uploaded</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {docs.map(doc => (
                  <tr key={doc.id}>
                    <td>
                      <Link to={`/documents/${doc.id}`} style={{ color: '#3b82f6', textDecoration: 'none', fontWeight: 500 }}>
                        📄 {doc.filename}
                      </Link>
                      {doc.status === 'failed' && doc.error_message && (
                        <div className="row-error">{doc.error_message}</div>
                      )}
                    </td>
                    <td><StatusBadge status={doc.status} /></td>
                    <td>{doc.page_count || '—'}</td>
                    <td>{doc.file_size_bytes ? `${(doc.file_size_bytes / 1024).toFixed(0)} KB` : '—'}</td>
                    <td>{new Date(doc.created_at).toLocaleDateString()}</td>
                    <td>
                      <div className="flex-center">
                        <Link to={`/documents/${doc.id}`} className="btn btn-sm btn-secondary">View</Link>
                        {doc.status === 'failed' && (
                          <button onClick={(e) => retryDoc(doc.id, e)} className="btn btn-sm btn-secondary">Retry</button>
                        )}
                        <button onClick={(e) => deleteDoc(doc.id, doc.filename, e)} className="btn btn-sm btn-danger">Del</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
