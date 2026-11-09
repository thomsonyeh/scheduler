import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import './index.css'
import { SubmitWorkflow } from './pages/SubmitWorkflow'
import { WorkflowDetailPage } from './pages/WorkflowDetail'
import { WorkflowList } from './pages/WorkflowList'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <header className="topbar">
          <Link to="/" className="brand">Workflow Scheduler</Link>
          <Link to="/new" className="button primary">New workflow</Link>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<WorkflowList />} />
            <Route path="/new" element={<SubmitWorkflow />} />
            <Route path="/workflows/:id" element={<WorkflowDetailPage />} />
          </Routes>
        </main>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
