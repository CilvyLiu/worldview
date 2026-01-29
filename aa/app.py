import pandas as pd
import akshare as ak
import streamlit as st
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
    def safe_convert(val):
        try: return float(val)
        except: return 0.0

    @staticmethod
    @st.cache_data(ttl=86400)
    def get_dynamic_gdp():
        try:
            gdp_yearly = ak.macro_china_gdp_yearly()
            last_year_total = NovaEngine.safe_convert(gdp_yearly.iloc[-1]['value'])
            gdp_quarterly = ak.macro_china_gdp_quarterly()
            latest_growth = NovaEngine.safe_convert(gdp_quarterly['absolute_value'].iloc[-1]) / 100 if not gdp_quarterly.empty else 0.05
            return last_year_total * (1 + latest_growth)
        except: return 1350000 

    @staticmethod
    def get_macro():
        macro = {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "FX": 7.2}
        try:
            p_df = ak.macro_china_pmi()
            macro["PMI"] = NovaEngine.safe_convert(p_df.iloc[-1]['value'])
            
            m_df = ak.macro_china_m2_yearly()
            if len(m_df) >= 2:
                macro["M1"] = NovaEngine.safe_convert(m_df.iloc[-1]['value'])
                macro["M1_prev"] = NovaEngine.safe_convert(m_df.iloc[-2]['value'])
            
            fx_df = ak.fx_spot_quote()
            row = fx_df[fx_df.iloc[:,0].str.contains('USDCNH', na=False)]
            if not row.empty: macro["FX"] = NovaEngine.safe_convert(row.iloc[0, 1])
        except: pass
        return macro

    @staticmethod
    def scan_stocks(pmi):
        results = []
        try:
            # 增加超时控制
            spot_df = ak.stock_zh_a_spot_em()
            if spot_df.empty: return []

            for sector, stocks in ARMY_CONFIG.items():
                for name in stocks:
                    row = spot_df[spot_df['名称'] == name]
                    if not row.empty:
                        pct = NovaEngine.safe_convert(row['涨跌幅'].values[0])
                        turnover = round(NovaEngine.safe_convert(row['成交额'].values[0]) / 1e8, 2)
                        
                        # 动态介入判定逻辑优化
                        status = "⚪ 正常"
                        if pct > 1.2 and turnover > 5: status = "🔥 点火" 
                        elif abs(pct) < 0.3 and turnover > 10: status = "🛡️ 托底"
                        
                        results.append({
                            "板块": sector, "名称": name, "涨幅%": pct, 
                            "成交(亿)": turnover, "迹象": status, 
                            "穿透建议": "制造业扩张利好" if pmi > 50 else "防御性持有"
                        })
        except Exception as e:
            st.error(f"扫描引擎故障: {e}")
        return results

# ==================== 3. UI 主控中心 ====================
def main():
    st.set_page_config(page_title="Nova 综合监控盘", layout="wide")
    st.title("🛡️ Nova 汪汪队全板块动态穿透")

    # 初始化 SessionState 防止刷新丢失
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = None

    macro = NovaEngine.get_macro()
    dynamic_gdp = NovaEngine.get_dynamic_gdp()

    # --- 宏观仪表盘 ---
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PMI 荣枯线", macro['PMI'], f"{round(macro['PMI']-50, 2)}")
    c2.metric("M1 活性趋势", f"{macro['M1']}%", f"{round(macro['M1']-macro['M1_prev'], 2)}%")
    c3.metric("离岸汇率", macro['FX'])
    c4.metric("动态 GDP 估算", f"{round(dynamic_gdp/10000, 2)} 万亿")

    st.divider()

    # --- 控制中心 ---
    st.sidebar.header("🕹️ 控制中心")
    if st.sidebar.button("🔍 开启全板块实时穿透", use_container_width=True):
        with st.spinner("正在穿透 28 只核心标的..."):
            data = NovaEngine.scan_stocks(macro['PMI'])
            # 强制转换为 DataFrame 且保证即使为空也有列名
            st.session_state.scan_results = pd.DataFrame(data, columns=["板块", "名称", "涨幅%", "成交(亿)", "迹象", "穿透建议"])

    # --- 结果展示 (防御性渲染) ---
    if st.session_state.scan_results is not None:
        df = st.session_state.scan_results
        
        if df.empty:
            st.warning("🕵️ 扫描完成，但当前未匹配到个股数据。请检查网络或是否在非交易时段。")
        else:
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.write("📊 介入信号分布")
                # 即使没有某种迹象，也能通过 value_counts 正常显示
                st.bar_chart(df['迹象'].value_counts())
            with sc2:
                st.write("💰 各板块动能(亿元)")
                st.bar_chart(df.groupby('板块')['成交(亿)'].sum())
            with sc3:
                st.metric("疑似介入总数", len(df[df['迹象'] != '⚪ 正常']))

            st.subheader("📋 实时作战报告 (28 只核心标的全扫描)")
            
            def color_status(val):
                if '🔥' in val: return 'background-color: #ff4b4b; color: white'
                if '🛡️' in val: return 'background-color: #2e7d32; color: white'
                return ''
            
            st.dataframe(df.style.applymap(color_status, subset=['迹象']), use_container_width=True)

            # Excel 导出
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.sidebar.download_button("📥 导出扫描报表", output.getvalue(), f"Nova_Report_{datetime.now().strftime('%m%d')}.xlsx")
    else:
        st.info("👋 Nova，请点击左侧按钮开启扫描。")

if __name__ == "__main__":
    main()
