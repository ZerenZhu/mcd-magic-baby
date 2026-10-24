# 麦当劳中国 MCP 工具全表（官方 README v1.0.9）

> 神奇麦麦宝贝（mcd-magic-baby）· 数据源参考
> 双主轴用到的工具：运势 = `now-time-info` + `query-my-coupons` + `campaign-calendar` + `query-my-account` + `list-nutrition-foods` + 订单缓存；盲盒 = `query-meals` + `list-nutrition-foods` + 运势结果。

> 接入地址：`https://mcp.mcd.cn`（Streamable HTTP，JSON-RPC 2.0）
> 鉴权：`Authorization: Bearer <Token>`；Token 由本 Skill 自动从环境变量 / .env / mcp.json 读取
> 限流：每 Token 600 次/分钟，超限返回 429（调用器已内置一次退避重试）
> 错误码：401 Token 无效/过期；429 限流
> 官方仓库：https://github.com/M-China/mcd-mcp-server | 控制台：https://open.mcd.cn/mcp

## 门店与地址

| 工具 | 说明 |
|---|---|
| delivery-query-addresses | 已创建的配送地址列表（下单第一步） |
| delivery-create-address | 新增配送地址 |
| delivery-query-stores | 收货地址附近可配送门店 |
| query-nearby-stores | 指定地址附近的麦当劳餐厅 |

## 菜单与价格

| 工具 | 说明 |
|---|---|
| query-meals | 当前门店可售菜单（分类、餐品编码、标签） |
| query-meal-detail | 餐品详情：套餐组成、可替换选项 |
| calculate-price | 商品金额、配送费、优惠额、应付总价 |

## 下单与订单

| 工具 | 说明 |
|---|---|
| create-order | 创建订单（外送 / 到店取餐 / 得来速 / 团餐），返回订单详情与支付链接 |
| cancel-order | 取消订单 |
| query-order | 订单详情、状态、配送进度 |
| order-list | 近期到店/外送历史订单 |
| query-meal-assistance | 企业团餐场景的助餐服务 |

## 优惠券

| 工具 | 说明 |
|---|---|
| query-store-coupons | 当前门店可用券 |
| available-coupons | 麦麦省可领券列表 |
| auto-bind-coupons | 一键领取全部可领券 |
| query-my-coupons | 我的优惠券 |

## 积分 · 商城 · 抽奖

| 工具 | 说明 |
|---|---|
| query-my-account | 积分账户：可用/累计/冻结/即将过期 |
| mall-points-products | 商城可兑换/购买商品列表 |
| mall-product-detail | 商城商品详情 |
| mall-create-order | 积分兑换下单，返回订单号与券码 |
| mall-order-list | 商城近一年订单列表 |
| mall-order-detail | 商城订单详情 |
| query-lottery-info | 积分抽奖活动信息（状态、奖品池、消耗规则） |
| draw-lottery | 执行一次积分抽奖（**消耗积分，需用户确认**） |
| query-my-prizes | 我的中奖记录 |

## 主题活动（派对 / 品鉴会）

> 真实流程：**先有 spuId**（`mall-points-products` 里的品鉴会/派对商品）→ 城市 → 门店 → 日期 → 场次 → 下单。
> 注意官方工具名是 `query-party-store-date` / `query-party-store-session`（中间有短横线）。

| 工具 | 必填参数 | 说明 |
|---|---|---|
| mall-points-products | — | 找派对/品鉴会商品，取 spuId（字段 spuName / catName / price） |
| query-party-city | spuId | 可参与城市（返回 code/经纬度） |
| query-party-store | spuId, code | 指定城市下的活动门店 |
| query-party-store-date | spuId, storeCode | 门店可预约日期 |
| query-party-store-session | spuId, storeCode, dateStr | 指定日期的场次（余位 leftNum） |
| party-order-create | code, spuId, storeCode, dateStr, id, count | 创建主题活动订单 |

## 营养与情报

| 工具 | 说明 |
|---|---|
| list-nutrition-foods | 餐品营养：**返回类 CSV 文本**（`[160]{productName,energyKcal,...}:` 逐行） |
| campaign-calendar | 当月营销活动日历（**Markdown**，`#### 日期` + `**活动标题**`） |
| now-time-info | 当前完整时间信息 |

## ⚠️ 响应格式差异（已在 common.py 统一适配）

| 工具 | 真实格式 | 适配函数 |
|---|---|---|
| query-meals | JSON：`data.categories[].meals[].code` + `data.meals{code:详情}`，价格 `currentPrice` 是**元**的字符串 | `common.parse_menu()` |
| list-nutrition-foods | 类 CSV 文本 | `common.parse_nutrition()` |
| query-my-coupons | Markdown（`# 您的优惠券列表` + `## 券名`） | `common.parse_coupons()` |
| campaign-calendar | Markdown | `common.parse_activities()` |
| query-my-account | JSON，字段是单数 `availablePoint` | `common.parse_account()` |
| order-list | JSON：`data.list[]`，金额字段 `realTotalAmount`（元字符串） | `monthly_report.py` |

**必填参数坑**：`query-meals` 必须传 `storeCode` + `orderType`(1到店/2外送) + `beType`(1到店取/2麦乐送/5得来速/6团餐)，
外送还需 `beCode`；`storeCode` 必须全数字 → 由 `common.store_args()` 统一构造（含 preferences 回落）。
价格单位：菜单/订单是**元的字符串**，算价接口是**分** → 用 `common.to_yuan()` 归一化。

## 脚本速查

```bash
# —— 双主轴 ——
python3 scripts/fortune.py                       # 🔮 麦麦运势（麦门指数/幸运单品/宜忌/吉时）
python3 scripts/fortune.py --refresh             # 忽略当日缓存重算
python3 scripts/blind_box.py                     # 🎁 今日一抽（运势决定手气倍率）
python3 scripts/blind_box.py --mode 放纵         # 省着吃/正常/放纵/减脂
python3 scripts/blind_box.py --ten               # 十连抽（保底 SR+）
python3 scripts/blind_box.py --seed 1024         # 换种子 = 换一抽
python3 scripts/blind_box.py --collection        # 稀有度图鉴与保底进度
python3 scripts/blind_box.py --rich              # 超预算也不妥协

# —— 配置与辅助军师 ——
python3 scripts/setup_token.py --token <TOKEN>   # 配 Token（.env, 600）
python3 scripts/doctor.py                        # 自检
python3 scripts/coupon_harvest.py                # 领券 + 我的券
python3 scripts/recommend.py --kcal 500          # 减脂搭配
python3 scripts/meal_solver.py --budget 40 --kcal 800 --goal value   # 配餐求解
python3 scripts/group_order.py --file 接龙.txt   # 团餐接龙 AA
python3 scripts/lottery.py --draw 1 --confirm    # 积分抽奖
python3 scripts/party_book.py                    # 派对预约：先挑商品拿 spuId
python3 scripts/party_book.py --spu 8516 --city 340800   # 逐级：城市→门店→日期→场次
python3 scripts/deal_calendar.py --days 7        # 薅羊毛日历
python3 scripts/auto_order.py --dry-run          # 自动下单预演
python3 scripts/monthly_report.py 2026-10        # 月度账单
python3 scripts/safe_package.py                  # 安全打包（排除 .env + 密钥扫描）
```

## 目录约定

| 位置 | 内容 | 能否分享 |
|---|---|---|
| `~/.workbuddy/mcd-magic-baby/.env`（旧版 `mcd-fortune-box` / `mcd-strategist` 沿用） | Token | ❌ 绝不 |
| 同目录 `order_cache.json`、`fortune_cache.json`、`box_history.json`、`reports/`、`auto_order_log.json` | 订单缓存、运势缓存、盲盒图鉴、账单、幂等锁 | ❌ 私人数据 |
| `preferences.md` | 忌口/预算/地址 ID | ⚠️ 不写手机号与详细门牌 |
| Skill 其余文件 | 代码与说明 | ✅ 经 safe_package.py 打包后可开源 |
