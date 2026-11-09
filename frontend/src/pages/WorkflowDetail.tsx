import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, api, isTerminal } from '../api/client'
import { DagView } from '../components/DagView'
import { ProgressBar, StatusBadge, StatusBreakdown } from '../components/Status'
import { TaskTable } from '../components/TaskTable'
import { duration } from '../format'

export function WorkflowDetailPage() {
  const { id = '' } = useParams()
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)

  const { data: wf, error, isPending } = useQuery({
    queryKey: ['workflow', id],
    queryFn: () => api.getWorkflow(id),
    refetchInterval: (q) => (isTerminal(q.state.data?.status) ? false : 1500),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  })

  const cancel = useMutation({
    mutationFn: () => api.cancelWorkflow(id),
    onSuccess: (data) => {
      queryClient.setQueryData(['workflow', id], data)
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })

  if (isPending) return <p className="muted">Loading…</p>
  if (error)
    return (
      <div className="empty">
        <p className="error-text">
          {error instanceof ApiError && error.status === 404 ? 'Workflow not found.' : error.message}
        </p>
        <Link to="/">Back to workflows</Link>
      </div>
    )

  return (
    <>
      <Link to="/" className="muted small">← All workflows</Link>
      <div className="detail-head">
        <div>
          <h1>
            {wf.name} <StatusBadge status={wf.status} />
          </h1>
          <div className="muted small">
            <span className="mono">{wf.id}</span> · started{' '}
            {wf.started_at ? new Date(wf.started_at).toLocaleTimeString() : '—'} · duration{' '}
            {duration(wf.started_at, wf.finished_at)}
          </div>
        </div>
        {!isTerminal(wf.status) && (
          <button className="button danger" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
            {cancel.isPending ? 'Cancelling…' : 'Cancel workflow'}
          </button>
        )}
      </div>
      {cancel.error && <p className="error-text">Cancel failed: {cancel.error.message}</p>}

      <section className="summary">
        <div className="summary-progress">
          <span className="num big">{Math.round(wf.progress)}%</span>
          <ProgressBar value={wf.progress} status={wf.status} />
        </div>
        <StatusBreakdown counts={wf.task_counts} total={wf.total_tasks} />
      </section>

      <DagView tasks={wf.tasks} selected={selected} onSelect={setSelected} />
      <TaskTable tasks={wf.tasks} selected={selected} onSelect={(n) => setSelected(n === selected ? null : n)} />
    </>
  )
}
