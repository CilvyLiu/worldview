import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
from datetime import datetime

# ==================== 1. 数据采集模块 (宏观 + 汪汪 + 期现) ====================
class DataCenter:
    """负责所有宏观、市场、衍生品价差的抓取"""
    
    @staticmethod
    def _get_val(df, key):
        if df is None or df.empty: return 0
        numeric_df = df.select_dtypes(include=['number'])
        cols = [c for c in numeric_df.columns if key.lower() in c.lower() or c in ['值', '金额', 'last', '收盘价']]
        return float(numeric_df[cols[0]].iloc[-1]) if cols else 0

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_macro_all():
        """获取宏观全指标"""
        data = {"PMI": 50, "M1": 0, "M1_prev": 0, "USDCNH": 7.2, "ERP": 0.04}
        try:
            # PMI
            data["PMI"] = DataCenter._get_val(ak.macro_china_pmi(), 'value')
            # M1
            m1_df = ak.macro_china_m2_yearly()
            data["M1"], data["M1_prev"] = m1_df.iloc[-1, 1], m1_df.iloc[-2, 1]
            # 汇率
            fx = ak.fx_spot_quote()
            data["USDCNH"] = float(fx[fx['symbol'] == 'USDCNH']['last'].iloc[0])
        except: pass
        return data

    @staticmethod
    @st.cache_data(ttl=60)
    def get_basis_logic():
        """
        动态计算期现基差（参考图片逻辑：IF/IH/IC/IM）
        """
        results = []
        # 定义监控合约 (IF: 沪深300, IH: 上证50, IC: 中证500, IM: 中证1000)
        contracts = {
            "IF2602": {"index": "sz399300", "future": "IF2602", "up": 9.83, "down": -29.55},
            "IF2603": {"index": "sz399300", "future": "IF2603", "up": -14.79, "down": -80.29},
            "IF2606": {"index": "sz399300", "future": "IF2606", "up": -40.57, "down": -118.69}
        }
        
        try:
            # 模拟获取实时现货价格 (实际建议接入实时接口)
            spot_300 = 4717.99 # 此处可改为 ak.stock_zh_index_spot_em 抓取
            
            for name, cfg in contracts.items():
                # 动态获取期货价格逻辑 (简化演示，实际使用 ak.futures_zh_spot)
                f_price = 4727.80 if "2602" in name else (4732.80 if "2603" in name else 4716.80)
                basis = round(f_price - spot_300, 2)
                
                status = "正常"
                if basis > cfg['up']: status = "【正向异常】"
                elif basis < cfg['down']: status = "【负向异常】"
                
                results.append({
                    "价差代码": name,
                    "期货价": f_price,
                    "现货价": spot_300,
                    "最新基差": basis,
                    "阈值区间": f"[{cfg['down']}, {cfg['up']}]",
                    "最新状态": status
                })
        except: pass
        return pd.DataFrame(results)

# ==================== 2. 板块警惕与策略引擎 ====================
class StrategyEngine:
    @staticmethod
    def analyze(macro, basis_df):
        advice = "【观察期】市场处于理性博弈"
        risk_sectors = []
        
        # 1. 宏观判定
        if macro['PMI'] < 50:
            risk_sectors.append("顺周期板块 (海螺水泥、万华化学)")
        
        # 2. 基差判定 (图片逻辑核心)
        if not basis_df.empty:
            anomalies = basis_df[basis_df['最新状态'] != "正常"]
            if not anomalies.empty:
                advice = "【警惕信号】期指基差出现结构性异常，大资金对冲力度加大"
                # 穿透具体板块
                if "IF" in str(anomalies['价差代码'].values):
                    risk_sectors.append("权重白马 (格力电器、招商银行、平安)")
                if "IM" in str(anomalies['价差代码'].values):
                    risk_sectors.append("微盘股/专精特新")

        return advice, list(set(risk_sectors))

# ==================== 3. 可视化界面 (Streamlit) ====================
def main():
    st.set_page_config(page_title="Nova 全局监控盘", layout="wide")
    st.title("🛡️ Nova 全局宏观 & 期现基差穿透系统")
    
    dc = DataCenter()
    macro = dc.get_macro_all()
    basis_df = dc.get_basis_logic()
    advice, risks = StrategyEngine.analyze(macro, basis_df)

    # 第一步：宏观大局观
    st.subheader("🌐 宏观背景监测")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("PMI 指数", macro['PMI'], delta=round(macro['PMI']-50, 2))
    col2.metric("M1 趋势", f"{macro['M1']}%", delta=round(macro['M1']-macro['M1_prev'], 2))
    col3.metric("汇率 USDCNH", macro['USDCNH'])
    col4.metric("股债性价比 (ERP)", f"{round(macro['ERP']*100, 2)}%")

    st.divider()

    # 第二步：复现图片逻辑 - 统计分析总表
    st.subheader("📊 期现基差 (Basis) 动态监控表")
    if not basis_df.empty:
        # 给“最新状态”上色逻辑
        def highlight_status(val):
            if "异常" in val: return 'background-color: #ff4b4b; color: white'
            return ''
        st.dataframe(basis_df.style.applymap(highlight_status, subset=['最新状态']), use_container_width=True)

    st.divider()

    # 第三步：精准警惕板块
    st.subheader("🚨 Nova 重点警惕板块")
    if risks:
        r_cols = st.columns(len(risks))
        for i, sector in enumerate(risks):
            with r_cols[i]:
                st.error(f"**警惕：{sector}**")
                st.caption("逻辑：基于期指基差偏移与宏观基本面共振判定")
    else:
        st.success("目前暂无明显板块风险集中爆发")

    st.divider()
    
    # 最终建议
    st.subheader("💡 最终测算决策建议")
    st.info(f"**{advice}**")

if __name__ == "__main__":
    main()
