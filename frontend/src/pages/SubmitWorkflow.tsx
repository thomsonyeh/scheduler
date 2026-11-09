import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type WorkflowCreate } from '../api/client'

const exampleModules = import.meta.glob<WorkflowCreate>('../../../examples/*.json', {
  eager: true,
  import: 'default',
})
const EXAMPLES = Object.fromEntries(
  Object.entries(exampleModules).map(([path, body]) => [
    path.split('/').pop()!.replace('.json', ''),
    JSON.stringify(body, null, 2),
  ]),
)
const FIRST = Object.keys(EXAMPLES).includes('diamond') ? 'diamond' : Object.keys(EXAMPLES)[0]

export function SubmitWorkflow() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [text, setText] = useState(EXAMPLES[FIRST] ?? '{\n  "name": "",\n  "tasks": []\n}')
  const [parseError, setParseError] = useState<string | null>(null)

  const submit = useMutation({
    mutationFn: api.createWorkflow,
    onSuccess: (wf) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      navigate(`/workflows/${wf.id}`)
    },
  })

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    let body: WorkflowCreate
    try {
      body = JSON.parse(text)
    } catch (err) {
      setParseError(`Invalid JSON: ${(err as Error).message}`)
      return
    }
    setParseError(null)
    submit.mutate(body)
  }

  const errorMsg = parseError ?? submit.error?.message

  return (
    <form onSubmit={onSubmit} className="submit-form">
      <h1>New workflow</h1>
      <p className="muted">
        A workflow is a name plus a list of tasks. Each task has a <code>name</code>, a{' '}
        <code>command</code>, and <code>depends_on</code> (names of tasks that must succeed first). The mock
        batch scheduler fails any task whose command contains the word <code>fail</code>.
      </p>
      <label className="row">
        Start from example
        <select
          defaultValue={FIRST}
          onChange={(e) => {
            setText(EXAMPLES[e.target.value])
            setParseError(null)
            submit.reset()
          }}
        >
          {Object.keys(EXAMPLES).map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
      </label>
      <textarea
        className="mono"
        spellCheck={false}
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={22}
        aria-label="Workflow JSON"
      />
      {errorMsg && <pre className="error-box">{errorMsg}</pre>}
      <div className="row">
        <button type="submit" className="button primary" disabled={submit.isPending}>
          {submit.isPending ? 'Submitting…' : 'Submit workflow'}
        </button>
      </div>
    </form>
  )
}
