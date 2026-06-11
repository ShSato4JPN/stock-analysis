"""機能11: 類似銘柄検索。

上場企業一覧CSVの業種区分(33/17業種)・規模区分・市場区分を使って、
基準銘柄と似た銘柄を探す。さらに上位候補は yfinance から
時価総額・PER・PBR・配当利回りを取得して横並び比較できる。
"""
import pandas as pd
import streamlit as st

from utils import listings
from utils.data_fetch import get_info
from utils.ui import symbol_picker


def _candidates(base: dict, industry_level: str, match_scale: bool, match_market: bool) -> pd.DataFrame:
    """基準銘柄と同じ区分の銘柄を上場企業一覧から抽出する(基準銘柄は除く)。"""
    df = listings.load_listings()
    col = "33業種区分" if industry_level == "33業種(細かい)" else "17業種区分"
    df = df[df[col] == base[col]]
    if match_scale and base["規模区分"] != "-":
        df = df[df["規模区分"] == base["規模区分"]]
    if match_market:
        df = df[df["市場・商品区分"] == base["市場・商品区分"]]
    return df[df["コード"] != base["コード"]]


def render():
    st.header("🔗 類似銘柄検索")
    st.caption("基準銘柄と同じ業種・規模・市場の銘柄を探し、指標を横並び比較します。"
               "同業他社の比較や乗り換え候補探しに使えます。")

    symbol = symbol_picker("基準銘柄", key="sim", default_code="7203")
    if not symbol:
        return

    code = symbol.replace(".T", "")
    base = listings.row_of(code)
    if not base:
        st.error("上場企業一覧に見つかりませんでした(国内銘柄のみ対応です)。")
        return

    # 基準銘柄の属性
    st.markdown(
        f"**基準**: {base['コード']} {base['銘柄名']} ／ "
        f"33業種: {base['33業種区分']} ／ 17業種: {base['17業種区分']} ／ "
        f"規模: {base['規模区分']} ／ 市場: {base['市場・商品区分']}"
    )

    c1, c2, c3 = st.columns(3)
    industry_level = c1.radio("業種の粒度", ["33業種(細かい)", "17業種(広い)"], horizontal=False)
    match_scale = c2.checkbox("規模区分も一致", value=True,
                              help=f"基準銘柄の規模: {base['規模区分']}")
    match_market = c3.checkbox("市場区分も一致", value=True,
                               help=f"基準銘柄の市場: {base['市場・商品区分']}")

    result = _candidates(base, industry_level, match_scale, match_market)
    st.markdown(f"**該当: {len(result)}銘柄**")
    if result.empty:
        st.info("条件に合う銘柄がありません。条件を緩めてください。")
        return

    show = result[["コード", "銘柄名", "市場・商品区分", "33業種区分", "規模区分"]]
    st.dataframe(show, use_container_width=True, hide_index=True)

    # --- 指標比較(取得件数を制限) ---
    st.divider()
    st.markdown("**📊 指標で比較**(yfinanceから取得するため件数を制限)")
    n = st.slider("比較する銘柄数", min_value=3, max_value=30, value=10)
    if not st.button("指標を取得して比較"):
        return

    targets = [base["コード"]] + result["コード"].head(n).tolist()
    rows = []
    progress = st.progress(0.0)
    for i, c in enumerate(targets):
        info = get_info(c)
        dy = info.get("dividendYield")
        rows.append({
            "コード": c,
            "銘柄名": listings.name_of(c),
            "株価": info.get("currentPrice") or info.get("regularMarketPrice"),
            "時価総額": info.get("marketCap"),
            "PER": info.get("trailingPE"),
            "PBR": info.get("priceToBook"),
            "配当利回り(%)": dy * 100 if dy else None,
        })
        progress.progress((i + 1) / len(targets))
    progress.empty()

    comp = pd.DataFrame(rows)

    # 基準銘柄との時価総額の近さでソート(基準は先頭固定)
    base_cap = comp.iloc[0]["時価総額"]
    if pd.notna(base_cap):
        others = comp.iloc[1:].copy()
        others["_dist"] = (others["時価総額"] - base_cap).abs()
        others = others.sort_values("_dist", na_position="last").drop(columns="_dist")
        comp = pd.concat([comp.iloc[[0]], others])

    def mark_base(row):
        is_base = row["コード"] == base["コード"]
        return ["background-color: #1a3a5c" if is_base else "" for _ in row]

    st.dataframe(
        comp.style.apply(mark_base, axis=1).format({
            "株価": "{:,.2f}", "時価総額": "{:,.0f}", "PER": "{:.2f}",
            "PBR": "{:.2f}", "配当利回り(%)": "{:.2f}",
        }, na_rep="-"),
        use_container_width=True, hide_index=True,
    )
    st.caption("先頭(ハイライト)が基準銘柄。候補は時価総額が近い順に並びます。")
