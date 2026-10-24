# MCP 集成说明（MCP_INTEGRATION）

> 本文件说明「神奇麦麦宝贝」如何真实使用麦当劳中国官方 MCP 能力。
> 所有能力均来自官方 MCP Server，未使用任何模拟数据或私有接口。

## 一、接入的 MCP Server

| 项 | 值 |
|---|---|
| 官方仓库 | https://github.com/M-China/mcd-mcp-server |
| 版本 | v1.0.9 |
| 服务地址 | `https://mcp.mcd.cn`（Streamable HTTP，JSON-RPC 2.0） |
| 鉴权 | HTTP Header `Authorization: Bearer <MCP_TOKEN>` |
| Token 获取 | https://open.mcd.cn → 登录 → 控制台 → 激活 → 复制 MCP Token |
| 限流 | 600 次/分钟（本项目在 `mcp_client.py` 内对 429 做一次退避重试） |
| 配置文件 | `mcp-config.example.json`（仅含 `${MCD_MCP_TOKEN}` 占位符，无真实凭证） |

本项目同时支持两种接入方式：

1. **脚本直连**（默认）：`scripts/mcp_client.py` 自己实现 JSON-RPC over Streamable HTTP，仅用 Python 标准库，Token 走 `.env` / 环境变量。
2. **Agent 直连**：在 WorkBuddy 中按 `mcp-config.example.json` 配好连接器后，由 Agent 直接调用同名工具，脚本与文档中的工具名完全一致。

## 二、实际使用的 MCP Tools

### 脚本内直接调用（22 个）

| Tool | 用途 | 用在哪个玩法 |
|---|---|---|
| `now-time-info` | 当前时间/星期/时段 | 🔮 麦麦运势（时段加成） |
| `query-my-coupons` | 我的优惠券与到期日 | 🔮 运势（财气）／💰 省钱／📅 情报 |
| `query-my-account` | 积分余额与将过期积分 | 🔮 运势／🎡 抽奖／📅 情报 |
| `campaign-calendar` | 营销活动日历 | 🔮 运势／📅 情报 |
| `list-nutrition-foods` | 餐品营养（能量/蛋白质/脂肪/钠） | 🔮 运势（幸运单品池）／🎁 盲盒／🥗 减脂／🎯 配餐 |
| `query-meals` | 门店菜单与价格 | 🎁 盲盒／🎯 配餐／👥 团餐 |
| `query-meal-detail` | 单品详情 | 💰 省钱（选品） |
| `calculate-price` | 带券算价比价 | 💰 省钱 |
| `create-order` | 创建外卖/到店取/得来速订单 | 💰 省钱／⏰ 懒人 |
| `order-list` | 历史订单 | 🧾 账单 |
| `auto-bind-coupons` | 一键领取「麦麦省」可领券 | 💰 省钱 |
| `query-store-coupons` | 门店可用券 | 💰 省钱 |
| `query-meal-assistance` | 企业团餐助餐服务 | 👥 团餐 |
| `query-lottery-info` | 积分抽奖活动与奖品池 | 🎡 抽奖 |
| `draw-lottery` | 执行积分抽奖 | 🎡 抽奖 |
| `query-my-prizes` | 我的中奖记录 | 🎡 抽奖 |
| `mall-points-products` | 积分商城商品（含派对/品鉴会 spuId） | 🎉 派对 |
| `query-party-city` | 可参与城市 | 🎉 派对 |
| `query-party-store` | 城市下活动门店 | 🎉 派对 |
| `query-party-store-date` | 门店可预约日期 | 🎉 派对 |
| `query-party-store-session` | 日期下场次 | 🎉 派对 |
| `party-order-create` | 创建主题活动订单 | 🎉 派对 |

### Agent 按意图路由直接调用（4 个）

| Tool | 用途 |
|---|---|
| `query-order` | 订单状态跟踪 |
| `cancel-order` | 取消订单 |
| `delivery-query-addresses` | 查询收货地址 ID（下单前的地址准备） |
| `mall-create-order` | 积分商城下单 |

合计 **26 个官方 Tools**。

## 三、调用流程

### 🔮 主轴一：麦麦运势

```
now-time-info            → 日期/星期/时段
query-my-coupons         → 可用券数、3 天内到期券
campaign-calendar        → 今日是否有活动
query-my-account         → 积分余额、本月将过期积分
list-nutrition-foods     → 幸运单品候选池
本地订单缓存(非 MCP)      → 本命餐品、本月消费
        ↓
  加权算出「麦门指数 ★1~5」→ 当日缓存 → 供盲盒复用手气加成
```

### 🎁 主轴二：麦麦宝贝盲盒

```
query-meals(storeCode, orderType, beType, beCode)  → 门店菜单树 → 摊平成 [{分类,名称,价格}]
list-nutrition-foods                                → 热量/蛋白质
读取当日运势缓存                                     → 手气倍率 + 幸运单品
        ↓
两阶段抽卡：先抽稀有度档位(SSR 5%/SR 15%/R 35%/N 45% × 运势倍率) → 再在档内抽餐品
        ↓
预算护栏 → 输出「今天吃这套」
```

### 💰 省钱下单链路

```
auto-bind-coupons → query-my-coupons → query-store-coupons
→ query-meals / query-meal-detail → calculate-price（带券算价 2~3 组比价）
→ 【用户确认】→ create-order → 支付链接交用户 → query-order 跟踪
```

> 「用户确认」是硬闸门：脚本侧 `--confirm` 才是真正执行开关，AI 侧必须先列明细再取得明确同意。

## 四、适配真实 MCP 时踩到并解决的三个坑

这部分是本项目对官方能力的实质适配工作，均已在 `scripts/common.py` 的适配层中固化：

1. **响应格式不统一**：`query-meals` 返回 JSON，而 `query-my-coupons` / `campaign-calendar` 返回 Markdown 文本，`list-nutrition-foods` 返回类 CSV 文本。
   → 统一适配层：`common.parse_menu / parse_coupons / parse_activities / parse_nutrition / parse_account`。
2. **必填参数与真实工具名**：`query-meals` 缺 `orderType` / `beType` 会直接报「缺少参数」，`storeCode` 必须全数字；派对系列真实工具名是 `query-party-store-date` / `query-party-store-session`，且必须先用 `mall-points-products` 取到 `spuId` 才能往下走。
   → 统一由 `common.store_args()` 构造参数；派对流程按真实工具名重写。
3. **单位与字段名**：菜单/订单金额是「元」的字符串（`currentPrice: "15.5"`、`realTotalAmount: "20.48"`），算价类接口是「分」的整数；积分字段是单数 `availablePoint`。
   → 统一 `common.to_yuan()` 归一化，展示一律换算为元。

另修掉一个隐蔽缺陷：偏好解析原先把纯数字转成 float，导致 `storeCode` 变成 `1990518.0`、超长 `addressId` 丢失精度（会把订单发错地址），现改为纯整数走 `int`。

## 五、业务价值

| 维度 | 价值 |
|---|---|
| 决策成本 | 把「今天吃什么」这一高频低价值决策，压缩成一条口令（麦麦启动）+ 一次抽卡 |
| 平台活跃 | 运势与盲盒均由真实券/活动/积分/订单驱动，用户要提升结论就得回来领券、对账、攒图鉴 |
| 优惠券核销 | 「财气」主动预警 3 天内到期券，「改运指南」直接引导去领券，把曝光转成核销动作 |
| 客单价与配餐 | 预算 + 热量双约束的配餐求解，让用户在既定预算内配出更合理的组合 |
| 场景拓展 | 覆盖团餐 AA、企业助餐、生日派对/品鉴会预约、积分抽奖、月度账单等官方能力中被低频使用的部分 |
| 安全合规 | 下单/抽奖/取消订单一律二次确认；Token 只走 `.env`（600 权限）且不进包；订单缓存外置且不含地址手机号 |
