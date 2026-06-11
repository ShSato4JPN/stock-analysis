"""機能1: ポートフォリオ管理。"""
import pandas as pd
import plotly.express as px
import streamlit as st

from utils import listings, storage
from utils.data_fetch import get_dividends, get_price, normalize_symbol
from utils.ui import symbol_picker

_STORE = "portfolio"


def _load():
    return storage.load(_STORE, [])


def _save(items):
    storage.save(_STORE, items)


def _annual_dividend(symbol: str) -> float:
    """直近1年間に支払われた1株あたり配当の合計(見積)。取得失敗時は0。"""
    div = get_dividends(symbol)
    if div.empty:
        return 0.0
    cutoff = pd.Timestamp.now(tz=div.index.tz) - pd.Timedelta(days=365)
    recent = div[div.index >= cutoff]
    return float(recent.sum())


def render():
    st.header("📊 ポートフォリオ管理")
    st.caption("保有銘柄を登録すると、現在株価から評価額・損益を自動計算します。")

    items = _load()

    # 登録フォーム
    with st.expander("➕ 銘柄を登録", expanded=not items):
        symbol = symbol_picker(key="pf_add")
        c1, c2 = st.columns(2)
        shares = c1.number_input("株数", min_value=0.0, step=1.0)
        cost = c2.number_input("取得単価", min_value=0.0, step=1.0)
        if st.button("登録") and symbol and shares > 0:
            items.append({"symbol": normalize_symbol(symbol), "shares": shares, "cost": cost})
            _save(items)
            st.success(f"{symbol} を登録しました")
            st.rerun()

    if not items:
        st.info("まだ銘柄が登録されていません。")
        return

    # 評価計算
    rows = []
    with st.spinner("株価・配当データを取得中..."):
        for it in items:
            name = listings.name_of(it["symbol"].replace(".T", ""))
            price = get_price(it["symbol"])
            annual_div = _annual_dividend(it["symbol"]) * it["shares"]  # 年間配当金(見積)
            if price is None:
                rows.append({**it, "name": name, "price": None, "value": None,
                             "pl": None, "pl_pct": None, "div": annual_div})
                continue
            value = price * it["shares"]
            invested = it["cost"] * it["shares"]
            pl = value - invested
            pl_pct = (pl / invested * 100) if invested else 0.0
            rows.append({**it, "name": name, "price": price, "value": value,
                         "pl": pl, "pl_pct": pl_pct, "div": annual_div})

    df = pd.DataFrame(rows)
    valid = df.dropna(subset=["value"])

    # サマリー
    total_value = valid["value"].sum()
    total_invested = (valid["cost"] * valid["shares"]).sum()
    total_pl = total_value - total_invested
    total_pct = (total_pl / total_invested * 100) if total_invested else 0.0
    total_div = valid["div"].sum()  # 年間配当金(見積)
    # トータルリターン = 評価損益 + 年間配当(配当込みリターン)
    total_return = total_pl + total_div
    total_return_pct = (total_return / total_invested * 100) if total_invested else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("合計評価額", f"{total_value:,.0f}")
    c2.metric("合計損益(値上がり)", f"{total_pl:,.0f}", f"{total_pct:+.2f}%")
    c3.metric("トータルリターン", f"{total_return:,.0f}", f"{total_return_pct:+.2f}%",
              help="評価損益 + 年間配当金(見積)の合計")
    c4.metric("年間配当金(見積)", f"{total_div:,.0f}")
    st.caption(f"📌 銘柄数: {len(items)} ／ トータルリターンは値上がり益に直近1年の配当見積を加えた金額です。")

    # 一覧(色分け)
    disp = df.rename(columns={
        "symbol": "銘柄", "name": "銘柄名", "shares": "株数", "cost": "取得単価",
        "price": "現在値", "value": "評価額", "pl": "損益", "pl_pct": "損益率(%)",
        "div": "年間配当",
    })[["銘柄", "銘柄名", "株数", "取得単価", "現在値", "評価額", "損益", "損益率(%)", "年間配当"]]

    def color_pl(v):
        if pd.isna(v):
            return ""
        return "color: #e74c3c" if v < 0 else "color: #2ecc71"

    st.dataframe(
        disp.style.map(color_pl, subset=["損益", "損益率(%)"]).format({
            "取得単価": "{:,.2f}", "現在値": "{:,.2f}", "評価額": "{:,.0f}",
            "損益": "{:,.0f}", "損益率(%)": "{:+.2f}", "年間配当": "{:,.0f}",
        }, na_rep="取得失敗"),
        use_container_width=True,
    )

    # 資産配分円グラフ(銘柄名があれば表示に使う)
    if not valid.empty:
        pie_df = valid.assign(
            label=valid.apply(lambda r: r["name"] or r["symbol"], axis=1))
        fig = px.pie(pie_df, names="label", values="value", title="資産配分")
        st.plotly_chart(fig, use_container_width=True)

    # 編集/削除
    with st.expander("✏️ 編集・削除"):
        labels = [f"{i}: {it['symbol']} ({it['shares']}株)" for i, it in enumerate(items)]
        idx = st.selectbox("対象", range(len(items)), format_func=lambda i: labels[i])
        c1, c2, c3 = st.columns(3)
        new_shares = c1.number_input("株数", value=float(items[idx]["shares"]), key="e_sh")
        new_cost = c2.number_input("取得単価", value=float(items[idx]["cost"]), key="e_co")
        if c3.button("更新"):
            items[idx]["shares"] = new_shares
            items[idx]["cost"] = new_cost
            _save(items)
            st.rerun()
        if st.button("🗑 削除", type="primary"):
            items.pop(idx)
            _save(items)
            st.rerun()
