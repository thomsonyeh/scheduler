import dagre from '@dagrejs/dagre'
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useMemo } from 'react'
import type { Task } from '../api/client'
import { duration } from '../format'
import { ProgressBar } from './Status'

const NODE_W = 210
const NODE_H = 76

type TaskNodeData = { task: Task; selected: boolean }
type TaskNodeType = Node<TaskNodeData, 'task'>

function TaskNode({ data: { task, selected } }: NodeProps<TaskNodeType>) {
  return (
    <div className={`dag-node s-${task.status}${selected ? ' selected' : ''}`} title={task.error ?? task.command}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className="dag-node-head">
        <span className="mono dag-node-name">{task.name}</span>
        <span className="num muted small">{duration(task.started_at, task.finished_at)}</span>
      </div>
      <div className="dag-node-status small">
        <i className={`dot s-${task.status}`} /> {task.status.toLowerCase()}
        <span className="num muted">{Math.round(task.progress)}%</span>
      </div>
      <ProgressBar value={task.progress} status={task.status} />
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  )
}

const nodeTypes = { task: TaskNode }

/** Positions depend only on graph shape, so nodes don't move as statuses change. */
function layout(tasks: Task[]): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 28, ranksep: 72 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const t of tasks) g.setNode(t.name, { width: NODE_W, height: NODE_H })
  for (const t of tasks) for (const dep of t.depends_on) g.setEdge(dep, t.name)
  dagre.layout(g)
  return new Map(
    tasks.map((t) => {
      const n = g.node(t.name)
      return [t.name, { x: n.x - NODE_W / 2, y: n.y - NODE_H / 2 }]
    }),
  )
}

export function DagView({ tasks, selected, onSelect }: {
  tasks: Task[]
  selected: string | null
  onSelect: (name: string | null) => void
}) {
  const shapeKey = tasks.map((t) => `${t.name}<${t.depends_on.join(',')}`).join('|')
  // Re-layout only when the graph shape changes, not on every status poll.
  // oxlint-disable-next-line react-hooks/exhaustive-deps
  const positions = useMemo(() => layout(tasks), [shapeKey])

  const byName = new Map(tasks.map((t) => [t.name, t]))
  const nodes: TaskNodeType[] = tasks.map((t) => ({
    id: t.name,
    type: 'task',
    position: positions.get(t.name) ?? { x: 0, y: 0 },
    data: { task: t, selected: t.name === selected },
    draggable: false,
    width: NODE_W,
    height: NODE_H,
  }))
  const edges: Edge[] = tasks.flatMap((t) =>
    t.depends_on.map((dep) => {
      const done = byName.get(dep)?.status === 'SUCCEEDED'
      const active = t.status === 'RUNNING' || t.status === 'SUBMITTED'
      return {
        id: `${dep}->${t.name}`,
        source: dep,
        target: t.name,
        animated: active,
        className: done ? 'edge-done' : 'edge-waiting',
      }
    }),
  )

  return (
    <div className="dag">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.2}
        nodesConnectable={false}
        colorMode="system"
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, n) => onSelect(n.id === selected ? null : n.id)}
        onPaneClick={() => onSelect(null)}
      >
        <Background gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
