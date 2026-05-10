import { useState } from 'react'
import api from '../../api/client'

interface ExportButtonProps {
  /** Export endpoint path, e.g. '/api/v1/export/content' */
  endpoint: string
  /** Query params to pass (topic_id, format, limit) */
  params: Record<string, string | number>
  /** Button label */
  label?: string
  /** File format: csv or json */
  format?: 'csv' | 'json'
}

/**
 * Reusable export button — downloads CSV/JSON from backend export endpoints.
 *
 * Usage:
 *   <ExportButton
 *     endpoint="/api/v1/export/content"
 *     params={{ topic_id: topicId }}
 *     label="Export CSV"
 *   />
 */
export default function ExportButton({
  endpoint,
  params,
  label = 'Export',
  format = 'csv',
}: ExportButtonProps) {
  const [loading, setLoading] = useState(false)

  const handleExport = async () => {
    setLoading(true)
    try {
      const response = await api.get(endpoint, {
        params: { ...params, format },
        responseType: 'blob',
      })

      const contentDisposition = response.headers['content-disposition']
      const filename = contentDisposition
        ? contentDisposition.split('filename="')[1]?.replace('"', '')
        : `anveshak_export.${format}`

      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleExport}
      disabled={loading}
      className="export-btn"
      title={`Download ${format.toUpperCase()}`}
    >
      {loading ? 'Exporting...' : label}
    </button>
  )
}
