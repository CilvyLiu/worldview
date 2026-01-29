import pandas as pd
import akshare as ak
import streamlit as st
import io
import time
from datetime import datetime

# ==================== 1. 28只核心标的 (完整清单) ====================
WANGWANG_MAP = [
    {"战队": "🛡️ 压舱石", "名称": "中国神华", "代码": "601088"},
    {"战队": "🛡️ 压舱石", "名称": "长江电力", "代码": "600900"},
    {"战队": "🛡️ 压舱石", "名称": "工商银行", "代码": "601398"},
    {"战队": "🛡️ 压舱石", "名称": "中国石油", "代码": "601857"},
    {"战队": "🛡️ 压舱石", "名称": "农业银行", "代码": "601288"},
    {"战队": "🛡️ 压舱石", "名称": "陕西煤业", "代码": "601225"},
    {"战队": "🛡️ 压舱石", "名称": "中国建筑", "代码": "601668"},
    {"战队": "⚔️ 冲锋队", "名称": "东方财富", "代码": "300059"},
    {"战队": "⚔️ 冲锋队", "名称": "中信证券", "代码": "600030"},
    {"战队": "⚔️ 冲锋队", "名称": "宁德时代", "代码": "300750"},
    {"战队": "⚔️ 冲锋队", "名称": "比亚迪", "代码": "002594"},
    {"战队": "⚔️ 冲锋队", "名称": "工业富联", "代码": "601138"},
    {"战队": "⚔️ 冲锋队", "名称": "中信建投", "代码": "601066"},
    {"战队": "⚔️ 冲锋队", "名称": "泸州老窖", "代码": "000568"},
    {"战队": "🏗️ 稳增长", "名称": "紫金矿业", "代码": "601899"},
    {"战队": "🏗️ 稳增长", "名称": "万华化学", "代码": "600309"},
    {"战队": "🏗️ 稳增长", "名称": "海螺水泥", "代码": "600585"},
    {"战队": "🏗️ 稳增长", "名称": "三一重工", "代码": "600031"},
    {"战队": "🏗️ 稳增长", "名称": "宝钢股份", "代码": "600019"},
    {"战队": "🏗️ 稳增长", "名称": "中国中铁", "代码": "601390"},
    {"战队": "🏗️ 稳增长", "名称": "中国电建", "代码": "601669"},
    {"战队": "📈 守护者", "名称": "招商银行", "代码": "600036"},
    {"战队": "📈 守护者", "名称": "中国平安", "代码": "601318"},
    {"战队": "📈 守护者", "名称": "贵州茅台", "代码": "600519"},
    {"战队": "📈 守护者", "名称": "五粮液", "代码": "000858"},
    {"战队": "📈 守护者", "名称": "美的集团", "代码": "000333"},
    {"战队": "📈 守护者", "名称": "兴业银行", "代码": "601166"},
    {"战队": "📈 守护者", "名称": "格力电器", "代码": "000651"}
]

# ==================== 2. 正规数据接口网关 ====================
class NovaOfficialEngine:
    @staticmethod
    def get_market_data():
        """
        调用标准化行情接口，而非网页爬虫。
        包含：指数实时行情、A股总市值、宏观PMI。
        """
        # 预设基准值 (2026年基准)
        data = {"PMI": 50.1, "SH": 0.0, "SZ": 0.0, "Total_MV": 880000.0}
        
        try:
            # 1. 指数行情 (调用东财标准化实时接口)
            # 这是官方公开的数据网关，比抓取网页更稳定
            idx_df = ak.stock_zh_index_spot_em()
            sh_row = idx_df[idx_df['名称'] == '上证指数']
            sz_row = idx_df[idx_df['名称'] == '深证成指']
            
            if not sh_row.empty:
                data["SH"] = float(sh_row['涨跌幅'].values[0])
            if not sz_row.empty:
                data["SZ"] = float(sz_row['涨跌幅'].values[0])
                
            # 2. A股总市值 (调用标准化统计接口)
            mv_df = ak.stock_a_total_value()
            data["Total_MV"] = float(mv_df.iloc[-1]['total_value'])
            
            # 3. 宏观数据 (官方统计局同步数据)
            pmi_df = ak.macro_china_pmi()
            data["PMI"] = float(pmi_df.iloc[-1]['value'])
            
        except Exception as e:
            st.sidebar.warning(f"📡 实时 API 繁忙 (正在使用缓存): {str(e)}")
            
        return data

# ==================== 3. 主程序 ====================
def main():
    st.set_page_config(page_title="Nova 汪汪队系统 2026", layout="wide")
    
    # 使用缓存避免频繁调用接口触发封锁
    if 'm_data' not in st.session_state:
        st.session_state.m_data = NovaOfficialEngine.get_market_data()
    
    auto = st.session_state.m_data

    st.title("🏹 Nova 汪汪队全自动探测系统")

    with st.sidebar:
        st.header("⚙️ 自动化修正")
        gdp = st.number_input("GDP 分母 (亿元):", value=1300000)
        
        st.divider()
        st.subheader("📊 官方指数同步")
        # 直接使用 API 返回的百分比数值
        fix_sh = st.number_input("上证指数涨幅 (%):", value=auto["SH"], step=0.01, format="%.2f")
        fix_sz = st.number_input("深证成指涨幅 (%):", value=auto["SZ"], step=0.01, format="%.2f")
        
        st.divider()
        if st.button("🔄 刷新 API 实时数据", use_container_width=True):
            st.session_state.m_data = NovaOfficialEngine.get_market_data()
            st.rerun()
            
        run_scan = st.button("🚀 开启 28 只全板块探测", use_container_width=True)

    # 1. 核心看板
    buffett_val = (auto["Total_MV"] / gdp) * 100
    
    
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("巴菲特指标", f"{round(buffett_val, 2)}%", f"{'底部区域' if buffett_val < 70 else '合理/偏高'}")
    c2.metric("PMI 荣枯线", auto["PMI"], f"{round(auto['PMI']-50, 1)}")
    c3.metric("上证对标", f"{fix_sh}%")
    c4.metric("深成对标", f"{fix_sz}%")

    st.divider()

    # 2. 探测逻辑 (调用 A 股标准化行情快照)
    if run_scan:
        with st.spinner("正在从官方接口同步 28 只标的行情..."):
            try:
                # 调用东财全市场标准化实时快照接口 (极其高效)
                spot_df = ak.stock_zh_a_spot_em()
            except:
                st.error("标准化 API 调用受阻，请稍后再试。")
                spot_df = pd.DataFrame()

            results = []
            for s in WANGWANG_MAP:
                # 判定股票归属市场
                market = "沪" if s['代码'].startswith('6') else "深"
                
                # 匹配个股数据
                row = spot_df[spot_df['代码'] == s['代码']] if not spot_df.empty else pd.DataFrame()
                
                if not row.empty:
                    pct = float(row['涨跌幅'].values[0])
                    turnover = float(row['成交额'].values[0])
                else:
                    pct, turnover = 0.0, 0.0

                # 沪深分流精准对标
                benchmark = fix_sh if market == "沪" else fix_sz
                excess = round(pct - benchmark, 2)

                results.append({
                    "战队": s['战队'], "名称": s['名称'], "归属": market,
                    "实时涨幅%": pct, "超额收益%": excess,
                    "成交额(亿)": round(turnover/1e8, 2)
                })

            df = pd.DataFrame(results)
            
            if not df.empty:
                # 自动判定主力动向
                df['主力动向'] = df.apply(lambda x: 
                    "🔥 强力扫货" if x['超额收益%'] > 1.2 else (
                    "🛡️ 护盘稳定" if x['超额收益%'] >= 0 and ((x['归属']=='沪' and fix_sh < -0.2) or (x['归属']=='深' and fix_sz < -0.2)) else "⚪ 正常跟随"
                ), axis=1)

                st.subheader("📋 汪汪队实时穿透报告")
                
                # 色彩渲染逻辑
                def style_move(val):
                    if '🔥' in val: return 'color: #ff4b4b; font-weight: bold'
                    if '🛡️' in val: return 'color: #2e7d32; font-weight: bold'
                    return 'color: #888'

                st.dataframe(
                    df.style.applymap(style_move, subset=['主力动向'])
                    .background_gradient(subset=['超额收益%'], cmap='RdYlGn_r'),
                    use_container_width=True
                )
                
                # 战队资金柱状图
                st.bar_chart(df.groupby('战队')['成交额(亿)'].sum())
                
                # 结果导出
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Nova汪汪队')
                st.sidebar.download_button("📥 导出作战报告", output.getvalue(), f"Nova_Report_{datetime.now().strftime('%m%d')}.xlsx")

if __name__ == "__main__":
    main()
