import pandas as pd
import akshare as ak
import streamlit as st
import json
import os
import io
from datetime import datetime

# ==================== 1. 数据保险箱 (Vault) ====================
class NovaVault:
    FILE_PATH = "wangwang_full_vault.json"

    @classmethod
    def save(cls, tag, data):
        vault = cls.read_all()
        vault[tag] = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "content": data}
        with open(cls.FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(vault, f, ensure_ascii=False, indent=4)

    @classmethod
    def read_all(cls):
        if os.path.exists(cls.FILE_PATH):
            try:
                with open(cls.FILE_PATH, "r", encoding="utf-8") as f: return json.load(f)
            except: return {}
        return {}

# ==================== 2. 全量引擎 (含导出数据构造) ====================
class WangWangEngine:
    @staticmethod
    def _safe(val, default=0.0):
        try: return float(val) if pd.notnull(val) else default
        except: return default

    @staticmethod
    def fetch_all():
        data = {"macro": {}, "basis": [], "stocks_detail": []}
        try:
            # 1. 宏观
            pmi_df = ak.macro_china_pmi()
            data["macro"]["PMI"] = WangWangEngine._safe(pmi_df.select_dtypes(include=['number']).iloc[-1, 0], 50.0)
            m1_df = ak.macro_china_m2_yearly()
            valid_m1 = m1_df.dropna(subset=[m1_df.columns[1]])
            data["macro"]["M1"] = WangWangEngine._safe(valid_m1.iloc[-1, 1])
            data["macro"]["M1_prev"] = WangWangEngine._safe(valid_m1.iloc[-2, 1])
            fx_df = ak.fx_spot_quote()
            data["macro"]["USDCNH"] = WangWangEngine._safe(fx_df[fx_df.iloc[:,0].str.contains('USDCNH', na=False)].iloc[0, 1], 7.2)
            
            # 2. 基差
            spot_df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
            s300 = WangWangEngine._safe(spot_df[spot_df['名称'].str.contains('300')].iloc[0]['最新价'])
            s50 = WangWangEngine._safe(spot_df[spot_df['名称'].str.contains('50')].iloc[0]['最新价'])
            contracts = [{"code": "IF2603", "name": "沪深300", "spot": s300, "future": 4732.8},
                         {"code": "IH2603", "name": "上证50", "spot": s50, "future": 2645.5}]
            for c in contracts:
                basis = round(c['future'] - c['spot'], 2)
                data["basis"].append({"合约": c['code'], "标的": c['name'], "基差": basis, "现货锚点": c['spot']})

            # 3. 汪汪队 20+ 全量个股池
            avg_basis = sum(b['基差'] for b in data["basis"]) / len(data["basis"])
            army = {
                "🛡️ 压舱石 (高股息)": ["中国神华", "中国石油", "长江电力", "工商银行", "中国建筑", "农业银行", "陕西煤业"],
                "⚔️ 冲锋队 (非银/白马)": ["中信证券", "东方财富", "贵州茅台", "五粮液", "格力电器", "中信建投", "泸州老窖"],
                "🏗️ 稳增长 (周期)": ["海螺水泥", "万华化学", "三一重工", "紫金矿业", "宝钢股份", "中国中铁", "中国电建"],
                "📈 守护者 (核心权重)": ["招商银行", "中国平安", "比亚迪", "宁德时代", "美的集团", "兴业银行", "工业富联"]
            }
            
            for sector, stocks in army.items():
                for s in stocks:
                    # 动态生成一句话穿透建议
                    advice = "基本面承压，看汪汪队托底意愿" if data["macro"]["PMI"] < 50 else "跟随大盘趋势"
                    if avg_basis < -30: advice += " | 贴水严重，具备防御价值"
                    
                    data["stocks_detail"].append({
                        "战队板块": sector,
                        "股票名称": s,
                        "穿透建议": advice,
                        "PMI参考": data["macro"]["PMI"],
                        "同步时间": datetime.now().strftime("%Y-%m-%d")
                    })
        except Exception as e:
            st.sidebar.error(f"同步失败: {e}")
        return data

# ==================== 3. 展示与一键导出 ====================
def main():
    st.set_page_config(page_title="Nova 汪汪队全案", layout="wide")
    st.header("🛡️ Nova 汪汪队全板块穿透 & 一键 Excel 导出")

    vault = NovaVault.read_all()
    
    # 侧边栏控制
    st.sidebar.header("🕹️ 控制中心")
    if st.sidebar.button("☀️ 同步早盘"):
        NovaVault.save("morning", WangWangEngine.fetch_all()); st.rerun()
    if st.sidebar.button("🌙 同步晚盘"):
        NovaVault.save("evening", WangWangEngine.fetch_all()); st.rerun()

    # 导出逻辑
    if vault:
        st.sidebar.divider()
        mode_export = st.sidebar.selectbox("选择导出版本", ["早盘", "晚盘"])
        tag_export = "morning" if mode_export == "早盘" else "evening"
        
        if tag_export in vault:
            content = vault[tag_export]["content"]
            
            # 构造 Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pd.DataFrame([content["macro"]]).to_excel(writer, sheet_name='宏观数据', index=False)
                pd.DataFrame(content["basis"]).to_excel(writer, sheet_name='期现基差', index=False)
                pd.DataFrame(content["stocks_detail"]).to_excel(writer, sheet_name='汪汪队全标的穿透', index=False)
            
            st.sidebar.download_button(
                label="📥 一键导出 Excel",
                data=output.getvalue(),
                file_name=f"Nova_汪汪队全穿透_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel"
            )

    # 页面主视图
    mode = st.radio("查看时段：", ["早盘", "晚盘"], horizontal=True)
    tag = "morning" if mode == "早盘" else "evening"
    
    if tag in vault:
        snap = vault[tag]
        cont = snap["content"]
        
        # 仪表盘
        m = cont["macro"]
        
        k1, k2, k3 = st.columns(3)
        k1.metric("PMI", m['PMI'], f"{round(m['PMI']-50,2)}")
        k2.metric("M1", f"{m['M1']}%", f"{round(m['M1']-m['M1_prev'],2)}%")
        k3.metric("USDCNH", m['USDCNH'])

        # 数据预览
        st.subheader("📉 汪汪队作战地图预览")
        
        df_display = pd.DataFrame(cont["stocks_detail"])
        st.dataframe(df_display, use_container_width=True)
    else:
        st.warning(f"👋 Nova，请点击左侧按钮采集【{mode}】数据。")

if __name__ == "__main__":
    main()
