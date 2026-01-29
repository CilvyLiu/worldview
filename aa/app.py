import pandas as pd
import akshare as ak
import streamlit as st
import plotly.express as px
from datetime import datetime

# ==================== 1. 数据采集模块 ====================
class DataCenter:
    """负责所有宏观与市场数据的抓取（已实现 GDP 动态化）"""
    
    @staticmethod
    @st.cache_data(ttl=86400) # GDP这类宏观基数数据每日更新一次即可
    def get_dynamic_gdp():
        """从官方数据动态估算当前年化 GDP"""
        try:
            # 1. 获取历年年度 GDP 总量 (亿元)
            gdp_yearly_df = ak.macro_china_gdp_yearly()
            last_year_total = float(gdp_yearly_df.iloc[-1]['value'])
            
            # 2. 获取最新季度 GDP 增长率 (进行动态平滑)
            gdp_quarterly_df = ak.macro_china_gdp_quarterly()
            # 取最近一个季度的同比增速，如果没有则默认为 5% (0.05)
            latest_growth = float(gdp_quarterly_df['absolute_value'].iloc[-1]) / 100 if not gdp_quarterly_df.empty else 0.05
            
            # 3. 动态计算估算值：去年基数 * (1 + 最新增速)
            dynamic_gdp = last_year_total * (1 + latest_growth)
            return dynamic_gdp
        except Exception as e:
            # 兜底方案：如果接口失效，返回一个2026年的合理预估常数
            return 1350000 

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_macro_indicators():
        data = {"PMI": None, "M1": None, "M1_prev": None, "USDCNH": None}
        try:
            # PMI 数据 (制造业)
            pmi_df = ak.macro_china_pmi()
            data["PMI"] = pmi_df['value'].iloc[-1]
            
            # M1 数据 (获取近两期对比趋势)
            m1_df = ak.macro_china_m2_yearly()
            data["M1"] = m1_df['value'].iloc[-1]
            data["M1_prev"] = m1_df['value'].iloc[-2] # 用于趋势 Delta 计算
            
            # 汇率 (USDCNH)
            fx = ak.fx_spot_quote()
            data["USDCNH"] = fx.loc[fx['symbol']=='USDCNH','last'].values[0]
        except Exception as e:
            st.error(f"宏观数据同步失败: {e}")
        return data

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_valuation():
        val = {"ERP": None, "Buffett": None}
        try:
            # 1. 股债性价比 (ERP)
            pe_df = ak.stock_a_indicator_lg(symbol="沪深300")
            pe_300 = pe_df['pe'].iloc[-1] if not pe_df.empty else 0
            
            # 这里的日期建议设为最近的一个月
            bond_df = ak.bond_china_yield(start_date="20260101")
            bond_yield = bond_df['yield'].iloc[-1] if not bond_df.empty else 0
            
            if pe_300 > 0:
                # bond_yield 为 2.5 这种格式，代表 2.5%
                val["ERP"] = (1 / pe_300) - (bond_yield / 100)
            
            # 2. 动态巴菲特指标 (总市值 / 动态预测 GDP)
            mv_df = ak.stock_a_total_value()
            total_mv = mv_df['total_value'].iloc[-1] # 亿元
            
            # 调用上面的动态 GDP 接口
            dynamic_gdp = DataCenter.get_dynamic_gdp()
            val["Buffett"] = total_mv / dynamic_gdp
            
        except Exception as e:
            st.error(f"估值数据同步失败: {e}")
        return val

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cn_wangwang_etf():
        # CN汪汪 ETF 监控: 300, 500, 1000, 2000
        symbols = {"沪深300": "sh510300", "中证500": "sh510500", "中证1000": "sh512100", "中证2000": "sh563300"}
        flows = {}
        for name, code in symbols.items():
            try:
                df = ak.fund_etf_hist_sina(symbol=code)
                if len(df) >= 20:
                    recent = df['amount'].tail(20)
                    z_score = (df['amount'].iloc[-1] - recent.mean()) / recent.std()
                    flows[name] = round(z_score, 2)
                else:
                    flows[name] = 0
            except:
                flows[name] = 0
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
