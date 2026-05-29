import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { organizationsApi, Organization, CreateOrgPayload } from '../api/organizations'

interface Props {
  embedded?: boolean
}

export default function OrganizationManagement({ embedded }: Props) {
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newSlug, setNewSlug] = useState('')
  const [error, setError] = useState('')
  const qc = useQueryClient()

  const { data: orgs = [], isLoading } = useQuery({
    queryKey: ['organizations'],
    queryFn: organizationsApi.list,
  })

  const createOrg = useMutation({
    mutationFn: (payload: CreateOrgPayload) => organizationsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['organizations'] })
      setShowCreate(false)
      setNewName('')
      setNewSlug('')
      setError('')
    },
    onError: (err: any) => setError(err?.response?.data?.detail || 'Failed to create organization'),
  })

  const toggleActive = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      organizationsApi.update(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['organizations'] }),
  })

  return (
    <div className={embedded ? 'p-6' : 'p-6'}>
      {!embedded && <h1 className="text-xl font-semibold text-text-primary mb-4">Organizations</h1>}

      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-text-muted">{orgs.length} organization{orgs.length !== 1 ? 's' : ''}</p>
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-1.5 text-sm rounded bg-anveshak-accent text-white hover:bg-anveshak-accent/80 transition-colors"
        >
          Create Organization
        </button>
      </div>

      {showCreate && (
        <div className="mb-4 p-4 border border-anveshak-border rounded-lg bg-anveshak-card space-y-3">
          <input
            type="text"
            placeholder="Organization name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full px-3 py-2 text-sm bg-anveshak-bg border border-anveshak-border rounded text-text-primary"
          />
          <input
            type="text"
            placeholder="Slug (URL-safe identifier)"
            value={newSlug}
            onChange={(e) => setNewSlug(e.target.value)}
            className="w-full px-3 py-2 text-sm bg-anveshak-bg border border-anveshak-border rounded text-text-primary"
          />
          {error && <p className="text-xs text-signal-high">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={() => createOrg.mutate({ name: newName, slug: newSlug })}
              disabled={!newName || !newSlug || createOrg.isPending}
              className="px-3 py-1.5 text-sm rounded bg-anveshak-accent text-white disabled:opacity-50"
            >
              {createOrg.isPending ? 'Creating...' : 'Create'}
            </button>
            <button
              onClick={() => { setShowCreate(false); setError('') }}
              className="px-3 py-1.5 text-sm rounded border border-anveshak-border text-text-muted"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading...</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-anveshak-border text-text-muted text-left">
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Slug</th>
              <th className="pb-2 font-medium">Status</th>
              <th className="pb-2 font-medium">Created</th>
              <th className="pb-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {orgs.map((org: Organization) => (
              <tr key={org.id} className="border-b border-anveshak-border/50">
                <td className="py-2.5 text-text-primary">{org.name}</td>
                <td className="py-2.5 text-text-muted font-mono text-xs">{org.slug}</td>
                <td className="py-2.5">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    org.is_active ? 'bg-cred-high/20 text-cred-high' : 'bg-anveshak-muted text-text-muted'
                  }`}>
                    {org.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="py-2.5 text-text-muted text-xs">{new Date(org.created_at).toLocaleDateString()}</td>
                <td className="py-2.5">
                  <button
                    onClick={() => toggleActive.mutate({ id: org.id, is_active: !org.is_active })}
                    className="text-xs text-text-muted hover:text-text-primary transition-colors"
                  >
                    {org.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
