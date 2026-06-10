"""機能10: リスク指標ダッシュボード。

過去の日次リターンから、シャープレシオ・最大ドローダウン・
年率ボラティリティ・ベータ(対ベンチマーク)を算出する。
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_fetch import get_history
from utils.ui import symbol_picker

_PERIODS = {"1年": "1y", "2年": "2y", "3年": "3y", "5年": "5y"}
_TRADING_DAYS = 252
# ベンチマーク(ベータ算出用)
_BENCHMARKS = {"日経225 (^N225)": "^N225", "TOPIX連動ETF (1306.T)": "1306.T", "S&P500 (^GSPC)": "^GSPC"}


def _daily_returns(symbol: str, period: str) -> pd.Series:
    df = get_history(symbol, period=period)
    if df.empty:
        return pd.Series(dtype=float)
    return df["Close"].pct_change().dropna()


def render():
    st.header("⚖️ リスク指標ダッシュボード")
    st.caption("過去の値動きからリスク・リターン指標を算出します。投資判断の参考にご利用ください。")

    symbol = symbol_picker(key="risk", default_code="7203")
    c1, c2, c3 = st.columns(3)
    period_label = c1.selectbox("期間", list(_PERIODS.keys()), index=1)
    bench_label = c2.selectbox("ベンチマーク(ベータ用)", list(_BENCHMARKS.keys()))
    rf_pct = c3.number_input("無リスク金利(年率%)", min_value=0.0, value=0.5, step=0.1)

    if not symbol or not st.button("指標を算出"):
        return

    period = _PERIODS[period_label]
    ret = _daily_returns(symbol, period)
    if ret.empty or len(ret) < 20:
        st.error("十分な過去データを取得できませんでした。")
        return

    # --- 指標計算 ---
    ann_return = float(ret.mean()) * _TRADING_DAYS * 100        # 年率リターン
    ann_vol = float(ret.std()) * np.sqrt(_TRADING_DAYS) * 100   # 年率ボラティリティ
    rf_daily = rf_pct / 100 / _TRADING_DAYS
    excess = ret - rf_daily
    sharpe = (excess.mean() / ret.std() * np.sqrt(_TRADING_DAYS)) if ret.std() else 0.0

    # 最大ドローダウン
    cum = (1 + ret).cumprod()
    peak = cum.cummax()
    drawdown = cum / peak - 1
    max_dd = float(drawdown.min()) * 100

    # ベータ(対ベンチマーク)
    bench_ret = _daily_returns(_BENCHMARKS[bench_label], period)
    beta = np.nan
    if not bench_ret.empty:
        joined = pd.concat([ret, bench_ret], axis=1, join="inner").dropna()
        if len(joined) >= 20:
            cov = np.cov(joined.iloc[:, 0], joined.iloc[:, 1])
            beta = cov[0, 1] / cov[1, 1] if cov[1, 1] else np.nan

    # --- 表示 ---
    c1, c2, c3 = st.columns(3)
    c1.metric("年率リターン", f"{ann_return:+.2f}%")
    c2.metric("年率ボラティリティ", f"{ann_vol:.2f}%")
    c3.metric("シャープレシオ", f"{sharpe:.2f}",
              help="(リターン − 無リスク金利) ÷ ボラティリティ。高いほど効率的")
    c1, c2, c3 = st.columns(3)
    c1.metric("最大ドローダウン", f"{max_dd:.2f}%", help="期間中の高値からの最大下落率")
    c2.metric(f"ベータ(対{bench_label.split(' ')[0]})",
              f"{beta:.2f}" if not np.isnan(beta) else "-",
              help="1より大きいと市場より値動きが大きい")
    c3.metric("データ日数", f"{len(ret)}")

    # ドローダウン推移
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=drawdown.index, y=drawdown.values * 100,
                             fill="tozeroy", line=dict(color="#e74c3c"), name="ドローダウン"))
    fig.update_layout(height=350, title="ドローダウン推移(%)",
                      yaxis_title="高値からの下落率(%)")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📐 指標の意味"):
        st.markdown(
            "- **年率ボラティリティ**: リターンの標準偏差を年率換算したもの。大きいほど価格変動リスクが高い。\n"
            "- **シャープレシオ**: リスク1単位あたりの超過リターン。一般に1以上で優秀とされる。\n"
            "- **最大ドローダウン**: 過去のピークからの最大下落率。精神的・資金的な耐性の目安。\n"
            "- **ベータ**: ベンチマークに対する感応度。1.2なら市場が1%動くと約1.2%動く傾向。"
        )
