import { useRef, useState } from 'react'
import { Database, FileUp, Gauge, Play, RotateCcw, Shuffle, SlidersHorizontal, Wand2 } from 'lucide-react'
import { Badge, Card, Field, NumberInput, Segmented, Slider, Spinner } from './ui.jsx'

export const DEFAULT_WEIGHTS = { w_same_branch: 3, w_consecutive_roll: 2, w_distance_two_conflict: 1, w_wasted_seat: 0.5 }

// UI wording for the four real backend weights (config/default_config.json).
const WEIGHT_UI = [
  { key: 'w_same_branch', label: 'Department separation', hint: 'Penalty per neighbouring pair from the same branch.' },
  { key: 'w_consecutive_roll', label: 'Roll-number separation', hint: 'Extra penalty when same-branch neighbours have consecutive roll numbers.' },
  { key: 'w_distance_two_conflict', label: 'Buffer distance (course overlap)', hint: 'Penalty when two students sharing a course sit two seats apart.' },
  { key: 'w_wasted_seat', label: 'Wasted seats', hint: 'Penalty per empty seat that separates nobody.' },
]

export default function Sidebar({ algorithms, dataset, busy, gen, setGen, onGenerate, onSample, onUpload, opts, setOpts, onRun }) {
  const [tab, setTab] = useState('generate')
  const studentsRef = useRef(null)
  const hallsRef = useRef(null)
  const jsonRef = useRef(null)
  const chosen = algorithms?.available.find((a) => a.id === opts.algorithm)

  const submitUpload = () => {
    const json = jsonRef.current?.files?.[0]
    const s = studentsRef.current?.files?.[0]
    const h = hallsRef.current?.files?.[0]
    if (json) return onUpload({ json })
    if (s && h) return onUpload({ students: s, halls: h })
    onUpload({ error: 'Choose either a JSON file, or both a students CSV and a halls CSV.' })
  }

  return (
    <aside className="flex flex-col gap-4 lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto lg:p-4 lg:pr-2">
      <Card title="Dataset" icon={Database}>
        <Segmented size="sm" value={tab} onChange={setTab} options={[{ value: 'generate', label: 'Generate' }, { value: 'upload', label: 'Upload' }]} />
        {tab === 'generate' ? (
          <div className="mt-3 grid grid-cols-2 gap-3">
            <Field label="Students"><NumberInput value={gen.n_students} min={1} max={2000} onChange={(v) => setGen({ ...gen, n_students: v })} /></Field>
            <Field label="Halls"><NumberInput value={gen.n_halls} min={1} max={50} onChange={(v) => setGen({ ...gen, n_halls: v })} /></Field>
            <Field label="Courses" hint="Fewer courses = denser conflicts.">
              <NumberInput value={gen.n_courses} min={1} max={500} onChange={(v) => setGen({ ...gen, n_courses: v })} />
            </Field>
            <Field label="Seed"><NumberInput value={gen.seed} min={0} onChange={(v) => setGen({ ...gen, seed: v })} /></Field>
            <button className="btn-ghost col-span-2" onClick={onGenerate} disabled={busy}><Shuffle className="h-4 w-4" /> Generate dataset</button>
          </div>
        ) : (
          <div className="mt-3 space-y-2.5 text-xs">
            <Field label="students.csv"><input ref={studentsRef} type="file" accept=".csv" className="field !p-1" /></Field>
            <Field label="halls.csv"><input ref={hallsRef} type="file" accept=".csv" className="field !p-1" /></Field>
            <p className="text-center text-slate-400">or</p>
            <Field label="dataset.json" hint='{"students": [...], "halls": [...]}'><input ref={jsonRef} type="file" accept=".json" className="field !p-1" /></Field>
            <button className="btn-ghost w-full" onClick={submitUpload} disabled={busy}><FileUp className="h-4 w-4" /> Upload</button>
          </div>
        )}
        <button className="mt-2 w-full text-xs font-medium text-indigo-600 hover:underline" onClick={onSample} disabled={busy}>Load bundled sample data</button>
        {dataset && (
          <div className="mt-3 rounded-lg bg-slate-50 p-2.5 text-xs text-slate-600">
            <div className="font-semibold text-slate-800">{dataset.source}</div>
            {dataset.n_students} students · {dataset.n_halls} halls · {dataset.total_capacity} seats
            <div className="mt-1 flex flex-wrap gap-1">
              <Badge tone="indigo" title="edges / possible edges in the conflict graph">density {dataset.density.toFixed(2)}</Badge>
              <Badge>{dataset.n_distinct_courses} courses</Badge>
              <Badge>{dataset.branches.length} depts</Badge>
            </div>
            {dataset.capacity_warning && <p className="mt-1.5 text-rose-600">{dataset.capacity_warning}</p>}
          </div>
        )}
      </Card>

      <Card title="Algorithm" icon={Gauge}>
        <Field label="Graph-coloring algorithm">
          <select className="field" value={opts.algorithm} onChange={(e) => setOpts({ ...opts, algorithm: e.target.value })}>
            {algorithms?.available.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            {algorithms?.unavailable.map((u) => <option key={u.id} value={u.id} disabled>{u.id.toUpperCase()} (not in backend)</option>)}
          </select>
        </Field>
        {chosen && <p className="mt-2 text-[11px] leading-snug text-slate-500">{chosen.description}</p>}
        <div className="mt-3">
          <span className="mb-1 block text-xs font-medium text-slate-600">Seat neighbourhood</span>
          <Segmented size="sm" value={opts.neighbourhood} onChange={(v) => setOpts({ ...opts, neighbourhood: v })}
            options={[{ value: '4', label: '4-way' }, { value: '8', label: '8-way (diagonals)' }]} />
        </div>
        {opts.algorithm === 'backtracking' && (
          <div className="mt-3 grid grid-cols-2 gap-3">
            <Field label="Node limit"><NumberInput value={opts.backtracking_node_limit} min={1} max={2000000} step={10000} onChange={(v) => setOpts({ ...opts, backtracking_node_limit: v })} /></Field>
            <Field label="Time limit (s)"><NumberInput value={opts.backtracking_time_limit_seconds} min={0.1} max={30} step={1} onChange={(v) => setOpts({ ...opts, backtracking_time_limit_seconds: v })} /></Field>
          </div>
        )}
      </Card>

      <Card title="Soft-constraint weights" icon={SlidersHorizontal}
        action={<button className="text-xs text-slate-500 hover:text-indigo-600" onClick={() => setOpts({ ...opts, weights: { ...DEFAULT_WEIGHTS } })}><RotateCcw className="mr-1 inline h-3 w-3" />Reset</button>}>
        <div className="space-y-4">
          {WEIGHT_UI.map((w) => (
            <Slider key={w.key} label={w.label} hint={w.hint} value={opts.weights[w.key]}
              onChange={(v) => setOpts({ ...opts, weights: { ...opts.weights, [w.key]: v } })} />
          ))}
        </div>
      </Card>

      <div className="sticky bottom-0 -mx-1 bg-gradient-to-t from-slate-100 via-slate-100 to-transparent px-1 pb-2 pt-3">
        <button className="btn-primary w-full py-2.5" onClick={onRun} disabled={busy || !dataset}>
          {busy === 'allocate' ? <Spinner label="Allocating…" /> : <><Play className="h-4 w-4" /> Run allocation</>}
        </button>
        {!dataset && <p className="mt-1.5 flex items-center justify-center gap-1 text-[11px] text-slate-500"><Wand2 className="h-3 w-3" /> Generate or load a dataset first</p>}
      </div>
    </aside>
  )
}
