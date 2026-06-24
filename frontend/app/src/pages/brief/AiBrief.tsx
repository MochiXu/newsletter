import type {
  Actual, ConsensusItem, FactorView, Horizon, Hypothesis, Impact, KeyFactor, PredDir, Scorecard, TaggedItem,
} from '../../types'
import { ASSET_CN, dirInfo, HORIZON_CN, PRED_DIR } from '../../lib/format'
import { renderRichText } from '../../lib/highlight'
import { Card, SectionHead } from '../../components/Card'
import { Tooltip } from '../../components/Tooltip'

// 小问号标注 + hover 说明(走统一 Tooltip,portal 渲染,不被打孔卡片裁剪)。
function InfoHint({ text }: { text: string }) {
  return (
    <Tooltip content={text}>
      <span
        aria-label={text}
        style={{
          fontFamily: 'var(--mono)', fontSize: 8, lineHeight: 1, width: 12, height: 12,
          borderRadius: '50%', border: '1px solid var(--hair)', color: 'var(--ink2)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'help', userSelect: 'none',
        }}
      >
        ?
      </span>
    </Tooltip>
  )
}

// 主题标签 chip(事实/解读共用)。空标签不渲染。
function TagChip({ tag, mr = 0 }: { tag: string; mr?: number }) {
  if (!tag) return null
  return (
    <span
      style={{
        display: 'inline-block',
        flex: '0 0 auto',
        fontFamily: 'var(--mono)',
        fontSize: 10,
        color: 'var(--ink2)',
        background: 'var(--paper2)',
        border: '1px solid var(--faint)',
        borderRadius: 3,
        padding: '1px 6px',
        whiteSpace: 'nowrap',
        marginRight: mr,
      }}
    >
      {tag}
    </span>
  )
}

const Muted = () => <div style={{ fontSize: 11.5, color: 'var(--ink2)', padding: '4px 0' }}>暂无</div>

// 影响层资产:显示中文短名,英文代码(若后端解析出)放 hover。
function ImpactAsset({ asset, code }: { asset: string; code?: string }) {
  const el = (
    <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink)' }}>{ASSET_CN[asset] ?? asset}</span>
  )
  return code ? (
    <Tooltip content={`代码 ${code}`} width={140} style={{ flex: '0 0 auto', cursor: 'help' }}>
      {el}
    </Tooltip>
  ) : (
    <span style={{ flex: '0 0 auto', display: 'inline-flex' }}>{el}</span>
  )
}

// 关键因子 chip:常显极短标签(label),完整读数(detail)放 hover。detail 与 label 相同则不挂 hover。
function KeyFactorChip({ kf }: { kf: KeyFactor }) {
  const hasMore = !!kf.detail && kf.detail !== kf.label
  const chip = (
    <span
      style={{
        fontSize: 9.5,
        color: 'var(--ink2)',
        background: 'var(--paper)',
        border: '1px solid var(--hair)',
        borderRadius: 3,
        padding: '2px 6px',
        cursor: hasMore ? 'help' : 'default',
        borderBottomStyle: hasMore ? 'dotted' : 'solid',
      }}
    >
      {kf.label}
    </span>
  )
  return hasMore ? (
    <Tooltip content={kf.detail} width={220} style={{ flex: '0 0 auto' }}>
      {chip}
    </Tooltip>
  ) : (
    <span style={{ flex: '0 0 auto', display: 'inline-flex' }}>{chip}</span>
  )
}

// 预测卡的「实际结果」行:未到期 → 沙漏;已结算 → 实际方向 + 幅度 + 命中✓/未中✗,LLM 复盘进 hover。
function ActualLine({ a, horizon }: { a?: Actual | null; horizon: Horizon }) {
  if (!a) return null
  const top = { borderTop: '1px dashed var(--hair)', marginTop: 7, paddingTop: 6 } as const
  if (a.status !== 'settled' || !a.realizedDir) {
    return (
      <div style={{ ...top, display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)' }}>
        <span style={{ fontSize: 11 }}>⏳</span>
        <span>实际结果待验证 · 到 {HORIZON_CN[horizon]} 后揭晓</span>
      </div>
    )
  }
  const rd = PRED_DIR[a.realizedDir]
  const hit = a.hit ? { t: '✓ 命中', col: 'var(--up)' } : { t: '✗ 未中', col: 'var(--down)' }
  return (
    <div style={{ ...top, display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', fontFamily: 'var(--mono)', fontSize: 10.5 }}>
      <span style={{ color: 'var(--ink2)' }}>实际</span>
      <span style={{ color: rd.col, fontWeight: 700 }}>
        {rd.ch} {rd.lab} {a.realizedText}
      </span>
      <span style={{ color: hit.col, fontWeight: 700 }}>{hit.t}</span>
      {a.note && <InfoHint text={a.note} />}
    </div>
  )
}

// 跨模型共识行(代码级投票,非某模型观点)。仅在 ≥2 模型(consensus 非空)时由 BriefPage 传入。
function ConsensusRow({ items, factors }: { items: ConsensusItem[]; factors?: Record<string, FactorView> }) {
  const order = ['up', 'down', 'flat'] as const
  return (
    <div
      style={{
        background: 'var(--paper2)',
        border: '1px solid var(--faint)',
        borderRadius: 5,
        padding: '8px 11px',
        marginBottom: 9,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '1px', color: 'var(--ink2)' }}>
          跨模型共识 · CONSENSUS
        </span>
        <InfoHint text="对每个资产,各模型方向投票的代码级汇总(不是某一个模型的观点):多数方向 + 认同票数 + 该方向均值信心;平票记为分歧(横盘)。" />
      </div>
      {items.map((c) => {
        const d = PRED_DIR[c.direction]
        const fv = factors?.[c.asset.toLowerCase()]
        const bd = fv ? PRED_DIR[fv.baselineDir] : null
        return (
          <div
            key={c.asset}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', fontSize: 11.5, flexWrap: 'wrap' }}
          >
            <span style={{ fontWeight: 600, color: 'var(--ink)', minWidth: 52 }}>{ASSET_CN[c.asset] ?? c.asset}</span>
            <span style={{ fontFamily: 'var(--mono)', color: d.col, fontWeight: 700 }}>
              {d.ch} {d.lab}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)' }}>
              {c.agree}/{c.n} 认同
              {c.meanConfidence > 0 && ` · 均值信心 ${Math.round(c.meanConfidence * 100)}%`}
            </span>
            {bd && (
              <Tooltip
                content={`代码因子基线今日方向(趋势/动量/价值合成);与共识${fv && fv.baselineDir === c.direction ? '一致' : '分歧'}。因子是 AI 的陪练标尺。`}
                width={220}
                style={{ flex: '0 0 auto', cursor: 'help' }}
              >
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--ink2)', borderBottom: '1px dotted var(--hair)' }}>
                  基线 <span style={{ color: bd.col }}>{bd.ch}</span>
                </span>
              </Tooltip>
            )}
            {c.actual &&
              (c.actual.status === 'settled' && c.actual.realizedDir ? (
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ color: PRED_DIR[c.actual.realizedDir].col, fontWeight: 700 }}>
                    实 {PRED_DIR[c.actual.realizedDir].ch}
                    {c.actual.realizedText}
                  </span>
                  <span style={{ color: c.actual.hit ? 'var(--up)' : 'var(--down)', fontWeight: 700 }}>
                    {c.actual.hit ? '✓' : '✗'}
                  </span>
                </span>
              ) : (
                <span title="实际结果待验证" style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)' }}>⏳</span>
              ))}
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 7, fontFamily: 'var(--mono)', fontSize: 10 }}>
              {order.map((k) =>
                c.votes[k] ? (
                  <span key={k} style={{ color: PRED_DIR[k].col }}>
                    {PRED_DIR[k].ch}
                    {c.votes[k]}
                  </span>
                ) : null,
              )}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// 信心校准提示:从 scorecard 找该模型(B 臂优先)对应信心档的历史实际命中率,挂进信心 tooltip。
function calibHint(sc: Scorecard | null | undefined, modelId: string, conf: number): string {
  if (!sc) return ''
  const lane = sc.models[`${modelId}·B`] ? `${modelId}·B` : sc.models[modelId] ? modelId : ''
  if (!lane) return ''
  const b = sc.models[lane].calibration.find((x) => conf >= x.lo && conf < x.hi)
  if (!b || !b.n || b.realized == null) return ''
  const src = sc.source === 'forward' ? '前向' : 'backfill·含记忆污染仅供参考'
  return ` ｜ 校准:该模型报此信心档,历史实际命中 ${Math.round(b.realized * 100)}%(n=${b.n}·${src})`
}

// 预测卡的「代码因子对照」条:AI 之外,代码因子模型(陪练标尺)今日怎么看 + 因子打分 + 波动率预测。
function FactorStrip({ factor, aiDir }: { factor: FactorView; aiDir: PredDir }) {
  const bd = PRED_DIR[factor.baselineDir]
  const disagree = factor.baselineDir !== aiDir
  const sc = factor.scores || {}
  const chip = (label: string, v: number | undefined) =>
    v == null ? null : (
      <span key={label} style={{ border: '1px solid var(--hair)', borderRadius: 3, padding: '1px 5px', color: 'var(--ink2)' }}>
        {label} <span style={{ color: v > 0 ? 'var(--up)' : v < 0 ? 'var(--down)' : 'var(--ink2)' }}>{v >= 0 ? '+' : ''}{v.toFixed(2)}</span>
      </span>
    )
  return (
    <div style={{ background: 'var(--paper)', border: '1px solid var(--faint)', borderRadius: 4, padding: '6px 8px', marginTop: 7 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5, flexWrap: 'wrap' }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)' }}>代码因子(陪练)</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: bd.col, fontWeight: 700 }}>
          {bd.ch} {bd.lab} {factor.composite >= 0 ? '+' : ''}{factor.composite.toFixed(2)}
        </span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)' }}>信心 {Math.round(factor.baselineConf * 100)}%</span>
        {disagree && (
          <span style={{ fontSize: 9, color: 'var(--accent)', border: '1px solid var(--faint)', borderRadius: 3, padding: '0 5px' }}>
            与 AI 分歧
          </span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', fontFamily: 'var(--mono)', fontSize: 9 }}>
        {chip('趋势', sc.trend)}
        {chip('动量', sc.momentum)}
        {chip('价值', sc.value)}
        {factor.volForecastAnn > 0 && (
          <span style={{ border: '1px solid var(--hair)', borderRadius: 3, padding: '1px 5px', color: 'var(--ink2)' }}>
            波动预测 <span style={{ color: 'var(--ink)' }}>{Math.round(factor.volForecastAnn * 100)}%</span>
          </span>
        )}
      </div>
    </div>
  )
}

function PredictionCard({ h, factor, hint }: { h: Hypothesis; factor?: FactorView; hint?: string }) {
  const d = PRED_DIR[h.direction]
  return (
    <div style={{ background: 'var(--paper2)', borderRadius: 5, padding: '10px 11px', marginBottom: 7 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
        <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--ink)' }}>{ASSET_CN[h.asset] ?? h.asset}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, fontWeight: 700, color: d.col }}>
          {d.ch} {d.lab}
        </span>
        <span
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 9.5,
            color: 'var(--ink2)',
            border: '1px solid var(--hair)',
            borderRadius: 3,
            padding: '1px 6px',
          }}
        >
          {HORIZON_CN[h.horizon]}
        </span>
        {h.confidence > 0 && (
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--ink2)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              信心 {Math.round(h.confidence * 100)}%
              <InfoHint text={'AI 模型对本条预测的信心自评:它自己判断这个方向有多大把握会兑现。属模型主观估计、未经校准,不是真实概率,仅供同期横向参考。' + (hint || '')} />
            </span>
            <span style={{ width: 42, height: 4, borderRadius: 3, background: 'var(--hair)', overflow: 'hidden' }}>
              <span
                style={{ display: 'block', height: '100%', width: `${Math.round(h.confidence * 100)}%`, background: d.col }}
              />
            </span>
          </span>
        )}
      </div>
      <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--ink)', fontWeight: 500, textWrap: 'pretty' }}>
        {h.ifThen}
      </div>
      <div style={{ fontSize: 10.5, lineHeight: 1.45, color: 'var(--ink2)', marginTop: 5, display: 'flex', gap: 6 }}>
        <span style={{ fontFamily: 'var(--mono)', color: 'var(--down)', flex: '0 0 auto' }}>✕ 失效</span>
        <span style={{ textWrap: 'pretty' }}>{h.invalidation}</span>
      </div>
      {h.keyFactors.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 7 }}>
          {h.keyFactors.map((f, i) => (
            <KeyFactorChip key={i} kf={f} />
          ))}
        </div>
      )}
      {factor && <FactorStrip factor={factor} aiDir={h.direction} />}
      <ActualLine a={h.actual} horizon={h.horizon} />
    </div>
  )
}

// AI BRIEF 四层 = 4 个独立打孔小票面板,分别导出,供 BriefPage 自由排进左右两列。

/** 事实层:主题标签 + 高亮数字的可扫读数据条。 */
export function FactsPanel({ facts }: { facts: TaggedItem[] }) {
  return (
    <Card punch>
      <SectionHead label="FACTS" zh="事实层" margin="0 0 8px" />
      {facts.length ? (
        facts.map((f, i) => (
          <div
            key={i}
            style={{ display: 'flex', gap: 9, alignItems: 'baseline', padding: '6px 0', borderBottom: '1px dashed var(--hair)' }}
          >
            <TagChip tag={f.tag} />
            <span style={{ fontSize: 12.5, lineHeight: 1.55, color: 'var(--ink)', textWrap: 'pretty' }}>
              {renderRichText(f.text, f.figures)}
            </span>
          </div>
        ))
      ) : (
        <Muted />
      )}
    </Card>
  )
}

/** 解读层:accent 竖线 + 主题标签 + 论述(判断的"嗓音")。 */
export function ReadsPanel({ reads }: { reads: TaggedItem[] }) {
  return (
    <Card punch>
      <SectionHead label="INTERPRETATION" zh="解读层" margin="0 0 8px" />
      {reads.length ? (
        reads.map((r, i) => (
          <div key={i} style={{ borderLeft: '2px solid var(--accent)', padding: '1px 0 1px 12px', marginBottom: 11 }}>
            <TagChip tag={r.tag} mr={7} />
            <span style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--ink)', textWrap: 'pretty' }}>
              {renderRichText(r.text, r.figures)}
            </span>
          </div>
        ))
      ) : (
        <Muted />
      )}
    </Card>
  )
}

/** 假设层 = 预测卡(多模型时上方先给跨模型共识);带因子对照 + 信心校准提示(scorecard)。 */
export function HypothesisPanel({
  hypotheses,
  consensus = [],
  factors,
  scorecard,
  modelId = '',
}: {
  hypotheses: Hypothesis[]
  consensus?: ConsensusItem[]
  factors?: Record<string, FactorView>
  scorecard?: Scorecard | null
  modelId?: string
}) {
  return (
    <Card punch>
      <SectionHead label="HYPOTHESIS" zh="假设层 · 预测" margin="0 0 8px" />
      {consensus.length > 0 && <ConsensusRow items={consensus} factors={factors} />}
      {hypotheses.length ? (
        hypotheses.map((h, i) => (
          <PredictionCard
            key={i}
            h={h}
            factor={factors?.[h.asset.toLowerCase()]}
            hint={calibHint(scorecard, modelId, h.confidence)}
          />
        ))
      ) : (
        <Muted />
      )}
    </Card>
  )
}

/** 影响层:中文资产名 + 英文代码 hover。 */
export function ImpactPanel({ impacts }: { impacts: Impact[] }) {
  return (
    <Card punch>
      <SectionHead label="IMPACT" zh="影响层" margin="0 0 8px" />
      {impacts.length ? (
        impacts.map((im, i) => {
          const di = dirInfo(im.dir)
          return (
            <div
              key={i}
              style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 12, lineHeight: 1.5, marginBottom: 5 }}
            >
              <span
                style={{ fontFamily: 'var(--mono)', fontSize: 12, color: di.col, flex: '0 0 auto', width: 12, textAlign: 'center' }}
              >
                {di.ch}
              </span>
              <ImpactAsset asset={im.asset} code={im.code} />
              <span style={{ color: 'var(--ink2)', textWrap: 'pretty' }}>{im.watch}</span>
            </div>
          )
        })
      ) : (
        <Muted />
      )}
    </Card>
  )
}
