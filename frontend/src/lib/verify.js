// Browser-side verification of the allocation. This does NOT allocate anything: it re-checks the
// finished plan from the raw seat data, so the "zero conflicts" claim never relies on the server alone.
export const neighbourOffsets = (nb) => (nb === '8'
  ? [[0, 1], [1, 0], [1, 1], [1, -1]]          // half of the 8 directions: every pair is visited once
  : [[0, 1], [1, 0]])

const key = (hall, r, c) => `${hall}|${r}|${c}`

export function seatIndex(seats) {
  const map = new Map()
  for (const s of seats) map.set(key(s.hall_id, s.row, s.col), s)
  return map
}

export const sharedCourses = (a, b) => a.courses.filter((c) => b.courses.includes(c))

/** All neighbouring seat pairs (4 or 8 neighbourhood) whose students share a course. */
export function adjacentConflicts(seats, nb = '4', onlyCourse = null) {
  const index = seatIndex(seats)
  const conflicts = []
  let pairs = 0
  for (const s of seats) {
    for (const [dr, dc] of neighbourOffsets(nb)) {
      const o = index.get(key(s.hall_id, s.row + dr, s.col + dc))
      if (!o) continue
      pairs += 1
      const shared = sharedCourses(s, o).filter((c) => onlyCourse === null || c === onlyCourse)
      if (shared.length) conflicts.push({ a: s, b: o, shared })
    }
  }
  return { pairs, conflicts }
}

/** The occupied neighbours of one seat (all directions of the chosen neighbourhood). */
export function neighboursOf(seat, index, nb = '4') {
  const dirs = nb === '8'
    ? [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]]
    : [[-1, 0], [0, -1], [0, 1], [1, 0]]
  const names = { '-1,0': 'Front', '1,0': 'Back', '0,-1': 'Left', '0,1': 'Right', '-1,-1': 'Front-left', '-1,1': 'Front-right', '1,-1': 'Back-left', '1,1': 'Back-right' }
  return dirs.map(([dr, dc]) => ({ dir: names[`${dr},${dc}`], other: index.get(key(seat.hall_id, seat.row + dr, seat.col + dc)) || null }))
}
