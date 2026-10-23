import { useCallback, useEffect, useState } from 'react'
import { BarChart3, Download, GraduationCap, LayoutGrid, Trash2, TriangleAlert } from 'lucide-react'
import { api, downloadExport } from './api.js'
import Sidebar, { DEFAULT_WEIGHTS } from './components/Sidebar.jsx'
import FloorPlan from './components/FloorPlan.jsx'
import { Breakdown, BenchmarkPanel, ColorClasses, KpiRow } from './components/Analytics.jsx'
import ExportHub from './components/ExportHub.jsx'
import { Badge, Card, Toast } from './components/ui.jsx'

const TABS = [
  { id: 'plan', label: 'Floor plan', icon: LayoutGrid },
  { id: 'analytics', label: 'Analytics & benchmark', icon: BarChart3 },
  { id: 'export', label: 'Export hub', icon: Download },
]

export default function App() {
  const [algorithms, setAlgorithms] = useState(null)
  const [dataset, setDataset] = useState(null)
  const [allocation, setAllocation] = useState(null)
  const [benchmark, setBenchmark] = useState(null)
  const [tab, setTab] = useState('plan')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [gen, setGen] = useState({ n_students: 100, n_halls: 2, n_courses: 40, seed: 42 })
  const [opts, setOpts] = useState({
    algorithm: 'welsh_powell', neighbourhood: '4', weights: { ...DEFAULT_WEIGHTS },
    backtracking_node_limit: 200000, backtracking_time_limit_seconds: 10,
  })

  // Run an async action with a busy flag and one consistent error path.
  const guard = useCallback(async (name, fn) => {
    setBusy(name); setError('')
    try { return await fn() } catch (e) {
      setError(e.message)
      // The server forgot our data (idle session expired or was reset): drop the stale screens too.
      if (e.message.startsWith('No dataset loaded')) { setDataset(null); setAllocation(null); setBenchmark(null) }
      return undefined
    } finally { setBusy('') }
  }, [])

  useEffect(() => {
    api.algorithms().then(setAlgorithms).catch((e) => setError(e.message))
    // Restore the server-side dataset after a page reload (only if one exists, so no 409 noise).
    api.health().then((h) => (h.dataset_loaded ? api.currentDataset().then(setDataset) : null)).catch(() => {})
  }, [])

  const useDataset = (d) => { setDataset(d); setAllocation(null) }
  const generate = () => guard('data', async () => useDataset(await api.generate(gen)))
  const sample = () => guard('data', async () => useDataset(await api.sample()))
  const upload = ({ json, students, halls, error: msg }) => {
    if (msg) return setError(msg)
    return guard('data', async () => useDataset(json ? await api.loadJson(JSON.parse(await json.text())) : await api.upload(students, halls)))
  }

  const run = () => guard('allocate', async () => {
    const result = await api.allocate({
      algorithm: opts.algorithm, neighbourhood: opts.neighbourhood, weights: opts.weights,
      backtracking_node_limit: opts.backtracking_node_limit, backtracking_time_limit_seconds: opts.backtracking_time_limit_seconds,
    })
    setAllocation(result)
  })

  const runBenchmark = (params) => guard('benchmark', async () => setBenchmark(await api.benchmark(params)))
  const resetSession = () => {
    if (!window.confirm('Remove your dataset, allocation and benchmark from the server?')) return
    guard('reset', async () => { await api.resetSession(); setDataset(null); setAllocation(null); setBenchmark(null) })
  }
  const download = (format, plot) => guard('export', () => downloadExport(format, plot))

  const ok = allocation?.status === 'ok'

  return (
    <div className="mx-auto grid max-w-[1500px] gap-4 p-3 lg:grid-cols-[330px_1fr] lg:p-0 lg:pr-4">
      <Sidebar algorithms={algorithms} dataset={dataset} busy={busy} gen={gen} setGen={setGen} onGenerate={generate}
        onSample={sample} onUpload={upload} opts={opts} setOpts={setOpts} onRun={run} />

      <main className="min-w-0 space-y-4 lg:py-4">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="rounded-xl bg-indigo-600 p-2.5 text-white shadow-sm"><GraduationCap className="h-6 w-6" aria-hidden /></span>
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">Multi-Hall Exam Seating</h1>
              <p className="text-xs text-slate-500">Graph coloring + grid placement · visual showcase of the allocation engine</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {allocation && (
              <>
                <Badge tone="indigo">{allocation.algorithm.label}</Badge>
                <Badge tone={ok ? 'green' : 'red'}>{ok ? 'allocation valid' : 'infeasible'}</Badge>
              </>
            )}
            {dataset && (
              <button className="btn-ghost !px-2.5 !py-1 text-xs" onClick={resetSession} disabled={!!busy} title="Delete my data from the server">
                <Trash2 className="h-3.5 w-3.5" aria-hidden /> Reset my data
              </button>
            )}
          </div>
        </header>

        <nav className="flex gap-1 border-b border-slate-200" role="tablist">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
              className={`-mb-px flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition ${tab === id ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
              <Icon className="h-4 w-4" aria-hidden />{label}
            </button>
          ))}
        </nav>

        {tab === 'plan' && (
          ok ? <FloorPlan data={allocation} />
            : allocation ? <Infeasible data={allocation} />
              : <EmptyState hasDataset={!!dataset} busy={busy} />
        )}

        {tab === 'analytics' && (
          <div className="space-y-4">
            {ok ? (
              <>
                <KpiRow data={allocation} />
                <div className="grid gap-4 xl:grid-cols-2"><Breakdown data={allocation} /><ColorClasses data={allocation} /></div>
              </>
            ) : allocation ? <Infeasible data={allocation} /> : <EmptyState hasDataset={!!dataset} busy={busy} compact />}
            <BenchmarkPanel algorithms={algorithms} result={benchmark} busy={busy} onRun={runBenchmark} engine={opts} />
          </div>
        )}

        {tab === 'export' && <ExportHub hasAllocation={ok} benchmark={benchmark} onDownload={download} />}
      </main>

      <Toast message={error} onClose={() => setError('')} />
    </div>
  )
}

function EmptyState({ hasDataset, busy, compact }) {
  return (
    <Card className={compact ? '' : 'py-8'}>
      <div className="mx-auto max-w-md text-center">
        <LayoutGrid className="mx-auto h-10 w-10 text-indigo-300" aria-hidden />
        <h2 className="mt-3 text-lg font-semibold text-slate-900">{hasDataset ? 'Ready to allocate' : 'Start with a dataset'}</h2>
        <p className="mt-1 text-sm text-slate-600">
          {busy === 'allocate' ? 'Allocating seats…'
            : hasDataset ? 'Pick an algorithm and weights in the sidebar, then press “Run allocation”.'
              : 'Generate a seeded dataset, upload your own CSV/JSON, or load the bundled sample from the sidebar.'}
        </p>
      </div>
    </Card>
  )
}

function Infeasible({ data }) {
  const m = data.metrics
  return (
    <Card className="border-rose-200">
      <div className="flex gap-3">
        <TriangleAlert className="h-6 w-6 shrink-0 text-rose-500" aria-hidden />
        <div className="text-sm">
          <h2 className="font-semibold text-slate-900">This algorithm could not seat everyone</h2>
          <p className="mt-1 text-slate-600">{data.message}</p>
          <p className="mt-2 text-slate-600">Phase 1 coloring still finished: <strong>{m.colors_used} colors</strong> in {m.coloring_runtime_ms} ms
            (density {m.density}, {m.n_edges} conflict edges). Dense conflict graphs need many buffer seats. Try a different
            algorithm, add halls, or use more courses.</p>
        </div>
      </div>
    </Card>
  )
}
