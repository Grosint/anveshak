import { useState, useEffect } from 'react'
import type { ReportStatus } from '../../api/reports'

interface ReportProgressProps {
  status: ReportStatus
  error?: string | null
  startedAt?: string  // ISO timestamp of when the report was requested
}

const STEPS = [
  { key: 'received', label: 'Request Received' },
  { key: 'generating', label: 'Generating' },
  { key: 'complete', label: 'Complete' },
] as const

function Elapsed({ since }: { since: string }) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const start = new Date(since).getTime()
    const tick = () => setSeconds(Math.floor((Date.now() - start) / 1000))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [since])

  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return (
    <span className="font-mono text-xs">
      {m > 0 ? `${m}m ${s}s` : `${s}s`}
    </span>
  )
}

export function ReportProgress({ status, error, startedAt }: ReportProgressProps) {
  const isFailed = status === 'failed'

  // Map status to step index: received=0, generating=1, complete=2
  const activeStep = status === 'complete' ? 2 : status === 'failed' ? 1 : status === 'queued' ? 1 : 0

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-6">
      {/* Step indicators */}
      <div className="flex items-center justify-between mb-6">
        {STEPS.map((step, idx) => {
          const isComplete = idx < activeStep || (idx === activeStep && status === 'complete')
          const isActive = idx === activeStep && status !== 'complete'
          const isError = isFailed && idx === 1

          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              {/* Step circle + label */}
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500 ${
                    isError
                      ? 'bg-signal-high/20 border-2 border-signal-high text-signal-high'
                      : isComplete
                        ? 'bg-cred-high/20 border-2 border-cred-high text-cred-high'
                        : isActive
                          ? 'bg-anveshak-accent/20 border-2 border-anveshak-accent text-anveshak-accent animate-pulse'
                          : 'bg-anveshak-muted/30 border-2 border-anveshak-border text-text-muted'
                  }`}
                >
                  {isError ? (
                    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
                      <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                    </svg>
                  ) : isComplete ? (
                    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
                      <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    idx + 1
                  )}
                </div>
                <span
                  className={`text-[11px] mt-1.5 font-medium whitespace-nowrap ${
                    isError
                      ? 'text-signal-high'
                      : isComplete
                        ? 'text-cred-high'
                        : isActive
                          ? 'text-anveshak-accent'
                          : 'text-text-muted'
                  }`}
                >
                  {step.label}
                </span>
              </div>

              {/* Connector line */}
              {idx < STEPS.length - 1 && (
                <div className="flex-1 mx-3 mt-[-1.25rem]">
                  <div className="h-0.5 w-full rounded-full overflow-hidden bg-anveshak-border">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ease-out ${
                        isError ? 'bg-signal-high' : idx < activeStep ? 'bg-cred-high' : isActive ? 'bg-anveshak-accent w-1/2' : ''
                      }`}
                      style={{
                        width: idx < activeStep || (idx === activeStep && status === 'complete')
                          ? '100%'
                          : isActive
                            ? '50%'
                            : '0%',
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Status message area */}
      <div className="text-center">
        {status === 'queued' && startedAt && (
          <div className="flex items-center justify-center gap-2 text-sm text-text-secondary">
            <svg className="w-4 h-4 text-anveshak-accent animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>LLM is generating the report...</span>
            <Elapsed since={startedAt} />
          </div>
        )}

        {isFailed && (
          <div className="bg-signal-high/10 border border-signal-high/20 rounded px-4 py-3 text-sm text-signal-high">
            {error ?? 'Report generation failed. Check that Ollama is running and the model is loaded.'}
          </div>
        )}

        {status === 'complete' && (
          <p className="text-sm text-cred-high font-medium">Report ready</p>
        )}
      </div>
    </div>
  )
}
