import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# =================== Streamlit 页面配置 ===================
st.set_page_config(page_title="Sniffer V2.0 - 嗅嗅探测器", layout="wide")

st.title("🚀 Sniffer V2.0 实时倒查系统")
st.info("💡 逻辑：板块资金流入 + 个股静默压盘 + 算法频率审计。建议在 10:30 以后执行。")

# =================== Sniffer 类 ===================
class StreamlitSniffer:
    def __init__(self):
        # =================== 侧边栏：动态审计参数 ===================
        st.sidebar.header("🛡️ 审计参数配置")
        self.min_neutral = st.sidebar.slider("中性盘占比阈值 (判断吸筹强度)", 0.1, 0.5, 0.25)
        self.interval_limit = st.sidebar.slider("算法频率稳定性 (std越小越机械)", 0.5, 5.0, 2.0)
        self.price_limit = st.sidebar.slider("价格标准差上限 (验证静默度)", 0.005, 0.05, 0.025)
        self.vwap_limit = st.sidebar.slider("VWAP偏离度上限 (寻找成本共振)", 0.001, 0.02, 0.005)
        
        # 内部审计常量
        self.tail_sample = 60
        self.min_tick_count = 30
        self.required_cols = ['time', 'price', '成交额', 'type']
        self.audited_codes = set()
    
    # ------------------- 第一层：板块探测 -------------------
    def get_sector_data(self):
        try:
            # 实时获取行业资金流向
            df = ak.stock_sector_fund_flow_rank(indicator="今日")
            # 核心过滤：资金净流入高，但板块尚未被拉起（静默区）
            silent_sectors = df[
                (df['主力净流入-净占比'] > 3.0) &
                (df['今日涨跌幅'].between(-0.5, 2.0))
            ].head(8)
            return silent_sectors
        except Exception as e:
            st.error(f"板块探测异常: {e}")
            return pd.DataFrame()
    
    # ------------------- 第二层：反算法个股审计 -------------------
    def audit_stock(self, symbol):
        try:
            time.sleep(1.2)  # 严格执行反爬频率保护
            df_tick = ak.stock_zh_a_tick_163(symbol=symbol)
            
            # 1. 字段健壮性校验
            if df_tick is None or df_tick.empty:
                return 0, 0, "无数据", None
            if not all(c in df_tick.columns for c in self.required_cols):
                return 0, 0, "字段缺失", None
            if len(df_tick) < self.min_tick_count:
                return 0, 0, f"样本不足({len(df_tick)})", None
            
            # 2. 样本预处理
            sample = df_tick.tail(min(self.tail_sample, len(df_tick))).copy()
            sample['time_dt'] = pd.to_datetime(sample['time'], format='%H:%M:%S', errors='coerce')
            
            # 3. 剔除集合竞价干扰
            sample = sample[~((sample['time_dt'].dt.hour==9) & (sample['time_dt'].dt.minute<30))]
            if sample.empty:
                return 0, 0, "集合竞价干扰", None
            
            # 4. 因子计算
            intervals = sample['time_dt'].diff().dt.total_seconds().dropna()
            i_std = intervals.std() # 频率稳定性
            p_std = sample['price'].std() # 价格稳定性
            vwap = (sample['price'] * sample['成交额']).sum() / sample['成交额'].sum()
            v_dev = abs(sample['price'].iloc[-1] - vwap) / vwap # VWAP偏离
            n_ratio = len(sample[sample['type']=='中性']) / len(sample) # 中性占比
            
            # 动态大单拆分审计
            avg_amount = sample['成交额'].mean()
            b_threshold = max(avg_amount * 5, 100000)
            b_count = len(sample[sample['成交额'] > b_threshold])
            
            # 5. 五因子评分系统
            score = 0
            factors_map = {
                "频率稳定": 1 if i_std < self.interval_limit else 0,
                "价格静默": 1 if p_std < self.price_limit else 0,
                "VWAP贴合": 1 if v_dev < self.vwap_limit else 0,
                "中性承接": 1 if n_ratio > self.min_neutral else 0,
                "拆单审计": 1 if b_count < 6 else 0
            }
            score = sum(factors_map.values())
            
            msg = f"Std:{i_std:.1f}, P_Std:{p_std:.3f}, Dev:{v_dev:.3%}"
            return score, n_ratio, msg, factors_map
        except Exception as e:
            return 0, 0, f"审计出错: {str(e)}", None

# =================== 主执行引擎 ===================
sniffer = StreamlitSniffer()

if st.button("🔥 立即执行全盘嗅探"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # STEP 1: 板块发现
    status_text.text("第一步：正在探测全市场静默资金流板块...")
    sectors = sniffer.get_sector_data()
    
    if sectors.empty:
        st.warning("当前时段未发现符合条件的静默扫货板块。")
    else:
        st.write(f"✅ 锁定候选板块: {', '.join(sectors['名称'].tolist())}")
        
        all_results = []
        all_factors = {}
        
        # STEP 2: 个股穿透
        target_list = []
        for _, s_row in sectors.iterrows():
            try:
                # 每个板块取前10只活跃股
                temp_stocks = ak.stock_board_industry_cons_em(symbol=s_row['名称']).head(10)
                for _, st_row in temp_stocks.iterrows():
                    target_list.append((st_row['代码'], st_row['名称'], s_row['名称']))
            except: continue
        
        total = len(target_list)
        for i, (code, name, s_name) in enumerate(target_list):
            if code in sniffer.audited_codes: continue
            sniffer.audited_codes.add(code)
            
            status_text.text(f"第二步：审计个股 [{name}] ({i+1}/{total})")
            f_code = f"sh{code}" if code.startswith('6') else f"sz{code}"
            
            score, n_ratio, msg, f_map = sniffer.audit_stock(f_code)
            
            res_obj = {
                "评分": score,
                "编号": code,
                "名称": name,
                "中性占比": f"{n_ratio*100:.1f}%",
                "所属板块": s_name,
                "审计详情": msg
            }
            all_results.append(res_obj)
            if f_map: all_factors[name] = f_map
            
            progress_bar.progress((i + 1) / total)

        # STEP 3: 结果展示
        df_res = pd.DataFrame(all_results).sort_values(by="评分", ascending=False)
        st.divider()
        st.subheader("📊 审计报告看板")
        
        # 样式渲染
        def style_scores(row):
            color = '#90ee90' if row['评分'] >= 4 else '#ffffff'
            return [f'background-color: {color}' for _ in row]
        
        st.dataframe(df_res.style.apply(style_scores, axis=1), use_container_width=True)

        # STEP 4: 可视化分析
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # 1. 评分分布
            fig_hist = px.histogram(df_res, x="评分", title="样本评分分布 (4分以上为扫货确认)", 
                                   color_discrete_sequence=['#636EFA'])
            st.plotly_chart(fig_hist, use_container_width=True)
            
            # 2. 下载功能
            st.download_button(label="⬇ 下载完整审计CSV", 
                             data=df_res.to_csv(index=False).encode('utf-8-sig'),
                             file_name=f"sniffer_report_{datetime.now().strftime('%H%M')}.csv")

        with col2:
            st.success(f"审计完成！发现 {len(df_res[df_res['评分']>=4])} 个高确信度算法标的。")
            
            # 展示Top 3标的的雷达图
            top_names = df_res[df_res['评分'] >= 4]['名称'].head(3).tolist()
            for t_name in top_names:
                if t_name in all_factors:
                    f_data = all_factors[t_name]
                    fig_radar = go.Figure()
                    fig_radar.add_trace(go.Scatterpolar(
                        r=list(f_data.values()),
                        theta=list(f_data.keys()),
                        fill='toself',
                        name=t_name
                    ))
                    fig_radar.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                        showlegend=True,
                        title=f"算法指纹：{t_name}",
                        height=350
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)
