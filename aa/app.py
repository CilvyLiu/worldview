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

# ==================== 2. 增强型引擎 ====================
class NovaEngine:
    @staticmethod
    def safe_float(val, default=0.0):
        """确保动态数据的数值准确性，防止崩溃"""
        try: return float(val)
        except: return default

    @staticmethod
    @st.cache_data(ttl=3600) # 缓存1小时，提高加载速度
    def get_macro():
        """宏观数据穿透：带容错处理"""
        macro = {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "FX": 7.2}
        try:
            # PMI
            p_df = ak.macro_china_pmi()
            macro["PMI"] = NovaEngine.safe_float(p_df.iloc[-1]['value'])
            # M1 (动态对比准确率加固)
            m_df = ak.macro_china_m2_yearly().dropna(subset=['value'])
            macro["M1"] = NovaEngine.safe_float(m_df.iloc[-1]['value'])
            macro["M1_prev"] = NovaEngine.safe_float(m_df.iloc[-2]['value'])
            # FX
            fx_df = ak.fx_spot_quote()
            row = fx_df[fx_df.iloc[:,0].str.contains('USDCNH', na=False)]
            if not row.empty: macro["FX"] = NovaEngine.safe_float(row.iloc[0, 1])
        except Exception as e:
            st.sidebar.error(f"宏观同步异常: {e}")
        return macro

    @staticmethod
    def scan_stocks(pmi):
        """核心扫描：解决动态显示不全问题"""
        results = []
        try:
            spot_df = ak.stock_zh_a_spot_em()
            for sector, stocks in ARMY_CONFIG.items():
                for name in stocks:
                    row = spot_df[spot_df['名称'] == name]
                    if not row.empty:
                        pct = NovaEngine.safe_float(row['涨跌幅'].values[0])
                        turnover = round(NovaEngine.safe_float(row['成交额'].values[0]) / 1e8, 2)
                        
                        # 介入逻辑判定准确率提升
                        status = "⚪ 正常"
                        if pct > 1.2 and turnover > 5: status = "🔥 点火" # 提升点火阈值至1.2%
                        elif abs(pct) < 0.3 and turnover > 8: status = "🛡️ 托底"
                        
                        results.append({
                            "板块": sector, "名称": name, "涨幅%": pct, 
                            "成交(亿)": turnover, "迹象": status, 
                            "穿透建议": "扩张拉升" if pmi > 50 else "防御护盘"
                        })
        except Exception as e:
            st.error(f"个股扫描中断: {e}")
        return results

# ==================== 3. UI 主控中心 ====================
def main():
    st.set_page_config(page_title="Nova 综合监控盘", layout="wide")
    st.title("🛡️ Nova 汪汪队全板块动态扫描")

    # --- 1. 初始化会话状态 ---
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = None

    # --- 2. 宏观看板 ---
    macro = NovaEngine.get_macro()
    
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("PMI 荣枯线", macro['PMI'], f"{round(macro['PMI']-50, 2)}")
    m2.metric("M1 活性趋势", f"{macro['M1']}%", f"{round(macro['M1']-macro['M1_prev'], 2)}%")
    m3.metric("离岸汇率", macro['FX'])
    m4.metric("更新时间", datetime.now().strftime("%H:%M:%S"))

    st.divider()

    # --- 3. 核心控制逻辑 ---
    with st.sidebar:
        st.header("🕹️ 控制中心")
        if st.button("🚀 开启全板块实时穿透", use_container_width=True):
            with st.spinner("正在采集最新动态..."):
                st.session_state.scan_results = NovaEngine.scan_stocks(macro['PMI'])

    # --- 4. 动态内容展示 ---
    if st.session_state.scan_results is not None:
        df = pd.DataFrame(st.session_state.scan_results)
        
        # 统计分析图
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("📊 介入信号")
            st.bar_chart(df['迹象'].value_counts())
        with c2:
            st.subheader("💰 战队动能 (成交额)")
            st.bar_chart(df.groupby('板块')['成交(亿)'].sum())

        # 详细表格
        st.subheader(f"📋 详细作战报告 ({len(df)} 只标的扫描完成)")
        
        def color_status(val):
            if '🔥' in val: return 'background-color: #ff4b4b; color: white'
            if '🛡️' in val: return 'background-color: #2e7d32; color: white'
            return ''
        
        st.dataframe(df.style.applymap(color_status, subset=['迹象']), use_container_width=True)

        # 导出
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='汪汪队扫描', index=False)
        st.sidebar.download_button("📥 导出全量报表", output.getvalue(), "Nova_Full_Report.xlsx")
    else:
        st.info("👋 Nova，请在左侧点击按钮开启扫描。目前处于待命状态。")

if __name__ == "__main__":
    main()
