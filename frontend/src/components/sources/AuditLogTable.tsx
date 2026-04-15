import { AuditEntry } from '../../api/sources'
import { format } from 'date-fns'

interface AuditLogTableProps {
  entries: AuditEntry[]
}

export function AuditLogTable({ entries }: AuditLogTableProps) {
  if (entries.length === 0) {
    return <p className="text-sm text-text-muted py-4">No credibility changes recorded.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs" aria-label="Credibility audit log">
        <thead>
          <tr className="border-b border-anveshak-border text-left">
            <th className="py-2 pr-4 font-medium text-text-muted">Date</th>
            <th className="py-2 pr-4 font-medium text-text-muted">Change</th>
            <th className="py-2 pr-4 font-medium text-text-muted">Reason</th>
            <th className="py-2 font-medium text-text-muted">Changed by</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const delta = entry.new_score - entry.old_score
            return (
              <tr key={entry.id} className="border-b border-anveshak-border/50 hover:bg-anveshak-muted/30">
                <td className="py-2 pr-4 text-text-muted font-mono whitespace-nowrap">
                  {format(new Date(entry.created_at), 'dd MMM HH:mm')}
                </td>
                <td className="py-2 pr-4">
                  <span className="text-text-secondary">{entry.old_score.toFixed(0)}</span>
                  <span className="mx-1 text-text-muted">→</span>
                  <span className="text-text-primary font-medium">{entry.new_score.toFixed(0)}</span>
                  <span
                    className={`ml-2 ${delta >= 0 ? 'text-cred-high' : 'text-cred-low'}`}
                    aria-label={`Change: ${delta >= 0 ? '+' : ''}${delta.toFixed(0)}`}
                  >
                    {delta >= 0 ? '+' : ''}{delta.toFixed(0)}
                  </span>
                </td>
                <td className="py-2 pr-4 text-text-secondary max-w-[200px] truncate" title={entry.reason}>
                  {entry.reason}
                </td>
                <td className="py-2 text-text-muted">{entry.changed_by}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
