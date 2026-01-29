import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
import io
from datetime import datetime

# ==================== 1. 配置中心 ====================
ARMY_CONFIG = {
    "🛡️ 压舱石 (高股息)": ["中国神华", "中国石油", "长江电力", "工商银行", "中国建筑", "农业银行", "陕西煤业"],
    "⚔️ 冲锋队 (非银/白马)": ["中信证券", "东方财富", "中信建投", "贵州茅台", "五粮液", "格力电器", "泸州老窖"],
    "🏗️ 稳增长 (周期龙头)": ["海螺水泥", "万华化学", "三一重工", "紫金矿业", "宝钢股份", "中国中铁", "中国电建"],
    "📈 守护者 (核心权重)": ["招商银行", "中国平安", "比亚迪", "宁德时代", "美的集团", "兴业银行", "工业富联"]
}

# ==================== 2. 数据与扫描引擎 ====================
class NovaEngine:
    @staticmethod
    @st.cache_data(ttl=86400)
    def get_dynamic_gdp():
        try:
            gdp_yearly_df = ak.macro_china_gdp_yearly()
            last_year_total = float(gdp_yearly_df.iloc[-1]['value'])
            gdp_quarterly_df = ak.macro_china_gdp_quarterly()
            latest_growth = float(gdp_quarterly_df['absolute_value'].iloc[-1]) / 100 if not gdp_quarterly_df.empty else 0.05
            return last_year_total * (1 + latest_growth)
        except: return 1350000 

    @staticmethod
    def get_macro():
        macro = {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "FX": 7.2, "ERP": 0.04}
        try:
            # PMI
            p_df = ak.macro_china_pmi()
            macro["PMI"] = float(p_df.select_dtypes(include=['number']).iloc[-1, 0])
            # M1
            m_df = ak.macro_china_m2_yearly()
            macro["M1"], macro["M1_prev"] = float(m_df.iloc[-1, 1]), float(m_df.iloc[-2, 1])
            # FX
            fx_df = ak.fx_spot_quote()
            row = fx_df[fx_df.iloc[:,0].str.contains('USDCNH', na=False)]
            if not row.empty: macro["FX"] = float(row.iloc[0, 1])
        except: pass
        return macro

    @staticmethod
    def scan_stocks(pmi):
        results = []
        try:
            spot_df = ak.stock_zh_a_spot_em()
            for sector, stocks in ARMY_CONFIG.items():
                for name in stocks:
                    row = spot_df[spot_df['名称'] == name]
                    if not row.empty:
                        pct = row['涨跌幅'].values[0]
                        turnover = round(row['成交额'].values[0] / 1e8, 2)
                        
                        # 介入判定
                        status = "⚪ 正常"
                        if pct > 1.0 and turnover > 5: status = "🔥 点火"
                        elif abs(pct) < 0.3 and turnover > 10: status = "🛡️ 托底"
                        
                        # 穿透建议
                        advice = "制造业扩张利好" if pmi > 50 else "防御性持有"
                        
                        results.append({
                            "板块": sector, "名称": name, "涨幅%": pct, 
                            "成交(亿)": turnover, "迹象": status, "穿透建议": advice
                        })
        except: pass
        return results

# ==================== 3. UI 主控中心 ====================
def main():
    st.set_page_config(page_title="Nova 综合监控盘", layout="wide")
    st.title("🛡️ Nova 汪汪队大局观 & 全板块动态扫描")

    # --- 侧边栏与数据初始化 ---
    macro = NovaEngine.get_macro()
    dynamic_gdp = NovaEngine.get_dynamic_gdp()

    # --- 第一行：宏观指标看板 ---
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PMI 荣枯线", macro['PMI'], f"{round(macro['PMI']-50, 2)}")
    c2.metric("M1 活性趋势", f"{macro['M1']}%", f"{round(macro['M1']-macro['M1_prev'], 2)}%")
    c3.metric("离岸汇率", macro['FX'])
    c4.metric("动态 GDP 估算", f"{round(dynamic_gdp/10000, 2)} 万亿")

    st.divider()

    # --- 第二行：全板块动态扫描 ---
    st.sidebar.header("🕹️ 控制中心")
    if st.sidebar.button("🔍 开启全板块实时穿透"):
        st.session_state.scan_results = NovaEngine.scan_stocks(macro['PMI'])

    if "scan_results" in st.session_state and st.session_state.scan_results:
        df = pd.DataFrame(st.session_state.scan_results)
        
        # 仪表盘小统计
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.write("📊 介入信号分布")
            st.bar_chart(df['迹象'].value_counts())
        with sc2:
            st.write("💰 各板块动能(成交额)")
            st.bar_chart(df.groupby('板块')['成交(亿)'].sum())
        with sc3:
            st.metric("疑似介入总数", len(df[df['迹象'] != '⚪ 正常']))

        st.subheader("📋 实时作战报告 (28 只核心标的扫描结果)")
        
        def color_status(val):
            if '🔥' in val: return 'background-color: #ff4b4b; color: white'
            if '🛡️' in val: return 'background-color: #2e7d32; color: white'
            return ''
        
        st.dataframe(df.style.applymap(color_status, subset=['迹象']), use_container_width=True)

        # Excel 导出
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='汪汪队扫描', index=False)
        st.sidebar.download_button("📥 导出扫描报表", output.getvalue(), "Nova_Scan.xlsx")
    else:
        st.info("👋 Nova，请在左侧点击‘开启全板块实时穿透’来刷新个股介入数据。")

    # --- 第三行：ETF 汪汪强度 (复刻自你的代码) ---
    st.divider()
    st.subheader("📊 宽基 ETF 介入强度 (Z-Score)")
    # 此处可继续添加你的 Plotly ETF 图表代码...

if __name__ == "__main__":
    main()
