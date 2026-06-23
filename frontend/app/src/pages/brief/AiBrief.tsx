import type { Actual, ConsensusItem, Horizon, Hypothesis, Impact, KeyFactor, TaggedItem } from '../../types'
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
function ConsensusRow({ items }: { items: ConsensusItem[] }) {
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

function PredictionCard({ h }: { h: Hypothesis }) {
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
              <InfoHint text="AI 模型对本条预测的信心自评:它自己判断这个方向有多大把握会兑现。属模型主观估计、未经校准,不是真实概率,仅供同期横向参考。" />
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

/** 假设层 = 预测卡(多模型时上方先给跨模型共识)。 */
export function HypothesisPanel({ hypotheses, consensus = [] }: { hypotheses: Hypothesis[]; consensus?: ConsensusItem[] }) {
  return (
    <Card punch>
      <SectionHead label="HYPOTHESIS" zh="假设层 · 预测" margin="0 0 8px" />
      {consensus.length > 0 && <ConsensusRow items={consensus} />}
      {hypotheses.length ? hypotheses.map((h, i) => <PredictionCard key={i} h={h} />) : <Muted />}
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
