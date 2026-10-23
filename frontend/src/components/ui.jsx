import { Loader2, X } from 'lucide-react'

export function Card({ title, icon: Icon, action, children, className = '' }) {
  return (
    <section className={`rounded-xl bg-white shadow-card ring-1 ring-slate-200/70 ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
            {Icon && <Icon className="h-4 w-4 text-indigo-600" aria-hidden />}
            {title}
          </h3>
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] leading-snug text-slate-500">{hint}</span>}
    </label>
  )
}

export function NumberInput({ value, onChange, min, max, step = 1 }) {
  return (
    <input
      type="number" className="field" value={value} min={min} max={max} step={step}
      onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
    />
  )
}

export function Slider({ label, hint, value, onChange, min = 0, max = 10, step = 0.5 }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-xs font-medium text-slate-700">{label}</span>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">{value.toFixed(1)}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value} aria-label={label}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-indigo-600"
      />
      {hint && <p className="mt-1 text-[11px] leading-snug text-slate-500">{hint}</p>}
    </div>
  )
}

export function Segmented({ options, value, onChange, size = 'md' }) {
  const pad = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm'
  return (
    <div role="tablist" className="inline-flex rounded-lg bg-slate-100 p-0.5">
      {options.map((o) => (
        <button
          key={o.value} role="tab" aria-selected={value === o.value} onClick={() => onChange(o.value)}
          className={`${pad} rounded-md font-medium transition ${value === o.value ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Badge({ tone = 'slate', children, title }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700', green: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
    red: 'bg-rose-50 text-rose-700 ring-1 ring-rose-200', amber: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200',
    indigo: 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200',
  }
  return <span title={title} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>
}

export function Spinner({ label }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-slate-600" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label}
    </span>
  )
}

export function Toast({ message, onClose }) {
  if (!message) return null
  return (
    <div role="alert" className="fixed bottom-4 right-4 z-50 flex max-w-md items-start gap-3 rounded-lg bg-rose-600 px-4 py-3 text-sm text-white shadow-lg">
      <span className="flex-1 leading-snug">{message}</span>
      <button onClick={onClose} aria-label="Dismiss" className="rounded p-0.5 hover:bg-rose-500"><X className="h-4 w-4" /></button>
    </div>
  )
}
