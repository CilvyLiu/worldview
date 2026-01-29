import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
from datetime import datetime

# ==================== 1. 数据采集模块 (加固版) ====================
class DataCenter:
    """负责所有宏观、市场、衍生品价差的抓取，具备强容错性"""
    
    @staticmethod
    def _safe_float(val, default=0.0):
        try:
            return float(val) if pd.notnull(val) else default
        except:
            return default

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_macro_data():
        """1. 宏观核心：PMI, M1, 汇率"""
        data = {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "USDCNH": 7.2}
        try:
            # PMI
            pmi_df = ak.macro_china_pmi()
            if not pmi_df.empty:
                data["PMI"] = DataCenter._safe_float(pmi_df.select_dtypes(include=['number']).iloc[-1, 0], 50.0)
            
            # M1 (货币供应)
            m1_df = ak.macro_china_m2_yearly()
            if not m1_df.empty:
                m1_series = m1_df.iloc[:, 1].dropna()
                if len(m1_series) >= 2:
                    data["M1"] = DataCenter._safe_float(m1_series.iloc[-1])
                    data["M1_prev"] = DataCenter._safe_float(m1_series.iloc[-2])
            
            # 汇率 (动态匹配列名)
            fx_df = ak.fx_spot_quote()
            sym_col = [c for c in fx_df.columns if 'symbol' in c.lower() or '代码' in c]
            last_col = [c for c in fx_df.columns if 'last' in c.lower() or '最新' in c]
            if sym_col and last_col:
                row = fx_df[fx_df[sym_col[0]].str.contains('USDCNH', na=False)]
                if not row.empty:
                    data["USDCNH"] = DataCenter._safe_float(row[last_col[0]].iloc[0], 7.2)
        except Exception as e:
            st.sidebar.error(f"宏观同步异常: {e}")
        return data

    @staticmethod
    @st.cache_data(ttl=600)
    def get_wang_etf_flow():
        """2. 汪汪队监控：基于核心 ETF 成交量 Z-Score"""
        etfs = {"沪深300": "sh510300", "上证50": "sh510050", "中证1000": "sh512100", "中证2000": "sh563300"}
        flows = {}
        for name, code in etfs.items():
            try:
                df = ak.fund_etf_hist_sina(symbol=code)
                if not df.empty and len(df) >= 20:
                    vols = df['amount'].tail(20)
                    z_score = (vols.iloc[-1] - vols.mean()) / vols.std()
                    flows[name] = round(z_score, 2)
                else: flows[name] = 0.0
            except: flows[name] = 0.0
        return flows

    @staticmethod
    @st.cache_data(ttl=60)
    def get_basis_analysis():
        """3. 期现基差：复现图片中的合约升贴水逻辑"""
        # 图片逻辑：IF2602, IF2603 等阈值
        results = []
        try:
            # 现货：沪深300
            spot_df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
            spot_300 = DataCenter._safe_float(spot_df[spot_df['名称'] == '沪深300']['最新价'].values[0])
            
            contracts = [
                {"code": "IF2602", "price": 4727.8, "up": 9.83, "down": -29.55},
                {"code": "IF2603", "price": 4732.8, "up": -14.79, "down": -80.29},
                {"code": "IF2606", "price": 4716.8, "up": -40.57, "down": -118.69}
            ]
            for c in contracts:
                basis = round(c['price'] - spot_300, 2)
                status = "正常"
                if basis > c['up']: status = "正向异常(警惕高估)"
                elif basis < c['down']: status = "负向异常(警惕杀跌)"
                results.append({"合约": c['code'], "最新价": c['price'], "基差": basis, "状态": status})
        except: pass
        return pd.DataFrame(results)

# ==================== 2. 界面展示逻辑 ====================
def main():
    st.set_page_config(page_title="Nova 全局监控", layout="wide")
    st.title("🛡️ Nova 宏观大局 & 资金基差穿透监控")

    dc = DataCenter()
    macro = dc.get_macro_data()
    wang = dc.get_wang_etf_flow()
    basis_df = dc.get_basis_analysis()

    # 第一行：宏观指标
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("制造业 PMI", f"{macro['PMI']}", delta=f"{round(macro['PMI']-50, 2)} (荣枯线)")
    m1_delta = round(macro['M1'] - macro['M1_prev'], 2)
    c2.metric("M1 增速", f"{macro['M1']}%", delta=f"{m1_delta}%")
    c3.metric("离岸汇率", f"{macro['USDCNH']}")
    active_wang = [k for k, v in wang.items() if v > 2.0]
    c4.metric("汪汪队异动", f"{len(active_wang)} 方向", delta="异常放量" if active_wang else "平稳")

    st.divider()

    # 第二行：两板斧对比
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.subheader("📊 汪汪队介入强度 (Z-Score)")
        
        if wang:
            w_df = pd.DataFrame(list(wang.items()), columns=['指数', '强度'])
            fig = px.bar(w_df, x='指数', y='强度', color='强度', color_continuous_scale='RdBu_r')
            fig.add_hline(y=2.0, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("📉 期现基差穿透 (衍生品结构)")
        
        if not basis_df.empty:
            def color_basis(val):
                if "正向" in val: return 'background-color: #ff4b4b; color: white'
                if "负向" in val: return 'background-color: #1c83e1; color: white'
                return ''
            st.table(basis_df.style.applymap(color_basis, subset=['状态']))

    st.divider()

    # 第三行：终极风险穿透
    st.subheader("🚨 Nova 实时风险穿透提示")
    risk_1, risk_2, risk_3 = st.columns(3)
    
    with risk_1:
        if macro['PMI'] < 50:
            st.error("### 警惕：周期类\n**海螺水泥、万华化学**\n理由：PMI 处于收缩区间，需求端逻辑证伪。")
        else:
            st.success("### 周期类：基本面尚可")

    with risk_2:
        if m1_delta < 0:
            st.warning("### 警惕：权重/白马\n**格力电器、招商银行**\n理由：M1 增速掉头，市场活钱减少，估值溢价收缩。")
        else:
            st.success("### 权重类：资金活性增强")

    with risk_3:
        if active_wang:
            st.info(f"### 重点关注：护盘方向\n**{', '.join(active_wang)}**\n理由：检测到大资金暴力介入，短期具韧性。")
        else:
            st.write("### 资金面：暂无大资金暴力护盘")

if __name__ == "__main__":
    main()
