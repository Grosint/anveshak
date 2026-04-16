import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import { WSProvider } from './contexts/WSContext'
import Layout from './components/ui/Layout'
import Login from './pages/Login'
import TopicsDashboard from './pages/TopicsDashboard'
import ContentFeed from './pages/ContentFeed'
import ImageAnalysis from './pages/ImageAnalysis'
import SignalsInbox from './pages/SignalsInbox'
import ReportBuilder from './pages/ReportBuilder'
import SourceManager from './pages/SourceManager'

// ── Error boundary — catches unhandled render errors so the page never
// goes silently blank. Shows the error message + a reload button.
interface EBState { error: Error | null }
class ErrorBoundary extends React.Component<{ children: React.ReactNode }, EBState> {
  state: EBState = { error: null }

  static getDerivedStateFromError(error: Error): EBState {
    return { error }
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: '#0f1117', padding: '2rem', fontFamily: 'monospace',
      }}>
        <div style={{ maxWidth: 560, width: '100%' }}>
          <p style={{ color: '#F5A623', fontSize: 11, letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: 12 }}>
            Render error
          </p>
          <p style={{ color: '#f1f5f9', fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
            {error.message}
          </p>
          <pre style={{
            color: '#64748b', fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
            background: '#1a1f2e', border: '1px solid #2d3748', borderRadius: 6,
            padding: '12px 14px', marginBottom: 20, maxHeight: 200, overflow: 'auto',
          }}>
            {error.stack}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: '#F5A623', color: '#1A0800', border: 'none', borderRadius: 6,
              padding: '8px 20px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}
          >
            Reload page
          </button>
        </div>
      </div>
    )
  }
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <ProtectedRoute>
              <WSProvider>
                <Layout />
              </WSProvider>
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Navigate to="/topics" replace />} />
          <Route path="/topics" element={<TopicsDashboard />} />
          <Route path="/topics/:topicId/feed" element={<ContentFeed />} />
          <Route path="/vision" element={<ImageAnalysis />} />
          <Route path="/signals" element={<SignalsInbox />} />
          <Route path="/reports" element={<ReportBuilder />} />
          <Route path="/sources" element={<SourceManager />} />
          <Route path="/source-health" element={<Navigate to="/sources" replace />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}
