import { useParams, useNavigate } from 'react-router-dom'
import SourceManager from './SourceManager'
import UserManagement from './UserManagement'
import AuditTrailPage from '../components/audit/AuditTrailPage'

type SettingsTab = 'sources' | 'users' | 'audit'

const TABS: { key: SettingsTab; label: string }[] = [
  { key: 'sources', label: 'Sources' },
  { key: 'users',   label: 'Users' },
  { key: 'audit',   label: 'Audit Trail' },
]

export default function Settings() {
  const { tab } = useParams<{ tab: string }>()
  const navigate = useNavigate()
  const activeTab: SettingsTab =
    tab === 'users' ? 'users' : tab === 'audit' ? 'audit' : 'sources'

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-0 border-b border-anveshak-border">
        <h1 className="text-xl font-semibold text-text-primary">Settings</h1>
        <p className="text-sm text-text-muted mt-0.5 mb-3">Platform configuration and administration</p>

        {/* Tabs */}
        <div className="flex" role="tablist">
          {TABS.map((t) => (
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
        {activeTab === 'audit' && <AuditTrailPage embedded />}
      </div>
    </div>
  )
}
