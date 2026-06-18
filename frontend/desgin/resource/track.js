// Mock track-record data — a stand-in for the JSON the Python pipeline emits.
// The front-end performs NO scoring; every score & grade below is precomputed.
// grade: 'green' (high) | 'yellow' (mid) | 'red' (low).  Absent date = no data /
// non-trading day (rendered gray). This mirrors N8 (trading-calendar aware).

function makeRng(seed) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  let s = h;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const gradeOf = (n) => (n >= 75 ? 'green' : n >= 60 ? 'yellow' : 'red');
const p2 = (n) => (n < 10 ? '0' + n : '' + n);

// Hand-set scores for the nine real briefs (graded upstream against next-day outcomes).
const REAL = {
  '2026-06-16': 58, '2026-06-15': 72, '2026-06-12': 86, '2026-06-11': 80,
  '2026-06-10': 64, '2026-06-09': 78, '2026-06-08': 83, '2026-06-05': 55, '2026-06-04': 70,
};

function build() {
  const days = {};
  const start = new Date('2025-09-01T00:00:00');
  const end = new Date('2026-06-16T00:00:00');
  const rng = makeRng('track-v1');
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const wd = d.getDay();
    if (wd === 0 || wd === 6) continue;                 // weekend → no data
    const iso = d.getFullYear() + '-' + p2(d.getMonth() + 1) + '-' + p2(d.getDate());
    if (!(iso in REAL) && rng() < 0.045) continue;       // sparse holidays / gaps
    let score;
    if (iso in REAL) score = REAL[iso];
    else { const base = (rng() + rng() + rng()) / 3; score = Math.round(34 + base * 58); } // ~mid-high skew
    days[iso] = { score, grade: gradeOf(score) };
  }
  // monthly + yearly rollups
  const months = {}, quarters = {}, years = {};
  Object.keys(days).forEach((iso) => {
    const s = days[iso].score, m = iso.slice(0, 7), y = iso.slice(0, 4);
    const q = y + '-Q' + Math.ceil((+iso.slice(5, 7)) / 3);
    (months[m] = months[m] || { sum: 0, n: 0, high: 0 });
    months[m].sum += s; months[m].n++; if (s >= 80) months[m].high++;
    (quarters[q] = quarters[q] || { sum: 0, n: 0, high: 0 });
    quarters[q].sum += s; quarters[q].n++; if (s >= 80) quarters[q].high++;
    (years[y] = years[y] || { sum: 0, n: 0, high: 0 });
    years[y].sum += s; years[y].n++; if (s >= 80) years[y].high++;
  });
  Object.keys(months).forEach((m) => { months[m].acc = Math.round(months[m].sum / months[m].n); });
  Object.keys(quarters).forEach((q) => { quarters[q].acc = Math.round(quarters[q].sum / quarters[q].n); });
  Object.keys(years).forEach((y) => { years[y].acc = Math.round(years[y].sum / years[y].n); });
  return { days, months, quarters, years };
}

export const TRACK = build();
