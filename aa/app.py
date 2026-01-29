import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
import time

# ==================== 1. 数据采集模块 (深度加固) ====================
class DataCenter:
    @staticmethod
    def _safe_float(val, default=0.0):
        try:
            if pd.isna(val) or val is None: return default
            return float(val)
        except: return default

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_macro_data():
        """宏观核心：PMI, M1, 汇率"""
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
    @st.cache_data(ttl=30) # 缩短基差缓存，增强实时性
    def get_basis_analysis():
        """
        加固版基差：解决 Connection aborted 报错
        """
        results = []
        try:
            # 增加重试逻辑
            spot_df = pd.DataFrame()
            for _ in range(3): # 最多尝试3次
                try:
                    spot_df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
                    if not spot_df.empty: break
                except: time.sleep(1)
            
            if spot_df.empty: raise Exception("所有行情源连接均已重置")

            target_row = spot_df[spot_df['名称'].str.contains('300', na=False)].iloc[0]
            price_col = [c for c in spot_df.columns if '最新' in c or '收盘' in c][0]
            spot_300 = DataCenter._safe_float(target_row[price_col])
            
            # 2026年监控合约 (Nova 专属阈值)
            contracts = [
                {"code": "IF2602", "price": 4727.8, "up": 9.83, "down": -29.55},
                {"code": "IF2603", "price": 4732.8, "up": -14.79, "down": -80.29},
                {"code": "IF2606", "price": 4716.8, "up": -40.57, "down": -118.69}
            ]
            
            for c in contracts:
                basis = round(c['price'] - spot_300, 2)
                status = "正常"
                if basis > c['up']: status = "正向异常(高估)"
                elif basis < c['down']: status = "负向异常(杀跌)"
                results.append({"合约": c['code'], "期货": c['price'], "现货": spot_300, "基差": basis, "状态": status})
        except Exception as e:
            st.sidebar.warning(f"基差同步受限 (网络拥堵): {e}")
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
            except: flows[name] = 0.0
        return flows

# ==================== 2. 可视化界面 ====================
def main():
    st.set_page_config(page_title="Nova 全局穿透", layout="wide")
    st.title("🛡️ Nova 宏观大局 & 基差穿透监控")

    dc = DataCenter()
    with st.spinner('透视全局数据中...'):
        macro = dc.get_macro_data()
        basis_df = dc.get_basis_analysis()
        wang = dc.get_wang_etf_flow()

    # 指标看板
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("制造业 PMI", f"{macro['PMI']}", delta=f"{round(macro['PMI']-50, 2)} (荣枯线)")
    m1_delta = round(macro['M1'] - macro['M1_prev'], 2)
    c2.metric("M1 增速趋势", f"{macro['M1']}%", delta=f"{m1_delta}%")
    c3.metric("离岸汇率", f"{macro['USDCNH']}")
    active_wang = [k for k, v in wang.items() if v > 2.0]
    c4.metric("汪汪队异动", f"{len(active_wang)} 方向", delta="异常放量" if active_wang else "自然波动")

    st.divider()

    # 利差表与汪汪队
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("📉 期现基差动态监控 (Basis)")
        
        if not basis_df.empty:
            st.dataframe(basis_df.style.applymap(
                lambda x: 'background-color: #ff4b4b; color: white' if "正向" in str(x) else 
                          'background-color: #1c83e1; color: white' if "负向" in str(x) else '',
                subset=['状态']
            ), use_container_width=True)
        else:
            st.warning("⚠️ 接口连接超时，正在尝试自动重连...")

    with col_r:
        st.subheader("📊 汪汪队 ETF 介入强度")
        if wang:
            w_df = pd.DataFrame(list(wang.items()), columns=['指数', '强度'])
            fig = px.bar(w_df, x='指数', y='强度', color='强度', color_continuous_scale='RdBu_r')
            fig.add_hline(y=2.0, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)

    # 风险穿透
    st.divider()
    st.subheader("🚨 Nova 实时风险提示")
    r1, r2, r3 = st.columns(3)
    with r1:
        if macro['PMI'] < 50:
            st.error("### 警惕：海螺水泥 (周期龙头)\n理由：制造业进入收缩区间，基建下游逻辑支撑力度减弱。")
    with r2:
        if m1_delta < 0:
            st.warning("### 警惕：格力电器 (权重白马)\n理由：货币活性下降，警惕白马股估值中枢下移。")
    with r3:
        if not basis_df.empty and any("负向" in x for x in basis_df['状态']):
            st.error("### 警惕：整体杀跌风险\n检测到衍生品基差严重贴水，资金正在暴力对冲。")

if __name__ == "__main__":
    main()
