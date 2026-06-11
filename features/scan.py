"""機能13: 一括スキャン(買い時/売り時の企業一覧)。

買い時チェックと同じ判定ロジックを多数の銘柄へ並列適用し、
スコア順に「買い時候補」「売り時候補」を一覧表示する。

高速化:
  - 株価履歴は yf.download のバッチ取得(スレッド並列)で一括ダウンロード
  - ファンダ情報(PER/PBR/配当)は ThreadPoolExecutor で並列取得
"""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st
import yfinance as yf

from features.buysignal import BUY, CAUTION, _fundamental_checks, _technical_checks
from utils import listings

_INFO_WORKERS = 16  # info並列取得のスレッド数


@st.cache_data(ttl=600, show_spinner=False)
def _bulk_history(symbols: tuple) -> dict:
    """複数銘柄の1年分終値をバッチ取得する。{symbol: Close Series}"""
    try:
        data = yf.download(
            list(symbols), period="1y", interval="1d",
            group_by="ticker", threads=True, progress=False, auto_adjust=True,
        )
    except Exception:
        return {}
    result = {}
    if data is None or data.empty:
        return result
    for sym in symbols:
        try:
            close = data[sym]["Close"].dropna()
            if len(close) >= 80:
                result[sym] = close
        except (KeyError, TypeError):
            continue
    return result


@st.cache_data(ttl=900, show_spinner=False)
def _bulk_info(symbols: tuple) -> dict:
    """複数銘柄のinfoを並列取得する。{symbol: info dict}"""
    def fetch(sym):
        try:
            return sym, yf.Ticker(sym).info or {}
        except Exception:
            return sym, {}

    with ThreadPoolExecutor(max_workers=_INFO_WORKERS) as ex:
        return dict(ex.map(fetch, symbols))


def render():
    st.header("🚀 一括スキャン(買い時・売り時の一覧)")
    st.caption("買い時チェックと同じ判定を多数の銘柄に並列適用し、スコア順に候補を一覧表示します。"
               "売買の推奨ではありません。")

    # --- 対象範囲の選択 ---
    df = listings.load_listings()
    if df.empty:
        st.error("上場企業一覧が見つかりません。")
        return

    c1, c2, c3 = st.columns(3)
    market = c1.selectbox("市場・商品区分", listings.markets(),
                          index=listings.markets().index("プライム（内国株式）")
                          if "プライム（内国株式）" in listings.markets() else 0)
    scales = ["すべて"] + sorted(df["規模区分"].dropna().unique().tolist())
    scale = c2.selectbox("規模区分", scales,
                         help="TOPIX Core30=超大型 〜 Small=小型")
    limit = c3.slider("スキャン銘柄数(上限)", 20, 500, 100, step=20,
                      help="多いほど時間がかかります(目安: 100銘柄で10秒前後)")
    use_fund = st.checkbox("ファンダメンタル指標(PER/PBR/配当)も加点に含める", value=True,
                           help="外すとテクニカルのみで高速になります")

    target = df[df["市場・商品区分"] == market]
    if scale != "すべて":
        target = target[target["規模区分"] == scale]
    codes = target["コード"].head(limit).tolist()
    st.markdown(f"**対象: {len(codes)}銘柄**(該当{len(target)}銘柄のうち先頭{limit}件まで)")

    if not st.button("🚀 スキャン実行", type="primary"):
        return

    symbols = tuple(f"{c}.T" for c in codes)

    # --- 並列取得 ---
    with st.spinner(f"{len(symbols)}銘柄の株価を一括取得中..."):
        closes = _bulk_history(symbols)
    infos = {}
    if use_fund:
        with st.spinner(f"ファンダ情報を{_INFO_WORKERS}並列で取得中..."):
            infos = _bulk_info(tuple(closes.keys()))

    if not closes:
        st.error("株価データを取得できませんでした。")
        return

    # --- スコアリング ---
    rows = []
    progress = st.progress(0.0, text="判定中...")
    for i, (sym, close) in enumerate(closes.items()):
        try:
            checks = _technical_checks(close)
            if use_fund:
                checks += _fundamental_checks(infos.get(sym, {}))
        except Exception:
            continue
        n_buy = sum(1 for c in checks if c[2] == BUY)
        n_caution = sum(1 for c in checks if c[2] == CAUTION)
        code = sym.replace(".T", "")
        rows.append({
            "コード": code,
            "銘柄名": listings.name_of(code),
            "現在値": float(close.iloc[-1]),
            "スコア": n_buy - n_caution,
            "買い寄り": n_buy,
            "注意": n_caution,
            "買い材料": ", ".join(c[0] for c in checks if c[2] == BUY) or "-",
            "注意材料": ", ".join(c[0] for c in checks if c[2] == CAUTION) or "-",
        })
        progress.progress((i + 1) / len(closes), text=f"判定中... {i + 1}/{len(closes)}")
    progress.empty()

    result = pd.DataFrame(rows)
    if result.empty:
        st.warning("判定できる銘柄がありませんでした。")
        return

    buy_df = result[result["スコア"] >= 2].sort_values("スコア", ascending=False)
    sell_df = result[result["スコア"] <= -2].sort_values("スコア")

    c1, c2, c3 = st.columns(3)
    c1.metric("スキャン完了", f"{len(result)}銘柄")
    c2.metric("🟢 買い時候補", f"{len(buy_df)}銘柄")
    c3.metric("🔴 売り時候補", f"{len(sell_df)}銘柄")

    fmt = {"現在値": "{:,.1f}", "スコア": "{:+d}"}
    tab_buy, tab_sell, tab_all = st.tabs(["🟢 買い時候補", "🔴 売り時候補", "📋 全銘柄"])
    with tab_buy:
        if buy_df.empty:
            st.info("スコア+2以上の銘柄はありませんでした。")
        else:
            st.dataframe(buy_df.drop(columns=["注意材料"]).style.format(fmt),
                         use_container_width=True, hide_index=True)
    with tab_sell:
        if sell_df.empty:
            st.info("スコア-2以下の銘柄はありませんでした。")
        else:
            st.dataframe(sell_df.drop(columns=["買い材料"]).style.format(fmt),
                         use_container_width=True, hide_index=True)
    with tab_all:
        st.dataframe(result.sort_values("スコア", ascending=False).style.format(fmt),
                     use_container_width=True, hide_index=True)

    st.info("⚠️ 教科書的な目安による機械判定です。気になる銘柄は「💡 買い時チェック」で個別に確認し、"
            "ニュース・決算も合わせてご判断ください。")
