"""機能5: アラート・ウォッチリスト。"""
import pandas as pd
import streamlit as st

from utils import listings, storage
from utils.data_fetch import get_price, normalize_symbol
from utils.ui import symbol_picker

_STORE = "watchlist"


def render():
    st.header("⭐ アラート・ウォッチリスト")
    st.caption("目標株価(上限/下限)を設定し、実行時に条件到達した銘柄をハイライトします。"
               "リアルタイム通知ではありません。")

    items = storage.load(_STORE, [])

    with st.expander("➕ 銘柄を登録", expanded=not items):
        symbol = symbol_picker(key="wl_add")
        c1, c2 = st.columns(2)
        upper = c1.number_input("上限目標(以上で通知)", min_value=0.0, value=0.0)
        lower = c2.number_input("下限目標(以下で通知)", min_value=0.0, value=0.0)
        if st.button("登録") and symbol:
            items.append({"symbol": normalize_symbol(symbol), "upper": upper, "lower": lower})
            storage.save(_STORE, items)
            st.rerun()

    if not items:
        st.info("まだ銘柄が登録されていません。")
        return

    rows = []
    with st.spinner("現在株価を取得中..."):
        prices = {it["symbol"]: get_price(it["symbol"]) for it in items}
    for it in items:
        price = prices[it["symbol"]]
        hit = ""
        if price is not None:
            if it["upper"] > 0 and price >= it["upper"]:
                hit = "🔼 上限到達"
            elif it["lower"] > 0 and price <= it["lower"]:
                hit = "🔽 下限到達"
        rows.append({
            "銘柄": it["symbol"], "銘柄名": listings.name_of(it["symbol"].replace(".T", "")),
            "現在値": price,
            "上限": it["upper"] or None, "下限": it["lower"] or None, "状態": hit,
        })

    df = pd.DataFrame(rows)

    def highlight(row):
        # 半透明色: ライト/ダークどちらのテーマでも視認できる
        return ["background-color: rgba(255, 99, 71, 0.25)" if row["状態"] else "" for _ in row]

    st.dataframe(
        df.style.apply(highlight, axis=1).format(
            {"現在値": "{:,.2f}", "上限": "{:,.2f}", "下限": "{:,.2f}"}, na_rep="-"),
        use_container_width=True,
    )

    hits = df[df["状態"] != ""]
    if not hits.empty:
        st.success(f"🔔 条件到達: {', '.join(hits['銘柄'])}")

    with st.expander("🗑 削除"):
        idx = st.selectbox("対象", range(len(items)),
                           format_func=lambda i: items[i]["symbol"])
        if st.button("削除"):
            items.pop(idx)
            storage.save(_STORE, items)
            st.rerun()
