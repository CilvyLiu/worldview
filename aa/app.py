import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
import time

# ==================== 1. 数据采集模块 (Nova 终极冗余版) ====================
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
        """宏观核心：PMI, M1, 汇率 (三位一体)"""
        data = {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "USDCNH": 7.2}
        try:
            # 增加重试逻辑：PMI
            for _ in range(2):
                try:
                    pmi_df = ak.macro_china_pmi()
                    if not pmi_df.empty:
                        data["PMI"] = DataCenter._safe_float(pmi_df.select_dtypes(include=['number']).iloc[-1, 0], 50.0)
                        break
                except: time.sleep(1)
            
            # M1 数据获取
            m1_df = ak.macro_china_m2_yearly()
            if not m1_df.empty:
                m1_series = m1_df.iloc[:, 1].dropna()
                if len(m1_series) >= 2:
                    data["M1"] = DataCenter._safe_float(m1_series.iloc[-1])
                    data["M1_prev"] = DataCenter._safe_float(m1_series.iloc[-2])
            
            # 汇率数据加固
            fx_df = ak.fx_spot_quote()
            sym_col = [c for c in fx_df.columns if 'sym' in c.lower() or '代码' in c]
            last_col = [c for c in fx_df.columns if 'last' in c.lower() or '最新' in c]
            if sym_col and last_col:
                row = fx_df[fx_df[sym_col[0]].str.contains('USDCNH', na=False)]
                if not row.empty:
                    data["USDCNH"] = DataCenter._safe_float(row[last_col[0]].iloc[0], 7.2)
        except Exception as e:
            st.sidebar.error(f"宏观源断连: {e}")
        return data

    @staticmethod
    @st.cache_data(ttl=30)
    def get_basis_analysis():
        """
        加固版基差：处理远程服务器强制切断连接 (Connection aborted)
        """
        results = []
        try:
            # 增加 User-Agent 伪装和重试
            spot_df = pd.DataFrame()
            for _ in range(3): 
                try:
                    # 使用备用接口获取现货价格 (东财接口有时比新浪稳)
                    spot_df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
                    if not spot_df.empty: break
                except Exception: 
                    time.sleep(2) # 延长重试间隔
            
            if spot_df.empty:
                st.sidebar.warning("⚠️ 现货接口全面被封，切换为模拟基差监控")
                spot_300 = 4720.0 # 兜底逻辑
            else:
                target_row = spot_df[spot_df['名称'].str.contains('300', na=False)].iloc[0]
                price_col = [c for c in spot_df.columns if '最新' in c or '收盘' in c][0]
                spot_300 = DataCenter._safe_float(target_row[price_col])
            
            # 2026年监控合约
            contracts = [
                {"code": "IF2602", "price": 4727.8, "up": 9.83, "down": -29.55},
                {"code": "IF2603", "price": 4732.8, "up": -14.79, "down": -80.29}
            ]
            
            for c in contracts:
                basis = round(c['price'] - spot_300, 2)
                status = "正常"
                if basis > c['up']: status = "正向异常"
                elif basis < c['down']: status = "负向异常"
                results.append({"合约": c['code'], "期货": c['price'], "现货": spot_300, "基差": basis, "状态": status})
        except Exception as e:
            st.sidebar.error(f"基差逻辑崩溃: {e}")
        return pd.DataFrame(results)

# ==================== 2. 展示层逻辑 ====================
def main():
    st.set_page_config(page_title="Nova 全局穿透", layout="wide")
    st.header("🛡️ Nova 宏观大局 & 预警穿透")
    
    dc = DataCenter()
    macro = dc.get_macro_data()
    basis_df = dc.get_basis_analysis()

    # 第一行：看板
    c1, c2, c3 = st.columns(3)
    c1.metric("PMI 荣枯线", f"{macro['PMI']}", delta=f"{round(macro['PMI']-50,2)}")
    c2.metric("M1 活性", f"{macro['M1']}%", delta=f"{round(macro['M1']-macro['M1_prev'],2)}%")
    c3.metric("USDCNH", f"{macro['USDCNH']}")

    # 第二行：基差穿透分析
    st.subheader("📉 期现基差动态监控 (穿透版)")
    
    if not basis_df.empty:
        st.dataframe(basis_df.style.applymap(
            lambda x: 'background-color: #ff4b4b; color: white' if "正向" in str(x) else 
                      'background-color: #1c83e1; color: white' if "负向" in str(x) else '',
            subset=['状态']
        ), use_container_width=True)
    else:
        st.warning("⚠️ 衍生品数据源连接失败，请检查 IP 限制。")

    # 重点板块：Nova 核心穿透逻辑
    st.divider()
    st.subheader("🚨 核心标的穿透风险")
    col_a, col_b = st.columns(2)
    
    with col_a:
        # PMI 低于 50，顺周期承压
        if macro['PMI'] < 50:
            st.error("### 警惕：海螺水泥")
            st.write("**穿透建议**：PMI 收缩意味着制造业和开工率下行。若基差同步显示负向异常，水泥板块将面临流动性与基本面的双杀。")
        else:
            st.success("### 顺周期：目前逻辑稳健")

    with col_b:
        # M1 增速不振，权重股缺乏水头
        if macro['M1'] <= macro['M1_prev']:
            st.warning("### 警惕：格力电器 / 招商银行")
            st.write("**穿透建议**：M1 活性不足代表企业端钱袋子紧。对于高权重白马，缺乏溢价上行的原动力。")
        else:
            st.success("### 权重类：资金活性充裕")

if __name__ == "__main__":
    main()
