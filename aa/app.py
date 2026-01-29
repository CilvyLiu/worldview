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

# ==================== 2. 全量引擎 (加固版) ====================
class WangWangEngine:
    @staticmethod
    def _safe(val, default=0.0):
        try:
            if pd.isna(val) or val is None: return default
            return float(val)
        except: return default

    @staticmethod
    def fetch_all():
        # [加固] 预设结构，彻底杜绝 KeyError
        data = {
            "macro": {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "USDCNH": 7.2}, 
            "basis": [], 
            "stocks_detail": []
        }
        try:
            # 1. 宏观 - PMI
            pmi_df = ak.macro_china_pmi()
            if not pmi_df.empty:
                data["macro"]["PMI"] = WangWangEngine._safe(pmi_df.select_dtypes(include=['number']).iloc[-1, 0], 50.0)
            
            # 2. 宏观 - M1
            m1_df = ak.macro_china_m2_yearly()
            valid_m1 = m1_df.dropna(subset=[m1_df.columns[1]])
            if len(valid_m1) >= 2:
                data["macro"]["M1"] = WangWangEngine._safe(valid_m1.iloc[-1, 1])
                data["macro"]["M1_prev"] = WangWangEngine._safe(valid_m1.iloc[-2, 1])
            
            # 3. [加固修复] 宏观 - 汇率
            try:
                fx_df = ak.fx_spot_quote()
                # 模糊搜索包含 USDCNH 的行
                row = fx_df[fx_df.iloc[:,0].str.contains('USDCNH', na=False, case=False)]
                if not row.empty:
                    data["macro"]["USDCNH"] = WangWangEngine._safe(row.iloc[0, 1], 7.2)
                else:
                    # 备选逻辑：找包含“人民币”字样的行
                    row_alt = fx_df[fx_df.iloc[:,0].str.contains('人民币', na=False)]
                    if not row_alt.empty:
                        data["macro"]["USDCNH"] = WangWangEngine._safe(row_alt.iloc[0, 1], 7.2)
            except:
                st.sidebar.warning("汇率实时同步受限，使用参考值")
            
            # 4. 基差
            spot_df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
            s300 = WangWangEngine._safe(spot_df[spot_df['名称'].str.contains('300')].iloc[0]['最新价'], 4000.0)
            s50 = WangWangEngine._safe(spot_df[spot_df['名称'].str.contains('50')].iloc[0]['最新价'], 2500.0)
            
            contracts = [{"code": "IF2603", "name": "沪深300", "spot": s300, "future": 4732.8},
                         {"code": "IH2603", "name": "上证50", "spot": s50, "future": 2645.5}]
            for c in contracts:
                basis = round(c['future'] - c['spot'], 2)
                data["basis"].append({"合约": c['code'], "标刻": c['name'], "基差": basis, "现货": c['spot']})

            # 5. 汪汪队全量个股
            avg_basis = sum(b['基差'] for b in data["basis"]) / len(data["basis"]) if data["basis"] else 0
            army = {
                "🛡️ 压舱石 (高股息)": ["中国神华", "中国石油", "长江电力", "工商银行", "中国建筑", "农业银行", "陕西煤业"],
                "⚔️ 冲锋队 (非银/白马)": ["中信证券", "东方财富", "贵州茅台", "五粮液", "格力电器", "中信建投", "泸州老窖"],
                "🏗️ 稳增长 (周期)": ["海螺水泥", "万华化学", "三一重工", "紫金矿业", "宝钢股份", "中国中铁", "中国电建"],
                "📈 守护者 (核心权重)": ["招商银行", "中国平安", "比亚迪", "宁德时代", "美的集团", "兴业银行", "工业富联"]
            }
            
            for sector, stocks in army.items():
                for s in stocks:
                    advice = "基本面承压，看汪汪队托底意愿" if data["macro"]["PMI"] < 50 else "跟随大盘趋势"
                    if avg_basis < -30: advice += " | 贴水严重，具备防御价值"
                    data["stocks_detail"].append({
                        "战队板块": sector, "股票名称": s, "穿透建议": advice,
                        "PMI参考": data["macro"]["PMI"], "同步时间": datetime.now().strftime("%Y-%m-%d")
                    })
        except Exception as e:
            st.sidebar.error(f"引擎运行异常: {e}")
        return data

# ==================== 3. 主程序 ====================
def main():
    st.set_page_config(page_title="Nova 汪汪队", layout="wide")
    st.header("🛡️ Nova 汪汪队全板块穿透 & 一键 Excel 导出")

    vault = NovaVault.read_all()
    
    st.sidebar.header("🕹️ 控制中心")
    if st.sidebar.button("☀️ 同步早盘"):
        NovaVault.save("morning", WangWangEngine.fetch_all()); st.rerun()
    if st.sidebar.button("🌙 同步晚盘"):
        NovaVault.save("evening", WangWangEngine.fetch_all()); st.rerun()

    if vault:
        st.sidebar.divider()
        mode_export = st.sidebar.selectbox("选择导出版本", ["早盘", "晚盘"])
        tag_export = "morning" if mode_export == "早盘" else "evening"
        
        if tag_export in vault:
            content = vault[tag_export]["content"]
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pd.DataFrame([content.get("macro", {})]).to_excel(writer, sheet_name='宏观数据', index=False)
                pd.DataFrame(content.get("basis", [])).to_excel(writer, sheet_name='期现基差', index=False)
                pd.DataFrame(content.get("stocks_detail", [])).to_excel(writer, sheet_name='汪汪队穿透', index=False)
            
            st.sidebar.download_button(
                label="📥 一键导出 Excel",
                data=output.getvalue(),
                file_name=f"Nova_WangWang_{datetime.now().strftime('%m%d')}.xlsx",
                mime="application/vnd.ms-excel"
            )

    mode = st.radio("查看时段：", ["早盘", "晚盘"], horizontal=True)
    tag = "morning" if mode == "早盘" else "evening"
    
    if tag in vault:
        cont = vault[tag]["content"]
        m = cont.get("macro", {"PMI": 50, "M1": 0, "M1_prev": 0, "USDCNH": 7.2})
        
        # 仪表盘
        k1, k2, k3 = st.columns(3)
        k1.metric("PMI", m.get('PMI', 50), f"{round(m.get('PMI', 50)-50, 2)}")
        k2.metric("M1", f"{m.get('M1', 0)}%", f"{round(m.get('M1', 0)-m.get('M1_prev', 0), 2)}%")
        # 使用 .get 保护，彻底解决 KeyError
        k3.metric("USDCNH", m.get('USDCNH', 7.2))

        st.subheader("📉 汪汪队作战地图预览")
        df_display = pd.DataFrame(cont.get("stocks_detail", []))
        if not df_display.empty:
            st.dataframe(df_display, use_container_width=True)
    else:
        st.warning(f"👋 Nova，请点击左侧按钮采集数据。")

if __name__ == "__main__":
    main()
