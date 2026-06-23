// 时区辅助:把简报的「美东交易日」换算成浏览器本地时刻。
// brief.date 是裸日期(美东交易日,= 美股当天 16:00 ET 收盘的数据)。裸日期无法直接换时区,
// 故锚定到「美东收盘 16:00 ET」这个具体时刻(用 Intl 自动处理 EDT/EST 夏令时),再格式化到本地。

export interface LocalMoment {
  date: string // 本地 MM-DD
  time: string // 本地 HH:mm
  tz: string // 本地时区名(如 Asia/Shanghai)
  shifted: boolean // 本地日期是否与美东交易日不同(用于决定是否值得提示)
}

/** 某 UTC 时刻在 tz 的挂钟时间相对 UTC 的偏移(分钟),含夏令时。 */
function tzOffsetMin(d: Date, tz: string): number {
  const p = new Intl.DateTimeFormat('en-US', {
    timeZone: tz, hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).formatToParts(d).reduce<Record<string, string>>((a, x) => ((a[x.type] = x.value), a), {})
  const asUTC = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second)
  return (asUTC - d.getTime()) / 60000
}

// IANA 时区 → 中文短标签(显式标注用)。未知则回退原名。
const TZ_LABEL: Record<string, string> = {
  'America/New_York': '美东',
  'America/Chicago': '美中',
  'America/Los_Angeles': '美西',
  'Asia/Shanghai': '北京',
  UTC: 'UTC',
}

/** IANA 时区 → 中文短标签(给标题旁的浅色标注)。 */
export const tzLabel = (tz: string): string => TZ_LABEL[tz] ?? tz

/** 交易日 'YYYY-MM-DD' 在 sourceTz 的收盘(默认 16:00)换算到浏览器本地时刻;非法日期返回 null。 */
export function usCloseLocal(dateStr: string, sourceTz = 'America/New_York', hourET = 16): LocalMoment | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr || '')
  if (!m) return null
  const y = +m[1], mo = +m[2], d = +m[3]
  // 迭代两次求「sourceTz 挂钟 hourET:00」对应的 UTC 瞬时(消除偏移自洽误差)
  let ts = Date.UTC(y, mo - 1, d, hourET, 0)
  for (let i = 0; i < 2; i++) ts = Date.UTC(y, mo - 1, d, hourET, 0) - tzOffsetMin(new Date(ts), sourceTz) * 60000
  const inst = new Date(ts)
  let tz = 'local'
  try {
    tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'local'
  } catch {
    /* 极少数环境拿不到时区名 */
  }
  const p = new Intl.DateTimeFormat('en-CA', {
    timeZone: tz === 'local' ? undefined : tz, hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).formatToParts(inst).reduce<Record<string, string>>((a, x) => ((a[x.type] = x.value), a), {})
  return {
    date: `${p.month}-${p.day}`,
    time: `${p.hour}:${p.minute}`,
    tz,
    shifted: `${p.year}-${p.month}-${p.day}` !== dateStr,
  }
}
