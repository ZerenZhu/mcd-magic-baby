# WorkBuddy 开发对话上下文

> 本文件用于核验本项目真实使用腾讯 WorkBuddy 智能体开发。
> 以下为 2026-10-24 开发「神奇麦麦宝贝」过程中的对话记录（节选，已脱敏，不含任何真实 Token / 手机号 / 地址）。

- **开发工具**：WorkBuddy（Agent 模式）
- **技能最终安装位置**：`~/.workbuddy/skills/mcd-magic-baby/`
- **运行时数据目录**：`~/.workbuddy/mcd-magic-baby/`（Token、订单缓存、账单、图鉴，均不入库）

---

## 1. 需求提出与创意定型

**用户**：基于麦当劳的 MCP 开发一个有创意的 Skill。可以参考这个思路，也可以自己发挥，起一个特别吸引人的名称：
食堂点餐助手（SKILL.md 入口路由 / preferences.md 共享偏好 / scripts 下 recommend、auto_order、group_order、monthly_report / order_cache.json 本地缓存）。

**WorkBuddy**：先联网确认官方能力（麦当劳中国官方 MCP，open.mcd.cn / mcp.mcd.cn，覆盖菜单、营养、算价、下单、优惠券、积分商城等 20+ 工具），再决定不只做「食堂点餐」，而是一个 Skill 覆盖多条工作流。随后用 `init_skill.py` 初始化脚手架，命名 **「麦门军师」**，落地四条工作流：省钱 / 减脂 / 懒人 / 账单，并用 `package_skill.py` 校验打包。

**产出**：SKILL.md（意图路由）、preferences.md（共享画像）、references/tools.md、scripts/{mcp_client,recommend,coupon_harvest,auto_order,monthly_report}.py、data/order_cache.json。

---

## 2. Token 改 .env + 安全审查

**用户**：token 用 .env 根据用户的 mcp token 添加配置，并且不上传，对目前的 skill 方案做安全审查和用户使用角度的优化。

**WorkBuddy**：先确认本机尚无麦当劳 Token 配置，并在审查中发现一个高风险问题 —— **上游 `package_skill.py` 会把目录里所有文件（含 `.env`）直接打进 zip，等于外泄 Token**。据此按「代码可分享 / 私密数据不进包」重构：

- Token 解析链：环境变量 `MCD_MCP_TOKEN` → skill/.env → 运行时 .env → `~/.workbuddy/.env` → `~/.workbuddy/mcp.json`
- 新增 `scripts/setup_token.py`（写入 / `--status` 脱敏显示 / `--remove`）、`scripts/doctor.py`（环境自检）
- 自研 `scripts/safe_package.py`：排除 `.env` / 缓存 / `__pycache__`，并做密钥正则扫描，**命中即中止打包**
- 隐私数据外置到 `~/.workbuddy/mcd-strategist/`（可用 `MCD_HOME` 覆盖），永不入包
- `auto_order.py` 加当日幂等锁与预算护栏；`preferences.md` 改为英文 key + 中文注释

**验证**：故意把 `.env` 放进技能目录 → 打包后 zip 内无此文件；故意把 Token 明文写进普通文件 → 打包中止并报出文件名。同时探明官方端点应为 `https://mcp.mcd.cn`（根路径，之前的 `/mcp` 会 404）。

---

## 3. 按官方仓库扩充玩法

**用户**：根据麦当劳 mcp 的功能新增一些特别有意思的功能（附 https://github.com/M-China/mcd-mcp-server）。

**WorkBuddy**：克隆官方仓库（v1.0.9，30+ 工具），发现此前未覆盖的**积分抽奖、麦当劳派对/品鉴会预约、团餐助餐、附近门店、取消订单、商城订单**等能力，据此新增 6 个玩法脚本，Skill 从 4 条工作流扩到 10 条。用模拟数据逐个跑通，并修正工具名（`query-meal-detail` 而非 `meal-detail` 等）、为官方 600 次/分钟限流加 429 退避重试、为菜单「分类→餐品」树结构加摊平逻辑。

**产出**：`blind_box.py`、`meal_solver.py`、`group_order.py`、`lottery.py`、`party_book.py`、`deal_calendar.py`。

---

## 4. 麦麦运势 + 点餐盲盒

**用户**：添加麦麦运势分析 和 麦麦点餐盲盒。

**WorkBuddy**：先把「今天吃什么」做成玄学决策 —— `fortune.py` 用真实券/活动/积分/时段/历史订单算「麦门指数 ★1~5」，以日期为随机种子保证同一天结果稳定，并导出 `pick_lucky()` 供盲盒复用。随后把 `blind_box.py` 重写为抽卡：SSR/SR/R/N 稀有度、单抽成套、十连、连续 5 抽保底、图鉴。

实测修掉的坑：十连出现重复单品、图鉴只记最佳稀有度导致 R/N 恒为 0、单抽抽到两个汉堡（「主食」「汉堡」同分类重复）、减脂模式因此超热量。

---

## 5. 为主轴重新设计 + 真实 MCP 适配

**用户**：把 skill 的名称和介绍以麦麦运势和点餐盲盒为主重新描述和设计。

**WorkBuddy**：改名 **麦麦玄学机（mcd-fortune-box）**，介绍以双主轴重写，并把运势结果与盲盒手气打通（★5 → SSR 权重 ×2.2）。

因为本机 Token 已配置，**改用真实 MCP 跑了一遍，暴露出「脚本其实都拿不到数据」的三个致命坑**，全部修掉：

1. 响应格式不统一（菜单是 JSON，券/活动是 Markdown，营养是类 CSV）→ 新增适配层
2. `query-meals` 必须传 `storeCode + orderType + beType`（外送还要 `beCode`）；派对工具真名是 `query-party-store-date` / `-session`，且须先由 `mall-points-products` 取 `spuId`
3. 菜单/订单金额是「元」字符串（`currentPrice: "15.5"`），算价是「分」；积分字段是单数 `availablePoint`

另修掉一个隐蔽炸弹：`load_preferences` 把纯数字转成 float，导致 `storeCode` 变成 `1990518.0`、超长 `addressId` 直接丢精度（下单会发错地址）。

**真实数据实测输出**：

```
🔮 麦麦运势 · 星期六｜晚餐时段
麦门指数 ★★★★★（5.0/5）｜本命餐品 龙焰鸡腿堡两件套
财气 可用券 10 张，其中 1 张 3 天内到期｜积分 1004.6｜本月已消费 ¥68.86

🎁 盲盒：🔹R 汉堡包 ¥15 + 🔹R 薄皮焦香V翅 ¥16.5 + 🔹R 鲜萃冰咖 ¥13 = ¥44.50
```

十连出过 SSR「精选单人餐四件套」；团餐 AA、月度账单、抽奖池（24 积分/次）、派对城市列表均跑通。

---

## 6. 改名

**用户**：名字改为神奇麦麦宝贝怎么样？

**WorkBuddy**：判断名字合适（把抽卡、图鉴、稀有度一次说清，并提醒避开「宝可梦/Pokémon」商标，只用「神奇宝贝」通用说法）。

**用户**：只是名字改了，里面的实现还保持不变。

**WorkBuddy**：严格按此执行 —— 仅替换展示串与路径串，逻辑/概率/护栏一律未动。目录改 `mcd-magic-baby`，并把历史运行时目录兼容链扩为 `mcd-fortune-box → mcd-strategist`，确保已有 Token 不失效（`doctor.py` 实测仍连通）。

---

## 7. 开机口令

**用户**：新增输入麦麦启动，就开启麦麦运势。

**WorkBuddy**：在 SKILL.md 的 description 触发词加入「麦麦启动」并标注为开机口令，意图路由表新增首行，并新增「🚀 开机口令：麦麦启动」小节，明确输入该口令即执行 `fortune.py`，随后追问是否开盲盒。脚本逻辑未改。

---

## 8. 参赛材料

**用户**：根据挑战赛项目里的挑战规则给 Skill 添加必要的文件和补充资料。

**WorkBuddy**：逐条比对 `activityGuidelines.md` 与 `README.md` 中的参赛文件要求，补齐：

| 文件 | 状态 | 说明 |
|---|---|---|
| README.md | 新增 | 项目介绍 / 安装方法 / 使用示例 / 目标用户 |
| CONTEST_DECLARATION.md | 原样复制 | 与官方文件逐字节一致（`cmp` 校验通过） |
| MCP_INTEGRATION.md | 新增 | 26 个真实 Tool、调用流程、踩坑与业务价值 |
| mcp-config.example.json | 新增 | 脱敏配置，仅含 `${MCD_MCP_TOKEN}` 占位符 |
| workbuddy.md | 新增 | 本文件 |
| 源代码 | 已有 | scripts/ 下 16 个脚本 + SKILL.md / preferences.md / references/ |

---

## 关键工具使用痕迹（WorkBuddy 侧）

- 文件读写与批量编辑：Read / Write / Edit / Glob / Grep
- 命令执行：Bash（`git clone` 官方仓库、`py_compile` 编译校验、`cmp` 逐字节校验、`unzip` 包内容核对、`safe_package.py` 打包）
- 联网获取：WebSearch / WebFetch（官方 MCP 仓库 README、接入地址与鉴权方式）
- 技能管理：skill-creator 脚手架（`init_skill.py` / `package_skill.py`）、skill_management 列表核验
- 结果呈现：present_files（SKILL.md、脚本、可分发 zip）
