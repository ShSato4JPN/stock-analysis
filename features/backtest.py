"""機能6: バックテスト(移動平均クロス戦略)。"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from utils.data_fetch import get_history
from utils.indicators import sma
from utils.ui import symbol_picker

_PERIODS = {"1年": "1y", "2年": "2y", "5年": "5y", "10年": "10y"}


def render():
    st.header("🔁 バックテスト")
    st.caption("ゴールデンクロス(短期>長期)で買い、デッドクロスで売る戦略を過去データで検証します。")

    symbol = symbol_picker(key="bt", default_code="7203")
    c1, c2, c3 = st.columns(3)
    short_w = c1.number_input("短期(日)", min_value=1, value=25)
    long_w = c2.number_input("長期(日)", min_value=2, value=75)
    period_label = c3.selectbox("期間", list(_PERIODS.keys()), index=2)

    if short_w >= long_w:
        st.warning("短期は長期より小さくしてください。")
        return
    if not symbol or not st.button("バックテスト実行"):
        return

    df = get_history(symbol, period=_PERIODS[period_label])
    if df.empty:
        st.error("データを取得できませんでした。")
        return

    close = df["Close"]
    df = df.assign(short=sma(close, short_w), long=sma(close, long_w)).dropna()
    if df.empty:
        st.error("期間が短く指標を計算できません。期間を延ばしてください。")
        return

    # クロス検出: short>long の状態変化
    above = df["short"] > df["long"]
    cross = above.astype(int).diff()
    buys = df.index[cross == 1]
    sells = df.index[cross == -1]

    # シミュレーション: 全額で1単位売買、ポジションは0/1
    position = 0
    entry = 0.0
    returns = []
    trades = 0
    for date in df.index:
        if date in buys and position == 0:
            position = 1
            entry = df.loc[date, "Close"]
        elif date in sells and position == 1:
            position = 0
            returns.append(df.loc[date, "Close"] / entry)
            trades += 1
    # 未決済ポジションを最終日でクローズ
    if position == 1:
        returns.append(df["Close"].iloc[-1] / entry)
        trades += 1

    strategy_return = (np.prod(returns) - 1) * 100 if returns else 0.0
    bh_return = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("戦略リターン", f"{strategy_return:+.2f}%")
    c2.metric("Buy&Hold", f"{bh_return:+.2f}%", f"{strategy_return - bh_return:+.2f}pt")
    c3.metric("取引回数", f"{trades}")

    # チャート
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=close.loc[df.index], name="終値",
                             line=dict(color="#aaa")))
    fig.add_trace(go.Scatter(x=df.index, y=df["short"], name=f"SMA{short_w}",
                             line=dict(color="#1f77b4")))
    fig.add_trace(go.Scatter(x=df.index, y=df["long"], name=f"SMA{long_w}",
                             line=dict(color="#ff7f0e")))
    fig.add_trace(go.Scatter(x=buys, y=df.loc[buys, "Close"], mode="markers",
                             name="買い", marker=dict(symbol="triangle-up", size=12, color="green")))
    fig.add_trace(go.Scatter(x=sells, y=df.loc[sells, "Close"], mode="markers",
                             name="売り", marker=dict(symbol="triangle-down", size=12, color="red")))
    fig.update_layout(height=600, legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)
