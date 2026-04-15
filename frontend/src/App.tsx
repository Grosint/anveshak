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

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
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
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
