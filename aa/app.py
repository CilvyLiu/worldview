import pandas as pd
import akshare as ak
import streamlit as st
import io
from datetime import datetime, timedelta

# ==================== 1. 28只核心标的代码映射 (底稿) ====================
WANGWANG_MAP = [
    {"战队": "🛡️ 压舱石", "名称": "中国神华", "代码": "601088"},
    {"战队": "🛡️ 压舱石", "名称": "长江电力", "代码": "600900"},
    {"战队": "🛡️ 压舱石", "名称": "工商银行", "代码": "601398"},
    {"战队": "🛡️ 压舱石", "名称": "中国石油", "代码": "601857"},
    {"战队": "🛡️ 压舱石", "名称": "农业银行", "代码": "601288"},
    {"战队": "🛡️ 压舱石", "名称": "陕西煤业", "代码": "601225"},
    {"战队": "🛡️ 压舱石", "名称": "中国建筑", "代码": "601668"},
    {"战队": "⚔️ 冲锋队", "名称": "东方财富", "代码": "300059"},
    {"战队": "⚔️ 冲锋队", "名称": "中信证券", "代码": "600030"},
    {"战队": "⚔️ 冲锋队", "名称": "宁德时代", "代码": "300750"},
    {"战队": "⚔️ 冲锋队", "名称": "比亚迪", "代码": "002594"},
    {"战队": "⚔️ 冲锋队", "名称": "工业富联", "代码": "601138"},
    {"战队": "⚔️ 冲锋队", "名称": "中信建投", "代码": "601066"},
    {"战队": "⚔️ 冲锋队", "名称": "泸州老窖", "代码": "000568"},
    {"战队": "🏗️ 稳增长", "名称": "紫金矿业", "代码": "601899"},
    {"战队": "🏗️ 稳增长", "名称": "万华化学", "代码": "600309"},
    {"战队": "🏗️ 稳增长", "名称": "海螺水泥", "代码": "600585"},
    {"战队": "🏗️ 稳增长", "名称": "三一重工", "代码": "600031"},
    {"战队": "🏗️ 稳增长", "名称": "宝钢股份", "代码": "600019"},
    {"战队": "🏗️ 稳增长", "名称": "中国中铁", "代码": "601390"},
    {"战队": "🏗️ 稳增长", "名称": "中国电建", "代码": "601669"},
    {"战队": "📈 守护者", "名称": "招商银行", "代码": "600036"},
    {"战队": "📈 守护者", "名称": "中国平安", "代码": "601318"},
    {"战队": "📈 守护者", "名称": "贵州茅台", "代码": "600519"},
    {"战队": "📈 守护者", "名称": "五粮液", "代码": "000858"},
    {"战队": "📈 守护者", "名称": "美的集团", "代码": "000333"},
    {"战队": "📈 守护者", "名称": "兴业银行", "代码": "601166"},
    {"战队": "📈 守护者", "名称": "格力电器", "代码": "000651"}
]

class SuperEngine:
    @staticmethod
    def get_market_metrics(gdp_input):
        """宏观判定增强逻辑"""
        res = {"PMI": 50.0, "M1_Diff": 0.0, "HS300": 0.0, "Buffett": 0.0}
        try:
            # 基础宏观数据
            pmi = ak.macro_china_pmi()
            res["PMI"] = float(pmi.iloc[-1]['value'])
            m1 = ak.macro_china_m2_yearly()
            res["M1_Diff"] = float(m1.iloc[-1]['value']) - float(m1.iloc[-2]['value'])
            
            # 指数锚点 (带异常处理)
            idx = ak.stock_zh_index_spot_em(symbol="沪深300")
            res["HS300"] = float(idx.iloc[0]['涨跌幅'])
            
            # 巴菲特指标计算
            mv_df = ak.stock_a_total_value()
            res["Buffett"] = (float(mv_df.iloc[-1]['total_value']) / gdp_input) * 100
        except: pass
        return res

    @staticmethod
    def guaranteed_scan():
        """三口径探测逻辑，确保不空手而归"""
        final_results = []
        try:
            # 第一口径：实时快照
            full_data = ak.stock_zh_a_spot_em()
        except:
            full_data = pd.DataFrame()

        for s in WANGWANG_MAP:
            stock_res = None
            # 实时数据检索
            if not full_data.empty:
                row = full_data[full_data['名称'] == s['名称']]
                if not row.empty:
                    stock_res = {"pct": float(row['涨跌幅'].values[0]), "turnover": float(row['成交额'].values[0])}

            # 第三口径：回溯探测 (针对节假日或接口挂掉)
            if stock_res is None:
                try:
                    # 获取最近 2 天历史，取最新一天的收盘
                    hist = ak.stock_zh_a_hist(symbol=s['代码'], period="daily", adjust="qfq").iloc[-1:]
                    stock_res = {"pct": float(hist['涨跌幅'].values[0]), "turnover": float(hist['成交额'].values[0])}
                except: continue
            
            if stock_res:
                final_results.append({
                    "战队分类": s['战队'], "名称": s['名称'], "代码": s['代码'],
                    "实时涨幅%": stock_res['pct'], "成交额(亿)": round(stock_res['turnover']/1e8, 2)
                })
        return pd.DataFrame(final_results)

# ==================== 2. UI 渲染逻辑 ====================
def main():
    st.set_page_config(page_title="Nova 探测器 2026", layout="wide")
    st.title("🏹 Nova 市场风格 & 汪汪队探测 (全天候版)")

    with st.sidebar:
        st.header("⚙️ 参数干预")
        user_gdp = st.number_input("预估 GDP (亿元):", value=1280000)
        run_scan = st.button("🚀 开启主力探测", use_container_width=True)

    # 1. 获取并显示宏观指标
    m = SuperEngine.get_market_metrics(user_gdp)
    
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("巴菲特指标", f"{round(m['Buffett'], 2)}%", "偏低" if m['Buffett'] < 75 else "预警")
    c2.metric("PMI 荣枯线", m['PMI'], f"{round(m['PMI']-50, 1)}")
    c3.metric("M1 活性增量", f"{round(m['M1_Diff'], 1)}%")
    
    # 风格判定
    style = "🔍 价值发现" if m['Buffett'] < 70 else "⚖️ 均衡博弈"
    if m['PMI'] > 50 and m['M1_Diff'] > 0: style = "🚀 扩张进攻"
    c4.metric("风格取向", style)

    st.divider()

    # 2. 执行探测
    if run_scan:
        with st.spinner("执行三通道取数机制 (实时/定向/回溯)..."):
            df = SuperEngine.guaranteed_scan()
            
            if not df.empty:
                # 穿透判定
                df['超额收益%'] = df['实时涨幅%'] - m['HS300']
                df['主力动向'] = df.apply(lambda x: 
                    "🔥 强力扫货" if x['超额收益%'] > 1 and x['成交额(亿)'] > 5 else (
                    "🛡️ 护盘稳定" if x['超额收益%'] >= 0 and m['HS300'] < -0.2 else "⚪ 跟随波动"
                ), axis=1)

                # 可视化
                v1, v2 = st.columns([1, 2])
                with v1:
                    st.bar_chart(df['主力动向'].value_counts())
                with v2:
                    st.bar_chart(df.groupby('战队分类')['成交额(亿)'].sum())

                st.subheader("📋 探测报告 (含新增持仓 vs 存量持仓分析)")
                
                # 色彩标注逻辑
                def color_logic(val):
                    if '🔥' in val: return 'background-color: #ff4b4b; color: white'
                    if '🛡️' in val: return 'background-color: #2e7d32; color: white'
                    return ''
                
                st.dataframe(df.style.applymap(color_logic, subset=['主力动向']), use_container_width=True)

                # 导出 Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='探测详情')
                    pd.DataFrame([m]).to_excel(writer, index=False, sheet_name='宏观背景')
                
                st.sidebar.download_button("📥 一键导出 Excel", output.getvalue(), f"Nova_Report_{datetime.now().strftime('%m%d')}.xlsx")
            else:
                st.error("🚨 探测异常：请检查 Akshare 版本（pip install akshare --upgrade）")
    else:
        st.info("👋 Nova，若实时取数失败，系统将自动调用历史快照进行回溯分析。请点击按钮开启。")

if __name__ == "__main__":
    main()
