import type { Task } from '../api/client'
import { duration } from '../format'
import { ProgressBar, StatusBadge } from './Status'

export function TaskTable({ tasks, selected, onSelect }: {
  tasks: Task[]
  selected?: string | null
  onSelect?: (name: string) => void
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Task</th>
            <th>Status</th>
            <th className="w-progress">Progress</th>
            <th>Depends on</th>
            <th>Duration</th>
            <th>Job</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => (
            <tr
              key={t.id}
              className={selected === t.name ? 'selected' : undefined}
              onClick={() => onSelect?.(t.name)}
            >
              <td>
                <div className="mono">{t.name}</div>
                {t.error && <div className="error-text">{t.error}</div>}
              </td>
              <td><StatusBadge status={t.status} /></td>
              <td>
                <div className="progress-cell">
                  <ProgressBar value={t.progress} status={t.status} />
                  <span className="num">{Math.round(t.progress)}%</span>
                </div>
              </td>
              <td className="mono muted">{t.depends_on.join(', ') || '—'}</td>
              <td className="num">{duration(t.started_at, t.finished_at)}</td>
              <td className="mono muted small">{t.batch_job_id ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
