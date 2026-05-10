import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi, User } from '../api/users'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { Modal } from '../components/ui/Modal'

type Role = 'viewer' | 'analyst' | 'admin'
type SortField = 'username' | 'role' | 'created_at'
type SortDir = 'asc' | 'desc'

const PAGE_SIZE = 10
const ROLES: Role[] = ['viewer', 'analyst', 'admin']
const ROLE_BADGE: Record<Role, 'ghost' | 'default' | 'accent'> = {
  viewer: 'ghost',
  analyst: 'default',
  admin: 'accent',
}

// ---------------------------------------------------------------------------
// Create User Modal
// ---------------------------------------------------------------------------

function CreateUserModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('analyst')
  const [error, setError] = useState('')
  const qc = useQueryClient()

  const create = useMutation({
    mutationFn: usersApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setUsername(''); setPassword(''); setRole('analyst'); setError('')
      onClose()
    },
    onError: (err: any) => setError(err?.response?.data?.detail || 'Failed to create user'),
  })

  return (
    <Modal open={open} onClose={onClose} title="Create User" footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button loading={create.isPending} disabled={!username || !password} onClick={() => create.mutate({ username, password, role })}>Create</Button>
      </>
    }>
      <div className="space-y-4">
        {error && <p className="text-sm text-signal-high bg-signal-high/10 rounded px-3 py-2">{error}</p>}
        <div>
          <label className="block text-sm text-text-secondary mb-1">Username</label>
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:border-anveshak-accent outline-none"
            placeholder="analyst1@anveshak.local" />
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1">Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:border-anveshak-accent outline-none"
            placeholder="Minimum 8 characters" />
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1">Role</label>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:border-anveshak-accent outline-none">
            {ROLES.map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
          </select>
        </div>
      </div>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Edit Role Modal
// ---------------------------------------------------------------------------

function EditRoleModal({ user, onClose }: { user: User | null; onClose: () => void }) {
  const [role, setRole] = useState<Role>(user?.role ?? 'analyst')
  const [error, setError] = useState('')
  const qc = useQueryClient()

  // Reset role when a different user is selected
  useState(() => { if (user) setRole(user.role) })

  const update = useMutation({
    mutationFn: () => usersApi.updateRole(user!.id, role),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); setError(''); onClose() },
    onError: (err: any) => setError(err?.response?.data?.detail || 'Failed to update role'),
  })

  if (!user) return null

  return (
    <Modal open={!!user} onClose={onClose} title={`Edit Role: ${user.username}`} footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button loading={update.isPending} disabled={role === user.role} onClick={() => update.mutate()}>Save</Button>
      </>
    }>
      <div className="space-y-4">
        {error && <p className="text-sm text-signal-high bg-signal-high/10 rounded px-3 py-2">{error}</p>}
        <div>
          <label className="block text-sm text-text-secondary mb-1">Current Role</label>
          <Badge variant={ROLE_BADGE[user.role]}>{user.role}</Badge>
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1">New Role</label>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:border-anveshak-accent outline-none">
            {ROLES.map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
          </select>
        </div>
      </div>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Delete Confirm Modal
// ---------------------------------------------------------------------------

function DeleteConfirmModal({ user, onClose }: { user: User | null; onClose: () => void }) {
  const qc = useQueryClient()

  const del = useMutation({
    mutationFn: () => usersApi.delete(user!.id),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ['users'] })
      const prev = qc.getQueryData<User[]>(['users'])
      qc.setQueryData<User[]>(['users'], (old = []) => old.filter((u) => u.id !== user!.id))
      return { prev }
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(['users'], ctx.prev) },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['users'] }); onClose() },
  })

  if (!user) return null

  return (
    <Modal open={!!user} onClose={onClose} title="Delete User" footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button variant="danger" loading={del.isPending} onClick={() => del.mutate()}>Delete</Button>
      </>
    }>
      <p className="text-sm text-text-secondary">
        Are you sure you want to delete <span className="font-medium text-text-primary">{user.username}</span>?
        This action cannot be undone.
      </p>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Sort Arrow Icon
// ---------------------------------------------------------------------------

function SortArrow({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="ml-1 text-text-muted opacity-40">&#x2195;</span>
  return <span className="ml-1 text-anveshak-accent">{dir === 'asc' ? '\u2191' : '\u2193'}</span>
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function UserManagement() {
  const [searchQuery, setSearchQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<'all' | Role>('all')
  const [sortField, setSortField] = useState<SortField>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [page, setPage] = useState(0)
  const [showCreate, setShowCreate] = useState(false)
  const [editUser, setEditUser] = useState<User | null>(null)
  const [deleteUser, setDeleteUser] = useState<User | null>(null)

  const { data: users = [], isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: usersApi.list,
  })

  // 403 = user's token doesn't have admin role (may need re-login)
  const is403 = (error as any)?.response?.status === 403

  // Client-side filter → sort → paginate
  const processed = useMemo(() => {
    let list = [...users]

    // Search
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      list = list.filter((u) => u.username.toLowerCase().includes(q))
    }

    // Role filter
    if (roleFilter !== 'all') {
      list = list.filter((u) => u.role === roleFilter)
    }

    // Sort
    list.sort((a, b) => {
      const av = a[sortField] ?? ''
      const bv = b[sortField] ?? ''
      const cmp = String(av).localeCompare(String(bv))
      return sortDir === 'asc' ? cmp : -cmp
    })

    return list
  }, [users, searchQuery, roleFilter, sortField, sortDir])

  const totalFiltered = processed.length
  const totalPages = Math.max(1, Math.ceil(totalFiltered / PAGE_SIZE))
  const safePage = Math.min(page, totalPages - 1)
  const pageUsers = processed.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE)
  const showingFrom = totalFiltered === 0 ? 0 : safePage * PAGE_SIZE + 1
  const showingTo = Math.min((safePage + 1) * PAGE_SIZE, totalFiltered)

  // Reset page when filters change
  const handleSearch = (q: string) => { setSearchQuery(q); setPage(0) }
  const handleRoleFilter = (r: 'all' | Role) => { setRoleFilter(r); setPage(0) }
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }

  const roleChips: { label: string; value: 'all' | Role }[] = [
    { label: 'All', value: 'all' },
    { label: 'Admin', value: 'admin' },
    { label: 'Analyst', value: 'analyst' },
    { label: 'Viewer', value: 'viewer' },
  ]

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-text-primary">User Management</h1>
            <p className="text-sm text-text-muted mt-0.5">
              {totalFiltered === users.length
                ? `${users.length} users`
                : `${totalFiltered} of ${users.length} users`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* Search */}
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder="Search username..."
                className="bg-anveshak-bg border border-anveshak-border rounded px-3 py-1.5 pl-8 text-sm text-text-primary focus:border-anveshak-accent outline-none w-56"
              />
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 absolute left-2.5 top-2 text-text-muted" aria-hidden="true">
                <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
              </svg>
            </div>
            <Button onClick={() => setShowCreate(true)}>Create User</Button>
          </div>
        </div>

        {/* Role filter chips */}
        <div className="flex gap-2 mt-3">
          {roleChips.map((chip) => (
            <button
              key={chip.value}
              onClick={() => handleRoleFilter(chip.value)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                roleFilter === chip.value
                  ? 'bg-anveshak-accent text-white'
                  : 'bg-anveshak-muted/50 text-text-muted hover:text-text-primary'
              }`}
            >
              {chip.label}
              {chip.value !== 'all' && (
                <span className="ml-1 opacity-70">
                  {users.filter((u) => u.role === chip.value).length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto p-6">
        {is403 ? (
          <EmptyState
            icon="&#x1F6AB;"
            title="Access denied"
            description="Admin role required. If you were recently promoted, log out and log back in to refresh your token."
            action={<Button variant="secondary" onClick={() => { localStorage.removeItem('anveshak_token'); window.location.href = '/login' }}>Re-login</Button>}
          />
        ) : isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner label="Loading users..." />
          </div>
        ) : users.length === 0 ? (
          <EmptyState
            icon="&#x1F464;"
            title="No users"
            description="Create the first user to get started."
            action={<Button onClick={() => setShowCreate(true)}>Create User</Button>}
          />
        ) : totalFiltered === 0 ? (
          <EmptyState
            icon="&#x1F50D;"
            title="No matches"
            description="No users match your search or filter criteria."
            action={<Button variant="secondary" onClick={() => { setSearchQuery(''); setRoleFilter('all') }}>Clear Filters</Button>}
          />
        ) : (
          <div className="bg-anveshak-card border border-anveshak-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-anveshak-border text-left text-xs text-text-muted uppercase tracking-wide">
                  <th className="px-4 py-3 cursor-pointer select-none" onClick={() => handleSort('username')}>
                    Username <SortArrow active={sortField === 'username'} dir={sortDir} />
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none" onClick={() => handleSort('role')}>
                    Role <SortArrow active={sortField === 'role'} dir={sortDir} />
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none" onClick={() => handleSort('created_at')}>
                    Created <SortArrow active={sortField === 'created_at'} dir={sortDir} />
                  </th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pageUsers.map((user) => (
                  <tr key={user.id} className="border-b border-anveshak-border last:border-0 hover:bg-anveshak-muted/30 transition-colors">
                    <td className="px-4 py-3 text-text-primary font-medium">{user.username}</td>
                    <td className="px-4 py-3">
                      <Badge variant={ROLE_BADGE[user.role as Role] ?? 'default'}>
                        {user.role}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-text-muted">
                      {new Date(user.created_at).toLocaleDateString(undefined, {
                        year: 'numeric', month: 'short', day: 'numeric',
                      })}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditUser(user)}>
                          Edit
                        </Button>
                        <Button variant="danger" size="sm" onClick={() => setDeleteUser(user)}>
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination footer */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-anveshak-border text-xs text-text-muted">
                <span>Showing {showingFrom}&#x2013;{showingTo} of {totalFiltered} users</span>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" disabled={safePage === 0} onClick={() => setPage((p) => p - 1)}>
                    Prev
                  </Button>
                  <span className="flex items-center px-2 text-text-secondary">
                    Page {safePage + 1} of {totalPages}
                  </span>
                  <Button variant="secondary" size="sm" disabled={safePage >= totalPages - 1} onClick={() => setPage((p) => p + 1)}>
                    Next
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modals */}
      <CreateUserModal open={showCreate} onClose={() => setShowCreate(false)} />
      <EditRoleModal user={editUser} onClose={() => setEditUser(null)} />
      <DeleteConfirmModal user={deleteUser} onClose={() => setDeleteUser(null)} />
    </div>
  )
}
