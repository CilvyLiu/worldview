import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ================= 页面配置 =================
st.set_page_config(page_title="嗅嗅 Sniffer - Nova 实盘量化版", layout="wide")

# ================= 数据清洗核心 (Pro 版) =================
def clean_val(val):
    """
    针对 Nova 实盘场景优化：处理东财无效符、负号空格、文字杂质及万元/亿元单位换算
    """
    INVALID_SET = {'-', '--', '—', '数据', '', 'None', 'nan', '不变', 'null', '详情', '股吧'}
    if pd.isna(val):
        return 0.0
    
    # 彻底移除空格、逗号及网页交互杂质
    val = str(val).strip().replace(' ', '').replace(',', '').replace('详情', '').replace('股吧', '')
    if val in INVALID_SET:
        return 0.0
    
    mult = 1.0
    # 统一基准：万元
    if '亿' in val:
        mult = 10000.0
        val = val.replace('亿','')
    elif '万' in val:
        mult = 1.0
        val = val.replace('万','')
    
    if '%' in val:
        val = val.replace('%','')
    
    try:
        # 针对可能出现的 "跌停28.98" 等混合文本，提取首个数字
        res = re.search(r'(-?\d+\.?\d*)', val)
        return float(res.group(1)) * mult if res else 0.0
    except:
        return 0.0

# ================= 强力正则解析 (Pro 鲁棒增强版) =================
def parse_smart(text, mode="sector"):
    """
    Nova 进化版：不再死磕空格，先“除杂”再通过正则“锚定”关键财务特征
    """
    # 预处理：剔除杂质，统一替换多个空格为一个
    text = re.sub(r'(大单详情|股吧|详情|数据)', ' ', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    data = []
    
    if mode == "sector":
        # 模式：序号 + 名称 + 涨跌幅% + 主力净额(含万亿) + 净占比%
        pattern = re.compile(r'(\d+)\s+([\u4e00-\u9fa5\w]+)\s+.*?(-?\d+\.?\d*%)\s+.*?(-?\d+\.?\d*[万亿])\s+.*?(-?\d+\.?\d*%)')
    else:
        # 个股模式：代码(6位) + 名称 + 价格 + 涨跌幅 + 资金(含万亿)
        pattern = re.compile(r'(\d{6})\s+([\u4e00-\u9fa5\w]+?)\s+(\d+\.?\d*)\s+(-?\d+\.?\d*%?)\s+(-?\d+\.?\d*[万亿]?)')

    for line in lines:
        match = pattern.search(line)
        if match:
            groups = list(match.groups())
            groups[1] = groups[1].strip() # 清洗名称空格
            data.append(groups)
            
    return data

# ================= UI 界面 =================
st.title("🕵️ 嗅嗅 Sniffer - Nova 实盘量化版")
st.markdown(f"> **Nova，当前策略流：First (板块生死线) -> Next (活跃度 Ea 因子) -> Finally (伏击判定)**")

col1, col2 = st.columns(2)

with col1:
    st.subheader("第一步：初筛板块 (First)")
    sector_raw = st.text_area("直接粘贴东财【板块流向】数据", height=250, placeholder="1 煤炭行业 1.2% 5.2亿 2.1% ...")

with col2:
    st.subheader("第二步：穿透个股 (Next)")
    stock_raw = st.text_area("直接粘贴东财【个股流向】列表", height=250, placeholder="002415 海康威视 31.33 -2.70% -1.83亿 ...")

# ================= 执行逻辑 =================
if st.button("🚀 执行 Nova 实盘量化分析"):
# --- 1. 板块逻辑 (Nova 通用去噪·审计版) ---
    if sector_raw:
        # 核心增强：在解析前先干掉所有“X日”干扰词，确保 [涨跌幅] 紧跟 [主力净额]
        # 这样你的 parse_smart 就能通过一套正则通杀所有周期的表
        clean_text = re.sub(r'\d+日', '', sector_raw) 
        sec_rows = parse_smart(clean_text, "sector")
        
        if sec_rows:
            # 这里的 expected_cols 对应你 parse_smart(mode="sector") 抓取的 5 个 Group
            # 即：(\d+), (名称), (涨跌幅), (主力净额), (净占比)
            df_sec = pd.DataFrame(sec_rows, columns=['序号', '名称', '涨跌幅', '主力净额', '主力净占比'])

            # 数值清洗
            num_cols = ['涨跌幅', '主力净额', '主力净占比']
            for c in num_cols:
                df_sec[c] = df_sec[c].apply(clean_val)

            st.write("### 📊 板块结构审计 (Nova 静默突围)")

            # ================= Nova 核心审计准则 (保持原逻辑) =================
            # 即使只有 5 列数据，我们依然执行吸筹效率审计
            condition = (
                (df_sec['主力净额'] > 5000) &   # ≥5000万
                (df_sec['主力净占比'] >= 1.5) & # ≥1.5%
                (df_sec['涨跌幅'].between(0.0, 5.0)) # 静默区
            )

            # 计算吸筹效率：资金/涨幅比
            df_sec['吸筹效率'] = df_sec['主力净额'] / (df_sec['涨跌幅'].abs() + 0.5)
            
            # 决策判定
            df_sec['穿透建议'] = np.where(condition, "🚀 静默吸筹", "观察")
            
            # 叠加突围信号
            if not df_sec[df_sec['主力净额'] > 0].empty:
                eff_threshold = df_sec[df_sec['主力净额'] > 0]['吸筹效率'].quantile(0.7)
                df_sec.loc[condition & (df_sec['吸筹效率'] >= eff_threshold), '穿透建议'] = "🔥 静默 -> 突围前夜"

            # 样式渲染
            def style_audit(val):
                if "🔥" in str(val): return 'background-color: #8b0000; color: #ffffff; font-weight: bold'
                if "🚀" in str(val): return 'background-color: #1e3d59; color: #ffc13b'
                return ''

            st.dataframe(
                df_sec.sort_values(by='吸筹效率', ascending=False).style.applymap(style_audit, subset=['穿透建议']), 
                use_container_width=True
            )
    # --- 2. 个股逻辑 ---
    if stock_raw:
        stk_rows = parse_smart(stock_raw, "stock")
        if stk_rows:
            df_stk = pd.DataFrame(stk_rows, columns=['代码', '名称', '价格', '涨跌幅', '今日净额'])
            
            df_stk['涨跌实数'] = df_stk['涨跌幅'].apply(clean_val)
            df_stk['主力万元'] = df_stk['今日净额'].apply(clean_val)
            df_stk['价格数值'] = df_stk['价格'].apply(pd.to_numeric, errors='coerce')

            # --- Ea 因子防爆炸保险 ---
            # Ea = 资金 / 振幅。np.clip 确保分母不为0，防止数据异常导致结果无穷大。
            df_stk['Ea'] = df_stk['主力万元'] / np.clip(df_stk['涨跌实数'].abs(), 0.3, None)
            
            # --- 决策信号层 ---
            df_stk['建议动作'] = "观察"
            
            # 💎 极品背离：股价在跌，主力在买 (洗筹特征)
            mask_gold = (df_stk['主力万元'] > 0) & (df_stk['涨跌实数'].between(-3.0, -0.01))
            # 🎯 低价扫货：横盘蓄势，资金暗流
            mask_ready = (df_stk['主力万元'] > 0) & (df_stk['涨跌实数'].between(-1.5, 1.5))
            # 🧨 警惕接盘：大跌 (>4%) 时的高额流入，可能是下跌中继或飞刀
            mask_fake = (df_stk['主力万元'] > 0) & (df_stk['涨跌实数'] < -4.0)

            df_stk.loc[mask_ready, '建议动作'] = "🎯 低价扫货"
            df_stk.loc[mask_gold, '建议动作'] = "💎 极品背离"
            df_stk.loc[mask_fake, '建议动作'] = "🧨 警惕接盘"
# ================= 3. 下一交易日砸盘预警模块 (Nova Pro 增强) =================
            # 1. 计算乖离率 (Bias)
            df_stk['乖离率'] = 0.0
            if '均价' in stock_raw:
                # 尝试用正则从原文中提取均价数值
                avg_match = re.search(r'均价[:：]?\s*(\d+\.?\d*)', stock_raw)
                if avg_match:
                    avg_price = float(avg_match.group(1))
                    df_stk['乖离率'] = (df_stk['价格数值'] - avg_price) / avg_price * 100

            # 2. 定义风险因子
            # A: 高位滞涨 (涨幅 > 4% 且未跌破均价但也没封板)
            risk_a = np.where(df_stk['涨跌实数'] > 4.0, 30, 0)
            # B: 弱动能 (Ea 因子过低，说明资金撑不住这个涨幅)
            risk_b = np.where(df_stk['Ea'] < 300, 25, 0) 
            # C: 节前效应 (今天是倒数第6天，权重拉满)
            # 2月6日是周五，today_day=4。设定下周一(0)到三(2)为高压区
            today_day = datetime.now().weekday() 
            is_holiday_pressure = 25 if today_day <= 2 or today_day == 4 else 0 
            
            df_stk['风险值'] = risk_a + risk_b + is_holiday_pressure

            # 3. 判定砸盘等级
            def judge_crash(row):
                if row['主力万元'] < 0 and row['涨跌实数'] > 0: return "📉 诱多砸盘"
                if row['风险值'] >= 50: return "🚨 极高风险"
                if row['风险值'] >= 30: return "⚠️ 高风险"
                return "✅ 风险受控"

            df_stk['砸盘预警'] = df_stk.apply(judge_crash, axis=1)

            # ================= 4. UI 渲染增强 =================
            def style_all(val):
                # 动作颜色
                if "💎" in str(val): return 'background-color: #8b0000; color: white'
                if "🎯" in str(val): return 'background-color: #006400; color: white'
                if "🧨" in str(val): return 'background-color: #444444; color: #ff4b4b'
                # 砸盘颜色
                if "🚨" in str(val): return 'background-color: #ff4b4b; color: white; font-weight: bold'
                if "⚠️" in str(val): return 'background-color: #ffa500; color: black'
                if "📉" in str(val): return 'background-color: #7d3cff; color: white'
                return ''

            st.divider()
            st.subheader("💰 Finally: 最终决策清单")
            
            # 【核心修复点】：改变筛选条件，同时显示有动作和有风险的个股
            # 只要触发了建议动作，或者砸盘预警不是“受控”状态，都要出现在清单里
            condition = (df_stk['建议动作'] != "观察") | (df_stk['砸盘预警'] != "✅ 风险受控")
            best = df_stk[condition].copy().sort_values(by='Ea', ascending=False)
            
            if not best.empty:
                # 按照你的习惯，隐藏掉中间计算的“风险值”和“乖离率”列，只看结果
                show_cols = ['代码', '名称', '价格', '涨跌幅', '今日净额', 'Ea', '建议动作', '砸盘预警']
                
                # 渲染最终表格
                st.dataframe(
                    best[show_cols].style.applymap(style_all, subset=['建议动作', '砸盘预警']), 
                    use_container_width=True
                )
                
                # --- 导出功能 (同步列名) ---
                today_str = datetime.now().strftime("%Y%m%d_%H%M")
                csv_data = best[show_cols].to_csv(index=False).encode('utf-8-sig')
                st.download_button(label="📥 导出 Nova 决策清单", data=csv_data, file_name=f"Nova_Pro_{today_str}.csv")
            else:
                st.info("当前数据未探测到实盘级信号或砸盘风险。")
