import pandas as pd
import akshare as ak
import streamlit as st
import io
from datetime import datetime

# ==================== 1. 深度穿透逻辑配置 ====================
ARMY_CONFIG = {
    "🛡️ 压舱石 (高股息/中特估)": {
        "stocks": {"中国神华": "601088", "中国石油": "601857", "长江电力": "600900", "工商银行": "601398", "中国建筑": "601668", "农业银行": "601288", "陕西煤业": "601225"},
        "trigger": "Basis", # 靠基差驱动
        "desc": "当大盘基差负值扩大，此处常有救灾资金。"
    },
    "⚔️ 冲锋队 (非银金融/券商)": {
        "stocks": {"中信证券": "600030", "东方财富": "300059", "中信建投": "601066", "贵州茅台": "600519", "五粮液": "000858", "格力电器": "000651", "泸州老窖": "000568"},
        "trigger": "M1", # 靠资金活性驱动
        "desc": "汪汪队点火风向标。成交额若破百亿，介入信号最强。"
    },
    "🏗️ 稳增长 (周期龙头)": {
        "stocks": {"海螺水泥": "600585", "万华化学": "600309", "三一重工": "600031", "紫金矿业": "601899", "宝钢股份": "600019", "中国中铁": "601390", "中国电建": "601669"},
        "trigger": "PMI", # 靠经济预期驱动
        "desc": "若PMI收缩但股价逆势横盘，说明有资金在死守。"
    },
    "📈 守护者 (核心权重/ETF)": {
        "stocks": {"招商银行": "600036", "中国平安": "601318", "比亚迪": "002594", "宁德时代": "300750", "美的集团": "000333", "兴业银行": "601166", "工业富联": "601138"},
        "trigger": "FX", # 靠汇率驱动
        "desc": "汇率波动剧烈时的‘定海神针’，护盘必选。"
    }
}

# ==================== 2. 全板块动态扫描引擎 ====================
class WangWangScanner:
    @staticmethod
    def scan_now():
        results = []
        try:
            # A. 宏观动态
            pmi_df = ak.macro_china_pmi()
            pmi = float(pmi_df.select_dtypes(include=['number']).iloc[-1, 0])
            fx_df = ak.fx_spot_quote()
            fx = float(fx_df[fx_df.iloc[:,0].str.contains('USDCNH')].iloc[0, 1])
            
            # B. 实时行情全扫描
            st.write("🔄 正在扫描全板块 28 只核心标的实时盘口...")
            spot_df = ak.stock_zh_a_spot_em()
            
            for sector, cfg in ARMY_CONFIG.items():
                for name, code in cfg["stocks"].items():
                    row = spot_df[spot_df['名称'] == name]
                    if not row.empty:
                        price = row['最新价'].values[0]
                        pct = row['涨跌幅'].values[0]
                        turnover = row['成交额'].values[0] / 100000000 # 换算成亿元
                        
                        # C. 判定介入迹象 (核心逻辑)
                        # 逻辑：如果涨跌幅 > 0.5% 且成交额在该板块前列，定义为“疑似介入”
                        intervention = "⚪ 暂无明显迹象"
                        if pct > 0.5 and turnover > 5: # 简单阈值：涨幅>0.5%且成交过5亿
                            intervention = "🔥 疑似介入点火"
                        elif pct < -1 and turnover > 10:
                            intervention = "⚠️ 承压放量"
                        elif abs(pct) < 0.2 and turnover > 8:
                            intervention = "🛡️ 强力托底中"

                        # D. 差异化建议
                        if "周期" in sector: advice = "PMI驱动" if pmi > 50 else "逆周期托底"
                        elif "冲锋" in sector: advice = "攻击性买入" if pct > 0 else "弹药补给中"
                        else: advice = "被动指数管理"

                        results.append({
                            "作战板块": sector,
                            "股票名称": name,
                            "最新价": price,
                            "涨跌幅%": pct,
                            "成交额(亿)": round(turnover, 2),
                            "介入迹象分析": intervention,
                            "板块底层逻辑": advice,
                            "参考指标": f"PMI:{pmi} / FX:{fx}"
                        })
        except Exception as e:
            st.error(f"扫描中断: {e}")
        return results

# ==================== 3. Nova 控制中心 ====================
def main():
    st.set_page_config(page_title="Nova 汪汪队全板块扫描", layout="wide")
    st.header("🚩 Nova 汪汪队全板块动态扫描 (实时数据版)")

    if st.sidebar.button("🔍 开始全板块深度扫描"):
        scan_data = WangWangScanner.scan_now()
        st.session_state.scan_results = scan_data

    if "scan_results" in st.session_state:
        df = pd.DataFrame(st.session_state.scan_results)

        # 数据可视化统计
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📊 板块介入度统计")
            inter_counts = df['介入迹象分析'].value_counts()
            st.bar_chart(inter_counts)
        with c2:
            st.subheader("💰 今日交火最剧烈标的")
            top_active = df.sort_values(by="成交额(亿)", ascending=False).head(5)
            st.table(top_active[['股票名称', '涨跌幅%', '成交额(亿)', '介入迹象分析']])

        st.divider()
        st.subheader("📋 全量作战地图 (已按板块穿透)")
        
        # 实时表格着色处理
        def color_intervention(val):
            if '🔥' in val: return 'background-color: #ff4b4b; color: white'
            if '🛡️' in val: return 'background-color: #2e7d32; color: white'
            return ''
        
        st.dataframe(df.style.applymap(color_intervention, subset=['介入迹象分析']), use_container_width=True)

        # 一键导出 Excel (包含所有动态字段)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='全板块扫描报告', index=False)
        
        st.sidebar.download_button(
            label="📥 导出今日全扫描 Excel",
            data=output.getvalue(),
            file_name=f"Nova_WangWang_Scan_{datetime.now().strftime('%m%d_%H%M')}.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.info("Nova，点击侧边栏‘开始全板块深度扫描’，我将为你实时穿透 28 只核心股的介入情况。")

if __name__ == "__main__":
    main()
