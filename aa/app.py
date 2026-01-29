二、潜在问题 / 可以优化点 ⚠

Tick 数据假设依然强

df_tick['type'] == '中性'
df_tick['price']
df_tick['成交额']


免费数据源 ak 的字段名称可能随时变

建议加字段存在检查，例如：

required_cols = ['time', 'price', '成交额', 'type']
if not all(c in df_tick.columns for c in required_cols):
    return False, 0, "缺少关键字段"


尾部数据样本太少

intervals = df_tick['time_dt'].diff().dt.total_seconds().tail(50)
price_std = df_tick['price'].tail(50).std()


如果股票冷门，tick 少于 50 条 → tail(50) 仍然返回所有行

可以先判断行数：

if len(df_tick) < 20:
    return False, 0, "Tick样本不足"


板块和个股没有去重

一个股票可能属于多个板块 → 重复审计

可用 set() 或记录已经审计过的股票编号来去重。

大单拆分逻辑简单

big_order_count = len(df_tick[df_tick['成交额'] > 100000].tail(100))


可能存在冷门股即便是真扫货也会触发阈值

可考虑按 成交额占比 / 均值 动态判断，而不是硬 100000 元。

未输出“未通过审计”的股票信息

对于分析复盘，建议记录：

results.append({
    "板块": s_name,
    "编号": code,
    "名称": st_row['名称'],
    "中性占比": f"{round(n_ratio*100,1)}%",
    "状态": msg
})


这样你能看到 为什么不被判断为扫货，利于策略迭代。

没有日志记录

对于连续运行或定时任务，建议把 print 改为 logger 或保存到 CSV / JSON。

三、可选增强建议 🔧

增加 VWAP / 量比验证

vwap = (df_tick['price'] * df_tick['成交额']).sum() / df_tick['成交额'].sum()
# 检查价格是否在 vwap ± 小幅波动


增加多板块评分

对每个板块累积多个个股反算法分数

输出板块总分 → 更可靠识别“板块静默扫货”。

异步请求 / 并发

每个股票 sleep 1.2 秒 → 单板块 10~15 个股会很慢

可用 asyncio + aiohttp + ak 的接口并发请求，提高效率。
