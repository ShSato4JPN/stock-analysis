"""機能9: 銘柄比較(複数銘柄の並列表示)。"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import listings
from utils.data_fetch import dividend_yield_pct, get_history, get_info
from utils.ui import symbol_multipicker

_PERIODS = {"3ヶ月": "3mo", "6ヶ月": "6mo", "1年": "1y", "3年": "3y", "5年": "5y"}


def render():
    st.header("📊 銘柄比較")
    st.caption("2〜4銘柄を選び、正規化リターン(起点=100)の重ね描きと指標の横並び比較を行います。")

    # サイドバーの注目メモから比較対象を取り込む
    memo = st.session_state.get("memo_codes", [])
    if memo:
        names = ", ".join(listings.name_of(c) or c for c in memo[:4])
        if st.button(f"📌 注目メモから取り込む({names})"):
            # 絞り込みをリセットしてメモの銘柄を選択状態にする
            st.session_state["cmp_mkt"] = "すべて"
            st.session_state["cmp_kw"] = ""
            st.session_state["cmp_sel"] = memo[:4]
            st.rerun()

    symbols = symbol_multipicker(key="cmp", default_codes=memo[:4] or ["7203", "6758"], max_n=4)
    period_label = st.selectbox("期間", list(_PERIODS.keys()), index=2)

    if len(symbols) < 2:
        st.info("2銘柄以上を選択してください。")
        return

    # --- 正規化リターン(起点=100)の重ね描き ---
    fig = go.Figure()
    perf = {}
    with st.spinner("株価データを取得中..."):
        for sym in symbols:
            df = get_history(sym, period=_PERIODS[period_label])
            if df.empty:
                st.warning(f"{sym}: 株価を取得できませんでした。")
                continue
            close = df["Close"].dropna()
            norm = close / close.iloc[0] * 100
            name = listings.name_of(sym.replace(".T", "")) or sym
            fig.add_trace(go.Scatter(x=norm.index, y=norm.values, name=f"{sym} {name}"))
            perf[sym] = (close.iloc[-1] / close.iloc[0] - 1) * 100

    fig.add_hline(y=100, line=dict(color="gray", dash="dot"))
    fig.update_layout(height=500, title="正規化リターン(起点=100)",
                      yaxis_title="指数(起点=100)", legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)

    # 期間リターン
    if perf:
        st.markdown("**期間リターン**")
        cols = st.columns(len(perf))
        for col, (sym, ret) in zip(cols, perf.items()):
            col.metric(sym, f"{ret:+.2f}%")

    # --- 指標の横並び比較 ---
    st.markdown("**指標比較**")
    rows = []
    for sym in symbols:
        info = get_info(sym)
        rows.append({
            "銘柄": sym,
            "銘柄名": listings.name_of(sym.replace(".T", "")),
            "株価": info.get("currentPrice") or info.get("regularMarketPrice"),
            "PER": info.get("trailingPE"),
            "PBR": info.get("priceToBook"),
            "配当利回り(%)": dividend_yield_pct(info),
            "時価総額": info.get("marketCap"),
            "ROE(%)": (info.get("returnOnEquity") or 0) * 100 if info.get("returnOnEquity") else None,
        })
    comp = pd.DataFrame(rows).set_index("銘柄")
    st.dataframe(
        comp.style.format({
            "株価": "{:,.2f}", "PER": "{:.2f}", "PBR": "{:.2f}",
            "配当利回り(%)": "{:.2f}", "時価総額": "{:,.0f}", "ROE(%)": "{:.2f}",
        }, na_rep="-"),
        use_container_width=True,
    )
    st.caption("指標はyfinance由来で、取得できない項目は「-」と表示されます。")
