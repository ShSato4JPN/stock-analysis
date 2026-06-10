"""機能4: 配当金シミュレーター。"""
import plotly.express as px
import streamlit as st

from utils.data_fetch import get_dividends, get_info, get_price, normalize_symbol
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

    # 年次集計
    annual = div.groupby(div.index.year).sum()
    latest_year = annual.index.max()
    latest_per_share = float(annual.loc[latest_year])

    price = get_price(sym)
    info = get_info(sym)
    yield_pct = info.get("dividendYield")
    yield_pct = yield_pct * 100 if yield_pct else (latest_per_share / price * 100 if price else None)

    c1, c2, c3 = st.columns(3)
    c1.metric(f"年間配当(1株/{latest_year}年)", f"{latest_per_share:,.2f}")
    c2.metric("年間配当金(試算)", f"{latest_per_share * shares:,.0f}")
    c3.metric("配当利回り", f"{yield_pct:.2f}%" if yield_pct else "-")

    # 推移グラフ
    plot_df = annual.reset_index()
    plot_df.columns = ["年", "1株あたり配当"]
    fig = px.bar(plot_df, x="年", y="1株あたり配当", title="1株あたり配当の推移")
    st.plotly_chart(fig, use_container_width=True)

    # 増配/減配判定
    if len(annual) >= 2:
        diff = annual.iloc[-1] - annual.iloc[-2]
        if diff > 0:
            st.success(f"📈 前年比 増配 (+{diff:,.2f})")
        elif diff < 0:
            st.warning(f"📉 前年比 減配 ({diff:,.2f})")
        else:
            st.info("前年比 横ばい")
