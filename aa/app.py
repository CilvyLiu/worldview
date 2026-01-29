import pandas as pd
import akshare as ak
import streamlit as st
import json
import os
import time
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
            try:
                with open(cls.FILE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

# ==================== 2. 数据采集引擎 (防御加固版) ====================
class MarketEngine:
    @staticmethod
    def _clean_float(val, default=0.0):
        """通用安全转换函数"""
        try:
            if pd.isna(val) or val is None: return default
            return float(val)
        except: return default

    @staticmethod
    def fetch_snapshot():
        """全量抓取：PMI, M1, 汇率, 沪深300基差"""
        # 初始化默认值，防止部分接口失败导致整体崩溃
        data = {
            "macro": {"PMI": 50.0, "M1": 0.0, "M1_prev": 0.0, "USDCNH": 7.2},
            "basis": []
        }
        
        # 1. 宏观数据采集
        try:
            # PMI
            pmi_df = ak.macro_china_pmi()
            if not pmi_df.empty:
                data["macro"]["PMI"] = MarketEngine._clean_float(pmi_df.select_dtypes(include=['number']).iloc[-1, 0], 50.0)
            
            # M1 (修复 TypeError 的核心逻辑)
            m1_df = ak.macro_china_m2_yearly()
            if not m1_df.empty:
                # 只取有值的行，避免取到末尾的空行
                valid_m1 = m1_df.dropna(subset=[m1_df.columns[1]])
                if len(valid_m1) >= 2:
                    data["macro"]["M1"] = MarketEngine._clean_float(valid_m1.iloc[-1, 1])
                    data["macro"]["M1_prev"] = MarketEngine._clean_float(valid_m1.iloc[-2, 1])
            
            # 汇率
            fx_df = ak.fx_spot_quote()
            fx_row = fx_df[fx_df.iloc[:, 0].str.contains('USDCNH', na=False)]
            if not fx_row.empty:
                data["macro"]["USDCNH"] = MarketEngine._clean_float(fx_row.iloc[0, 1], 7.2)
        except Exception as e:
            st.sidebar.error(f"宏观同步异常: {e}")

        # 2. 基差数据采集
        try:
            spot_df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
            target = spot_df[spot_df['名称'].str.contains('300', na=False)].iloc[0]
            # 动态适配“最新价”或“收盘价”列名
            price_col = [c for c in spot_df.columns if any(k in c for k in ['最新', '收盘'])][0]
            spot_300 = MarketEngine._clean_float(target[price_col])
            
            # 2026年监控合约
            contracts = [
                {"code": "IF2602", "price": 4727.8, "up": 9.83, "down": -29.55},
                {"code": "IF2603", "price": 4732.8, "up": -14.79, "down": -80.29}
            ]
            for c in contracts:
                basis = round(c['price'] - spot_300, 2)
                status = "正常"
                if basis > c['up']: status = "正向异常"
                elif basis < c['down']: status = "负向异常"
                data["basis"].append({
                    "合约": c['code'], "期货": c['price'], "现货": spot_300, 
                    "基差": basis, "状态": status
                })
        except Exception as e:
            st.sidebar.error(f"基差同步异常: {e}")
            
        return data

# ==================== 3. 展示层逻辑 ====================
def main():
    st.set_page_config(page_title="Nova 双时段穿透", layout="wide")
    st.title("🛡️ Nova 宏观基差穿透 (早晚固化版)")

    vault = DataVault.read_all()

    # 侧边栏控制
    st.sidebar.header("🕹️ 数据调度中心")
    st.sidebar.info("模式：早晚各更新一次，其余时间全离线浏览。")
    
    col1, col2 = st.sidebar.columns(2)
    if col1.button("☀️ 同步早盘"):
        with st.spinner("正在加固采集早盘数据..."):
            DataVault.save("morning", MarketEngine.fetch_snapshot())
            st.rerun()
    
    if col2.button("🌙 同步晚盘"):
        with st.spinner("正在加固采集晚盘数据..."):
            DataVault.save("evening", MarketEngine.fetch_snapshot())
            st.rerun()

    # 选择展示版本
    mode = st.radio("选择快照版本：", ["早盘快照 (Morning)", "晚盘快照 (Evening)"], horizontal=True)
    tag = "morning" if "早盘" in mode else "evening"
    
    if tag in vault:
        snapshot = vault[tag]
        content = snapshot["content"]
        st.caption(f"📌 数据版本：{snapshot['time']} (本时段已锁定，刷新页面不会产生 API 请求)")

        # 1. 核心看板
        m = content["macro"]
        c1, c2, c3 = st.columns(3)
        c1.metric("PMI 荣枯线", f"{m['PMI']}", delta=f"{round(m['PMI']-50,2)} (荣枯)")
        c2.metric("M1 活性", f"{m['M1']}%", delta=f"{round(m['M1']-m['M1_prev'],2)}% (环比)")
        c3.metric("USDCNH", f"{m['USDCNH']}")

        # 2. 基差穿透
        st.subheader("📉 基差详情与市场情绪")
        
        if content["basis"]:
            basis_df = pd.DataFrame(content["basis"])
            st.dataframe(basis_df.style.applymap(
                lambda x: 'background-color: #ff4b4b; color: white' if "正向" in str(x) else 
                          'background-color: #1c83e1; color: white' if "负向" in str(x) else '',
                subset=['状态']
            ), use_container_width=True)
        else:
            st.warning("⚠️ 该快照内无基差数据，请重新同步。")

        # 3. 风险穿透逻辑
        st.divider()
        st.subheader("🚨 Nova 实时风险穿透")
        r1, r2 = st.columns(2)
        with r1:
            if m['PMI'] < 50: 
                st.error("### 海螺水泥：PMI 收缩警告")
                st.write("**理由**：制造业进入萎缩区间，下游基建需求支撑力减弱。")
            else: 
                st.success("### 海螺水泥：逻辑稳健")
        with r2:
            if m['M1'] <= m['M1_prev']: 
                st.warning("### 格力电器：流动性预警")
                st.write("**理由**：M1 增速未见起色，存量博弈下白马股估值中枢承压。")
            else: 
                st.success("### 格力电器：资金活性支撑")
    else:
        st.warning(f"👋 Nova，本地暂无【{mode}】数据。请点击侧边栏按钮执行同步。")

if __name__ == "__main__":
    main()
