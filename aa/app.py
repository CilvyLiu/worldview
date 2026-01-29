import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# =================== 1. 协议穿透引擎 (Nova 专属动态版) ===================

def get_market_sectors_dynamic():
    """板块侦测：扫描全市场板块，按实时资金强度排序"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2+f:!50", 
        "fields": "f12,f14,f3,f62,f184" # f14:名称, f12:ID, f62:净额, f184:主力占比
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()['data']['diff']
        df = pd.DataFrame(data).rename(columns={
            'f12': 'ID', 'f14': '板块名称', 'f3': '今日涨幅', 
            'f62': '主力净额', 'f184': '主力占比'
        })
        # 换算单位为亿，作为板块评分
        df['板块评分'] = pd.to_numeric(df['主力净额'], errors='coerce') / 100000000
        return df.sort_values(by='板块评分', ascending=False)
    except Exception as e:
        st.error(f"板块侦测握手异常: {e}")
        return None

def get_stock_penetration(sector_id):
    """个股侦测：穿透指定板块下的所有个股"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
        "fltt": "2", "invt": "2", "fid": "f164", 
        "fs": f"b:{sector_id}",
        "fields": "f12,f14,f2,f3,f62,f164,f174" 
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        df = pd.DataFrame(resp.json()['data']['diff']).rename(columns={
            'f12': '代码', 'f14': '名称', 'f2': '价格', 'f3': '今日涨幅',
            'f62': '今日主力', 'f164': '5日主力', 'f174': '10日主力'
        })
        for c in ['今日主力', '5日主力', '10日主力']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0) / 10000
        return df
    except: return None

# =================== 2. 投行级扫货审计算法 (Nova 升级版) ===================

class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: return [datetime.now().strftime("%Y%m%d")]

    def analyze_individual_stock(self, df):
        """个股投行因子审计"""
        # 1. 计算静默吸筹得分 (资金流入/涨幅惩罚)
        # 逻辑：资金流入越多、涨幅越低，说明主力在“静默”压盘，得分越高
        df['静默得分'] = np.where(
            (df['今日主力'] > 0),
            round(df['今日主力'] / (df['今日涨幅'].abs() + 0.1), 2),
            0
        )
        
        # 2. 判定侦测状态 (多维穿透)
        conditions = [
            (df['今日主力'] > 1500) & (df['今日涨幅'] <= 2.0),  # 顶级静默标的
            (df['今日主力'] > 300) & (df['5日主力'] < 0),      # 趋势空翻多
            (df['今日主力'] < -500) & (df['今日涨幅'] > 4.0),   # 热钱拉高诱多
            (df['今日主力'] > 5000) & (df['今日涨幅'] > 8.0)    # 主升浪高潮
        ]
        choices = ["💎 顶级静默扫货", "⚡ 机构空翻多", "⚠️ 游资诱多陷阱", "🚀 趋势主升"]
        df['侦测状态'] = np.select(conditions, choices, default="正常波动")
        return df.sort_values(by='静默得分', ascending=False)

    def analyze_silent_trace(self, df_tick):
        """
        投行算法穿透：吸筹效率系数 Ea + 稳定性系数 Sm
        """
        if df_tick is None or df_tick.empty: return 0
        
        # 数据清洗
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        
        # 1. 计算吸筹效率系数 (Ea)
        # Ea = 净买入额 / (波动率 * 总额)
        buy_flow = df_tick[df_tick['type'] == '买盘']['成交额'].sum()
        sell_flow = df_tick[df_tick['type'] == '卖盘']['成交额'].sum()
        net_flow = buy_flow - sell_flow
        total_vol = df_tick['成交额'].sum()
        price_range = (df_tick['price'].max() - df_tick['price'].min()) / df_tick['price'].mean()
        
        # 防止分母为0
        ea_score = (net_flow / (total_vol * price_range)) if (total_vol * price_range) != 0 else 0
        
        # 2. 计算中性盘占比 (静默吸筹特征)
        neutral_df = df_tick[df_tick['type'] == '中性']
        n_ratio = len(neutral_df) / len(df_tick) if len(df_tick) > 0 else 0
        
        # 3. 综合评分逻辑
        score = 0
        if ea_score > 2.0: score += 4  # 高效率吸筹：每一单位波幅承接了巨大的净买入
        if n_ratio > 0.40: score += 2  # 高中性占比：典型静默扫货，不引发盘面激动
        if price_range < 0.008: score += 2 # 极度窄幅控盘
        
        return round(score, 1)

# =================== 3. 动态侦测 UI ===================

st.set_page_config(page_title="Sniffer Pro V12.0", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)

st.title("🏛️ Sniffer Pro V12.0 - 投行量化侦测系统")
st.caption(f"当前用户: {st.session_state.get('user_name', 'Nova')} | 算法库版本: Investment Bank Alpha V12")

# --- Step 1: 实时板块侦测 ---
st.header("Step 1: 全市场板块资金侦测")
df_all_sectors = get_market_sectors_dynamic()

if df_all_sectors is not None:
    st.sidebar.header("📂 审计配置")
    st.sidebar.info(f"审计日期范围: {', '.join(dates)}")
    
    # 高亮显示符合投行吸筹区的板块 (低涨幅+高分)
    st.dataframe(
        df_all_sectors.style.apply(lambda x: ['background-color: #1a3a3a' if (x['今日涨幅'] < 1.5 and x['板块评分'] > 15) else '' for i in x], axis=1), 
        use_container_width=True,
        column_config={"板块评分": st.column_config.NumberColumn(format="%.2f 亿 🟢")}
    )
    
    csv_step1 = df_all_sectors.to_csv(index=False).encode('utf_8_sig')
    st.download_button("📥 导出板块侦测报告", data=csv_step1, file_name=f"Nova_Sectors_{datetime.now().strftime('%m%d')}.csv")
    
    st.divider()
    sector_map = df_all_sectors.set_index('板块名称')['ID'].to_dict()
    selected_sector_name = st.selectbox("🎯 选定待审计板块:", ["请选择探测目标"] + list(sector_map.keys()))

    if selected_sector_name != "请选择探测目标":
        sid = sector_map[selected_sector_name]
        
        # --- Step 2: 个股精细穿透 ---
        st.header(f"Step 2: {selected_sector_name} - 个股因子穿透")
        df_stocks = get_stock_penetration(sid)
        
        if df_stocks is not None:
            # 注入投行个股因子审计
            df_stocks = sniffer.analyze_individual_stock(df_stocks)
            
            # 视觉颜色映射：静默绿，诱多红
            def color_audit(val):
                if '💎' in val: return 'background-color: #064e3b'
                if '⚠️' in val: return 'background-color: #7f1d1d'
                if '⚡' in val: return 'background-color: #1e3a8a'
                return ''

            st.dataframe(
                df_stocks.style.applymap(color_audit, subset=['侦测状态'])
                .background_gradient(subset=['静默得分'], cmap='Greens'),
                use_container_width=True
            )

            csv_step2 = df_stocks.to_csv(index=False).encode('utf_8_sig')
            st.download_button("📥 导出个股穿透报告", data=csv_step2, file_name=f"Nova_Stocks_{selected_sector_name}.csv")

            # --- Step 3: 深度审计与综合导出 ---
            st.divider()
            st.header("Step 3: 投行算法复盘 (Ea 系数深度扫描)")
            
            targets = st.multiselect(
                "勾选标的执行深度 Tick 审计 (识别吸筹效率):", 
                df_stocks['名称'].tolist(),
                default=df_stocks[df_stocks['侦测状态'].str.contains("💎|⚡")]['名称'].tolist()[:3]
            )
            
            if targets:
                reports = []
                p_bar = st.progress(0)
                selected_df = df_stocks[df_stocks['名称'].isin(targets)]
                
                for idx, (s_idx, row) in enumerate(selected_df.iterrows()):
                    c_str = str(row['代码']).zfill(6)
                    f_code = f"{'sh' if c_str.startswith('6') else 'sz'}{c_str}"
                    
                    report_row = {
                        "标的名称": row['名称'], "代码": c_str,
                        "今日涨幅%": row['今日涨幅'], "静默得分": row['静默得分']
                    }
                    
                    total_s = 0
                    for d_idx, date in enumerate(dates):
                        try:
                            df_t = ak.stock_zh_a_tick_163(symbol=f_code, date=date)
                            s = sniffer.analyze_silent_trace(df_t)
                        except: s = 0
                        report_row[f"T-{d_idx} 审计(Ea)"] = s
                        total_s += s
                    
                    report_row["审计综合总分"] = total_s
                    reports.append(report_row)
                    p_bar.progress((idx + 1) / len(selected_df))
                
                df_rep = pd.DataFrame(reports)
                st.subheader("📊 最终复盘矩阵 (投行吸筹权数)")
                st.dataframe(df_rep.style.background_gradient(subset=['审计综合总分'], cmap='RdYlGn'), use_container_width=True)

                csv_step3 = df_rep.to_csv(index=False).encode('utf_8_sig')
                st.download_button("📥 导出深度复盘报告", data=csv_step3, file_name=f"Nova_Audit_Final.csv", use_container_width=True)
