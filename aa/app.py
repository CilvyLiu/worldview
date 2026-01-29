import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
from datetime import datetime

# ==================== 1. 数据采集模块 (终极加固) ====================
class DataCenter:
    @staticmethod
    def _safe_float(val, default=0.0):
        try:
            if pd.isna(val) or val is None: return default
            return float(val)
        except:
            return default

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_macro_data():
        data = {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "USDCNH": 7.2}
        try:
            pmi_df = ak.macro_china_pmi()
            if not pmi_df.empty:
                data["PMI"] = DataCenter._safe_float(pmi_df.select_dtypes(include=['number']).iloc[-1, 0], 50.0)
            
            m1_df = ak.macro_china_m2_yearly()
            if not m1_df.empty:
                m1_series = m1_df.iloc[:, 1].dropna()
                if len(m1_series) >= 2:
                    data["M1"] = DataCenter._safe_float(m1_series.iloc[-1])
                    data["M1_prev"] = DataCenter._safe_float(m1_series.iloc[-2])
            
            fx_df = ak.fx_spot_quote()
            sym_col = [c for c in fx_df.columns if 'sym' in c.lower() or '代码' in c]
            last_col = [c for c in fx_df.columns if 'last' in c.lower() or '最新' in c]
            if sym_col and last_col:
                row = fx_df[fx_df[sym_col[0]].str.contains('USDCNH', na=False)]
                if not row.empty:
                    data["USDCNH"] = DataCenter._safe_float(row[last_col[0]].iloc[0], 7.2)
        except Exception as e:
            st.sidebar.error(f"宏观同步异常: {e}")
        return data

    @staticmethod
    @st.cache_data(ttl=60)
    def get_basis_analysis():
        """
        修复版：期现基差
        确保即使现货接口微调也能抓到数据
        """
        results = []
        try:
            # 现货：改用更稳定的东财接口模糊匹配
            spot_df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
            # 模糊搜索包含 '300' 的行
            target_row = spot_df[spot_df['名称'].str.contains('300', na=False)].iloc[0]
            
            # 寻找类似 '最新价' 或 '收盘价' 的列
            price_col = [c for c in spot_df.columns if '最新' in c or '收盘' in c][0]
            spot_300 = DataCenter._safe_float(target_row[price_col])
            
            # 2026年1月 监控合约
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
                results.append({
                    "价差代码": c['code'], 
                    "期货价": c['price'], 
                    "现货价": spot_300, 
                    "最新基差": basis, 
                    "状态": status
                })
        except Exception as e:
            st.sidebar.warning(f"基差计算组件暂不可用: {e}")
        return pd.DataFrame(results)

    @staticmethod
    @st.cache_data(ttl=600)
    def get_wang_etf_flow():
        etfs = {"沪深300": "sh510300", "上证50": "sh510050", "中证1000": "sh512100"}
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

# ==================== 2. 可视化界面 ====================
def main():
    st.set_page_config(page_title="Nova 全局监控", layout="wide")
    st.title("🛡️ Nova 宏观大局 & 资金基差穿透监控")

    dc = DataCenter()
    macro = dc.get_macro_data()
    wang = dc.get_wang_etf_flow()
    basis_df = dc.get_basis_analysis()

    # 指标看板
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("制造业 PMI", f"{macro['PMI']}", delta=f"{round(macro['PMI']-50, 2)} (荣枯线)")
    m1_delta = round(macro['M1'] - macro['M1_prev'], 2)
    c2.metric("M1 增速趋势", f"{macro['M1']}%", delta=f"{m1_delta}%")
    c3.metric("离岸汇率", f"{macro['USDCNH']}")
    active_wang = [k for k, v in wang.items() if v > 2.0]
    c4.metric("汪汪队异动", f"{len(active_wang)} 方向", delta="异常放量" if active_wang else "自然波动")

    st.divider()

    # 数据中场：基差与汪汪
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("📊 汪汪队介入强度 (Z-Score)")
        
        if wang:
            w_df = pd.DataFrame(list(wang.items()), columns=['指数', '强度'])
            fig = px.bar(w_df, x='指数', y='强度', color='强度', color_continuous_scale='RdBu_r')
            fig.add_hline(y=2.0, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("📉 期现基差动态监控表")
        
        if not basis_df.empty:
            def style_basis(val):
                if "正向" in val: return 'background-color: #ff4b4b; color: white'
                if "负向" in val: return 'background-color: #1c83e1; color: white'
                return ''
            st.dataframe(basis_df.style.applymap(style_basis, subset=['状态']), use_container_width=True)
        else:
            st.info("💡 基差计算正在等待现货行情同步...")

    st.divider()

    # 预警穿透
    st.subheader("🚨 Nova 实时风险穿透提示")
    r1, r2, r3 = st.columns(3)
    with r1:
        if macro['PMI'] < 50:
            st.error("### 警惕：周期类\n**海螺水泥、万华化学**\nPMI收缩压力较大。")
    with r2:
        if m1_delta < 0:
            st.warning("### 警惕：白马股\n**格力电器、招商银行**\nM1增速放缓，流动性溢价受限。")
    with r3:
        if not basis_df.empty and any("异常" in x for x in basis_df['状态']):
            st.error("### 警惕：衍生品风险\n基差结构出现异常位移，关注大资金对冲动向。")

if __name__ == "__main__":
    main()
