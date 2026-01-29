import pandas as pd
import akshare as ak
import streamlit as st
import io
from datetime import datetime

# ==================== 1. 28只核心标的 (全量不省略) ====================
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

# ==================== 2. 全自动数据探测引擎 ====================
class NovaPowerEngine:
    @staticmethod
    def get_market_data():
        """强制多口径抓取：指数、市值、PMI"""
        # 默认垫底数据
        data = {"PMI": 50.1, "SH": 0.0, "SZ": 0.0, "Total_MV": 880000.0}
        try:
            # 1. 抓取指数快照 (修复了之前中断的语句)
            idx_df = ak.stock_zh_index_spot_em()
            
            # 这里的筛选逻辑要健壮：防止名称不匹配
            sh_match = idx_df[idx_df['名称'].str.contains('上证指数', na=False)]
            sz_match = idx_df[idx_df['名称'].str.contains('深证成指', na=False)]
            
            data["SH"] = float(sh_match['涨跌幅'].values[0]) if not sh_match.empty else 0.0
            data["SZ"] = float(sz_match['涨跌幅'].values[0]) if not sz_match.empty else 0.0
            
            # 2. 获取 A 股总市值
            mv_df = ak.stock_a_total_value()
            data["Total_MV"] = float(mv_df.iloc[-1]['total_value'])
            
            # 3. 获取最新 PMI (荣枯值)
            pmi_df = ak.macro_china_pmi()
            data["PMI"] = float(pmi_df.iloc[-1]['value'])
        except Exception as e:
            st.sidebar.error(f"自动化引擎取数受阻: {e}")
        return data

# ==================== 3. UI 渲染逻辑 ====================
def main():
    st.set_page_config(page_title="Nova 汪汪队探测器", layout="wide")
    
    # Session State 保持刷新不重置
    if 'market_snapshot' not in st.session_state:
        st.session_state.market_snapshot = NovaPowerEngine.get_market_data()
    
    auto = st.session_state.market_snapshot

    st.title("🏹 Nova 汪汪队实时探测系统")

    with st.sidebar:
        st.header("⚙️ 自动化修正")
        gdp = st.number_input("GDP 分母 (亿元):", value=1300000)
        
        st.divider()
        st.subheader("📊 沪深指数自动同步")
        # 修复了百分比显示逻辑
        fix_sh = st.number_input("上证指数涨幅 (%):", value=auto["SH"], step=0.01, format="%.2f")
        fix_sz = st.number_input("深证成指涨幅 (%):", value=auto["SZ"], step=0.01, format="%.2f")
        
        st.divider()
        if st.button("🔄 强制全网刷新", use_container_width=True):
            st.session_state.market_snapshot = NovaPowerEngine.get_market_data()
            st.rerun()
        
        run_scan = st.button("🚀 开启 28 只精准穿透", use_container_width=True)

    # 1. 顶部核心指标
    buffett = (auto["Total_MV"] / gdp) * 100
    
    
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("巴菲特指标", f"{round(buffett, 2)}%", f"{'安全' if buffett < 70 else '注意'}")
    c2.metric("PMI 荣枯线", auto["PMI"], f"{round(auto['PMI']-50, 1)}", help="大于50为扩张，小于50为收缩")
    c3.metric("上证对标", f"{fix_sh}%")
    c4.metric("深成对标", f"{fix_sz}%")

    st.divider()

    # 2. 执行穿透分析
    if run_scan:
        with st.spinner("正在点名探测 28 只核心标的..."):
            try:
                # 获取全 A 行情快照
                all_stocks = ak.stock_zh_a_spot_em()
            except:
                st.error("无法连接实时行情接口")
                all_stocks = pd.DataFrame()

            results = []
            for s in WANGWANG_MAP:
                # 市场分流逻辑：6开头是沪，其他（0/3）是深
                is_sh = s['代码'].startswith('6')
                m_label = "沪" if is_sh else "深"
                
                # 匹配股票
                row = all_stocks[all_stocks['代码'] == s['代码']] if not all_stocks.empty else pd.DataFrame()
                pct = float(row['涨跌幅'].values[0]) if not row.empty else 0.0
                turnover = float(row['成交额'].values[0]) if not row.empty else 0.0

                # 沪深分流：减去对应的指数涨幅
                bench = fix_sh if is_sh else fix_sz
                excess = round(pct - bench, 2)

                results.append({
                    "战队": s['战队'], "名称": s['名称'], "归属": m_label,
                    "实时涨幅%": pct, "超额收益%": excess,
                    "成交额(亿)": round(turnover/1e8, 2)
                })

            df = pd.DataFrame(results)
            
            if not df.empty:
                # 判定主力动向
                df['主力动向'] = df.apply(lambda x: 
                    "🔥 强力扫货" if x['超额收益%'] > 1.2 else (
                    "🛡️ 护盘支撑" if x['超额收益%'] >= 0 and ((x['归属']=='沪' and fix_sh < -0.2) or (x['归属']=='深' and fix_sz < -0.2)) else "⚪ 正常跟随"
                ), axis=1)

                st.subheader("📋 汪汪队穿透探测报告")
                
                # 增加样式增强
                def style_move(val):
                    color = '#ff4b4b' if '🔥' in val else ('#2e7d32' if '🛡️' in val else '#888')
                    return f'color: {color}; font-weight: bold'

                st.dataframe(
                    df.style.applymap(style_move, subset=['主力动向'])
                    .background_gradient(subset=['超额收益%'], cmap='RdYlGn_r'),
                    use_container_width=True
                )
                
                # 战队资金柱状图
                st.write("💰 战队资金活跃度对比")
                st.bar_chart(df.groupby('战队')['成交额(亿)'].sum())
                
                # 导出
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='探测结果')
                st.sidebar.download_button("📥 导出作战 Excel", output.getvalue(), "Nova_Report.xlsx")

if __name__ == "__main__":
    main()
