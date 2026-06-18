import { Outlet, NavLink, useNavigate } from 'react-router-dom'

export default function Layout() {
  const navigate = useNavigate()
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  const initials = (user.full_name || user.email || 'U').slice(0, 2).toUpperCase()

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">Doc<span>IQ</span></div>
        <nav className="sidebar-nav">
          <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">DI</span> Dashboard
          </NavLink>
          <NavLink to="/documents" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">DO</span> Documents
          </NavLink>
          <NavLink to="/alerts" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">AL</span> Alerts
          </NavLink>
        </nav>
        <div className="sidebar-footer">
          <div style={{ color: '#cbd5e1', fontSize: 12, marginBottom: 8 }}>{user.email}</div>
          <button onClick={logout} className="btn btn-sm" style={{ background: '#334155', color: '#94a3b8', border: 'none', width: '100%' }}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">
        <div className="topbar">
          <span className="topbar-title">DocIQ Platform</span>
          <div className="topbar-user">
            <span>{user.full_name || user.email}</span>
            <div className="avatar">{initials}</div>
          </div>
        </div>
        <div className="page-content">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
