import pandas as pd
import akshare as ak
import streamlit as st
import json
import os
from datetime import datetime

# ==================== 1. 数据保险箱 (零请求核心) ====================
class DataVault:
    FILE_PATH = "market_vault.json"

    @classmethod
    def save(cls, tag, data):
        """存入本地，带上时间戳"""
        vault = cls.read_all()
        vault[tag] = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content": data
        }
        with open(cls.FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(vault, f, ensure_ascii=False, indent=4)

    @classmethod
    def read_all(cls):
        if os.path.exists(cls.FILE_PATH):
            with open(cls.FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

# ==================== 2. 数据采集引擎 ====================
class MarketEngine:
    @staticmethod
    def fetch_snapshot():
        """全量抓取：PMI, M1, 汇率, 沪深300基差"""
        data = {"macro": {}, "basis": []}
        # 1. 宏观
        pmi_df = ak.macro_china_pmi()
        data["macro"]["PMI"] = float(pmi_df.select_dtypes(include=['number']).iloc[-1, 0])
        m1_df = ak.macro_china_m2_yearly()
        data["macro"]["M1"] = float(m1_df.iloc[-1, 1])
        data["macro"]["M1_prev"] = float(m1_df.iloc[-2, 1])
        fx_df = ak.fx_spot_quote()
        data["macro"]["USDCNH"] = float(fx_df[fx_df.iloc[:, 0].str.contains('USDCNH', na=False)].iloc[0, 1])
        
        # 2. 基差
        spot_df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
        spot_300 = float(spot_df[spot_df['名称'].str.contains('300')].iloc[0]['最新价'])
        contracts = [
            {"code": "IF2602", "price": 4727.8, "up": 9.83, "down": -29.55},
            {"code": "IF2603", "price": 4732.8, "up": -14.79, "down": -80.29}
        ]
        for c in contracts:
            basis = round(c['price'] - spot_300, 2)
            status = "正常"
            if basis > c['up']: status = "正向异常"
            elif basis < c['down']: status = "负向异常"
            data["basis"].append({"合约": c['code'], "期货": c['price'], "现货": spot_300, "基差": basis, "状态": status})
        return data

# ==================== 3. 展示层逻辑 ====================
def main():
    st.set_page_config(page_title="Nova 双时段穿透", layout="wide")
    st.title("🛡️ Nova 宏观基差穿透 (早晚固化版)")

    vault = DataVault.read_all()

    # 侧边栏控制
    st.sidebar.header("🕹️ 数据调度中心")
    st.sidebar.info("模式：早晚各更新一次，其余时间离线。")
    
    col1, col2 = st.sidebar.columns(2)
    if col1.button("☀️ 同步早盘"):
        with st.spinner("早盘数据固化中..."):
            DataVault.save("morning", MarketEngine.fetch_snapshot())
            st.rerun()
    
    if col2.button("🌙 同步晚盘"):
        with st.spinner("晚盘数据固化中..."):
            DataVault.save("evening", MarketEngine.fetch_snapshot())
            st.rerun()

    # 选择展示版本
    mode = st.radio("选择快照版本：", ["早盘快照 (Morning)", "晚盘快照 (Evening)"], horizontal=True)
    tag = "morning" if "早盘" in mode else "evening"
    
    if tag in vault:
        snapshot = vault[tag]
        content = snapshot["content"]
        st.caption(f"📌 数据采集时间：{snapshot['time']} (已锁定，刷新页面不会重取)")

        # 1. 核心看板
        
        m = content["macro"]
        c1, c2, c3 = st.columns(3)
        c1.metric("PMI 荣枯线", f"{m['PMI']}", delta=f"{round(m['PMI']-50,2)}")
        c2.metric("M1 活性", f"{m['M1']}%", delta=f"{round(m['M1']-m['M1_prev'],2)}%")
        c3.metric("USDCNH", f"{m['USDCNH']}")

        # 2. 基差穿透
        st.subheader("📉 基差详情")
        basis_df = pd.DataFrame(content["basis"])
        st.dataframe(basis_df.style.applymap(
            lambda x: 'background-color: #ff4b4b; color: white' if "正向" in str(x) else 
                      'background-color: #1c83e1; color: white' if "负向" in str(x) else '',
            subset=['状态']
        ), use_container_width=True)

        # 3. 风险逻辑
        st.divider()
        st.subheader("🚨 Nova 实时风险穿透")
        r1, r2 = st.columns(2)
        with r1:
            if m['PMI'] < 50: st.error("### 海螺水泥：PMI收缩警告\n制造业动能不足，周期龙头承压。")
            else: st.success("### 海螺水泥：逻辑稳健")
        with r2:
            if m['M1'] <= m['M1_prev']: st.warning("### 格力电器：流动性预警\nM1增速未起，权重股缺乏溢价动力。")
            else: st.success("### 格力电器：资金活性支撑")
    else:
        st.warning(f"👋 Nova，本地暂无【{mode}】数据。请点击侧边栏按钮执行今日同步。")

if __name__ == "__main__":
    main()
