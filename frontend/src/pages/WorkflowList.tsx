import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { StatusBadge, StatusBreakdown } from '../components/Status'
import { duration, timeAgo } from '../format'

export function WorkflowList() {
  const { data, error, isPending } = useQuery({
    queryKey: ['workflows'],
    queryFn: api.listWorkflows,
    refetchInterval: 1500,
  })

  if (isPending) return <p className="muted">Loading…</p>
  if (error) return <p className="error-text">Could not load workflows: {error.message}</p>
  if (data.length === 0)
    return (
      <div className="empty">
        <p>No workflows yet.</p>
        <Link to="/new" className="button primary">Submit one</Link>
      </div>
    )

  return (
    <>
      <h1>Workflows</h1>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th className="w-breakdown">Tasks</th>
              <th>Progress</th>
              <th>Created</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {data.map((wf) => (
              <tr key={wf.id}>
                <td>
                  <Link to={`/workflows/${wf.id}`}>{wf.name}</Link>
                  <div className="mono muted small">{wf.id.slice(0, 8)}</div>
                </td>
                <td><StatusBadge status={wf.status} /></td>
                <td><StatusBreakdown counts={wf.task_counts} total={wf.total_tasks} /></td>
                <td className="num">{Math.round(wf.progress)}%</td>
                <td className="muted">{timeAgo(wf.created_at)}</td>
                <td className="num">{duration(wf.started_at, wf.finished_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
