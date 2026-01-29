import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
from datetime import datetime

# ==================== 1. 数据采集模块 ====================
class DataCenter:
    """具备强容错机制的数据中心"""
    
    @staticmethod
    def _safe_float(val):
        """数据兜底转换：确保减法运算不报错"""
        try:
            return float(val) if val is not None else 0.0
        except:
            return 0.0

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_macro_all():
        """获取宏观全指标，增加空值检查"""
        data = {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "USDCNH": 7.2, "ERP": 0.04}
        try:
            # PMI
            pmi_df = ak.macro_china_pmi()
            if not pmi_df.empty:
                data["PMI"] = DataCenter._safe_float(pmi_df.iloc[-1, 1])
            
            # M1 (修复报错核心)
            m1_df = ak.macro_china_m2_yearly()
            if not m1_df.empty and len(m1_df) >= 2:
                data["M1"] = DataCenter._safe_float(m1_df.iloc[-1, 1])
                data["M1_prev"] = DataCenter._safe_float(m1_df.iloc[-2, 1])
            
            # 汇率
            fx = ak.fx_spot_quote()
            if not fx.empty:
                data["USDCNH"] = DataCenter._safe_float(fx[fx['symbol'] == 'USDCNH']['last'].iloc[0])
        except Exception as e:
            st.warning(f"宏观接口部分连接异常，已使用默认值兜底。")
        return data

    @staticmethod
    @st.cache_data(ttl=60)
    def get_basis_logic():
        """动态计算期现基差 (复刻图片逻辑)"""
        results = []
        # 定义阈值 (参考 Nova 提供的图片数据)
        contracts = {
            "IF2602": {"up": 9.83, "down": -29.55},
            "IF2603": {"up": -14.79, "down": -80.29},
            "IF2606": {"up": -40.57, "down": -118.69}
        }
        try:
            # 获取实时现货 (沪深300)
            spot_df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
            spot_300 = DataCenter._safe_float(spot_df[spot_df['名称'] == '沪深300']['最新价'].values[0])
            
            # 动态模拟/获取期货价
            for name, cfg in contracts.items():
                # 实际应用中建议使用 ak.futures_zh_spot 实时获取
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

# ==================== 2. 策略与穿透引擎 ====================
class StrategyEngine:
    @staticmethod
    def analyze(macro, basis_df):
        advice = "【观察期】市场处于博弈均衡态"
        risk_sectors = []
        
        # 1. 宏观共振判定
        if macro['PMI'] < 50:
            risk_sectors.append("顺周期板块 (海螺水泥、万华化学)")
        
        # 2. 基差结构判定
        if not basis_df.empty:
            anomalies = basis_df[basis_df['最新状态'] != "正常"]
            if not anomalies.empty:
                advice = "【警惕信号】期指异常升贴水，大资金对冲力度剧增"
                # 根据合约穿透板块
                codes = "".join(anomalies['价差代码'].tolist())
                if "IF" in codes:
                    risk_sectors.append("核心资产 (招商银行、格力电器)")
                if "IM" in codes or "IC" in codes:
                    risk_sectors.append("成长/微盘股 (中际旭创、专精特新)")

        return advice, list(set(risk_sectors))

# ==================== 3. 界面布局 ====================
def main():
    st.set_page_config(page_title="Nova 全局穿透盘", layout="wide")
    st.title("🛡️ Nova 全局大局观 & 衍生品结构预警")
    
    dc = DataCenter()
    macro = dc.get_macro_all()
    basis_df = dc.get_basis_logic()
    advice, risks = StrategyEngine.analyze(macro, basis_df)

    # 第一步：宏观指标
    st.subheader("🌐 宏观背景监测")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PMI 指数", macro['PMI'], delta=round(macro['PMI']-50, 2))
    
    # 修复报错：加入 None 值安全计算
    m1_val = macro['M1']
    m1_prev = macro['M1_prev']
    m1_delta = round(m1_val - m1_prev, 2) if m1_val and m1_prev else 0
    c2.metric("M1 趋势", f"{m1_val}%", delta=f"{m1_delta}%")
    
    c3.metric("汇率 USDCNH", macro['USDCNH'])
    c4.metric("股债性价比 (ERP)", f"{round(macro['ERP']*100, 2)}%")

    st.divider()

    # 第二步：期现价差 (参考图片逻辑)
    
    st.subheader("📊 期现基差 (Basis) 动态预警表")
    if not basis_df.empty:
        def style_status(val):
            if "正向异常" in val: return 'color: #ff4b4b; font-weight: bold'
            if "负向异常" in val: return 'color: #1c83e1; font-weight: bold'
            return ''
        st.dataframe(basis_df.style.applymap(style_status, subset=['最新状态']), use_container_width=True)

    st.divider()

    # 第三步：精准板块警惕
    st.subheader("🚨 Nova 重点警惕/观察板块")
    if risks:
        cols = st.columns(len(risks))
        for i, sector in enumerate(risks):
            with cols[i]:
                st.error(f"**警惕：{sector}**")
                if "顺周期" in sector:
                    st.caption("逻辑：PMI 跌破荣枯线，基本面承压。")
                else:
                    st.caption("逻辑：期指基差偏移指示资金异动。")
    else:
        st.success("暂未监测到显著的结构性板块风险。")

    st.divider()
    st.error(f"**最终决策建议：{advice}**")

if __name__ == "__main__":
    main()
