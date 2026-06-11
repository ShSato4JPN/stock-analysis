"""機能4: 配当金シミュレーター。"""
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_fetch import (
    dividend_yield_pct,
    get_dividends,
    get_info,
    get_price,
    normalize_symbol,
)
from utils.ui import symbol_picker


def render():
    st.header("💰 配当金シミュレーター")
    st.caption("配当履歴から年間配当金を試算し、増配/減配傾向をグラフ化します。")

    symbol = symbol_picker(key="div", default_code="8306")
    shares = st.number_input("保有株数", min_value=0.0, value=100.0, step=1.0)
    if not symbol:
        return

    sym = normalize_symbol(symbol)
    div = get_dividends(sym)
    if div.empty:
        st.error("配当履歴を取得できませんでした(無配当銘柄の可能性もあります)。")
        return

    # 直近12ヶ月の1株配当(年の途中でも正確な「年間」になる)
    now = pd.Timestamp.now(tz=div.index.tz)
    ttm_per_share = float(div[div.index >= now - pd.Timedelta(days=365)].sum())

    price = get_price(sym)
    info = get_info(sym)
    yield_pct = dividend_yield_pct(info)
    if yield_pct is None and price and ttm_per_share:
        yield_pct = ttm_per_share / price * 100  # フォールバック: 直近12ヶ月配当÷株価

    c1, c2, c3 = st.columns(3)
    c1.metric("年間配当(1株・直近12ヶ月)", f"{ttm_per_share:,.2f}")
    c2.metric("年間配当金(試算)", f"{ttm_per_share * shares:,.0f}")
    c3.metric("配当利回り", f"{yield_pct:.2f}%" if yield_pct else "-")

    # 年次集計と推移グラフ
    annual = div.groupby(div.index.year).sum()
    current_year = now.year
    plot_df = annual.reset_index()
    plot_df.columns = ["年", "1株あたり配当"]
    fig = px.bar(plot_df, x="年", y="1株あたり配当", title="1株あたり配当の推移")
    st.plotly_chart(fig, use_container_width=True)
    if annual.index.max() == current_year:
        st.caption(f"※ {current_year}年は年途中までの合計です。")

    # 増配/減配判定(進行中の年は除いて確定年同士で比較)
    full_years = annual[annual.index < current_year]
    if len(full_years) >= 2:
        diff = full_years.iloc[-1] - full_years.iloc[-2]
        y1, y0 = full_years.index[-1], full_years.index[-2]
        if diff > 0:
            st.success(f"📈 増配傾向: {y0}年→{y1}年 (+{diff:,.2f})")
        elif diff < 0:
            st.warning(f"📉 減配傾向: {y0}年→{y1}年 ({diff:,.2f})")
        else:
            st.info(f"{y0}年→{y1}年 横ばい")
