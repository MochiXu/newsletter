import type { BriefsPayload } from '../types'
import { DEMO_PAYLOAD } from '../demo/demoBriefs'

// 真实数据是否「有内容」:至少一条简报有 headline。空壳(管线刚上线、四层为空)时退回 demo。
function hasContent(p: unknown): p is BriefsPayload {
  if (!p || typeof p !== 'object') return false
  const briefs = (p as BriefsPayload).briefs
  return Array.isArray(briefs) && briefs.some((b) => !!b?.headline && b.headline.trim().length > 0)
}

/**
 * 加载简报数据。优先 fetch 构建期拷入的 data/briefs.json(真实管线产出);
 * 文件缺失 / 解析失败 / 内容为空 → 回退到 9 天 demo,保证界面始终有内容。
 */
export async function loadBriefs(): Promise<BriefsPayload> {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}data/briefs.json`, { cache: 'no-cache' })
    if (res.ok) {
      const data = await res.json()
      if (hasContent(data)) return data
    }
  } catch {
    // 网络/解析失败:回退 demo
  }
  return DEMO_PAYLOAD
}
