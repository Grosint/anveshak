import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import SourceManager from './SourceManager'
import UserManagement from './UserManagement'
import OrganizationManagement from './OrganizationManagement'
import AuditTrailPage from '../components/audit/AuditTrailPage'

type SettingsTab = 'sources' | 'users' | 'organizations' | 'audit'

const ALL_TABS: { key: SettingsTab; label: string; adminOnly?: boolean; superAdminOnly?: boolean }[] = [
  { key: 'sources',       label: 'Sources' },
  { key: 'users',         label: 'Users', adminOnly: true },
  { key: 'organizations', label: 'Organizations', superAdminOnly: true },
  { key: 'audit',         label: 'Audit Trail' },
]

export default function Settings() {
  const { tab } = useParams<{ tab: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin' || user?.role === 'super-admin'
  const isSuperAdmin = user?.role === 'super-admin'
  const tabs = ALL_TABS.filter((t) => {
    if (t.superAdminOnly) return isSuperAdmin
    if (t.adminOnly) return isAdmin
    return true
  })
  const activeTab: SettingsTab =
    tab === 'users' && isAdmin ? 'users'
    : tab === 'organizations' && isSuperAdmin ? 'organizations'
    : tab === 'audit' ? 'audit'
    : 'sources'

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-0 border-b border-anveshak-border">
        <h1 className="text-xl font-semibold text-text-primary">Settings</h1>
        <p className="text-sm text-text-muted mt-0.5 mb-3">Platform configuration and administration</p>

        {/* Tabs */}
        <div className="flex" role="tablist">
          {tabs.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={activeTab === t.key}
              onClick={() => navigate(`/settings/${t.key}`, { replace: true })}
              className={`px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none ${
                activeTab === t.key
                  ? 'text-anveshak-accent border-b-2 border-anveshak-accent'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'sources' && <SourceManager embedded />}
        {activeTab === 'users' && <UserManagement embedded />}
        {activeTab === 'organizations' && <OrganizationManagement embedded />}
        {activeTab === 'audit' && <AuditTrailPage embedded />}
      </div>
    </div>
  )
}
