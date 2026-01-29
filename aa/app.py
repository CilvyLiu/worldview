import pandas as pd
import akshare as ak
import streamlit as st
import time
import json
import os
from datetime import datetime

# ==================== 1. 数据保险箱模块 ====================
class DataVault:
    CACHE_FILE = "nova_market_vault.json"

    @classmethod
    def save_data(cls, macro_data, basis_df):
        """将数据固化到本地文件"""
        vault_content = {
            "update_date": str(datetime.now().date()),
            "macro": macro_data,
            "basis": basis_df.to_dict(orient="records")
        }
        with open(cls.CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(vault_content, f, ensure_ascii=False, indent=4)

    @classmethod
    def load_data(cls):
        """尝试读取本地数据"""
        if os.path.exists(cls.CACHE_FILE):
            with open(cls.CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 如果数据日期是今天，返回数据，否则提示更新
                is_today = data.get("update_date") == str(datetime.now().date())
                return data, is_today
        return None, False

# ==================== 2. 加固采集模块 ====================
class DataCenter:
    @staticmethod
    def fetch_all():
        """执行全量数据抓取（建议每天仅运行一次）"""
        # 1. 宏观数据
        macro = {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "USDCNH": 7.2}
        try:
            pmi_df = ak.macro_china_pmi()
            macro["PMI"] = float(pmi_df.select_dtypes(include=['number']).iloc[-1, 0])
            m1_df = ak.macro_china_m2_yearly()
            macro["M1"] = float(m1_df.iloc[-1, 1])
            macro["M1_prev"] = float(m1_df.iloc[-2, 1])
            fx_df = ak.fx_spot_quote()
            macro["USDCNH"] = float(fx_df[fx_df.iloc[:, 0].str.contains('USDCNH', na=False)].iloc[0, 1])
        except: pass

        # 2. 基差数据
        results = []
        try:
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
                results.append({"合约": c['code'], "期货": c['price'], "现货": spot_300, "基差": basis, "状态": status})
        except: pass
        
        return macro, pd.DataFrame(results)

# ==================== 3. 展示层逻辑 ====================
def main():
    st.set_page_config(page_title="Nova 全局穿透", layout="wide")
    st.header("🛡️ Nova 离线优先监控盘")

    # 检查本地是否有今日数据
    vault_data, is_today = DataVault.load_data()

    # 侧边栏：同步控制台
    st.sidebar.header("📊 数据同步状态")
    if is_today:
        st.sidebar.success(f"数据已锁定：{vault_data['update_date']}")
        st.sidebar.info("当前模式：离线浏览（不产生API请求）")
    else:
        st.sidebar.warning("数据非最新，建议执行每日同步")

    if st.sidebar.button("🔄 执行今日全量采集 (每天一次)"):
        with st.spinner("正在穿透行情源..."):
            macro, basis_df = DataCenter.fetch_all()
            DataVault.save_data(macro, basis_df)
            st.rerun()

    # 如果没有数据则停止展示
    if not vault_data:
        st.info("👋 你好 Nova，本地暂无缓存，请点击左侧按钮执行首次采集。")
        return

    # 数据分发
    macro = vault_data["macro"]
    basis_df = pd.DataFrame(vault_data["basis"])

    # 1. 看板展示
    
    c1, c2, c3 = st.columns(3)
    c1.metric("PMI 荣枯线", f"{macro['PMI']}", delta=f"{round(macro['PMI']-50,2)}")
    c2.metric("M1 活性", f"{macro['M1']}%", delta=f"{round(macro['M1']-macro['M1_prev'],2)}%")
    c3.metric("USDCNH", f"{macro['USDCNH']}")

    # 2. 基差表格
    st.subheader("📉 期现基差结构 (当日固化版)")
    st.dataframe(basis_df.style.applymap(
        lambda x: 'background-color: #ff4b4b; color: white' if "正向" in str(x) else 
                  'background-color: #1c83e1; color: white' if "负向" in str(x) else '',
        subset=['状态']
    ), use_container_width=True)

    # 3. 风险逻辑
    st.divider()
    st.subheader("🚨 核心标的风险透视")
    col_a, col_b = st.columns(2)
    with col_a:
        if macro['PMI'] < 50:
            st.error("### 警惕：海螺水泥\nPMI 收缩，周期股缺乏基本面动能。")
    with col_b:
        if macro['M1'] <= macro['M1_prev']:
            st.warning("### 警惕：格力电器\nM1 增速放缓，白马股流动性溢价面临收缩。")

if __name__ == "__main__":
    main()
