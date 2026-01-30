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
    修正 1 & 2: 处理东财无效符、负号空格及单位换算
    """
    INVALID_SET = {'-', '--', '—', '数据', '', 'None', 'nan', '不变', 'null', '—'}
    if pd.isna(val):
        return 0.0
    
    # 彻底移除空格、逗号及东财杂质
    val = str(val).strip().replace(' ', '').replace(',', '').replace('详情', '').replace('股吧', '')
    if val in INVALID_SET:
        return 0.0
    
    mult = 1.0
    if '亿' in val:
        mult = 10000.0  # 统一基准：万元
        val = val.replace('亿','')
    elif '万' in val:
        mult = 1.0
        val = val.replace('万','')
    
    is_percent = '%' in val
    if is_percent:
        val = val.replace('%','')
    
    try:
        return float(val) * mult
    except:
        return 0.0

# ================= 强力正则解析 (Pro 鲁棒增强版) =================
def parse_smart(text, mode="sector"):
    """
    进化版：不再死磕空格，而是先“除杂”再“提取”
    """
    # 预处理：剔除网页杂质，统一替换多个空格为一个
    text = re.sub(r'(大单详情|股吧|详情)', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    data = []
    
    if mode == "sector":
        # 模式说明：序号 + 名称 + 涨跌幅% + 主力净额(含万亿) + 净占比%
        # 核心改进：使用 (.*?) 非贪婪匹配名称，适应“亿”字掉落到下一行的情况
        pattern = re.compile(r'(\d+)\s+([\u4e00-\u9fa5\w]+)\s+.*?(-?\d+\.?\d*%)\s+.*?(-?\d+\.?\d*[万亿])\s+.*?(-?\d+\.?\d*%)')
    else:
        # 个股模式：代码 + 名称 + 价格 + 涨跌幅 + 资金
        pattern = re.compile(r'(\d{6})\s+([\u4e00-\u9fa5\w\s]+?)\s+(\d+\.?\d*)\s+(-?\d+\.?\d*%?)\s+(-?\d+\.?\d*[万亿]?)')

    for line in lines:
        match = pattern.search(line)
        if match:
            groups = list(match.groups())
            # 针对个股名称中可能夹杂的空格进行清洗
            groups[1] = groups[1].strip() 
            data.append(groups)
            
    # 如果正则没抓到，启动“备用逻辑”：处理那种字符完全掉到下一行的情况
    if not data and mode == "sector":
        # 这里可以添加更复杂的逻辑，但在 Nova 版中，我们优先保证正则的宽度
        pass
        
    return data

# ================= UI 界面 =================
st.title("🕵️ 嗅嗅 Sniffer - Nova 实盘量化版")
st.markdown(f"> **Nova，当前策略：First (板块生死线) -> Next (防爆炸 Ea) -> Finally (排雷伏击)**")

col1, col2 = st.columns(2)

with col1:
    st.subheader("第一步：初筛板块 (First)")
    sector_raw = st.text_area("粘贴板块流向数据", height=250, placeholder="粘贴示例：1 煤炭行业 1.2% 5.2亿 2.1%")

with col2:
    st.subheader("第二步：穿透个股 (Next)")
    stock_raw = st.text_area("粘贴个股资金数据", height=250, placeholder="直接粘贴东财个股流向列表...")

# ================= 执行逻辑 =================
if st.button("🚀 执行 Nova 实盘量化分析"):
    # --- 板块逻辑 (修正 3: 引入净占比生死线) ---
    if sector_raw:
        sec_rows = parse_smart(sector_raw, "sector")
        if sec_rows:
            df_sec = pd.DataFrame(sec_rows, columns=['序号', '名称', '涨跌幅', '主力净额', '净占比'])
            for c in ['涨跌幅','主力净额','净占比']: df_sec[c] = df_sec[c].apply(clean_val)
            
            st.write("### 📊 板块初筛结果")
            df_sec['穿透建议'] = np.where(
                (df_sec['主力净额'] > 0) & (df_sec['净占比'] > 1.0) & (df_sec['涨跌幅'] < 2.0),
                "🎯 重点去搜", "观察"
            )
            st.dataframe(df_sec.sort_values(by='主力净额', ascending=False), use_container_width=True)

    # --- 个股逻辑 ---
    if stock_raw:
        stk_rows = parse_smart(stock_raw, "stock")
        if stk_rows:
            df_stk = pd.DataFrame(stk_rows, columns=['代码', '名称', '价格', '涨跌幅', '今日净额'])
            
            df_stk['涨跌实数'] = df_stk['涨跌幅'].apply(clean_val)
            df_stk['主力万元'] = df_stk['今日净额'].apply(clean_val)
            df_stk['价格数值'] = df_stk['价格'].apply(pd.to_numeric, errors='coerce')

            # --- 修正 4: Ea 因子防爆炸保险 (np.clip 0.3) ---
            df_stk['Ea'] = df_stk['主力万元'] / np.clip(df_stk['涨跌实数'].abs(), 0.3, None)
            
            # --- 修正 5: 增强型信号层 (含排雷) ---
            df_stk['建议动作'] = "观察"
            
            # 💎 极品背离：资金流入且股价小幅下跌
            mask_gold = (df_stk['主力万元'] > 0) & (df_stk['涨跌实数'].between(-3.0, -0.01))
            # 🎯 低价扫货：资金流入且横盘
            mask_ready = (df_stk['主力万元'] > 0) & (df_stk['涨跌实数'].between(-1.5, 1.5))
            # 🧨 警惕接盘：大跌（<-4%）流入，疑似接飞刀
            mask_fake = (df_stk['主力万元'] > 0) & (df_stk['涨跌实数'] < -4.0)

            df_stk.loc[mask_ready, '建议动作'] = "🎯 低价扫货"
            df_stk.loc[mask_gold, '建议动作'] = "💎 极品背离"
            df_stk.loc[mask_fake, '建议动作'] = "🧨 警惕接盘"

            st.divider()
            st.subheader("💰 Finally: 最终决策清单")
            
            best = df_stk[df_stk['建议动作'] != "观察"].copy().sort_values(by='Ea', ascending=False)
            best['Ea'] = best['Ea'].round(2)
            
            if not best.empty:
                def style_action(val):
                    if "💎" in val: return 'background-color: #8b0000; color: white'
                    if "🎯" in val: return 'background-color: #006400; color: white'
                    if "🧨" in val: return 'background-color: #444444; color: #ff4b4b'
                    return ''

                show_cols = ['代码', '名称', '价格', '涨跌幅', '今日净额', 'Ea', '建议动作']
                st.dataframe(best[show_cols].style.applymap(style_action, subset=['建议动作']), use_container_width=True)
                
                # --- 导出功能 ---
                today_str = datetime.now().strftime("%Y%m%d_%H%M")
                csv_data = best[show_cols].to_csv(index=False).encode('utf-8-sig')
                st.download_button(label="📥 导出 Nova 决策清单", data=csv_data, file_name=f"Nova_Pro_{today_str}.csv")
            else:
                st.info("当前数据未探测到实盘级信号。")
        else:
            st.error("❌ 个股解析失败：请确保粘贴内容包含【6位代码、名称、价格、涨跌、资金】")
