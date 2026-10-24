# 🍔 神奇麦麦宝贝（McMagicBaby）

> 今天吃什么？先算一卦，再开个盲盒。
> **「麦麦启动」** 是它的开机口令 —— 输入这四个字，直接开今日麦麦运势。
>
> GitHub：https://github.com/ZerenZhu/mcd-magic-baby（觉得有意思的话，欢迎点个 ⭐，本次比赛排名以 Star 数为依据）

一个基于**麦当劳中国官方 MCP** 的点餐 Skill。玄学是壳子，数据是真的：运势不是随机数，而是用你的**真实可用券、活动、积分、时段与历史订单**算出来的；盲盒的每一只「宝贝」都是**真实门店菜单里的餐品**，带真实价格与热量。

```
🔮 麦麦运势 · 星期六｜晚餐时段
麦门指数  ★★★★★（5.0/5）
本命餐品  龙焰鸡腿堡两件套
幸运单品  蜜汁快乐
今日宜忌  宜带券下单，能省则省｜忌临时加购薯条，钠容易爆表
吉时      17:30 前下单，赶上第一波现炸
财气      可用券 10 张，其中 1 张 3 天内到期，优先用掉
积分      1004.6｜本月已消费 ¥68.86｜⚠️ 84.0 积分本月过期
今日麦门签：小吉 · 优惠券会乖乖生效
```

---

## 一、项目介绍

### 它解决什么问题

「今天吃什么」是一个每天都要做、却没人愿意做的小决策。本项目不直接问你想吃什么，而是把决策变成一场有仪式的游戏：

1. **先算一卦** —— 用你的真实麦当劳账号数据算出今日「麦门指数 ★1~5」，顺带告诉你本命餐品、今日幸运单品、宜忌、吉时，以及**哪些券 3 天内要过期**。
2. **再开个盲盒** —— 抽卡式点餐，SSR / SR / R / N 四档稀有度，**运势越好出货越欧**（★5 时 SSR 概率 ×2.2），带保底、十连与图鉴。
3. **不满意就问它要方案** —— 省钱、减脂、配餐、团餐 AA、积分抽奖、生日派对预约、月度账单，共 10 条工作流随时可用。

### 两条主轴互相咬合

运势决定盲盒的手气倍率，盲盒吃运势算出的幸运单品权重（×4）。先算运势再抽卡，结果会明显不同 —— 这就是设计上的钩子。

### 完整能力（10 条工作流）

| | 玩法 | 一句话 |
|---|---|---|
| 🔮 | **麦麦运势** | 真实数据算麦门指数，含 3 天内到期券 / 将过期积分预警与「改运指南」 |
| 🎁 | **点餐盲盒** | SSR/SR/R/N 抽卡，运势联动、保底、十连、图鉴、预算护栏 |
| 💰 | 省钱军师 | 一键领券 → 带券算价比价 → 确认后下单 |
| 🥗 | 减脂军师 | 按卡路里预算搭配，蛋白质优先、钠不过量 |
| 🎯 | 配餐军师 | 预算 + 热量双约束背包求解（每元蛋白最高） |
| 👥 | 团餐军师 | 群接龙解析 → 汇总清单 → AA 分账（含配送费均摊） |
| 🎡 | 抽奖军师 | 积分抽奖池与欧气值，`--confirm` 才真抽 |
| 🎉 | 派对军师 | 麦当劳派对 / 品鉴会逐级预约引导 |
| 📅 | 情报军师 | 活动 + 券到期 + 积分过期 → 「今天该薅什么」 |
| 🧾 | 账单军师 | 月度账单 + 麦门成色评级（路人→常客→信徒→长老→本门） |
| ⏰ | 懒人军师 | 定时自动点餐（四道护栏 + 当日幂等锁） |

---

## 二、目标用户

- **每天纠结吃什么的人** —— 把决策交给一只麦麦宝贝，比刷外卖 App 快
- **麦当劳常客 / 麦门信徒** —— 想把券、积分、活动日历真正用起来，而不是领了就忘
- **控卡 / 减脂人群** —— 麦当劳不是不能吃，是得会配（有热量与蛋白质约束的求解）
- **团餐发起人 / 行政** —— 群接龙一贴，自动汇总清单并 AA 分账
- **想送礼的家长** —— 生日派对/品鉴会预约不用翻官网
- **开发者** —— 想看看「MCP 真实接入要踩哪些坑」的可运行参考（见 `MCP_INTEGRATION.md` 第四节）

---

## 三、安装方法

### 前置条件

1. 在 https://open.mcd.cn 登录 → 控制台 → 激活 → **复制 MCP Token**
2. Python 3（仅用标准库，无需 pip install）

### 步骤

```bash
# 1. 放到 WorkBuddy 的用户级技能目录（也可用本项目自带的 zip 解压）
git clone https://github.com/ZerenZhu/mcd-magic-baby.git ~/.workbuddy/skills/mcd-magic-baby

# 2. 配 Token（写入 ~/.workbuddy/mcd-magic-baby/.env，权限 600）
cd ~/.workbuddy/skills/mcd-magic-baby
python3 scripts/setup_token.py --token <你的MCP_TOKEN>

# 3. 自检（Token / 连通性 / 偏好完整度）
python3 scripts/doctor.py
```

看到 `全部就绪 🍟` 即可开玩。

<details>
<summary>在 WorkBuddy 中作为连接器接入（可选）</summary>

复制 `mcp-config.example.json` 的内容，把 `${MCD_MCP_TOKEN}` 换成真实 Token，粘贴到
WorkBuddy → 左侧边栏【专家·技能·连接器】→【连接器】→ 自定义连接器 → 配置 MCP。

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer ${MCD_MCP_TOKEN}" }
    }
  }
}
```
</details>

### 补一下偏好（可选但推荐）

编辑 `preferences.md`：忌口、预算、默认门店、`box_budget`（盲盒单餐预算，真实菜单多为套餐件套，建议 45~60）。

---

## 四、使用示例

### 🚀 开机：麦麦启动

```
你：麦麦启动
AI：🔮 麦麦运势 · 星期六｜晚餐时段
    麦门指数 ★★★★★（5.0/5）……
    要开盲盒吗？
```

等价命令：

```bash
python3 scripts/fortune.py
```

### 🎁 开一个盲盒

```bash
$ python3 scripts/blind_box.py
🎁 麦麦点餐盲盒 · 今日一抽（正常模式｜种子 20261024，同一天结果一致）

🔮 今日运势 ★★★★★（5.0/5）→ 手气加成 SSR×2.2 SR×1.5
🍀 幸运单品 蜜汁快乐（权重 ×4）

  🔹R  汉堡包      ¥15.00
  🔹R  薄皮焦香V翅 ¥16.50
  🔹R  鲜萃冰咖   ¥13.00

合计 ¥44.50｜最佳 🔹R
预算 ¥50：✅ 没超
保底进度：0/5（满 5 下一抽必出 SR+）
```

```bash
python3 scripts/blind_box.py --ten             # 十连抽（保底一张 SR+）
python3 scripts/blind_box.py --mode 减脂       # 减脂模式（实测 420 kcal 以内）
python3 scripts/blind_box.py --seed 1024       # 换种子 = 换一抽
python3 scripts/blind_box.py --collection      # 看我的图鉴与保底进度
python3 scripts/blind_box.py --rich            # 抽到 SSR 也别拿预算压我
```

稀有度由餐品价格/规格决定：

| 稀有度 | 门槛 | 基础概率 |
|---|---|---|
| ✨SSR | ≥30 元 | 5% |
| 🌟SR | 18~30 元 | 15% |
| 🔹R | 9~18 元 | 35% |
| ▪️N | <9 元 | 45% |

### 其他玩法速查

```bash
python3 scripts/coupon_harvest.py                              # 领券 + 我的券（按到期排序）
python3 scripts/recommend.py --kcal 500                        # 500 大卡内能吃什么
python3 scripts/meal_solver.py --budget 40 --kcal 800 --goal value   # 40 元 800 大卡怎么吃最划算
python3 scripts/group_order.py --file 接龙.txt --fee 9         # 团餐汇总 + AA 分账
python3 scripts/lottery.py                                     # 看积分抽奖池与欧气值
python3 scripts/lottery.py --draw 1 --confirm                  # 真抽（需确认）
python3 scripts/party_book.py                                  # 派对/品鉴会预约引导
python3 scripts/deal_calendar.py --days 7                      # 未来 7 天该薅什么
python3 scripts/monthly_report.py 2026-10                      # 月度账单
python3 scripts/auto_order.py --dry-run                        # 定时点餐预演
python3 scripts/safe_package.py .                              # 打包前安全扫描
```

**任意脚本加 `--json` 可得机器可读输出**，退出码统一：`0` 成功 / `1` 网络错误 / `2` 缺配置 / `3` 触发预算护栏。

---

## 五、目录结构

```
mcd-magic-baby/
├── SKILL.md                 # 入口：意图路由 + 安全红线 + 真实 MCP 适配备注
├── README.md                # 本文件
├── CONTEST_DECLARATION.md   # 参赛声明（官方原文，未改动）
├── MCP_INTEGRATION.md       # MCP 集成说明：Server / Tools / 流程 / 业务价值
├── mcp-config.example.json  # 脱敏 MCP 配置（仅环境变量占位符）
├── workbuddy.md             # WorkBuddy 开发对话上下文
├── preferences.md           # 共享画像：忌口 / 预算 / 门店 / 默认模式
├── .env.example             # Token 配置模板（真实 .env 永不入库）
├── references/tools.md      # 官方 MCP 工具全表与调用要点
└── scripts/                 # 纯标准库实现
    ├── common.py            # 适配层：store_args / parse_* / to_yuan / 脱敏
    ├── mcp_client.py        # JSON-RPC over Streamable HTTP
    ├── fortune.py           # 🔮 麦麦运势
    ├── blind_box.py         # 🎁 点餐盲盒
    ├── coupon_harvest.py    # 💰 省钱
    ├── recommend.py         # 🥗 减脂
    ├── meal_solver.py       # 🎯 配餐
    ├── group_order.py       # 👥 团餐
    ├── lottery.py           # 🎡 抽奖
    ├── party_book.py        # 🎉 派对
    ├── deal_calendar.py     # 📅 情报
    ├── monthly_report.py    # 🧾 账单
    ├── auto_order.py        # ⏰ 懒人
    ├── setup_token.py       # Token 配置（600 权限）
    ├── doctor.py            # 环境自检
    └── safe_package.py      # 打包前密钥扫描
```

---

## 六、安全设计

- **Token 只走 `.env`**（权限 600），`.gitignore` 已排除，**打包脚本会二次扫描并在发现明文时中止打包**
- 运行时数据（订单缓存、账单、图鉴、幂等锁）全部写在技能目录**之外**的 `~/.workbuddy/mcd-magic-baby/`
- 缓存只存「时间 / 金额 / 商品」，**不存地址与手机号**
- 任何下单 / 抽奖 / 取消订单都必须先列明细再取得明确确认，脚本侧 `--confirm` 才是真正执行开关
- 自动下单四道护栏：显式开关 + 地址必填 + 预算上限 + 当日幂等锁

---

## 七、报名参赛

本项目的参赛报名信息：

```text
【参赛申请】
项目名称：神奇麦麦宝贝
项目地址：https://github.com/ZerenZhu/mcd-magic-baby
项目简介：输入「麦麦启动」，用麦当劳官方 MCP 的真实券/活动/积分算今日麦麦运势，再开 SSR 盲盒让命运决定吃什么
```

> 提交时请参考活动规则：报名 Issue 的标题与正文之间不使用换行符，项目地址不使用 Markdown 链接格式。

---

## 八、说明

- 本项目为「麦当劳程序员节创意开发大赛」参赛作品，由参赛者独立开发，**非麦当劳官方产品**。
- 项目输出仅供参考，不构成医疗、营养或其他专业建议；餐品信息、价格及供应状态**以麦当劳官方渠道的实时结果为准**。
- 数据源自麦当劳中国官方 MCP Server（https://github.com/M-China/mcd-mcp-server）。
- 若觉得有意思，欢迎点个 ⭐ —— 活动排名以 GitHub Star 数为依据。
