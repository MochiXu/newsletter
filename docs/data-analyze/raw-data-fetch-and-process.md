现有的数据体系比较少，LLM 拿到的数据分析起来估计也不太准确，我觉得可以考虑拿到具体的数据细节，然后可以考虑用 python 进行一些数据计算，得到一些技术指标，然后让 LLM 进行分析。

关于 FRED 我认为可以建立一个最小的观察集合
| 类别  | 代码                                       |
| --- | ---------------------------------------- |
| 美股  | **SP500**, **NASDAQCOM**, **NASDAQ100**  |
| 恐慌  | **VIXCLS**                               |
| 美债  | **DGS2**, **DGS10**, **T10Y2Y**          |
| 美联储 | **FEDFUNDS**                             |
| 美元  | **DTWEXBGS**                             |
| 通胀  | **CPIAUCSL**, **CPILFESL**, **PCEPILFE** |
| 就业  | **UNRATE**, **PAYEMS**, **ICSA**         |
| 经济  | **GDPC1**, **INDPRO**, **RSAFS**         |
| 黄金  | **GOLDPMGBD228NLBM**, **DFII10**         |

关于 FRED 提供的这些 symbol 的数据频率特征如下：

| 类别 | FRED 代码              | 指标          | 是否日频 | 说明                                            |
| -- | -------------------- | ----------- | ---- | --------------------------------------------- |
| 美股 | **SP500**            | 标普500       | 是    | 日频，收盘值。FRED 说明 SP500 是每日市场收盘指数值。([FRED][1])   |
| 美股 | **NASDAQCOM**        | 纳斯达克综合指数    | 是    | 日频，通常是收盘指数值                                   |
| 恐慌 | **VIXCLS**           | VIX 恐慌指数    | 是    | 日频，收盘值。FRED 页面显示它是 Daily。([FRED][2])          |
| 利率 | **DGS2**             | 美国2年期国债收益率  | 是    | 日频，单位是百分比                                     |
| 利率 | **DGS10**            | 美国10年期国债收益率 | 是    | 日频，单位是百分比。FRED 的 H.15 利率数据是 Daily。([FRED][3]) |
| 利差 | **T10Y2Y**           | 10年-2年收益率差  | 是    | 日频，本质上是 DGS10 - DGS2                          |
| 美元 | **DTWEXBGS**         | 广义美元贸易加权指数  | 是    | 日频                                            |
| 黄金 | **GOLDPMGBD228NLBM** | 黄金伦敦下午定盘价   | 是    | 日频，但不是 24 小时实时金价                              |
| 通胀 | **CPIAUCSL**         | CPI         | 否    | 月频                                            |
| 就业 | **UNRATE**           | 失业率         | 否    | 月频                                            |

[1]: https://fred.stlouisfed.org/graph/?g=zR9T&utm_source=chatgpt.com "S&P 500 | FRED | St. Louis Fed"
[2]: https://fred.stlouisfed.org/series/VIXCLS?utm_source=chatgpt.com "CBOE Volatility Index: VIX (VIXCLS) | FRED | St. Louis Fed"
[3]: https://fred.stlouisfed.org/graph/?g=qkKk&utm_source=chatgpt.com "FRED Graph"

FRED 的日频数据通常不是 open/high/low/close，而是 daily close 或每日观测值。
所以它适合做“趋势 + 相关性 + 宏观解释”，不适合做“开盘买、收盘卖、K线形态”这种交易策略。

其中 DFII10 是 10 年期实际利率，对黄金很有用。你可以把它理解成：名义利率扣掉通胀预期后的真实利率。

一个简单的宏观分析框架是：
- 美股看 SP500 / NASDAQCOM
- 恐慌看 VIXCLS
- 利率看 DGS2 / DGS10 / DFII10
- 经济周期看 T10Y2Y
- 美元看 DTWEXBGS
- 黄金看 GOLDPMGBD228NLBM

我们可以把数据处理的流程 直接变成一个数据管线：先拿原始表，再加衍生列，最后用这些列判断市场环境。
可以把它理解成一个**从原始数据 → 衍生列 → 自定义分析函数 → 宏观判断**的流程。

## 1. 第一步：最小原始表

从 FRED 拿到之后，最开始可以是这样：

| date       | SP500 | NASDAQCOM | VIXCLS | DGS2 | DGS10 | T10Y2Y | DTWEXBGS | GOLD | DFII10 |
| ---------- | ----: | --------: | -----: | ---: | ----: | -----: | -------: | ---: | -----: |
| 2026-06-01 |  5900 |     19000 |   16.2 | 4.20 |  4.45 |   0.25 |    122.1 | 2350 |   2.05 |
| 2026-06-02 |  5925 |     19120 |   15.8 | 4.18 |  4.42 |   0.24 |    121.8 | 2362 |   2.02 |

这是 FRED 的 **基础表**。

## 2. 第二步：加第一层衍生列

先加最基础的几类：

| 类型      | 例子                     | 含义           |
| ------- | ---------------------- | ------------ |
| 收益率     | `SP500_return`         | 标普500每日涨跌幅   |
| 变化量     | `DGS10_change`         | 10年期美债收益率变化  |
| 均线      | `SP500_MA20`           | 标普500 20日均线  |
| 波动率     | `SP500_vol20`          | 20日滚动波动率     |
| 相关性     | `corr_SP500_DGS10_60d` | 股市和利率的60日相关性 |
| z-score | `VIX_zscore252`        | VIX 是否处于极端位置 |

注意：

**价格类指标**适合算收益率，比如：

```text
SP500, NASDAQCOM, GOLD, DTWEXBGS
```

**利率类指标**更适合算变化量，比如：

```text
DGS2, DGS10, DFII10, T10Y2Y
```

因为利率本身已经是百分比，再算百分比收益率意义不大。

---

## 3. 第三步：常用自定义函数

用 Python 举例，核心函数其实不多：

```python
def add_return(df, col, window=1):
    df[f"{col}_ret_{window}d"] = df[col].pct_change(window)
    return df


def add_change(df, col, window=1):
    df[f"{col}_chg_{window}d"] = df[col].diff(window)
    return df


def add_ma(df, col, window):
    df[f"{col}_ma_{window}d"] = df[col].rolling(window).mean()
    return df


def add_volatility(df, col, window):
    ret = df[col].pct_change()
    df[f"{col}_vol_{window}d"] = ret.rolling(window).std()
    return df


def add_rolling_corr(df, col_a, col_b, window):
    df[f"corr_{col_a}_{col_b}_{window}d"] = (
        df[col_a].rolling(window).corr(df[col_b])
    )
    return df


def add_zscore(df, col, window):
    mean = df[col].rolling(window).mean()
    std = df[col].rolling(window).std()
    df[f"{col}_z_{window}d"] = (df[col] - mean) / std
    return df
```

然后你可以这样使用：

```python
df = add_return(df, "SP500", 1)
df = add_return(df, "SP500", 20)
df = add_change(df, "DGS10", 20)
df = add_ma(df, "SP500", 20)
df = add_ma(df, "SP500", 60)
df = add_volatility(df, "SP500", 20)
df = add_zscore(df, "VIXCLS", 252)
```

---

## 4. 第四步：短期、中期、长期分别看什么

### 短期：1 到 20 个交易日

适合看市场情绪和短期风险。

| 指标              | 用途         |
| --------------- | ---------- |
| `SP500_ret_1d`  | 今天股市涨跌     |
| `SP500_ret_5d`  | 最近一周表现     |
| `SP500_ret_20d` | 最近一个月表现    |
| `SP500_MA20`    | 短期趋势       |
| `VIXCLS_z_252d` | 恐慌是否异常     |
| `DGS10_chg_5d`  | 最近利率是否快速上升 |
| `GOLD_ret_20d`  | 黄金短期强弱     |

短期可以这样判断：

```text
SP500 在 MA20 上方 + VIX 下降：
    短期风险偏好较强

SP500 跌破 MA20 + VIX 快速上升：
    短期风险偏高
```

---

### 中期：20 到 120 个交易日

适合看一到六个月的宏观方向。

| 指标                     | 用途      |
| ---------------------- | ------- |
| `SP500_ret_60d`        | 股市中期表现  |
| `NASDAQCOM_ret_60d`    | 科技股中期表现 |
| `SP500_MA60`           | 中期趋势    |
| `SP500_vol_60d`        | 中期风险    |
| `DGS10_chg_60d`        | 中期利率方向  |
| `DTWEXBGS_ret_60d`     | 美元中期强弱  |
| `corr_SP500_DGS10_60d` | 股市和利率关系 |
| `GOLD_ret_60d`         | 黄金中期表现  |

中期可以这样判断：

```text
DGS10 上升 + DTWEXBGS 上升 + SP500 走弱：
    可能是利率和美元压制风险资产

DFII10 下降 + GOLD 上升：
    黄金环境可能变好
```

---

### 长期：120 到 252 个交易日以上

适合看大周期和宏观 regime。

| 指标                            | 用途     |
| ----------------------------- | ------ |
| `SP500_MA200` 或 `SP500_MA252` | 长期股市趋势 |
| `SP500_ret_252d`              | 最近一年收益 |
| `SP500_drawdown`              | 最大回撤   |
| `T10Y2Y`                      | 收益率曲线  |
| `DFII10_MA120`                | 实际利率趋势 |
| `DTWEXBGS_MA120`              | 美元长期趋势 |
| `GOLD_MA120`                  | 黄金长期趋势 |
| `VIXCLS_MA60`                 | 市场风险中枢 |

长期更看“环境”：

```text
收益率曲线倒挂 + VIX 中枢上升 + 股市跌破长期均线：
    宏观风险偏高

实际利率下降 + 美元走弱 + 黄金站上长期均线：
    黄金环境偏强
```

---

## 5. 推荐你最终构建的衍生列

你可以先从这一组开始，不要一开始搞太复杂：

```text
SP500_ret_1d
SP500_ret_20d
SP500_ret_60d
SP500_MA20
SP500_MA60
SP500_MA252
SP500_vol_20d
SP500_vol_60d

NASDAQCOM_ret_20d
NASDAQCOM_ret_60d

VIXCLS_MA20
VIXCLS_z_252d

DGS2_chg_20d
DGS10_chg_20d
DGS10_chg_60d
T10Y2Y_chg_60d

DTWEXBGS_ret_20d
DTWEXBGS_ret_60d

GOLD_ret_20d
GOLD_ret_60d
GOLD_MA60

DFII10_chg_20d
DFII10_chg_60d

corr_SP500_DGS10_60d
corr_SP500_GOLD_60d
corr_GOLD_DFII10_60d
```

这套已经够做一个基础宏观分析面板了。

---

## 6. 一个简单的宏观分析框架

你最后可以把衍生列变成几个模块：

| 模块   | 看什么                        |
| ---- | -------------------------- |
| 股市趋势 | SP500 / NASDAQ 的收益率、均线、波动率 |
| 风险情绪 | VIX 均线、VIX z-score         |
| 利率环境 | DGS2、DGS10、DFII10 的变化      |
| 经济周期 | T10Y2Y 是否倒挂、是否修复           |
| 美元环境 | DTWEXBGS 的收益率和均线           |
| 黄金环境 | GOLD、DFII10、美元之间的关系        |

简单说：

> 原始 FRED 数据只是 `date + value`。
> 真正有用的分析来自你自己构建的衍生列。
> 短期看收益率、均线、VIX。
> 中期看利率、美元、相关性。
> 长期看收益率曲线、实际利率、长期均线和回撤。



关于 LLM 根据指标得到的预测结果准确性：把“LLM 解释器”变成可验证系统的关键一步：不要只分析今天，要支持历史任意日期回放。
可以考虑为数据处理加一些特殊参数，用来控制数据分析的时间点，分析的时间范围。
这一步其实就是把系统从：“只分析今天的市场” 升级成：“可以回到历史上任意一天，模拟当时我们会怎么分析，然后用未来数据验证这个分析是否靠谱。”

这就是一个**宏观分析回测系统**。

## 1. 核心参数不应该只叫 `target_date`

我建议你设计几个参数：

| 参数                | 含义                         |
| ----------------- | -------------------------- |
| `target_date`     | 你要站在哪一天做分析                 |
| `lookback_window` | 向前看多少天的数据，比如 252 天         |
| `short_horizon`   | 短期验证周期，比如未来 5 或 20 个交易日    |
| `mid_horizon`     | 中期验证周期，比如未来 60 个交易日        |
| `long_horizon`    | 长期验证周期，比如未来 120 或 252 个交易日 |
| `symbols`         | 要分析的指标列表                   |
| `model_version`   | 使用哪个 LLM / 哪个 prompt 版本    |

比如：

```json
{
  "target_date": "2024-06-18",
  "lookback_window": 252,
  "short_horizon": 20,
  "mid_horizon": 60,
  "long_horizon": 120,
  "symbols": [
    "SP500",
    "NASDAQCOM",
    "VIXCLS",
    "DGS2",
    "DGS10",
    "T10Y2Y",
    "DTWEXBGS",
    "GOLDPMGBD228NLBM",
    "DFII10"
  ]
}
```

这样你的系统就不是只能分析“今天”，而是可以分析历史上的任意一天。

---

## 2. 最重要的一条：不能偷看未来

假设 `target_date = 2024-06-18`。

那么你构建技术指标时，只能使用：

```text
<= 2024-06-18 的数据
```

不能用：

```text
2024-06-19 之后的数据
```

否则就是**未来函数 / 数据泄漏**。

比如你算：

```text
SP500_MA60
VIX_zscore252
DGS10_chg_20d
GOLD_ret_60d
```

这些都只能基于 `target_date` 之前的数据算。

这点非常重要。
否则 LLM 的分析看起来会很准，但其实它已经间接看到了未来。

---

## 3. 每个 target date 生成一份分析快照

你的数据结构可以这样设计：

### 原始数据表

| date       | SP500 | VIXCLS | DGS10 | DTWEXBGS | GOLD |
| ---------- | ----: | -----: | ----: | -------: | ---: |
| 2024-06-14 |  5431 |   12.6 |  4.22 |    123.1 | 2320 |
| 2024-06-17 |  5473 |   12.8 |  4.28 |    123.4 | 2315 |
| 2024-06-18 |  5487 |   13.1 |  4.31 |    123.7 | 2308 |

### 衍生指标快照

站在 `2024-06-18`，系统生成：

| target_date | SP500_ret_20d | SP500_MA60_signal | VIX_z252 | DGS10_chg_20d | GOLD_ret_60d |
| ----------- | ------------: | ----------------- | -------: | ------------: | -----------: |
| 2024-06-18  |          3.2% | above_ma60        |     -0.8 |         +0.15 |        -2.1% |

然后把这些技术值交给 LLM。

---

## 4. LLM 不应该负责算指标，只负责解释

这里我建议你强制分层：

```text
数据层：从 FRED 拉数据
特征层：计算收益率、均线、波动率、z-score、相关性
LLM 层：根据特征做解释和判断
评估层：用未来真实走势验证 LLM 判断
```

不要让 LLM 自己算：

```text
20日收益率是多少？
60日均线是多少？
z-score 是多少？
```

这些应该由代码算。
LLM 只负责做类似这种判断：

```json
{
  "target_date": "2024-06-18",
  "short_term_view": "risk_on",
  "mid_term_view": "neutral",
  "long_term_view": "late_cycle_pressure",
  "equity_view": "bullish_short_term",
  "gold_view": "weak_short_term",
  "risk_level": "medium",
  "reasoning": [
    "SP500 is above MA60",
    "VIX is below its 1-year average",
    "DGS10 has risen over the last 20 days",
    "Gold is below its 60-day moving average"
  ]
}
```

这样比较稳定，也方便回测。

---

## 5. 未来验证怎么做？

假设 LLM 在 `2024-06-18` 给出判断：

```text
短期：risk_on
中期：neutral
长期：risk_on
```

那你可以用未来真实数据验证：

| 验证周期     | 看什么      |
| -------- | -------- |
| 未来 5 天   | 短线是否正确   |
| 未来 20 天  | 短期判断是否正确 |
| 未来 60 天  | 中期判断是否正确 |
| 未来 120 天 | 长期判断是否正确 |

比如：

```text
future_SP500_ret_20d = SP500[t+20] / SP500[t] - 1
future_GOLD_ret_20d = GOLD[t+20] / GOLD[t] - 1
future_VIX_change_20d = VIX[t+20] - VIX[t]
```

然后你可以定义规则：

```text
如果 LLM 判断 risk_on：
    未来 SP500 20日收益率 > 0
    且 VIX 没有明显上升
    那么判断基本正确

如果 LLM 判断 risk_off：
    未来 SP500 20日收益率 < 0
    或 VIX 明显上升
    那么判断基本正确
```

---

## 6. 你需要把 LLM 输出结构化

不要只让 LLM 输出自然语言。
最好让它输出固定 JSON。

例如：

```json
{
  "target_date": "2024-06-18",
  "market_regime": "risk_on",
  "short_term": {
    "equity": "bullish",
    "gold": "neutral",
    "usd": "bullish",
    "rates": "bearish_for_equity"
  },
  "medium_term": {
    "equity": "neutral",
    "gold": "bearish",
    "usd": "bullish"
  },
  "long_term": {
    "cycle_risk": "medium",
    "inflation_pressure": "medium",
    "recession_risk": "low_to_medium"
  },
  "confidence": 0.68,
  "key_factors": [
    "SP500 above 60-day moving average",
    "VIX below 252-day average",
    "DGS10 rising over 20 days",
    "Dollar index strengthening"
  ]
}
```

这样你后面可以统计：

```text
LLM 判断 bullish 时，未来收益率平均是多少？
LLM 判断 risk_off 时，未来最大回撤是多少？
LLM 置信度高的时候，准确率是否更高？
不同 prompt 版本哪个更准？
```

这才是真正可优化的系统。

---

## 7. 推荐你的回测流程

可以这样跑：

```text
1. 选择历史区间
   比如 2015-01-01 到 2025-12-31

2. 每个交易日作为一个 target_date

3. 对每个 target_date：
   只取 target_date 之前的数据

4. 计算技术指标：
   return, change, MA, volatility, correlation, z-score

5. 把特征喂给 LLM

6. 保存 LLM 的结构化判断

7. 用 target_date 之后的真实数据做验证

8. 统计准确率、平均收益、最大回撤、胜率、盈亏比
```

---

## 8. 宏观分析里建议验证哪些结果？

不要只验证“涨跌对不对”。
宏观分析更应该验证这些：

| LLM 判断                   | 验证指标                |
| ------------------------ | ------------------- |
| risk_on / risk_off       | SP500 未来收益、VIX 未来变化 |
| equity bullish / bearish | SP500、NASDAQ 未来收益   |
| gold bullish / bearish   | GOLD 未来收益           |
| dollar strong / weak     | DTWEXBGS 未来收益       |
| rates pressure           | DGS10、DFII10 未来变化   |
| recession risk           | T10Y2Y、VIX、SP500 回撤 |
| volatility risk          | 未来 20/60 日波动率       |

比如：

```text
LLM 说 short_term = risk_on
验证：
- SP500 未来20日收益率是否 > 0
- VIX 未来20日是否下降
- SP500 未来20日最大回撤是否较小
```

---

## 9. 短中长期可以这样定义

| 类型 |           推荐周期 | 验证方式                |
| -- | -------------: | ------------------- |
| 短期 |    5 / 20 个交易日 | 看短期收益率、VIX变化        |
| 中期 |        60 个交易日 | 看趋势是否延续             |
| 长期 | 120 / 252 个交易日 | 看大周期方向、回撤、宏观 regime |

我建议你先用：

```text
短期 = 20d
中期 = 60d
长期 = 120d
```

不要一开始做太多周期。
先把系统跑通，再扩展到 5d、252d。

---

## 10. 还要注意一个坑：宏观数据有修正

市场价格类数据，比如 SP500、VIX、DGS10，通常问题不大。

但宏观数据，比如：

```text
GDP
CPI
就业
非农
```

这些可能会有**数据修正**。

也就是说，今天你看到的 2020 年 GDP 数据，可能不是 2020 年当时市场看到的数据。

如果你以后做严格回测，需要考虑：

```text
point-in-time data
vintage data
```

简单说就是：

> 站在历史某一天，只允许使用当时已经发布的数据版本。

这个对严格宏观回测很重要。
不过你现在先用日频市场数据做第一版，是更合理的。

---

## 11. 我的建议：第一版先这样做

第一版不要做太复杂。
我建议你先做这个 MVP：

```text
数据：
SP500, NASDAQCOM, VIXCLS, DGS2, DGS10, T10Y2Y, DTWEXBGS, GOLD, DFII10

target_date：
每天一个交易日

特征：
ret_20d, ret_60d
chg_20d, chg_60d
MA20, MA60, MA120
vol_20d, vol_60d
zscore_252d
corr_60d

LLM 输出：
risk_on / risk_off / neutral
equity bullish / bearish / neutral
gold bullish / bearish / neutral
usd bullish / bearish / neutral
rates pressure high / medium / low
confidence

验证：
future_ret_20d
future_ret_60d
future_max_drawdown_20d
future_max_drawdown_60d
future_vix_change_20d
```

这样你就可以回答一个很关键的问题：

> LLM 基于这套宏观技术指标，在历史上判断市场环境，到底有没有预测价值？

这比单纯让 LLM 分析今天强很多。

---

一句话总结：

> 是的，应该加 `target_date`。
> 每个 `target_date` 都生成一份“当时视角”的技术指标和 LLM 分析。
> 然后用未来 20 / 60 / 120 天的数据验证它。
> 这就是把 LLM 宏观分析变成可回测、可评估、可优化的系统。
