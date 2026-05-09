import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi, User } from '../api/users'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { Modal } from '../components/ui/Modal'

function CreateUserModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'analyst' | 'admin'>('analyst')
  const [error, setError] = useState('')
  const qc = useQueryClient()

  const create = useMutation({
    mutationFn: usersApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setUsername('')
      setPassword('')
      setRole('analyst')
      setError('')
      onClose()
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || 'Failed to create user')
    },
  })

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create User"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={create.isPending}
            disabled={!username || !password}
            onClick={() => create.mutate({ username, password, role })}
          >
            Create
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error && (
          <p className="text-sm text-signal-high bg-signal-high/10 rounded px-3 py-2">{error}</p>
        )}
        <div>
          <label className="block text-sm text-text-secondary mb-1">Username</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:border-anveshak-accent outline-none"
            placeholder="analyst1"
          />
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:border-anveshak-accent outline-none"
            placeholder="Minimum 8 characters"
          />
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1">Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as 'analyst' | 'admin')}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:border-anveshak-accent outline-none"
          >
            <option value="analyst">Analyst</option>
            <option value="admin">Admin</option>
          </select>
        </div>
      </div>
    </Modal>
  )
}

export default function UserManagement() {
  const [showCreate, setShowCreate] = useState(false)
  const qc = useQueryClient()

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: usersApi.list,
  })

  const deleteUser = useMutation({
    mutationFn: usersApi.delete,
    onMutate: async (userId) => {
      await qc.cancelQueries({ queryKey: ['users'] })
      const prev = qc.getQueryData<User[]>(['users'])
      qc.setQueryData<User[]>(['users'], (old = []) => old.filter((u) => u.id !== userId))
      return { prev }
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(['users'], ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })

  const toggleRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: 'analyst' | 'admin' }) =>
      usersApi.updateRole(userId, role),
    onSettled: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Users</h1>
          <p className="text-sm text-text-muted mt-0.5">{users.length} users</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>Create User</Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner label="Loading users..." />
          </div>
        ) : users.length === 0 ? (
          <EmptyState
            icon="👤"
            title="No users"
            description="Create the first user to get started."
            action={<Button onClick={() => setShowCreate(true)}>Create User</Button>}
          />
        ) : (
          <div className="bg-anveshak-card border border-anveshak-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-anveshak-border text-left text-xs text-text-muted uppercase tracking-wide">
                  <th className="px-4 py-3">Username</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b border-anveshak-border last:border-0 hover:bg-anveshak-muted/30">
                    <td className="px-4 py-3 text-text-primary font-medium">{user.username}</td>
                    <td className="px-4 py-3">
                      <Badge variant={user.role === 'admin' ? 'accent' : 'default'}>
                        {user.role}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-text-muted">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            toggleRole.mutate({
                              userId: user.id,
                              role: user.role === 'admin' ? 'analyst' : 'admin',
                            })
                          }
                          disabled={toggleRole.isPending}
                        >
                          {user.role === 'admin' ? 'Demote' : 'Promote'}
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => {
                            if (confirm(`Delete user "${user.username}"?`)) {
                              deleteUser.mutate(user.id)
                            }
                          }}
                          disabled={deleteUser.isPending}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <CreateUserModal open={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  )
}
