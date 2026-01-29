import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
from datetime import datetime

# ==================== 1. 数据采集模块 ====================
class DataCenter:
    @staticmethod
    def _safe_val(df, key, default=0.0):
        """增强版取值：自动处理 None、空表和列名匹配"""
        if df is None or df.empty: return default
        try:
            numeric_df = df.select_dtypes(include=['number'])
            # 优先找包含 key 的列，找不到就取最后一列
            cols = [c for c in numeric_df.columns if key.lower() in c.lower() or c in ['值', '金额', 'last']]
            target_col = cols[0] if cols else numeric_df.columns[-1]
            val = numeric_df[target_col].iloc[-1]
            return float(val) if pd.notnull(val) else default
        except:
            return default

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_macro_data():
        """获取宏观数据：PMI, M1, 汇率"""
        data = {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "USDCNH": 7.2}
        try:
            # 1. PMI (制造业)
            data["PMI"] = DataCenter._safe_val(ak.macro_china_pmi(), "value", 50.0)
            
            # 2. M1 (货币供应量) - 报错高发区修复
            m1_df = ak.macro_china_m2_yearly()
            if not m1_df.empty and len(m1_df) >= 2:
                # 取倒数第一和第二个数
                data["M1"] = DataCenter._safe_float_convert(m1_df.iloc[-1, 1])
                data["M1_prev"] = DataCenter._safe_float_convert(m1_df.iloc[-2, 1])
            
            # 3. 汇率
            fx_df = ak.fx_spot_quote()
            if not fx_df.empty:
                row = fx_df[fx_df['symbol'] == 'USDCNH']
                data["USDCNH"] = DataCenter._safe_val(row, "last", 7.2)
        except Exception as e:
            st.sidebar.error(f"数据源同步异常: {e}")
        return data

    @staticmethod
    def _safe_float_convert(val):
        try: return float(val) if pd.notnull(val) else 0.0
        except: return 0.0

    @staticmethod
    @st.cache_data(ttl=300)
    def get_wang_data():
        """汪汪队 ETF 动向监控"""
        symbols = {"沪深300": "sh510300", "中证500": "sh510500", "中证1000": "sh512100"}
        flows = {}
        for name, code in symbols.items():
            try:
                df = ak.fund_etf_hist_sina(symbol=code)
                if not df.empty and len(df) >= 20:
                    # 计算最近成交额相对于 20 日均值的偏离度 (Z-Score)
                    recent_amt = df['amount'].tail(20)
                    z_score = (recent_amt.iloc[-1] - recent_amt.mean()) / recent_amt.std()
                    flows[name] = round(z_score, 2)
                else: flows[name] = 0.0
            except: flows[name] = 0.0
        return flows

# ==================== 2. 可视化布局 ====================
def main():
    st.set_page_config(page_title="Nova 全局穿透盘", layout="wide")
    st.title("🛡️ Nova 宏观大局 & 汪汪动向监控")
    
    dc = DataCenter()
    
    # 获取数据
    with st.spinner('正在透视宏观与资金面数据...'):
        macro = dc.get_macro_data()
        wang = dc.get_wang_data()

    # 第一行：宏观看板
    st.subheader("🌐 核心宏观指标")
    c1, c2, c3, c4 = st.columns(4)
    
    # PMI 仪表
    c1.metric("制造业 PMI", f"{macro['PMI']}", delta=round(macro['PMI']-50, 2))
    
    # M1 趋势 (修复报错)
    m1_delta = round(macro['M1'] - macro['M1_prev'], 2)
    c2.metric("M1 货币增速", f"{macro['M1']}%", delta=f"{m1_delta}%")
    
    # 汇率
    c3.metric("离岸人民币 USDCNH", f"{macro['USDCNH']}")
    
    # 汪汪状态
    active_wang = [k for k, v in wang.items() if v > 2.0]
    c4.metric("汪汪队异动指数", f"{len(active_wang)} 个方向", delta="异常入场" if active_wang else "自然波动")

    st.divider()

    # 第二行：汪汪介入强度图
    st.subheader("📊 汪汪队 ETF 介入强度 (Z-Score)")
    
    if wang:
        wang_df = pd.DataFrame(list(wang.items()), columns=['指数', '强度'])
        fig = px.bar(wang_df, x='指数', y='强度', color='强度', color_continuous_scale='RdBu_r')
        fig.add_hline(y=2.0, line_dash="dash", line_color="red", annotation_text="国家队异常放量区")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("汪汪队数据抓取中，请稍后刷新...")

    # 第三行：板块警惕与建议
    st.divider()
    st.subheader("🚨 Nova 风险穿透")
    
    col_l, col_r = st.columns(2)
    with col_l:
        if macro['PMI'] < 50:
            st.error("**警惕板块：海螺水泥、万华化学 (顺周期)**")
            st.write("逻辑：PMI 在荣枯线下，顺周期缺乏需求支撑。")
        else:
            st.success("顺周期基本面平稳")
            
    with col_r:
        if active_wang:
            st.warning(f"**关注板块：{', '.join(active_wang)} 权重股**")
            st.write("逻辑：监测到护盘资金暴力拉升，关注格力、招行等核心资产。")
        else:
            st.info("目前暂无显著资金护盘迹象，建议防御。")

if __name__ == "__main__":
    main()
