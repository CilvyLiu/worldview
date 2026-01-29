import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
from datetime import datetime

# ==================== 1. 数据采集模块 ====================
class DataCenter:
    """负责所有宏观与市场数据的抓取（多源冗余 + GDP 动态化）"""
    
    @staticmethod
    def _get_val(df, key):
        """内部工具：过滤数值列并自动匹配中英文列名"""
        if df is None or df.empty: return 0
        numeric_df = df.select_dtypes(include=['number'])
        if numeric_df.empty: return 0
        
        cols = [c for c in numeric_df.columns if key.lower() in c.lower() or c == '值' or c == '金额']
        return float(numeric_df[cols[0]].iloc[-1]) if cols else float(numeric_df.iloc[:, -1].iloc[-1])

    @staticmethod
    @st.cache_data(ttl=86400)
    def get_dynamic_gdp():
        """动态计算 GDP：基于去年总量与最新季度增速"""
        try:
            # 获取历年总量
            gdp_year = ak.macro_china_gdp_yearly()
            base_gdp = DataCenter._get_val(gdp_year, 'value')
            # 获取最新季度增速 (通常返回如 5.2 代表 5.2%)
            gdp_q = ak.macro_china_gdp_quarterly()
            growth = DataCenter._get_val(gdp_q, 'absolute_value') / 100 if not gdp_q.empty else 0.05
            return base_gdp * (1 + growth)
        except:
            return 1350000 # 2026年保底预估值

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_macro_indicators():
        data = {"PMI": None, "M1": None, "M1_prev": None, "USDCNH": None}
        try:
            # 1. PMI (制造业)
            pmi_df = ak.macro_china_pmi()
            data["PMI"] = DataCenter._get_val(pmi_df, 'value')
            
            # 2. M1 (货币供应量)
            m1_df = ak.macro_china_m2_yearly()
            num_df = m1_df.select_dtypes(include=['number'])
            if not num_df.empty and len(num_df) >= 2:
                col = num_df.columns[0]
                data["M1"] = float(num_df[col].iloc[-1])
                data["M1_prev"] = float(num_df[col].iloc[-2])
            
            # 3. 汇率 (冗余逻辑：先找行情，再找新浪接口)
            try:
                # 优先：新浪实时外汇
                fx_df = ak.fx_spot_quote()
                row = fx_df[fx_df['symbol'].str.contains('USDCNH', na=False)]
                data["USDCNH"] = float(row['last'].values[0])
            except:
                # 备选：全球汇率
                fx_df = ak.currency_latest_sina()
                row = fx_df[fx_df['symbol'] == 'USDCNH']
                data["USDCNH"] = float(row['trade'].values[0])
        except Exception as e:
            st.error(f"宏观数据同步失败: {e}")
        return data

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_valuation():
        val = {"ERP": None, "Buffett": None}
        try:
            # 1. 股债性价比 (ERP)
            pe_300 = 12.0 # 默认值
            # 冗余接口 A: 乐咕 (lg)
            try:
                pe_df = ak.stock_a_indicator_lg(symbol="沪深300")
                pe_300 = float(pe_df['pe'].iloc[-1])
            except:
                # 冗余接口 B: FundDB
                try:
                    pe_df = ak.index_value_hist_funddb(symbol="沪深300", indicator="市盈率")
                    pe_300 = float(pe_df['pe'].iloc[-1])
                except: pass
            
            # 国债收益率
            bond_df = ak.bond_china_yield(start_date="20251201")
            bond_yield = DataCenter._get_val(bond_df, 'yield')
            
            if pe_300 > 0:
                val["ERP"] = (1 / pe_300) - (bond_yield / 100)
            
            # 2. 巴菲特指标 (冗余获取全 A 总市值)
            total_mv = 0
            try:
                # 冗余接口 A: 官方统计
                mv_df = ak.stock_a_total_value()
                total_mv = float(mv_df['total_value'].iloc[-1])
            except:
                # 冗余接口 B: 实时行情汇总 (东财接口，非常稳)
                spot_df = ak.stock_zh_a_spot_em()
                total_mv = spot_df['总市值'].sum() / 100000000
                
            val["Buffett"] = total_mv / DataCenter.get_dynamic_gdp()
        except Exception as e:
            st.error(f"估值数据同步失败: {e}")
        return val

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cn_wangwang_etf():
        """汪汪队监控 (基于新浪 ETF 成交量异动)"""
        symbols = {"沪深300": "sh510300", "中证500": "sh510500", "中证1000": "sh512100", "中证2000": "sh563300"}
        flows = {}
        for name, code in symbols.items():
            try:
                # 使用新浪接口获取 ETF 历史成交额
                df = ak.fund_etf_hist_sina(symbol=code)
                num_df = df.select_dtypes(include=['number'])
                amt_col = [c for c in num_df.columns if 'amount' in c.lower() or '成交' in c]
                
                if not num_df.empty and len(num_df) >= 20:
                    target = num_df[amt_col[0]].dropna()
                    recent = target.tail(20)
                    z_score = (target.iloc[-1] - recent.mean()) / recent.std()
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
