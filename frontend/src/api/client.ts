import type { components } from './types'

export type WorkflowSummary = components['schemas']['WorkflowSummary']
export type WorkflowDetail = components['schemas']['WorkflowDetail']
export type WorkflowCreate = components['schemas']['WorkflowCreate']
export type Task = components['schemas']['TaskOut']
export type TaskStatus = components['schemas']['TaskStatus']
export type WorkflowStatus = components['schemas']['WorkflowStatus']

export const TASK_STATUSES: TaskStatus[] = [
  'SUCCEEDED',
  'RUNNING',
  'SUBMITTED',
  'PENDING',
  'FAILED',
  'SKIPPED',
  'CANCELLED',
]

export const isTerminal = (s: WorkflowStatus | undefined) =>
  s === 'SUCCEEDED' || s === 'FAILED' || s === 'CANCELLED'

type ValidationError = components['schemas']['HTTPValidationError']

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail))
        message = (body as ValidationError).detail!
          .map((d) => `${d.loc.slice(1).join('.') || 'body'}: ${d.msg.replace(/^Value error, /, '')}`)
          .join('\n')
    } catch {
      /* keep status text */
    }
    throw new ApiError(res.status, message)
  }
  return res.json() as Promise<T>
}

export const api = {
  listWorkflows: () => request<WorkflowSummary[]>('/workflows'),
  getWorkflow: (id: string) => request<WorkflowDetail>(`/workflows/${id}`),
  createWorkflow: (body: WorkflowCreate) =>
    request<WorkflowDetail>('/workflows', { method: 'POST', body: JSON.stringify(body) }),
  cancelWorkflow: (id: string) =>
    request<WorkflowDetail>(`/workflows/${id}/cancel`, { method: 'POST' }),
}
