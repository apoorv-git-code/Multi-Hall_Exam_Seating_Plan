import { useState } from 'react'
import { Download, FileCode2, FileSpreadsheet, FileText, Image } from 'lucide-react'
import { Card, Spinner } from './ui.jsx'

export default function ExportHub({ hasAllocation, benchmark, onDownload }) {
  const [plot, setPlot] = useState('')
  const [busy, setBusy] = useState('')
  const go = async (key, format, p) => { setBusy(key); try { await onDownload(format, p) } finally { setBusy('') } }
  const plots = benchmark?.plots ?? []

  const items = [
    { key: 'csv', icon: FileSpreadsheet, title: 'CSV seat manifest', text: 'One row per student: SAP ID, hall, row, column, color class.', format: 'csv', ok: hasAllocation, why: 'Run an allocation first' },
    { key: 'html', icon: FileCode2, title: 'Standalone HTML seating cards', text: 'Printable per-hall seating grids and seat lists. Opens in any browser.', format: 'html', ok: hasAllocation, why: 'Run an allocation first' },
    { key: 'md', icon: FileText, title: 'Markdown summary report', text: 'Dataset, conflict-graph metrics, coloring run and allocation quality.', format: 'md', ok: hasAllocation, why: 'Run an allocation first' },
  ]

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map(({ key, icon: Icon, title, text, format, ok, why }) => (
          <Card key={key}>
            <Icon className="h-8 w-8 text-indigo-600" aria-hidden />
            <h3 className="mt-3 font-semibold text-slate-900">{title}</h3>
            <p className="mt-1 min-h-[2.5rem] text-sm text-slate-600">{text}</p>
            <button className="btn-primary mt-4 w-full" disabled={!ok || busy === key} onClick={() => go(key, format)}>
              {busy === key ? <Spinner label="Preparing…" /> : <><Download className="h-4 w-4" />{ok ? `Download .${format}` : why}</>}
            </button>
          </Card>
        ))}
        <Card>
          <Image className="h-8 w-8 text-indigo-600" aria-hidden />
          <h3 className="mt-3 font-semibold text-slate-900">SVG benchmark plots</h3>
          <p className="mt-1 text-sm text-slate-600">Hand-written SVG charts from the reporting module.</p>
          <select className="field mt-3" value={plot} onChange={(e) => setPlot(e.target.value)} disabled={!plots.length} aria-label="Plot to export">
            {plots.length === 0 && <option>—</option>}
            {plots.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <button className="btn-primary mt-3 w-full" disabled={!plots.length || busy === 'svg'} onClick={() => go('svg', 'svg', plot || plots[0])}>
            {busy === 'svg' ? <Spinner label="Preparing…" /> : <><Download className="h-4 w-4" />{plots.length ? 'Download .svg' : 'Run a benchmark first'}</>}
          </button>
        </Card>
      </div>
      <p className="text-xs text-slate-500">Files are produced by <code>src/reporting/</code> from the latest successful allocation or benchmark.</p>
    </div>
  )
}
