import { useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Flame, Layers, Palette, Search } from 'lucide-react'
import { branchColors, classColor, heatColor, textOn } from '../lib/palette.js'
import { adjacentConflicts, seatIndex } from '../lib/verify.js'
import { Badge, Card, Segmented } from './ui.jsx'
import SeatModal from './SeatModal.jsx'

const MODES = [
  { value: 'dept', label: 'Department' },
  { value: 'class', label: 'Color class' },
  { value: 'course', label: 'Course' },
  { value: 'heat', label: 'Heatmap' },
]

export default function FloorPlan({ data }) {
  const [hallId, setHallId] = useState(data.halls.find((h) => h.seated > 0)?.hall_id ?? data.halls[0].hall_id)
  const [mode, setMode] = useState('dept')
  const [course, setCourse] = useState('')
  const [hover, setHover] = useState(null)
  const [selected, setSelected] = useState(null)

  const hall = data.halls.find((h) => h.hall_id === hallId) ?? data.halls[0]
  const nb = data.neighbourhood
  const deptColors = useMemo(() => branchColors(new Set(data.seats.map((s) => s.branch))), [data])
  const index = useMemo(() => seatIndex(data.seats), [data])
  const courses = useMemo(() => [...new Set(data.seats.flatMap((s) => s.courses))].sort(), [data])
  const activeCourse = course || courses[0] || ''
  const empties = useMemo(() => {
    const m = new Map()
    for (const e of data.empty_seats) m.set(`${e.hall_id}|${e.row}|${e.col}`, e)
    return m
  }, [data])
  const blocked = useMemo(() => new Set(hall.blocked.map(([r, c]) => `${r}|${c}`)), [hall])
  const heatMax = Math.max(data.soft?.heat_max ?? 0, 1e-9)

  const verdict = useMemo(() => adjacentConflicts(data.seats, nb), [data, nb])
  const courseVerdict = useMemo(
    () => (mode === 'course' ? adjacentConflicts(data.seats, nb, activeCourse) : null), [data, nb, mode, activeCourse])
  const enrolled = mode === 'course' ? data.seats.filter((s) => s.courses.includes(activeCourse)).length : 0

  const paint = (seat) => {
    let bg, label
    if (mode === 'dept') { bg = deptColors[seat.branch]; label = seat.roll_no }
    else if (mode === 'class') { bg = classColor(seat.color); label = seat.color + 1 }
    else if (mode === 'course') {
      const on = seat.courses.includes(activeCourse)
      bg = on ? '#4f46e5' : '#e2e8f0'; label = on ? '●' : ''
    } else { bg = heatColor(seat.penalty / heatMax); label = seat.penalty > 0 ? Math.round(seat.penalty * 10) / 10 : '' }
    return { bg, label, fg: textOn(bg) }
  }

  const showTip = (e, seat) => setHover({ seat, rect: e.currentTarget.getBoundingClientRect() })

  return (
    <div className="space-y-4">
      <ConflictBanner data={data} verdict={verdict} nb={nb} />

      <Card title="Floor plan" icon={Layers}
        action={<Segmented size="sm" value={mode} onChange={setMode} options={MODES} />}>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {data.halls.map((h) => (
            <button key={h.hall_id} onClick={() => setHallId(h.hall_id)} disabled={h.seated === 0}
              className={`rounded-lg border px-3 py-1.5 text-left text-xs transition disabled:opacity-40 ${h.hall_id === hall.hall_id ? 'border-indigo-500 bg-indigo-50 text-indigo-800' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'}`}>
              <span className="font-semibold">{h.hall_id}</span>
              <span className="ml-2 text-slate-500">{h.seated}/{h.capacity} seats · {h.rows}×{h.cols}</span>
            </button>
          ))}
        </div>

        {mode === 'course' && (
          <div className="mb-3 flex flex-wrap items-center gap-3 rounded-lg bg-indigo-50 p-2.5 text-xs text-indigo-900">
            <Search className="h-4 w-4" aria-hidden />
            <label className="flex items-center gap-2">Highlight course
              <select className="field !w-auto !py-1" value={activeCourse} onChange={(e) => setCourse(e.target.value)}>
                {courses.map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <span>{enrolled} students enrolled →{' '}
              <strong className={courseVerdict.conflicts.length ? 'text-rose-700' : 'text-emerald-700'}>
                {courseVerdict.conflicts.length} adjacent pairs
              </strong>
              {courseVerdict.conflicts.length === 0 && ' (no two sit next to each other)'}
            </span>
          </div>
        )}

        <div className="overflow-x-auto pb-1">
          <div className="mx-auto w-fit min-w-full">
            <div className="mx-auto mb-2 w-2/3 rounded-b-xl bg-slate-800 py-1 text-center text-[11px] font-semibold uppercase tracking-[0.25em] text-white">Front of hall</div>
            <div className="grid gap-1" style={{ gridTemplateColumns: `1.5rem repeat(${hall.cols}, minmax(2.1rem, 3.1rem))`, justifyContent: 'center' }}>
              <span />
              {Array.from({ length: hall.cols }, (_, c) => <span key={c} className="text-center text-[10px] text-slate-400">{c + 1}</span>)}
              {Array.from({ length: hall.rows }, (_, r) => (
                <Row key={r} r={r} hall={hall} index={index} empties={empties} blocked={blocked} paint={paint} mode={mode}
                  onHover={showTip} onLeave={() => setHover(null)} onPick={setSelected} />
              ))}
            </div>
          </div>
        </div>

        <Legend mode={mode} deptColors={deptColors} classes={data.color_classes} heatMax={data.soft?.heat_max ?? 0} />
      </Card>

      {hover && <Tooltip hover={hover} />}
      {selected && <SeatModal seat={selected} index={index} nb={nb} deptColors={deptColors} onClose={() => setSelected(null)} />}
    </div>
  )
}

function Row({ r, hall, index, empties, blocked, paint, mode, onHover, onLeave, onPick }) {
  return (
    <>
      <span className="self-center text-right text-[10px] text-slate-400">{r + 1}</span>
      {Array.from({ length: hall.cols }, (_, c) => {
        if (blocked.has(`${r}|${c}`)) return <div key={c} className="blocked-seat aspect-square rounded-md" title="Blocked seat" aria-label={`Row ${r + 1} column ${c + 1}: blocked`} />
        const seat = index.get(`${hall.hall_id}|${r}|${c}`)
        if (!seat) {
          const e = empties.get(`${hall.hall_id}|${r}|${c}`)
          const cls = e?.kind === 'wasted' ? 'border-amber-300 text-amber-500' : e?.kind === 'buffer' ? 'border-sky-300 text-sky-500' : 'border-slate-200 text-slate-300'
          return (
            <div key={c} aria-label={`Row ${r + 1} column ${c + 1}: ${e?.kind ?? 'unused'} seat`}
              className={`flex aspect-square items-center justify-center rounded-md border border-dashed text-[9px] ${cls}`}>
              {mode === 'heat' && e ? (e.kind === 'wasted' ? 'waste' : 'buf') : ''}
            </div>
          )
        }
        const { bg, label, fg } = paint(seat)
        return (
          <button key={c} onClick={() => onPick(seat)} onMouseEnter={(e) => onHover(e, seat)} onFocus={(e) => onHover(e, seat)}
            onMouseLeave={onLeave} onBlur={onLeave}
            aria-label={`${seat.seat_label}: ${seat.name}, ${seat.branch}, courses ${seat.courses.join(', ')}`}
            className="aspect-square rounded-md text-[11px] font-semibold shadow-sm ring-1 ring-black/10 transition hover:z-10 hover:scale-110 hover:ring-2 hover:ring-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900"
            style={{ backgroundColor: bg, color: fg }}>
            {label}
          </button>
        )
      })}
    </>
  )
}

function Tooltip({ hover: { seat, rect } }) {
  const left = Math.min(Math.max(rect.left + rect.width / 2, 120), window.innerWidth - 120)
  return (
    <div role="tooltip" className="pointer-events-none fixed z-40 w-56 -translate-x-1/2 -translate-y-full rounded-lg bg-slate-900 px-3 py-2 text-xs text-white shadow-xl"
      style={{ left, top: rect.top - 8 }}>
      <div className="font-semibold">{seat.name}</div>
      <div className="text-slate-300">{seat.sap_id} · {seat.seat_label}</div>
      <div className="mt-1 text-slate-300">{seat.branch} · roll {seat.roll_no}</div>
      <div className="mt-1 text-slate-200">{seat.courses.join(' · ')}</div>
      {seat.penalty > 0 && <div className="mt-1 text-amber-300">penalty {seat.penalty}</div>}
    </div>
  )
}

function ConflictBanner({ data, verdict, nb }) {
  const ok = verdict.conflicts.length === 0
  const backendOk = data.metrics.hard_constraints_satisfied
  return (
    <div className={`flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl px-4 py-3 text-sm ring-1 ${ok && backendOk ? 'bg-emerald-50 text-emerald-900 ring-emerald-200' : 'bg-rose-50 text-rose-900 ring-rose-200'}`}>
      {ok && backendOk ? <CheckCircle2 className="h-5 w-5 text-emerald-600" aria-hidden /> : <AlertTriangle className="h-5 w-5 text-rose-600" aria-hidden />}
      <strong>{verdict.conflicts.length} adjacent same-course conflicts</strong>
      <span className="text-xs opacity-80">
        checked across {verdict.pairs} neighbouring seat pairs ({nb}-way) in your browser · backend hard constraints H1–H5: {backendOk ? 'satisfied' : 'VIOLATED'}
      </span>
    </div>
  )
}

function Legend({ mode, deptColors, classes, heatMax }) {
  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-100 pt-3 text-xs text-slate-600">
      {mode === 'dept' && Object.entries(deptColors).map(([b, c]) => (
        <span key={b} className="inline-flex items-center gap-1.5"><i className="h-3 w-3 rounded" style={{ background: c }} />{b}</span>
      ))}
      {mode === 'dept' && <span className="text-slate-400">· number = roll no.</span>}
      {mode === 'class' && (
        <>
          <Palette className="h-3.5 w-3.5" aria-hidden />
          {classes.slice(0, 14).map((c) => <span key={c.color} className="inline-flex items-center gap-1"><i className="h-3 w-3 rounded" style={{ background: classColor(c.color) }} />{c.color + 1}</span>)}
          {classes.length > 14 && <span>+{classes.length - 14} more</span>}
          <span className="text-slate-400">· students of one class share no course</span>
        </>
      )}
      {mode === 'course' && <span><i className="mr-1 inline-block h-3 w-3 rounded bg-indigo-600 align-middle" />enrolled in the chosen course <i className="ml-3 mr-1 inline-block h-3 w-3 rounded bg-slate-200 align-middle" />other students</span>}
      {mode === 'heat' && (
        <>
          <Flame className="h-3.5 w-3.5 text-orange-500" aria-hidden />
          <span>0</span>
          <i className="h-2.5 w-40 rounded" style={{ background: `linear-gradient(90deg, ${heatColor(0)}, ${heatColor(0.5)}, ${heatColor(1)})` }} />
          <span>{heatMax.toFixed(1)} (seat penalty)</span>
          <Badge tone="amber">waste = empty, separates nobody</Badge>
          <Badge tone="indigo">buf = buffer seat</Badge>
        </>
      )}
      {mode !== 'heat' && <><i className="inline-block h-3 w-3 rounded border border-dashed border-sky-400" /> buffer seat <i className="blocked-seat inline-block h-3 w-3 rounded" /> blocked</>}
    </div>
  )
}
