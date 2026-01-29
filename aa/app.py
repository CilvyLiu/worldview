import pandas as pd
import akshare as ak
import streamlit as st
import io
from datetime import datetime

# ==================== 1. 核心标的代码映射 (内置市场属性) ====================
WANGWANG_MAP = [
    {"战队": "🛡️ 压舱石", "名称": "中国神华", "代码": "601088", "市场": "沪"},
    {"战队": "🛡️ 压舱石", "名称": "长江电力", "代码": "600900", "市场": "沪"},
    {"战队": "🛡️ 压舱石", "名称": "工商银行", "代码": "601398", "市场": "沪"},
    {"战队": "🛡️ 压舱石", "名称": "中国石油", "代码": "601857", "市场": "沪"},
    {"战队": "🛡️ 压舱石", "名称": "农业银行", "代码": "601288", "市场": "沪"},
    {"战队": "🛡️ 压舱石", "名称": "陕西煤业", "代码": "601225", "市场": "沪"},
    {"战队": "🛡️ 压舱石", "名称": "中国建筑", "代码": "601668", "市场": "沪"},
    {"战队": "⚔️ 冲锋队", "名称": "东方财富", "代码": "300059", "市场": "深"},
    {"战队": "⚔️ 冲锋队", "名称": "中信证券", "代码": "600030", "市场": "沪"},
    {"战队": "⚔️ 冲锋队", "名称": "宁德时代", "代码": "300750", "市场": "深"},
    {"战队": "⚔️ 冲锋队", "名称": "比亚迪", "代码": "002594", "市场": "深"},
    {"战队": "⚔️ 冲锋队", "名称": "工业富联", "代码": "601138", "市场": "沪"},
    {"战队": "⚔️ 冲锋队", "名称": "中信建投", "代码": "601066", "市场": "沪"},
    {"战队": "⚔️ 冲锋队", "名称": "泸州老窖", "代码": "000568", "市场": "深"},
    {"战队": "🏗️ 稳增长", "名称": "紫金矿业", "代码": "601899", "市场": "沪"},
    {"战队": "🏗️ 稳增长", "名称": "万华化学", "代码": "600309", "市场": "沪"},
    {"战队": "🏗️ 稳增长", "名称": "海螺水泥", "代码": "600585", "市场": "沪"},
    {"战队": "🏗️ 稳增长", "名称": "三一重工", "代码": "600031", "市场": "沪"},
    {"战队": "🏗️ 稳增长", "名称": "宝钢股份", "代码": "600019", "市场": "沪"},
    {"战队": "🏗️ 稳增长", "名称": "中国中铁", "代码": "601390", "市场": "沪"},
    {"战队": "🏗️ 稳增长", "名称": "中国电建", "代码": "601669", "市场": "沪"},
    {"战队": "📈 守护者", "名称": "招商银行", "代码": "600036", "市场": "沪"},
    {"战队": "📈 守护者", "名称": "中国平安", "代码": "601318", "市场": "沪"},
    {"战队": "📈 守护者", "名称": "贵州茅台", "代码": "600519", "市场": "沪"},
    {"战队": "📈 守护者", "名称": "五粮液", "代码": "000858", "市场": "深"},
    {"战队": "📈 守护者", "名称": "美的集团", "代码": "000333", "市场": "深"},
    {"战队": "📈 守护者", "名称": "兴业银行", "代码": "601166", "市场": "沪"},
    {"战队": "📈 守护者", "名称": "格力电器", "代码": "000651", "市场": "深"}
]

# ==================== 2. 全自动增强引擎 ====================
class NovaAutoEngine:
    @staticmethod
    def get_market_data():
        """三位一体自动抓取：沪深指数+总市值+PMI"""
        # 基准存档数据
        data = {"PMI": 50.1, "SH": 0.0, "SZ": 0.0, "Total_MV": 870000.0}
        try:
            # 1. 指数分流抓取
            idx_df = ak.stock_zh_index_spot_em()
            data["SH"] = float(idx_df[idx_df['名称'] == '上证指数']['涨跌幅'].values[0])
            data["SZ"] = float(idx_df[idx_df['名称'] == '深证成指']['涨跌幅'].values[0])
            # 2. 市值一键获取
            mv_df = ak.stock_a_total_value()
            data["Total_MV"] = float(mv_df.iloc[-1]['total_value'])
            # 3. PMI 实时荣枯线
            pmi_df = ak.macro_china_pmi()
            data["PMI"] = float(pmi_df.iloc[-1]['value'])
        except:
            st.sidebar.warning("📡 实时接口受限，已启用逻辑存档。")
        return data

# ==================== 3. UI 界面渲染 ====================
def main():
    st.set_page_config(page_title="Nova 汪汪队 2026", layout="wide")
    auto = NovaAutoEngine.get_market_data()

    st.title("🏹 Nova 汪汪队全自动探测系统")

    with st.sidebar:
        st.header("⚙️ 自动化纠偏")
        gdp = st.number_input("1. GDP 分母 (亿元):", value=1300000)
        st.divider()
        st.subheader("📊 沪深指数涨幅修正")
        fix_sh = st.number_input("上证指数 (%):", value=auto["SH"])
        fix_sz = st.number_input("深证成指 (%):", value=auto["SZ"])
        st.divider()
        run_scan = st.button("🚀 开启 28 只全板块穿透", use_container_width=True)

    # 1. 仪表盘：宏观风格判定
    buffett_val = (auto["Total_MV"] / gdp) * 100
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("巴菲特指标", f"{round(buffett_val, 2)}%", f"{'安全' if buffett_val < 75 else '警惕'}")
    c2.metric("PMI 荣枯线", auto["PMI"], f"{round(auto['PMI']-50, 1)}")
    c3.metric("上证指数", f"{fix_sh}%")
    c4.metric("深证成指", f"{fix_sz}%")

    style = "💎 底部价值" if buffett_val < 65 else "⚖️ 均衡博弈"
    if auto["PMI"] > 50: style = "🚀 扩张扩张"
    st.subheader(f"当前市场取向：{style}")

    st.divider()

    # 2. 探测核心逻辑
    if run_scan:
        with st.spinner("执行沪深精准对标探测..."):
            results = []
            try:
                spot_df = ak.stock_zh_a_spot_em()
            except:
                spot_df = pd.DataFrame()

            for s in WANGWANG_MAP:
                # 获取个股数据
                row = spot_df[spot_df['代码'] == s['代码']] if not spot_df.empty else pd.DataFrame()
                pct = float(row['涨跌幅'].values[0]) if not row.empty else 0.0
                turnover = float(row['成交额'].values[0]) if not row.empty else 0.0

                # 精准对标分流
                benchmark = fix_sh if s['市场'] == "沪" else fix_sz
                excess = round(pct - benchmark, 2)

                results.append({
                    "战队": s['战队'], "名称": s['名称'], "归属": s['市场'],
                    "涨幅%": pct, "对标指数": "上证" if s['市场']=="沪" else "深成",
                    "超额收益%": excess, "成交额(亿)": round(turnover/1e8, 2)
                })

            df = pd.DataFrame(results)
            
            # 汪汪队主力动向智能判定
            df['主力动向'] = df.apply(lambda x: 
                "🔥 强力扫货" if x['超额收益%'] > 1.2 else (
                "🛡️ 护盘稳定" if x['超额收益%'] >= 0 and ((x['归属']=='沪' and fix_sh < -0.2) or (x['归属']=='深' and fix_sz < -0.2)) else "⚪ 正常跟随"
            ), axis=1)

            # 展示与色彩渲染
            st.subheader("📋 沪深对标探测报告")
            def color_move(val):
                color = '#ff4b4b' if '🔥' in val else ('#2e7d32' if '🛡️' in val else '#666')
                return f'color: {color}; font-weight: bold'

            st.dataframe(df.style.applymap(color_move, subset=['主力动向']).background_gradient(subset=['超额收益%'], cmap='RdYlGn_r'), use_container_width=True)

            # 战队资金流可视化
            st.bar_chart(df.groupby(['归属', '战队'])['成交额(亿)'].sum().unstack())

            # 导出 Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='汪汪队报告')
            st.sidebar.download_button("📥 导出 Excel", output.getvalue(), f"Nova_Report_{datetime.now().strftime('%m%d')}.xlsx")

if __name__ == "__main__":
    main()
