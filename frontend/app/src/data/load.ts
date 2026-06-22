import type { BriefsPayload } from '../types'

const EMPTY: BriefsPayload = { model: '', generatedAt: '', briefs: [] }

/**
 * 加载简报数据:fetch 构建期拷入的 data/briefs.json(真实管线产出)。
 * 文件缺失 / 解析失败 → 返回空 payload(App 显示空态)。完全 data-driven,无内置 demo。
 */
export async function loadBriefs(): Promise<BriefsPayload> {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}data/briefs.json`, { cache: 'no-cache' })
    if (res.ok) {
      const data = (await res.json()) as BriefsPayload
      if (data && Array.isArray(data.briefs)) return data
    }
  } catch {
    /* 网络/解析失败:空态 */
  }
  return EMPTY
}
