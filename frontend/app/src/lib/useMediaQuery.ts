import { useEffect, useState } from 'react'

/** 订阅一个媒体查询的匹配状态(SSR 安全)。 */
export function useMediaQuery(query: string): boolean {
  const [match, setMatch] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches,
  )
  useEffect(() => {
    const mql = window.matchMedia(query)
    const onChange = () => setMatch(mql.matches)
    onChange()
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [query])
  return match
}

/** 窄屏(移动端)判定:决定时间线/小票走移动布局与「点击直切」交互。 */
export const useIsNarrow = (): boolean => useMediaQuery('(max-width: 720px)')
