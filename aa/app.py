import pandas as pd
import akshare as ak
import streamlit as st
import io
from datetime import datetime

# ==================== 1. 汪汪队作战配置 (28只核心标的) ====================
ARMY_CONFIG = {
    "🛡️ 压舱石 (存量机构核心)": ["中国神华", "长江电力", "工商银行", "中国石油", "农业银行"],
    "⚔️ 冲锋队 (新增介入探测)": ["东方财富", "中信证券", "宁德时代", "比亚迪", "工业富联"],
    "🏗️ 稳增长 (周期权重)": ["紫金矿业", "万华化学", "海螺水泥", "三一重工"],
    "📈 守护者 (金融/白马)": ["招商银行", "中国平安", "贵州茅台", "五粮液", "美的集团"]
}

# ==================== 2. 核心分析引擎 ====================
class NovaIntelligence:
    @staticmethod
    def get_market_metrics():
        """抓取 M1、PMI 及指数实时点位"""
        metrics = {"PMI": 50.0, "M1_Diff": 0.0, "Index_Change": 0.0}
        try:
            # PMI
            pmi_df = ak.macro_china_pmi()
            metrics["PMI"] = float(pmi_df.iloc[-1]['value'])
            # M1 趋势 (当期 - 上期)
            m_df = ak.macro_china_m2_yearly()
            metrics["M1_Diff"] = float(m_df.iloc[-1]['value']) - float(m_df.iloc[-2]['value'])
            # 沪深300实时涨幅 (作为锚点)
            hs300 = ak.stock_zh_index_spot_em(symbol="沪深300")
            metrics["Index_Change"] = float(hs300.iloc[0]['涨跌幅'])
        except: pass
        return metrics

    @staticmethod
    def detect_wangwang(pmi, index_change):
        """探测汪汪队动向：个股 vs 总指数"""
        results = []
        try:
            spot_df = ak.stock_zh_a_spot_em()
            for sector, stocks in ARMY_CONFIG.items():
                for name in stocks:
                    row = spot_df[spot_df['名称'] == name]
                    if not row.empty:
                        pct = float(row['涨跌幅'].values[0])
                        turnover = round(float(row['成交额'].values[0]) / 1e8, 2)
                        
                        # 汪汪队行为探测逻辑
                        # 1. 强力护盘：大盘跌，个股不跌反涨且放量
                        # 2. 点火扫货：个股涨幅远超大盘 1% 以上
                        diff = pct - index_change
                        action = "⚪ 随波动"
                        if diff > 1.0 and turnover > 5: action = "🔥 机构强力扫货"
                        elif index_change < -0.5 and pct >= 0 and turnover > 10: action = "🛡️ 汪汪存量护盘"
                        
                        results.append({
                            "战队分类": sector,
                            "标的名称": name,
                            "实时涨幅%": pct,
                            "超额收益%": round(diff, 2),
                            "成交额(亿)": turnover,
                            "主力动向": action
                        })
        except: pass
        return pd.DataFrame(results)

# ==================== 3. UI 主控中心 ====================
def main():
    st.set_page_config(page_title="Nova 汪汪队监控", layout="wide")
    st.header("🏹 Nova 市场风格判定 & 汪汪队动向监控")

    # --- 1. 侧边栏：GDP 输入与控制 ---
    with st.sidebar:
        st.header("📊 数据输入")
        user_gdp = st.number_input("请输入当前预估 GDP (亿元):", value=1300000, step=10000)
        st.divider()
        st.header("🕹️ 控制中心")
        run_scan = st.button("🚀 开启全板块主力探测", use_container_width=True)

    # --- 2. 动态指标计算 ---
    metrics = NovaIntelligence.get_market_metrics()
    
    # 动态巴菲特指标计算
    total_mv = 950000 # 假设总市值基数(实际可调用 ak.stock_a_total_value)
    try:
        mv_df = ak.stock_a_total_value()
        total_mv = float(mv_df.iloc[-1]['total_value'])
    except: pass
    buffett_val = (total_mv / user_gdp) * 100

    # 风格判定逻辑
    style = "🔍 震荡格局"
    if metrics['PMI'] > 50 and metrics['M1_Diff'] > 0: style = "🚀 扩张点火 (顺周期)"
    elif metrics['PMI'] < 50 and metrics['M1_Diff'] < 0: style = "🛡️ 缩表防御 (红利低估)"
    elif buffett_val < 60: style = "💎 底部价值区间"

    # --- 3. 顶部仪表盘 ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("巴菲特指标", f"{round(buffett_val, 2)}%", "偏低" if buffett_val < 70 else "偏高")
    c2.metric("PMI 状态", metrics['PMI'], f"{round(metrics['PMI']-50, 1)}")
    c3.metric("M1 活性增量", f"{round(metrics['M1_Diff'], 2)}%")
    c4.metric("当前风格取向", style)

    st.divider()

    # --- 4. 汪汪队探测报告 ---
    if run_scan:
        with st.spinner("正在探测 28 只核心机构持仓动向..."):
            df = NovaIntelligence.detect_wangwang(metrics['PMI'], metrics['Index_Change'])
            
            if not df.empty:
                # 展示核心发现
                col_a, col_b = st.columns([1, 2])
                with col_a:
                    st.write("📈 主力行为分布")
                    st.bar_chart(df['主力动向'].value_counts())
                with col_b:
                    st.write("💰 各战队资金吸纳量 (亿元)")
                    st.bar_chart(df.groupby('战队分类')['成交额(亿)'].sum())

                st.subheader("📋 详细作战报告 (含沪深300超额匹配)")
                
                def color_action(val):
                    if '🔥' in val: return 'background-color: #ff4b4b; color: white'
                    if '🛡️' in val: return 'background-color: #2e7d32; color: white'
                    return ''
                
                st.dataframe(df.style.applymap(color_action, subset=['主力动向']), use_container_width=True)

                # 一键导出 Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='汪汪队探测')
                    # 也可以把宏观指标存入另一个sheet
                    pd.DataFrame([metrics]).to_excel(writer, sheet_name='宏观环境', index=False)
                
                st.sidebar.success("扫描完成！数据已就绪。")
                st.sidebar.download_button(
                    label="📥 一键导出 Excel 报告",
                    data=output.getvalue(),
                    file_name=f"Nova_WangWang_Report_{datetime.now().strftime('%m%d_%H%M')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
            else:
                st.error("探测失败，请检查行情接口连接。")
    else:
        st.info("👋 Nova，请在左侧侧边栏输入预估 GDP 并点击‘开启探测’，我将为你分析 28 只标的的机构介入情况。")

if __name__ == "__main__":
    main()
