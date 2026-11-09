import { TASK_STATUSES, type TaskStatus, type WorkflowStatus } from '../api/client'

export function StatusBadge({ status }: { status: TaskStatus | WorkflowStatus }) {
  return <span className={`badge s-${status}`}>{status.toLowerCase()}</span>
}

export function ProgressBar({ value, status }: { value: number; status: TaskStatus | WorkflowStatus }) {
  return (
    <div className="progress" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div className={`progress-fill s-${status}`} style={{ width: `${Math.min(100, value)}%` }} />
    </div>
  )
}

/** One segment per task status, sized by count. */
export function StatusBreakdown({ counts, total }: { counts: Record<string, number>; total: number }) {
  const parts = TASK_STATUSES.filter((s) => counts[s])
  return (
    <div>
      <div className="stacked">
        {parts.map((s) => (
          <div key={s} className={`s-${s}`} style={{ flex: counts[s] }} title={`${counts[s]} ${s.toLowerCase()}`} />
        ))}
      </div>
      <div className="stacked-legend">
        {parts.map((s) => (
          <span key={s}>
            <i className={`dot s-${s}`} /> {counts[s]} {s.toLowerCase()}
          </span>
        ))}
        {parts.length === 0 && <span>{total} tasks</span>}
      </div>
    </div>
  )
}
