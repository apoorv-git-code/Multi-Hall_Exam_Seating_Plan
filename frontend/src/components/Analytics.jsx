import { useState } from 'react'
import { Activity, BarChart3, Clock, Cpu, Gauge, Hash, Info, Percent, Timer, TriangleAlert } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { classColor } from '../lib/palette.js'
import { Badge, Card, Field, NumberInput, Segmented, Spinner } from './ui.jsx'

const ALGO_COLORS = { greedy: '#d62728', welsh_powell: '#1f77b4', backtracking: '#2ca02c' }
const fmt = (v, d = 2) => (v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d }))

function Kpi({ icon: Icon, label, value, unit, sub, tone = 'indigo' }) {
  const tones = { indigo: 'bg-indigo-50 text-indigo-600', emerald: 'bg-emerald-50 text-emerald-600', amber: 'bg-amber-50 text-amber-600', violet: 'bg-violet-50 text-violet-600' }
  return (
    <div className="rounded-xl bg-white p-4 shadow-card ring-1 ring-slate-200/70">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
        <span className={`rounded-lg p-1.5 ${tones[tone]}`}><Icon className="h-4 w-4" aria-hidden /></span>
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-3xl font-semibold tabular-nums text-slate-900">{value}</span>
        {unit && <span className="text-sm text-slate-500">{unit}</span>}
      </div>
      {sub && <p className="mt-1 text-xs leading-snug text-slate-500">{sub}</p>}
    </div>
  )
}

export function KpiRow({ data }) {
  const m = data.metrics
  const chi = m.chromatic_number != null ? `χ(G) = ${m.colors_used}${m.search_completed && data.algorithm.id === 'backtracking' ? ' — proven optimal by exhaustive search' : ' — matches the clique lower bound'}`
    : `Upper bound. χ(G) ≥ ${m.chromatic_lower_bound} (largest course). Only exact when proven.`
  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <Kpi icon={Percent} tone="emerald" label="Capacity utilisation" value={fmt(m.capacity_utilisation_pct, 1)} unit="%" sub={`${m.seated} of ${m.total_students} students seated across ${m.used_halls ?? 0} hall(s)`} />
      <Kpi icon={Hash} tone="indigo" label={m.chromatic_number != null ? 'Chromatic number χ(G)' : 'Colors used (χ upper bound)'} value={m.colors_used} sub={chi} />
      <Kpi icon={Timer} tone="violet" label="Coloring runtime" value={fmt(m.coloring_runtime_ms, 3)} unit="ms" sub={`Whole pipeline ${fmt(m.pipeline_runtime_ms, 1)} ms incl. graph + seat mapping${m.nodes_explored ? ` · ${m.nodes_explored.toLocaleString()} search nodes` : ''}`} />
      <Kpi icon={Activity} tone="amber" label="Soft penalty score" value={fmt(m.soft_score, 2)} sub={`Lower is better · ${m.buffer_seats ?? 0} buffer, ${m.wasted_seats ?? 0} wasted seats`} />
    </div>
  )
}

export function Breakdown({ data }) {
  const s = data.soft
  const items = [
    { name: 'Same department', value: s.contributions.same_branch, count: s.counts.same_branch_pairs, color: '#6366f1' },
    { name: 'Consecutive rolls', value: s.contributions.consecutive_roll, count: s.counts.consecutive_roll_pairs, color: '#8b5cf6' },
    { name: 'Course overlap @ 2 seats', value: s.contributions.distance_two_conflict, count: s.counts.distance_two_pairs, color: '#f59e0b' },
    { name: 'Wasted seats', value: s.contributions.wasted_seat, count: s.counts.wasted_seats, color: '#94a3b8' },
  ]
  return (
    <Card title="Soft-constraint violation breakdown" icon={BarChart3}
      action={<Badge tone={s.heat_reconciles ? 'green' : 'red'} title="Per-seat heatmap values sum exactly to the backend score">{s.heat_reconciles ? 'heatmap reconciles with score' : 'heatmap mismatch'}</Badge>}>
      <div className="h-56">
        <ResponsiveContainer>
          <BarChart data={items} layout="vertical" margin={{ left: 24, right: 24 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v, _n, p) => [`${v} (${p.payload.count} × weight)`, 'Weighted penalty']} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>{items.map((i) => <Cell key={i.name} fill={i.color} />)}</Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-500">Total {fmt(s.total, 2)} = Σ weight × count. Neighbour pairs use the {data.neighbourhood}-way neighbourhood.</p>
    </Card>
  )
}

export function ColorClasses({ data }) {
  const rows = data.color_classes.map((c) => ({ name: `#${c.color + 1}`, count: c.count, color: c.color }))
  return (
    <Card title="Color-class sizes" icon={Gauge}>
      <div className="h-56">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ right: 12 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => [v, 'students']} />
            <Bar dataKey="count" radius={[3, 3, 0, 0]}>{rows.map((r) => <Cell key={r.name} fill={classColor(r.color)} />)}</Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-500">Students in one class share no course, so a class may sit anywhere together.</p>
    </Card>
  )
}

export function BenchmarkPanel({ algorithms, result, busy, onRun, engine }) {
  const [p, setP] = useState({ mode: 'density', n_students: 100, courses: '80, 40, 25, 15', sizes: '50, 100, 200', n_courses: 40, repeats: 1, algos: ['greedy', 'welsh_powell', 'backtracking'] })
  const [log, setLog] = useState(true)
  const nums = (t) => t.split(/[ ,]+/).filter(Boolean).map(Number)
  const toggle = (id) => setP({ ...p, algos: p.algos.includes(id) ? p.algos.filter((a) => a !== id) : [...p.algos, id] })
  const run = () => onRun({
    mode: p.mode, algorithms: p.algos, n_students: p.n_students, course_counts: nums(p.courses), sizes: nums(p.sizes),
    n_courses: p.n_courses, repeats: p.repeats, neighbourhood: engine.neighbourhood, weights: engine.weights,
  })

  const xs = result ? [...new Set(result.rows.map((r) => r[result.x_key]))].sort((a, b) => a - b) : []
  const merged = (yKey) => xs.map((x) => {
    const point = { x }
    for (const r of result.rows) if (r[result.x_key] === x) point[r.algorithm] = yKey === 'runtime_ms' ? Math.max(r[yKey], 0.001) : r[yKey]
    return point
  })
  const labels = Object.fromEntries((algorithms?.available ?? []).map((a) => [a.id, a.label]))
  const used = result ? [...new Set(result.rows.map((r) => r.algorithm))] : []

  return (
    <Card title="Algorithm benchmark" icon={Cpu}>
      <div className="grid gap-3 md:grid-cols-4">
        <Field label="Experiment">
          <Segmented size="sm" value={p.mode} onChange={(mode) => setP({ ...p, mode })} options={[{ value: 'density', label: 'vs density' }, { value: 'size', label: 'vs size' }]} />
        </Field>
        {p.mode === 'density' ? (
          <>
            <Field label="Students (fixed)"><NumberInput value={p.n_students} min={10} max={1000} onChange={(v) => setP({ ...p, n_students: v })} /></Field>
            <Field label="Course counts" hint="One dataset each. Fewer courses = denser graph."><input className="field" value={p.courses} onChange={(e) => setP({ ...p, courses: e.target.value })} /></Field>
          </>
        ) : (
          <>
            <Field label="Student counts"><input className="field" value={p.sizes} onChange={(e) => setP({ ...p, sizes: e.target.value })} /></Field>
            <Field label="Courses"><NumberInput value={p.n_courses} min={2} max={500} onChange={(v) => setP({ ...p, n_courses: v })} /></Field>
          </>
        )}
        <Field label="Repeats (timing mean)"><NumberInput value={p.repeats} min={1} max={5} onChange={(v) => setP({ ...p, repeats: v })} /></Field>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        {(algorithms?.available ?? []).map((a) => (
          <label key={a.id} className="flex items-center gap-1.5 text-sm text-slate-700">
            <input type="checkbox" className="accent-indigo-600" checked={p.algos.includes(a.id)} onChange={() => toggle(a.id)} />{a.label}
          </label>
        ))}
        <button className="btn-primary ml-auto" onClick={run} disabled={busy || p.algos.length === 0}>
          {busy === 'benchmark' ? <Spinner label="Benchmarking…" /> : <><Clock className="h-4 w-4" /> Run benchmark</>}
        </button>
      </div>

      {result && (
        <div className="mt-5 space-y-5">
          {result.truncated && <p className="flex items-center gap-2 rounded-lg bg-amber-50 p-2.5 text-xs text-amber-800"><TriangleAlert className="h-4 w-4" />Time budget reached: only part of the experiment was run.</p>}
          <div className="grid gap-5 xl:grid-cols-2">
            <div>
              <div className="mb-1 flex items-center justify-between">
                <h4 className="text-sm font-semibold text-slate-700">Execution time vs {result.x_label.toLowerCase()}</h4>
                <label className="flex items-center gap-1.5 text-xs text-slate-600"><input type="checkbox" className="accent-indigo-600" checked={log} onChange={(e) => setLog(e.target.checked)} />log scale</label>
              </div>
              <div className="h-72">
                <ResponsiveContainer>
                  <LineChart data={merged('runtime_ms')} margin={{ left: 4, right: 16, top: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="x" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(v) => Number(Number(v).toFixed(2))} tick={{ fontSize: 11 }} label={{ value: result.x_label, position: 'insideBottom', offset: -4, fontSize: 11 }} height={48} />
                    <YAxis scale={log ? 'log' : 'linear'} domain={log ? [0.001, 'auto'] : [0, 'auto']} allowDataOverflow tick={{ fontSize: 11 }} width={52} label={{ value: 'ms', angle: -90, position: 'insideLeft', fontSize: 11 }} />
                    <Tooltip formatter={(v, name) => [`${fmt(v, 3)} ms`, labels[name] ?? name]} labelFormatter={(x) => `${result.x_label}: ${x}`} />
                    <Legend verticalAlign="top" formatter={(n) => labels[n] ?? n} wrapperStyle={{ fontSize: 12 }} />
                    {used.map((a) => <Line key={a} type="monotone" dataKey={a} stroke={ALGO_COLORS[a]} strokeWidth={2} dot={{ r: 4 }} connectNulls />)}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div>
              <h4 className="mb-1 text-sm font-semibold text-slate-700">Colors used vs {result.x_label.toLowerCase()}</h4>
              <div className="h-72">
                <ResponsiveContainer>
                  <LineChart data={merged('colors_used')} margin={{ left: 4, right: 16, top: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="x" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(v) => Number(Number(v).toFixed(2))} tick={{ fontSize: 11 }} height={48} label={{ value: result.x_label, position: 'insideBottom', offset: -4, fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} width={40} allowDecimals={false} />
                    <Tooltip formatter={(v, name) => [v, labels[name] ?? name]} labelFormatter={(x) => `${result.x_label}: ${x}`} />
                    <Legend verticalAlign="top" formatter={(n) => labels[n] ?? n} wrapperStyle={{ fontSize: 12 }} />
                    {used.map((a) => <Line key={a} type="monotone" dataKey={a} stroke={ALGO_COLORS[a]} strokeWidth={2} dot={{ r: 4 }} connectNulls />)}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600">
                <tr>{[result.mode === 'density' ? 'Density' : 'Students', 'Algorithm', 'Colors', 'Runtime ms', 'Nodes', 'Search done', 'Seated?', 'Soft score'].map((h) => <th key={h} className="px-3 py-2 font-semibold">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {result.rows.map((r, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-3 py-1.5 tabular-nums">{r[result.x_key]}</td>
                    <td className="px-3 py-1.5">{labels[r.algorithm] ?? r.algorithm}</td>
                    <td className="px-3 py-1.5 tabular-nums">{r.colors_used}</td>
                    <td className="px-3 py-1.5 tabular-nums">{fmt(r.runtime_ms, 3)}</td>
                    <td className="px-3 py-1.5 tabular-nums">{r.nodes_explored}</td>
                    <td className="px-3 py-1.5">{r.completed ? 'yes' : 'limit hit'}</td>
                    <td className="px-3 py-1.5">{r.valid ? <Badge tone="green">valid</Badge> : <Badge tone="red" title="Phase 2 could not seat everyone">infeasible</Badge>}</td>
                    <td className="px-3 py-1.5 tabular-nums">{fmt(r.soft_score, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="flex items-start gap-2 text-xs text-slate-500"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />{result.note} Finished in {result.elapsed_seconds}s.</p>
        </div>
      )}
    </Card>
  )
}
