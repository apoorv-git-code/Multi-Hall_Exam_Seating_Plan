// Colour helpers. Departments use a colour-blind-friendly categorical palette (Okabe-Ito based).
const DEPT = ['#0072B2', '#E69F00', '#009E73', '#CC79A7', '#D55E00', '#56B4E9', '#C9B800', '#6B7280', '#8E44AD', '#16A085']

export function branchColors(branches) {
  const map = {}
  ;[...branches].sort().forEach((b, i) => { map[b] = DEPT[i % DEPT.length] })
  return map
}

/** Distinct colours for any number of conflict-graph color classes (golden-angle hue walk). */
export function classColor(k) {
  return `hsl(${Math.round((k * 137.508) % 360)} 62% 52%)`
}

/** Readable label colour (dark or white) for a hex, rgb() or hsl() background. */
export function textOn(bg) {
  let r, g, b
  if (bg.startsWith('#')) {
    r = parseInt(bg.slice(1, 3), 16); g = parseInt(bg.slice(3, 5), 16); b = parseInt(bg.slice(5, 7), 16)
  } else if (bg.startsWith('rgb')) {
    ;[r, g, b] = bg.match(/\d+/g).map(Number)
  } else {
    const [h, s, l] = bg.match(/[\d.]+/g).map(Number)
    const a = (s / 100) * Math.min(l / 100, 1 - l / 100)
    const f = (n) => { const k = (n + h / 30) % 12; return Math.round(255 * (l / 100 - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)))) }
    r = f(0); g = f(8); b = f(4)
  }
  return (0.299 * r + 0.587 * g + 0.114 * b) > 150 ? '#0f172a' : '#ffffff'
}

/** White -> amber -> red ramp for heat in [0, 1]. */
export function heatColor(t) {
  const x = Math.max(0, Math.min(1, t))
  const stops = [[255, 247, 237], [251, 191, 36], [220, 38, 38]]
  const seg = x < 0.5 ? 0 : 1
  const u = x < 0.5 ? x / 0.5 : (x - 0.5) / 0.5
  const [a, b] = [stops[seg], stops[seg + 1]]
  return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * u)).join(',')})`
}
