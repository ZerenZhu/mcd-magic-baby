---
name: mcd-magic-baby
description: 神奇麦麦宝贝 —— 用麦当劳中国官方 MCP 的真实数据，把「今天吃什么」变成一场仪式：先算今日麦麦运势（麦门指数 ★1~5、本命餐品、幸运单品、宜忌吉时），再开麦麦点餐盲盒（SSR/SR/R/N 抽卡、运势越好出货越欧、保底与图鉴）。**「麦麦启动」是开机口令，听到就直接跑运势**。当用户说麦麦启动/今天吃什么/随便/帮我抽/来一卦/今天运势怎么样/麦麦运势/点餐盲盒/抽卡/SSR/神奇麦麦宝贝，或提到麦当劳、McDonald's、金拱门、麦乐送、麦麦省、麦当劳优惠券、积分抽奖、麦当劳派对、团餐接龙、卡路里配餐、定时点餐、月度账单时触发。
---

# 神奇麦麦宝贝（McMagicBaby）

> 今天吃什么？先算一卦，再开个盲盒。
> 玄学是壳子，数据是真的 —— 一切来自麦当劳中国官方 MCP。

## Overview

这是一个「**决策娱乐化**」的麦当劳点餐 Skill：不直接问你要吃什么，而是先用你的真实数据算出一卦（可用券、活动、积分、时段、历史订单），再让抽卡机制替你拍板。

**双主轴**：

| 主轴 | 脚本 | 一句话 |
|---|---|---|
| 🔮 **麦麦运势** | `scripts/fortune.py` | 用真实数据算「麦门指数 ★1~5」，给出本命餐品、今日幸运单品、宜忌、吉时、财气与麦门签 |
| 🎁 **点餐盲盒** | `scripts/blind_box.py` | 抽卡式点餐：SSR/SR/R/N 稀有度、运势联动概率、保底、十连、图鉴 |

两条轴**互相咬合**：运势决定盲盒的手气倍率，盲盒吃运势算出的幸运单品权重。

底层是麦当劳中国官方 MCP（`https://mcp.mcd.cn`，Streamable HTTP，Bearer Token）的 30+ 个工具：菜单与营养、算价、领券、点外卖/到店取/得来速、团餐、积分商城、积分抽奖、派对与品鉴会预约、活动日历、历史订单与取消订单。

其余 8 个实用军师（省钱/减脂/配餐/团餐/抽奖/派对/情报/账单/懒人）作为**辅助工具**保留，按需调用。

## 🔮 主轴一：麦麦运势

```bash
python3 scripts/fortune.py              # 今日一卦
python3 scripts/fortune.py --json       # 机器可读
python3 scripts/fortune.py --refresh    # 忽略当日缓存重算
```

**指数怎么算的**（不是瞎编）：

| 因子 | 权重 | 来源 |
|---|---|---|
| 底分 | 1.5★ | 人人有基础运，不至于天天一星 |
| 可用券数量 | 最多 +1.5★ | `query-my-coupons` |
| 今日有活动 | +1★ | `campaign-calendar` |
| 积分 ≥500 | +0.5★ | `query-my-account`（字段名 `availablePoint`） |
| 时段加成 | +0.5~1★ | `now-time-info`（午晚高峰打折） |
| 日期玄学浮动 | ±0.5★ | 以日期为随机种子 |

**输出**：麦门指数 ★★★★☆（4.2/5）／本命餐品（来自订单缓存）／今日幸运单品／宜忌／吉时／财气（含**3 天内到期券预警**）／积分与本月消费（含**本月将过期积分**预警）／今日麦门签／**🪄 改运指南**。

**改运指南**是这套设计的关键闭环：运势低不是死路，它会告诉你怎么刷 —— 没券就 `coupon_harvest.py` 领（+1.5★）、没活动就 `deal_calendar.py` 蹲下一个、积分不够就记得积分、正处高峰就错峰下单。每条建议都对应一个真实动作。

**关键性质**：同一天结果稳定（日期为随机种子），结果当日缓存到运行时目录，盲盒复用时不会重复拉 MCP。

## 🎁 主轴二：麦麦点餐盲盒

```bash
python3 scripts/blind_box.py                    # 今日一抽（同一天结果一致）
python3 scripts/blind_box.py --mode 犒劳        # 省着吃 / 正常 / 犒劳 / 减脂
python3 scripts/blind_box.py --ten              # 十连抽（保底一张 SR+）
python3 scripts/blind_box.py --seed 1024        # 换种子 = 换一抽
python3 scripts/blind_box.py --collection       # 我的图鉴 + 保底进度
python3 scripts/blind_box.py --rich             # 超预算也不妥协
python3 scripts/blind_box.py --no-lucky         # 关幸运单品加权
python3 scripts/blind_box.py --no-fortune       # 关运势手气加成
```

**稀有度**（按餐品价格/规格定级）：

| 稀有度 | 门槛 | 基础概率 |
|---|---|---|
| ✨SSR | ≥30 元（旗舰堡/大份） | 5% |
| 🌟SR | 18~30 元（主力堡/大份小食） | 15% |
| 🔹R | 9~18 元（小食/中杯饮料） | 35% |
| ▪️N | <9 元（甜品/小杯饮料） | 45% |

**运势联动（核心机制）**：

| 麦门指数 | SSR 倍率 | SR 倍率 | 提示 |
|---|---|---|---|
| ★5 | ×2.2 | ×1.5 | 五星大吉 —— 今天适合赌一把十连 |
| ★4 | ×1.6 | ×1.25 | 手气不错 —— 单抽出货概率明显偏高 |
| ★3 | ×1.0 | ×1.0 | 运势平平 —— 别慌，保底机制兜着你 |
| ★2 | ×0.7 | ×0.85 | 手气偏弱 —— 建议老实点回本命餐品 |
| ★1 | ×0.5 | ×0.7 | 诸事不宜 —— 不如明天再开，或先去领张券 |

**其他机制**：
- **两阶段抽卡**：先按稀有度档位（SSR 5% / SR 15% / R 35% / N 45%，再乘运势倍率）抽档，再在档内抽具体餐品 —— 概率与标注一致
- **单抽成套**：每个分类各抽一件，绝不会抽到两个汉堡
- **战利品保护**：超预算降级时，最稀有的那一件不会被换掉（十连出的 SSR 不会被剥夺）
- **十连**：十张卡，单品最多重复 2 次，保底一张 SR+，再从卡里挑出「能吃的一套」推荐下单
- **保底**：连续 5 抽未出 SR+，下一抽强制出货
- **幸运单品**：今日幸运单品权重 ×4
- **预算护栏**：抽贵了自动向钱包低头（同组换便宜的，实在不行割掉配角保住主堡），`--rich` 可拒绝妥协
- **图鉴**：`--collection` 看稀有度分布与保底进度，历史写在运行时目录，不入包

**推荐仪式**：`fortune.py` 看运势 → `blind_box.py` 让命运拍板 → 满意就走省钱军师下单。

> 预算提示：真实门店菜单以「套餐/件套」为主，正常模式三件通常 ¥40~60，`preferences.md` 的 `box_budget` 建议设 45~60（默认 35 会经常触发降级）。

## 首次使用：三步配置

1. **配 Token**：`python3 scripts/setup_token.py --token <TOKEN>` → 写入运行时目录的 `.env`（默认 `~/.workbuddy/mcd-magic-baby/.env`，权限 600）。获取：open.mcd.cn → 控制台 → 激活并复制 MCP Token。
   自动查找顺序：环境变量 `MCD_MCP_TOKEN` → skill 目录 `.env` → 运行时目录 `.env` → `~/.workbuddy/.env` → `~/.workbuddy/mcp.json`。
2. **自检**：`python3 scripts/doctor.py`（Token / 连通性 / 偏好完整度）。
3. **补偏好**：`preferences.md` 里填忌口、预算、`box_mode`（盲盒默认模式）、`lucky_boost`；下单还需默认地址（`delivery-query-addresses` 查得）。

> 运行时数据目录默认 `~/.workbuddy/mcd-magic-baby/`（Token、订单缓存、运势缓存、盲盒图鉴、账单），可用 `MCD_HOME` 覆盖；若检测到旧目录 `mcd-fortune-box` / `mcd-strategist` 会自动沿用，老配置不丢。

## 🔴 安全红线

1. 绝不用 Read/Edit 打开 `.env`，绝不要把 Token 读进对话、写进参数或任何 md/py/json 文件。
2. 任何 `create-order` / `party-order-create` / `mall-create-order` / **积分抽奖** / 取消订单前，必须列出完整明细并**取得明确确认**。脚本侧：`--confirm` 才是真正的执行开关。
3. 打包/开源前必须跑 `scripts/safe_package.py`（排除 `.env`、缓存、`__pycache__` + 密钥扫描）。**不要用上游 `package_skill.py`**。
4. 金额单位为「分」，展示换算为元；限流 600 次/分钟（429 已内置一次退避重试）。
5. 地址/手机号/订单明细属隐私：展示截断；缓存只存「时间/金额/商品」且写在 Skill 目录之外。

## 🚀 开机口令：麦麦启动

用户只要输入 **「麦麦启动」**（或「麦麦 启动」「启动麦麦」），就立即执行：

```bash
python3 scripts/fortune.py
```

即**直接开启麦麦运势**，并把结果原样呈现给用户；随后追问一句要不要接着开盲盒：

> 要开盲盒吗？`python3 scripts/blind_box.py`（运势已算好，手气加成自动生效）

若 Token 未配置导致失败，转「首次使用：三步配置」引导，不要让用户自己排查。

## 意图路由

| 用户意图 | 走哪条 | 入口 |
|---|---|---|
| **"麦麦启动"** | 🔮 运势（开机） | `fortune.py` → 追问是否开盲盒 |
| "今天吃啥/随便/帮我抽/来一卦" | 🔮 运势 → 🎁 盲盒 | `fortune.py` → `blind_box.py` |
| "今天运势怎么样" / "麦麦运势" | 🔮 运势 | `fortune.py` |
| "十连！" / "看图鉴" / "我出过 SSR 吗" | 🎁 盲盒 | `blind_box.py --ten` / `--collection` |
| "有什么券/便宜点" | 💰 省钱 | `coupon_harvest.py` → `calculate-price` → 确认后 `create-order` |
| "减脂期能吃啥/500 大卡配一顿" | 🥗 减脂 | `recommend.py --kcal 500` |
| "40 块 800 大卡怎么吃最划算" | 🎯 配餐 | `meal_solver.py --budget 40 --kcal 800 --goal protein` |
| 群接龙/团餐 AA | 👥 团餐 | `group_order.py --file 接龙.txt` |
| "积分能抽奖吗/我中了啥" | 🎡 抽奖 | `lottery.py` / `--my` / `--draw 1 --confirm` |
| "给孩子办麦当劳生日派对" | 🎉 派对 | `party_book.py` 选商品拿 spuId → `--spu` → 城市→门店→日期→场次→`--confirm` |
| "最近有什么羊毛" | 📅 情报 | `deal_calendar.py --days 7` |
| "每天 11:30 自动点套餐" | ⏰ 懒人 | `auto_order.py`（需 `auto_order_enabled: true`） |
| "这个月吃了多少" | 🧾 账单 | `monthly_report.py [YYYY-MM]` |
| "帮我取消订单" | — | 直接调 `cancel-order`（先确认订单号） |

## 辅助工作流要点

**💰 省钱**：`coupon_harvest.py` 领券并按到期日汇总 → `query-store-coupons` → `query-meals` / `query-meal-detail` 选品 → `calculate-price` 带券比价 2~3 组 → 确认 → `create-order` → 支付链接交用户 → `query-order` 跟踪。

**🥗 减脂**：`list-nutrition-foods` + 偏好忌口，按「贴近预算 + 蛋白质优先 − 钠超标」排序。

**🎯 配餐**：菜单价格 + 营养表，预算与热量双约束下背包求解（protein / cheap / value）。

**👥 团餐**：解析 `名字: 餐品x数量` 接龙 → 汇总 → 匹配价格 → AA 分账（含配送费均摊）。**绝不自动下单**。

**🎡 抽奖**：`query-lottery-info` 看奖品池与「欧气值」、`query-my-account` 看积分、`query-my-prizes` 看中奖；`--draw N --confirm` 才真抽。

**🎉 派对**：`query-party-city` → `query-party-store` → `query-partystore-date` → `query-partystore-session` → `party-order-create --confirm`，逐级引导。

**📅 情报**：`campaign-calendar` + 券 + 积分 + 抽奖状态 → 「今天该薅什么」日历。

**⏰ 懒人**：先 `--dry-run`；护栏为显式开关 + 预算上限 + 当日幂等锁。

**🧾 账单**：`order-list` 拉历史 → 增量缓存 → Markdown 报告（总花费、客单价、Top 5、麦门成色评级）。

## 实现备注：真实 MCP 的三个坑（已全部适配）

1. **响应格式不统一**：`query-meals` 返回 JSON，但 `query-my-coupons` / `campaign-calendar` 返回 Markdown，`list-nutrition-foods` 返回类 CSV 文本。统一走 `common.parse_menu / parse_coupons / parse_activities / parse_nutrition / parse_account`。
2. **必填参数**：`query-meals` 缺 `orderType`/`beType` 直接报「缺少参数」，`storeCode` 必须全数字；派对系列工具要先从商城拿 `spuId`。统一走 `common.store_args()`。
3. **单位与字段名**：菜单/订单金额是「元」的字符串（`currentPrice: "15.5"`、`realTotalAmount: "20.48"`），算价接口是「分」；积分字段是单数 `availablePoint`。统一走 `common.to_yuan()`。

改动任何脚本前先读 `scripts/common.py` 的适配层，不要各自解析原始返回。

## 退出码

`0` 成功 | `1` MCP/网络错误 | `2` 缺 Token 或偏好未配置 | `3` 触发预算护栏跳过下单
