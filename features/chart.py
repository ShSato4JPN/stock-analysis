"""機能2: 株価チャート表示。"""
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from utils.data_fetch import get_history
from utils.indicators import bollinger, sma
from utils.ui import symbol_picker

_PERIODS = {"1ヶ月": "1mo", "3ヶ月": "3mo", "6ヶ月": "6mo", "1年": "1y",
            "5年": "5y", "10年": "10y", "20年": "20y", "30年": "30y"}
# 10年以上は週足に切り替え(日足だと数千本になり重く見づらい)
_WEEKLY_PERIODS = {"10y", "20y", "30y"}


def render():
    st.header("🕯 株価チャート")
    st.caption("ローソク足・移動平均線(25/75日)・ボリンジャーバンド・出来高を表示します。")

    symbol = symbol_picker(key="chart", default_code="7203")
    c1, c2 = st.columns([1, 1])
    period_label = c1.selectbox("期間", list(_PERIODS.keys()), index=3)
    show_bb = c2.checkbox("ボリンジャーバンド", value=False)

    if not symbol:
        return

    period = _PERIODS[period_label]
    weekly = period in _WEEKLY_PERIODS
    df = get_history(symbol, period=period, interval="1wk" if weekly else "1d")
    if df.empty:
        st.error("データを取得できませんでした。銘柄コードを確認してください。")
        return
    if weekly:
        st.caption("📅 10年以上は週足で表示しています(移動平均・ボリンジャーバンドも週足ベース)。")

    close = df["Close"]
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=[0.75, 0.25], subplot_titles=("株価", "出来高"),
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=close,
        name="ローソク足",
    ), row=1, col=1)

    for w, color in [(25, "#1f77b4"), (75, "#ff7f0e")]:
        fig.add_trace(go.Scatter(x=df.index, y=sma(close, w), name=f"SMA{w}",
                                 line=dict(color=color, width=1)), row=1, col=1)

    if show_bb:
        mid, upper, lower = bollinger(close)
        fig.add_trace(go.Scatter(x=df.index, y=upper, name="BB +2σ",
                                 line=dict(color="gray", width=1, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=lower, name="BB -2σ", fill="tonexty",
                                 fillcolor="rgba(128,128,128,0.1)",
                                 line=dict(color="gray", width=1, dash="dot")), row=1, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="出来高",
                         marker_color="#888"), row=2, col=1)

    fig.update_layout(height=700, xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)
