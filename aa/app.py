import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
from datetime import datetime

#=======================数据中心=======================#
class DataCenter:
    """终极防错版：自适应列名 + 冗余接口切换"""
    
    @staticmethod
    def _safe_get_last(df, col_keywords=['value', '值', '成交额', 'pe', 'yield', '收益率']):
        if df is None or df.empty:
            return None
        # 排除日期和字符串，锁定数值列
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if not numeric_cols:
            return None
        
        # 优先找关键词匹配的列
        for kw in col_keywords:
            for col in numeric_cols:
                if kw.lower() in col.lower():
                    series = df[col].dropna()
                    return float(series.iloc[-1]) if not series.empty else None
        
        # 兜底：取最后一个数值列
        series = df[numeric_cols[-1]].dropna()
        return float(series.iloc[-1]) if not series.empty else None

    @staticmethod
    @st.cache_data(ttl=86400)
    def get_dynamic_gdp():
        try:
            gdp_df = ak.macro_china_gdp_yearly()
            val = DataCenter._safe_get_last(gdp_df)
            return val * 1.05 if val else 1350000
        except:
            return 1350000

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_macro_indicators():
        data = {"PMI": None, "M1": None, "M1_prev": None, "USDCNH": None}
        try:
            # PMI
            pmi_df = ak.macro_china_pmi()
            data["PMI"] = DataCenter._safe_get_last(pmi_df)
            
            # M1
            m1_df = ak.macro_china_m2_yearly()
            if not m1_df.empty:
                # 寻找 M1 或“值”相关的列
                col = [c for c in m1_df.columns if '值' in c or 'value' in c]
                if col:
                    series = m1_df[col[0]].dropna()
                    if len(series) >= 2:
                        data["M1"] = float(series.iloc[-1])
                        data["M1_prev"] = float(series.iloc[-2])
            
            # 汇率 (修复 symbol 报错)
            try:
                fx_df = ak.fx_spot_quote()
                # 不再依赖 symbol 列名，直接在所有列里找 USDCNH
                target = fx_df[fx_df.apply(lambda row: row.astype(str).str.contains('USDCNH').any(), axis=1)]
                if not target.empty:
                    data["USDCNH"] = DataCenter._safe_get_last(target, ['last', 'p', '价'])
            except:
                pass
        except Exception as e:
            st.warning(f"宏观清洗层提示: {e}")
        return data

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_valuation():
        val = {"ERP": None, "Buffett": None}
        try:
            # 1. 股债性价比 (ERP)
            pe_300 = 12.0
            try:
                # 优先尝试 funddb 接口 (目前最稳)
                pe_df = ak.index_value_hist_funddb(symbol="沪深300", indicator="市盈率")
                res = DataCenter._safe_get_last(pe_df, ['pe'])
                if res: pe_300 = res
            except:
                pass
            
            bond_df = ak.bond_china_yield(start_date="20260101")
            bond_yield = DataCenter._safe_get_last(bond_df, ['yield', '收益率'])
            
            if pe_300 and bond_yield:
                val["ERP"] = (1 / pe_300) - (bond_yield / 100)
            
            # 2. 动态巴菲特指标 (修复 stock_a_total_value 缺失)
            # 使用替代接口获取市场总市值 (A股全市场指标)
            try:
                # 替代接口：stock_a_ttm_ex (包含全市场市值数据)
                mv_df = ak.stock_a_ttm_ex(symbol="all") 
                # 或者尝试简单接口：直接获取全市场实时行情并求和
                # total_mv = ak.stock_zh_a_spot_em()['总市值'].sum() / 100000000 # 亿
                total_mv = mv_df['total_mv'].sum() / 10000 if 'total_mv' in mv_df.columns else 900000
            except:
                # 接口备选方案
                df_spot = ak.stock_zh_a_spot_em()
                total_mv = df_spot['总市值'].sum() / 100000000 # 转为亿元
                
            gdp = DataCenter.get_dynamic_gdp()
            val["Buffett"] = total_mv / gdp
            
        except Exception as e:
            st.error(f"估值模块关键报错: {e}")
        return val

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cn_wangwang_etf():
        symbols = {"沪深300": "sh510300", "中证500": "sh510500", "中证1000": "sh512100", "中证2000": "sh563300"}
        flows = {}
        for name, code in symbols.items():
            try:
                df = ak.fund_etf_hist_sina(symbol=code)
                num_df = df.select_dtypes(include=['number'])
                if not num_df.empty and len(df) >= 20:
                    # 成交额通常是最后一列
                    target = num_df.iloc[:, -1].dropna()
                    z_score = (target.iloc[-1] - target.tail(20).mean()) / target.tail(20).std()
                    flows[name] = round(z_score, 2)
                else: flows[name] = 0
            except: flows[name] = 0
        return flows
# ==================== 2. 策略引擎模块 ====================
class StrategyEngine:
    @staticmethod
    def analyze(macro, valuation, cn_wangwang):
        # 1. 宏观信号 (修复 M1 逻辑)
        macro_sig = "震荡"
        if macro['PMI'] and macro['M1']:
            if macro['PMI'] > 50 and macro['M1'] > macro['M1_prev']:
                macro_sig = "扩张 (复苏期)"
            elif macro['PMI'] < 50 and macro['M1'] < macro['M1_prev']:
                macro_sig = "收缩 (衰退期)"
        
        # 2. 估值信号
        val_sig = "中性"
        if valuation['ERP'] and valuation['Buffett']:
            if valuation['ERP'] > 0.05: val_sig = "底部极具性价比"
            elif valuation['Buffett'] > 1.0: val_sig = "高估风险区"
            else: val_sig = "估值合理"

        # 3. 汪汪信号
        active_etf = [k for k, v in cn_wangwang.items() if v > 2.0]
        cn_sig = f"监测到 汪汪 强力入场: {active_etf}" if active_etf else "市场自然波动"

        # 4. 自动策略建议 (三维判定)
        if "扩张" in macro_sig and "底部" in val_sig:
            action = "【全力出击】宏观反转+估值底部，建议配置权重龙头"
        elif "收缩" in macro_sig and active_etf:
            action = "【护盘行情】经济承压但资金介入，博弈政策性反弹"
        elif "收缩" in macro_sig and "风险" in val_sig:
            action = "【清仓防御】经济下行+估值过高，配置长期美债或红利"
        else:
            action = "【中性观望】信号不一致，建议等待趋势明朗"

        return {"宏观": macro_sig, "估值": val_sig, "汪汪": cn_sig, "建议": action, "active": active_etf}

# ==================== 3. 可视化界面 ====================
def main():
    st.set_page_config(page_title="Nova 全局监控盘", layout="wide")
    st.title("🛡️ Nova 全局大局观 & 汪汪动向监控 (修复版)")
    
    dc = DataCenter()
    macro = dc.get_macro_indicators()
    val = dc.get_valuation()
    cn_wangwang = dc.get_cn_wangwang_etf()
    res = StrategyEngine.analyze(macro, val, cn_wangwang)

    # 第一行：大局看板
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("PMI 指数", macro['PMI'], delta=round(macro['PMI']-50, 2) if macro['PMI'] else None)
    col2.metric("M1 增速趋势", f"{macro['M1']}%", delta=f"{round(macro['M1']-macro['M1_prev'], 2)}%" if macro['M1_prev'] else None)
    col3.metric("汇率 USDCNH", macro['USDCNH'])
    col4.metric("股债性价比 (ERP)", f"{round(val['ERP']*100, 2)}%" if val['ERP'] else "数据加载中")

    st.divider()

    # 第二行：汪汪强度图
    st.subheader("📊 汪汪介入强度 (红色线以上代表大资金异动)")
    etf_df = pd.DataFrame(list(cn_wangwang.items()), columns=['指数名称', '介入强度'])
    fig = px.bar(etf_df, x='指数名称', y='介入强度', color='介入强度', color_continuous_scale='RdBu_r')
    fig.add_hline(y=2.0, line_dash="dash", line_color="red", annotation_text="国家队异动区")
    st.plotly_chart(fig, use_container_width=True)

    # 第三行：个股可见性补丁
    if res['active']:
        st.success(f"🔥 {res['汪汪']}")
        st.subheader("🎯 重点关注板块/个股 (基于汪汪介入方向)")
        stock_map = {
            "沪深300": ["贵州茅台", "中国平安", "招商银行", "长江电力"],
            "中证500": ["科大讯飞", "阳光电源", "中际旭创", "特变电工"],
            "中证1000/2000": ["微盘股龙头", "专精特新企业", "半导体小票"]
        }
        for etf_name in res['active']:
            st.write(f"**{etf_name} 相关核心权重股建议：**")
            st.table(stock_map.get(etf_name, ["暂无参考"]))

    st.divider()

    # 第四行：结论
    st.subheader("💡 最终决策建议")
    st.error(f"**当前策略建议：{res['建议']}**")

if __name__ == "__main__":
    main()
