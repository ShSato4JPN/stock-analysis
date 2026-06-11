"""機能3: スクリーニング。

yfinanceは一括スクリーニング非対応のため、対象銘柄リストを回して
指標を取得し、条件でフィルタする方式。
"""
import pandas as pd
import streamlit as st

from utils import listings
from utils.data_fetch import dividend_yield_pct, get_info, normalize_symbol

# サンプル: 日経225の一部 + 米国主要銘柄
_DEFAULT = "7203, 9984, 8306, 6758, 9432, AAPL, MSFT, KO, JNJ, VZ"


def render():
    st.header("🔍 スクリーニング")
    st.caption("対象銘柄リストに対しPER/PBR/配当利回り/時価総額を取得し、条件で絞り込みます。"
               "銘柄数が多いと取得に時間がかかります。")

    st.session_state.setdefault("scr_symbols", _DEFAULT)

    # 市場区分から対象銘柄を取り込む(任意)
    mkts = listings.markets()
    if mkts:
        with st.expander("📥 市場区分から対象銘柄を取り込む"):
            c1, c2 = st.columns([2, 1])
            mkt = c1.selectbox("市場・商品区分", mkts, key="scr_mkt")
            limit = c2.number_input("最大件数", min_value=1, max_value=200, value=30,
                                    help="取得に時間がかかるため上限を設定")
            if st.button("この市場の銘柄を反映"):
                codes = listings.search("", mkt)["コード"].head(int(limit)).tolist()
                st.session_state["scr_symbols"] = ", ".join(codes)
                st.rerun()

    symbols_raw = st.text_area("対象銘柄(カンマ区切り。コード or ティッカー)",
                               key="scr_symbols")
    symbols = [normalize_symbol(s) for s in symbols_raw.split(",") if s.strip()]

    st.markdown("**絞り込み条件**(空欄は無効)")
    c1, c2, c3 = st.columns(3)
    per_max = c1.number_input("PER上限", min_value=0.0, value=0.0)
    pbr_max = c2.number_input("PBR上限", min_value=0.0, value=0.0)
    div_min = c3.number_input("配当利回り下限(%)", min_value=0.0, value=0.0)

    if not st.button("スクリーニング実行"):
        return

    rows = []
    progress = st.progress(0.0)
    for i, sym in enumerate(symbols):
        info = get_info(sym)
        rows.append({
            "銘柄": sym,
            "PER": info.get("trailingPE"),
            "PBR": info.get("priceToBook"),
            "配当利回り(%)": dividend_yield_pct(info),
            "時価総額": info.get("marketCap"),
        })
        progress.progress((i + 1) / len(symbols))
    progress.empty()

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("データを取得できませんでした。")
        return

    # フィルタ
    if per_max > 0:
        df = df[df["PER"].notna() & (df["PER"] <= per_max)]
    if pbr_max > 0:
        df = df[df["PBR"].notna() & (df["PBR"] <= pbr_max)]
    if div_min > 0:
        df = df[df["配当利回り(%)"].notna() & (df["配当利回り(%)"] >= div_min)]

    if df.empty:
        st.info("条件に合致する銘柄はありませんでした。")
        return

    st.dataframe(
        df.style.format({
            "PER": "{:.2f}", "PBR": "{:.2f}", "配当利回り(%)": "{:.2f}",
            "時価総額": "{:,.0f}",
        }, na_rep="-"),
        use_container_width=True,
    )
    st.caption("列ヘッダーをクリックするとソートできます。")
