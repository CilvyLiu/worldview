import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime

class Sniffer:
    def __init__(self):
        # 核心审计参数
        self.min_neutral_ratio = 0.25       # 中性盘占比阈值
        self.algo_interval_std_limit = 2.0  # 成交间隔标准差上限（越小越像机器）
        self.price_stability_limit = 0.02   # 价格波动标准差上限
        self.vwap_dev_limit = 0.005         # 价格偏离VWAP上限
        self.min_tick_count = 30            # 最小样本量要求
        self.tail_sample = 60               # tick取尾部样本数量
        
        # 动态去重记录
        self.audited_codes = set()
        self.required_cols = ['time', 'price', '成交额', 'type']

    def first_sector_probe(self):
        """板块探测：静默流入识别"""
        try:
            sector_flow = ak.stock_sector_fund_flow_rank(indicator="今日")
            silent_sectors = sector_flow[
                (sector_flow['主力净流入-净占比'] > 3.0) & 
                (sector_flow['今日涨跌幅'].between(-0.5, 1.5))
            ].head(8)
            return silent_sectors
        except Exception as e:
            print(f"❌ [板块探测异常]: {e}")
            return pd.DataFrame()

    def next_stock_filter(self, sector_name):
        """个股初筛：去重并剔除冷门/风险标的"""
        try:
            stocks = ak.stock_board_industry_cons_em(symbol=sector_name)
            candidates = stocks[
                (stocks['涨跌幅'] < 2.5) & 
                (stocks['量比'] > 1.1) &
                (~stocks['名称'].str.contains("ST|N|C"))
            ].copy()
            
            candidates = candidates[~candidates['代码'].isin(self.audited_codes)]
            return candidates.head(10)
        except Exception as e:
            print(f"⚠️ [个股过滤异常] {sector_name}: {e}")
            return pd.DataFrame()

    def finally_anti_algo_audit(self, symbol):
        """反算法审计：评分系统"""
        try:
            time.sleep(1.1)
            df_tick = ak.stock_zh_a_tick_163(symbol=symbol)
            
            # 字段和样本检查
            if df_tick is None or df_tick.empty:
                return 0, 0, "空数据"
            if not all(c in df_tick.columns for c in self.required_cols):
                missing = list(set(self.required_cols) - set(df_tick.columns))
                return 0, 0, f"缺少字段: {missing}"
            if len(df_tick) < self.min_tick_count:
                return 0, 0, f"样本不足({len(df_tick)})"

            sample = df_tick.tail(min(self.tail_sample, len(df_tick))).copy()

            # 排除集合竞价（09:25~09:30）
            sample['time_dt'] = pd.to_datetime(sample['time'], format='%H:%M:%S')
            sample = sample[~((sample['time_dt'].dt.hour==9) & (sample['time_dt'].dt.minute<30))]
            if sample.empty:
                return 0, 0, "集合竞价数据被排除后无样本"

            # 频率审计
            intervals = sample['time_dt'].diff().dt.total_seconds().dropna()
            interval_std = intervals.std()

            # 价格稳定性与VWAP偏离
            price_std = sample['price'].std()
            vwap = (sample['price'] * sample['成交额']).sum() / sample['成交额'].sum()
            last_price = sample['price'].iloc[-1]
            vwap_dev = abs(last_price - vwap) / vwap

            # 中性盘占比
            neutral_ratio = len(sample[sample['type']=='中性']) / len(sample)

            # 大单拆分（动态阈值）
            avg_amount = sample['成交额'].mean()
            big_order_threshold = max(avg_amount*5, 100000)
            big_order_count = len(sample[sample['成交额'] > big_order_threshold])

            # --- 多因子评分 ---
            score = 0
            score += 1 if interval_std < self.algo_interval_std_limit else 0
            score += 1 if price_std < self.price_stability_limit else 0
            score += 1 if vwap_dev < self.vwap_dev_limit else 0
            score += 1 if neutral_ratio > self.min_neutral_ratio else 0
            score += 1 if big_order_count < 6 else 0

            msg = f"评分 {score}/5"
            return score, neutral_ratio, msg

        except Exception as e:
            return 0, 0, f"审计出错: {str(e)}"

    def run_sniffer(self):
        """主流程"""
        self.audited_codes.clear()
        sectors = self.first_sector_probe()
        if sectors.empty:
            print("未发现静默板块")
            return

        all_results = []
        for _, s_row in sectors.iterrows():
            s_name = s_row['名称']
            potential_stocks = self.next_stock_filter(s_name)
            
            for _, st_row in potential_stocks.iterrows():
                code = st_row['代码']
                self.audited_codes.add(code)

                formatted_code = f"sh{code}" if code.startswith('6') else f"sz{code}"
                score, neutral_ratio, msg = self.finally_anti_algo_audit(formatted_code)

                all_results.append({
                    "板块": s_name,
                    "编号": code,
                    "名称": st_row['名称'],
                    "中性占比": f"{round(neutral_ratio*100,1)}%",
                    "评分": score,
                    "详情": msg
                })

        if all_results:
            report_df = pd.DataFrame(all_results)
            print(f"\n🔎 【嗅嗅】多维评分倒查快照 - {datetime.now().strftime('%H:%M:%S')}")
            print("-"*80)
            print(report_df.sort_values(by="评分", ascending=False).to_string(index=False))
            # 可选保存
            # report_df.to_csv(f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", index=False)


# 启动示例
if __name__ == "__main__":
    sniffer = Sniffer()
    sniffer.run_sniffer()
