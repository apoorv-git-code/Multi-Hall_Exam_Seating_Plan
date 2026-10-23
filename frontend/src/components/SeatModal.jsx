import { useEffect, useRef } from 'react'
import { Check, X } from 'lucide-react'
import { classColor } from '../lib/palette.js'
import { neighboursOf, sharedCourses } from '../lib/verify.js'

export default function SeatModal({ seat, index, nb, deptColors, onClose }) {
  const closeRef = useRef(null)
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const neighbours = neighboursOf(seat, index, nb)
  const rows = [['SAP ID', seat.sap_id], ['Roll number', seat.roll_no], ['Department', seat.branch], ['Hall', seat.hall_id],
    ['Row / column', `${seat.row + 1} / ${seat.col + 1}  (row 1 = front)`], ['Soft penalty', seat.penalty]]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" onClick={onClose} role="presentation">
      <div role="dialog" aria-modal="true" aria-label={`Seat ${seat.seat_label}`} onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-slate-100 p-5">
          <div className="flex items-center gap-3">
            <span className="h-10 w-1.5 rounded-full" style={{ background: deptColors[seat.branch] }} />
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Seat {seat.seat_label}</p>
              <h2 className="text-lg font-semibold text-slate-900">{seat.name}</h2>
            </div>
          </div>
          <button ref={closeRef} onClick={onClose} aria-label="Close" className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100"><X className="h-5 w-5" /></button>
        </header>

        <div className="space-y-5 p-5">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {rows.map(([k, v]) => (
              <div key={k}><dt className="text-xs text-slate-500">{k}</dt><dd className="font-medium text-slate-800">{v}</dd></div>
            ))}
            <div><dt className="text-xs text-slate-500">Conflict-graph color</dt>
              <dd className="flex items-center gap-1.5 font-medium"><i className="h-3 w-3 rounded" style={{ background: classColor(seat.color) }} />class {seat.color + 1}</dd></div>
          </dl>

          <div>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Enrolled courses</h3>
            <div className="flex flex-wrap gap-1.5">
              {seat.courses.map((c) => <span key={c} className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700">{c}</span>)}
            </div>
          </div>

          <div>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Neighbours ({nb}-way)</h3>
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm">
              {neighbours.map(({ dir, other }) => {
                const shared = other ? sharedCourses(seat, other) : []
                return (
                  <li key={dir} className="flex items-center justify-between gap-3 px-3 py-2">
                    <span className="w-20 text-xs text-slate-500">{dir}</span>
                    <span className="flex-1 truncate">{other ? `${other.name} · ${other.branch}` : <em className="text-slate-400">empty / blocked / wall</em>}</span>
                    {other && (shared.length
                      ? <span className="rounded bg-rose-100 px-1.5 py-0.5 text-xs font-medium text-rose-700">shares {shared.join(', ')}</span>
                      : <span className="inline-flex items-center gap-1 text-xs text-emerald-700"><Check className="h-3.5 w-3.5" />no shared course</span>)}
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
