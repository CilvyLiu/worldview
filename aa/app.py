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
    
# --- 1. 板块逻辑 (Nova 5日静默突围·结构审计版) ---
    if sector_raw:
        sec_rows = parse_smart(sector_raw, "sector")
        if sec_rows:
            # 动态匹配列名（适配 5日完整资金流向表结构）
            df_sec = pd.DataFrame(sec_rows, columns=[
                '序号', '名称', '涨跌幅', 
                '主力净额', '主力净占比', 
                '超大单净额', '超大单净占比', 
                '大单净额', '大单净占比', 
                '中单净额', '中单净占比', 
                '小单净额', '小单净占比'
            ])

            # 数值清洗
            num_cols = [c for c in df_sec.columns if c not in ['序号', '名称']]
            for c in num_cols:
                df_sec[c] = df_sec[c].apply(clean_val)

            st.write("### 📊 5日主力结构审计（Nova 静默突围）")

            # ================= Nova 核心审计准则 =================
            # 1. 主力净额：≥5000万 (5000) - 针对板块级初选
            # 2. 净占比：≥1.5% - 机构真实控盘线
            # 3. 涨跌幅：0% ~ 5% - 拒绝追高，锁定静默吸筹区
            # 4. 结构正向：超大单 & 大单双为正 (机构在买)
            # 5. 筹码交换：小单净额为负 (散户在卖，筹码锁定)
            
            condition = (
                (df_sec['主力净额'] > 5000) & 
                (df_sec['主力净占比'] >= 1.5) & 
                (df_sec['涨跌幅'].between(0.0, 5.0)) & 
                (df_sec['超大单净额'] >= 0) & 
                (df_sec['大单净额'] >= 0) &
                (df_sec['小单净额'] <= 0)
            )

            # 计算吸筹效率：资金/涨幅比，值越大代表“压盘吸筹”越明显
            df_sec['吸筹效率'] = df_sec['主力净额'] / (df_sec['涨跌幅'].abs() + 0.5)
            
            # 决策判定
            df_sec['穿透建议'] = np.where(condition, "🚀 5日静默吸筹", "观察")
            
            # 叠加突围信号：在吸筹基础上，效率处于前 30% 的标的
            eff_threshold = df_sec['吸筹效率'].quantile(0.7)
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
                st.info("当前数据未探测到实盘级信号（需满足资金流入且价格未暴涨）。")
        else:
            st.error("❌ 个股解析失败：请确保粘贴内容包含【6位代码、名称、价格、涨跌幅、今日净额】")
