import pandas as pd
import akshare as ak
import streamlit as st
import json
import os
from datetime import datetime

# ==================== 1. 数据中心 (Vault) ====================
class NovaVault:
    FILE_PATH = "wangwang_vault.json"

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

# ==================== 2. 全板块采集引擎 ====================
class WangWangEngine:
    @staticmethod
    def _safe(val, default=0.0):
        try: return float(val) if pd.notnull(val) else default
        except: return default

    @staticmethod
    def fetch_all():
        data = {"macro": {}, "basis": []}
        try:
            # 1. 宏观锚点
            pmi_df = ak.macro_china_pmi()
            data["macro"]["PMI"] = WangWangEngine._safe(pmi_df.select_dtypes(include=['number']).iloc[-1, 0], 50.0)
            
            m1_df = ak.macro_china_m2_yearly()
            valid_m1 = m1_df.dropna(subset=[m1_df.columns[1]])
            data["macro"]["M1"] = WangWangEngine._safe(valid_m1.iloc[-1, 1])
            data["macro"]["M1_prev"] = WangWangEngine._safe(valid_m1.iloc[-2, 1])
            
            fx_df = ak.fx_spot_quote()
            data["macro"]["USDCNH"] = WangWangEngine._safe(fx_df[fx_df.iloc[:,0].str.contains('USDCNH', na=False)].iloc[0, 1], 7.2)
            
            # 2. 现货锚点 (沪深300/上证50)
            spot_df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
            s300 = WangWangEngine._safe(spot_df[spot_df['名称'].str.contains('300')].iloc[0]['最新价'])
            s50 = WangWangEngine._safe(spot_df[spot_df['名称'].str.contains('50')].iloc[0]['最新价'])
            
            # 3. 期货基差
            contracts = [{"code": "IF2603", "price": 4732.8, "spot": s300, "name": "沪深300"},
                         {"code": "IH2603", "price": 2645.5, "spot": s50, "name": "上证50"}]
            for c in contracts:
                basis = round(c['price'] - c['spot'], 2)
                data["basis"].append({"合约": c['code'], "标的": c['name'], "基差": basis})
        except Exception as e:
            st.sidebar.error(f"接口采集失败: {e}")
        return data

# ==================== 3. 汪汪队全板块穿透逻辑 ====================
def render_full_army(macro, basis_list):
    st.divider()
    st.subheader("🚩 汪汪队全板块作战态势")
    
    # 获取平均基差情绪
    avg_basis = sum(b['基差'] for b in basis_list) / len(basis_list) if basis_list else 0
    
    # 汪汪队全图谱
    army = {
        "🛡️ 压舱石战队 (中特估/高股息)": {
            "stocks": ["中国神华", "中国石油", "长江电力", "中国建筑", "工商银行"],
            "logic": "基差贴水时，这类票是汪汪队的防御盾牌。",
            "risk": "🟢 避风港模式" if avg_basis < -20 else "🟡 溢价震荡"
        },
        "⚔️ 冲锋战队 (非银金融/白马)": {
            "stocks": ["中信证券", "东方财富", "贵州茅台", "五粮液", "格力电器"],
            "logic": "汇率走强且M1反转时，汪汪队会通过券商发动反攻。",
            "risk": "🔴 汇率受压" if macro['USDCNH'] > 7.25 else "🟢 动能充足"
        },
        "🏗️ 稳增长战队 (顺周期龙头)": {
            "stocks": ["海螺水泥", "万华化学", "三一重工", "紫金矿业", "宝钢股份"],
            "logic": "PMI必须站上50，汪汪队护盘这类票才有基本面回旋余地。",
            "risk": "🔴 PMI收缩压制" if macro['PMI'] < 50 else "🟢 扩张周期"
        },
        "📈 指数守护者 (核心ETF权重)": {
            "stocks": ["招商银行", "中国平安", "比亚迪", "宁德时代", "美的集团"],
            "logic": "沪深300的核心，基差升水时，汪汪队可能在减缓买入节奏。",
            "risk": "🟡 情绪过热" if avg_basis > 10 else "🟢 托底区间"
        }
    }

    cols = st.columns(2)
    for i, (name, detail) in enumerate(army.items()):
        with cols[i % 2]:
            st.info(f"### {name}")
            st.metric("作战状态", detail['risk'])
            st.write(f"**核心标的**：{', '.join(detail['stocks'])}")
            st.caption(f"**穿透逻辑**：{detail['logic']}")
            st.progress(40 if "🔴" in detail['risk'] else 80)

# ==================== 4. UI 主控 ====================
def main():
    st.set_page_config(page_title="Nova 汪汪队全维监控", layout="wide")
    st.header("🛡️ Nova 汪汪队全板块穿透监控 (早晚版)")

    vault = NovaVault.read_all()
    
    # 侧边栏按钮
    st.sidebar.header("🕹️ 采样控制")
    if st.sidebar.button("☀️ 早盘数据采集"):
        NovaVault.save("morning", WangWangEngine.fetch_all()); st.rerun()
    if st.sidebar.button("🌙 晚盘数据采集"):
        NovaVault.save("evening", WangWangEngine.fetch_all()); st.rerun()

    mode = st.radio("选择快照：", ["早盘 (Morning)", "晚盘 (Evening)"], horizontal=True)
    tag = "morning" if "早盘" in mode else "evening"
    
    if tag in vault:
        snapshot = vault[tag]
        cont = snapshot["content"]
        st.caption(f"📌 数据版本：{snapshot['time']} | 状态：锁定离线浏览")

        # 宏观仪表盘
        m = cont["macro"]
        
        k1, k2, k3 = st.columns(3)
        k1.metric("PMI 荣枯线", f"{m['PMI']}", f"{round(m['PMI']-50,2)}")
        k2.metric("M1 资金活性", f"{m['M1']}%", f"{round(m['M1']-m['M1_prev'],2)}%")
        k3.metric("离岸人民币 (USDCNH)", f"{m['USDCNH']}")

        # 基差数据
        st.subheader("📉 汪汪队护盘基差锚点")
        
        if cont["basis"]:
            st.table(cont["basis"])
        
        # 全板块穿透
        render_full_army(m, cont["basis"])
    else:
        st.warning(f"👋 Nova，请点击左侧按钮采集【{mode}】数据。")

if __name__ == "__main__":
    main()
