interface Props {
  date: string
  model: string
}

/** 小票页脚:免责水印 + 装饰条形码 + 收尾签名(从设计稿 1:1 移植)。 */
export default function ReceiptFooter({ date, model }: Props) {
  return (
    <>
      <div style={{ borderTop: '1px dashed var(--faint)', margin: '20px 0 0' }} />
      <div
        style={{
          textAlign: 'center',
          fontFamily: 'var(--mono)',
          fontSize: 9.5,
          color: 'var(--ink2)',
          letterSpacing: '.6px',
          marginTop: 13,
          lineHeight: 1.7,
        }}
      >
        本简报仅供研究 · 非投资建议
        <br />
        NOT INVESTMENT ADVICE
      </div>
      {/* 装饰条形码:固定的重复线性渐变,无信息含义 */}
      <div
        style={{
          height: 30,
          margin: '14px 0 7px',
          opacity: 0.82,
          backgroundImage:
            'repeating-linear-gradient(90deg,var(--ink) 0 2px,transparent 2px 4px,var(--ink) 4px 5px,transparent 5px 9px,var(--ink) 9px 11px,transparent 11px 13px)',
        }}
      />
      <div
        style={{
          textAlign: 'center',
          fontFamily: 'var(--mono)',
          fontSize: 9.5,
          color: 'var(--ink2)',
          letterSpacing: '1px',
        }}
      >
        ★ {date} · GEN {model} ★
      </div>
    </>
  )
}
