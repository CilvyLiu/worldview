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
    修正 1 & 2: 
    - 扩充 INVALID_SET 处理 '--', 'nan', '不变' 等噪音
    - 处理 '负号 + 空格' 的鲁棒性解析
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

# ================= 强力正则解析 (Pro 版) =================
def parse_smart(text, mode="sector"):
    """
    修正 2: 增加对负号中间可能存在空格的正则包容度
    """
    lines = text.strip().split('\n')
    data = []
    
    if mode == "sector":
        # 匹配：序号 名称 涨跌幅% 资金 净占比%
        pattern = re.compile(r'(\d+)\s*([\u4e00-\u9fa5]+).*?(-?\s*\d+\.?\d*%).*?(-?\s*\d+\.?\d*[万亿]).*?(-?\s*\d+\.?\d*%)')
    else:
        # 匹配：代码 名称 价格 涨跌幅% 资金
        pattern = re.compile(r'(\d{6})\s+([\u4e00-\u9fa5\w]+)\s+(\d+\.?\d*)\s+(-?\s*\d+\.?\d*%?)\s+(-?\s*\d+\.?\d*[万亿]?)')

    for line in lines:
        match = pattern.search(line)
        if match:
            data.append(match.groups())
    return data

# ================= UI 界面 =================
st.title("🕵️ 嗅嗅 Sniffer - Nova 实盘量化版")
st.markdown(f"> **Nova，当前策略：First (板块生死线) -> Next (防爆炸 Ea) -> Finally (排雷伏击)**")

col1, col2 = st.columns(2)

with col1:
    st.subheader("第一步：初筛板块 (First)")
    sector_raw = st.text_area("粘贴板块流向数据", height=250, placeholder="支持粘连格式...")

with col2:
    st.subheader("第二步：穿透个股 (Next)")
    stock_raw = st.text_area("粘贴个股资金数据", height=250, placeholder="直接粘贴东财个股列表流向...")

# ================= 执行逻辑 =================
if st.button("🚀 执行 Nova 实盘量化分析"):
    # --- 板块逻辑 (修正 3: 引入净占比生死线) ---
    if sector_raw:
        sec_rows = parse_smart(sector_raw, "sector")
        if sec_rows:
            df_sec = pd.DataFrame(sec_rows, columns=['序号', '名称', '涨跌幅', '主力净额', '净占比'])
            for c in ['涨跌幅','主力净额','净占比']: df_sec[c] = df_sec[c].apply(clean_val)
            
            st.write("### 📊 板块初筛结果")
            # 修正判定：主力流入 且 净占比 > 1.0% (生死线) 且 涨幅未透支
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
            # 防止涨跌幅趋于 0 时 Ea 无限大导致假信号霸榜
            df_stk['Ea'] = df_stk['主力万元'] / np.clip(df_stk['涨跌实数'].abs(), 0.3, None)
            
            # --- 修正 5: 增强型信号层 (含排雷) ---
            df_stk['建议动作'] = "观察"
            
            # 💎 真·极品背离：流入且跌幅在 0 到 -3% 之间 (非断头铡)
            mask_gold = (df_stk['主力万元'] > 0) & (df_stk['涨跌实数'].between(-3.0, -0.01))
            
            # 🎯 低价扫货：横盘蓄势 (1.5% 以内)
            mask_ready = (df_stk['主力万元'] > 0) & (df_stk['涨跌实数'].between(-1.5, 1.5))
            
            # 🧨 警惕接盘：大跌（<-4%）时的流入，极可能是散户接飞刀
            mask_fake = (df_stk['主力万元'] > 0) & (df_stk['涨跌实数'] < -4.0)

            df_stk.loc[mask_ready, '建议动作'] = "🎯 低价扫货"
            df_stk.loc[mask_gold, '建议动作'] = "💎 极品背离"
            df_stk.loc[mask_fake, '建议动作'] = "🧨 警惕接盘"

            st.divider()
            st.subheader("💰 Finally: 最终决策清单")
            
            # 过滤非观察类并排序
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
                st.download_button(
                    label="📥 导出 Nova 实盘决策清单 (CSV)",
                    data=csv_data,
                    file_name=f"Nova_Pro_Decision_{today_str}.csv",
                    mime="text/csv"
                )
            else:
                st.info("当前数据中未探测到符合实盘标准的信号。")

st.markdown("""
---
### Nova 实盘量化说明：
1. **净占比生死线**：板块净占比 < 1% 的流入视为“虚火”，不再建议重点穿透。
2. **防爆炸 Ea**：涨跌幅绝对值若低于 0.3，分母将强制取 0.3，确保 Ea 因子对稳态吸筹的敏感度更真实。
3. **排雷机制**：新增 `🧨 警惕接盘` 信号，自动识别跌幅过大导致的被动流入（飞刀风险）。
""")
