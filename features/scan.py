"""機能13: 一括スキャン(買い時/売り時の企業一覧)。

買い時チェックと同じ判定ロジックを多数の銘柄へ並列適用し、
スコア順に「買い時候補」「売り時候補」を一覧表示する。
結果の行をクリックするとその銘柄の株価チャートへ遷移する。

高速化:
  - 株価履歴は yf.download のバッチ取得(スレッド並列)をチャンク分割で一括取得
  - ファンダ情報(PER/PBR/配当)は ThreadPoolExecutor で並列取得
"""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st
import yfinance as yf

from features.buysignal import BUY, CAUTION, _fundamental_checks, _technical_checks
from utils import listings
from utils.ui import goto_chart

_INFO_WORKERS = 16  # info並列取得のスレッド数
_CHUNK = 200        # バッチ取得のチャンクサイズ(チャンク単位でキャッシュが効く)


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


def _run_scan(codes: list, use_fund: bool) -> None:
    """スキャンを実行して結果をセッションに保存する。"""
    symbols = tuple(f"{c}.T" for c in codes)

    # --- 並列取得(チャンク分割でキャッシュと進捗を両立) ---
    chunks = [symbols[i:i + _CHUNK] for i in range(0, len(symbols), _CHUNK)]
    closes = {}
    prog = st.progress(0.0, text="株価を一括取得中...")
    for j, ch in enumerate(chunks):
        closes.update(_bulk_history(ch))
        done = min((j + 1) * _CHUNK, len(symbols))
        prog.progress((j + 1) / len(chunks), text=f"株価取得 {done}/{len(symbols)}銘柄")
    prog.empty()

    infos = {}
    if use_fund and closes:
        ok_syms = tuple(closes.keys())
        ichunks = [ok_syms[i:i + _CHUNK] for i in range(0, len(ok_syms), _CHUNK)]
        prog = st.progress(0.0, text="ファンダ情報を取得中...")
        for j, ch in enumerate(ichunks):
            infos.update(_bulk_info(ch))
            done = min((j + 1) * _CHUNK, len(ok_syms))
            prog.progress((j + 1) / len(ichunks),
                          text=f"ファンダ取得({_INFO_WORKERS}並列) {done}/{len(ok_syms)}銘柄")
        prog.empty()

    if not closes:
        st.error("株価データを取得できませんでした。")
        return

    # --- スコアリング ---
    rows = []
    prog = st.progress(0.0, text="判定中...")
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
        prog.progress((i + 1) / len(closes), text=f"判定中... {i + 1}/{len(closes)}")
    prog.empty()

    st.session_state["scan_state"] = {
        "result": pd.DataFrame(rows),
        "requested": len(symbols),
        "missing": [s.replace(".T", "") for s in symbols if s not in closes],
    }


def _selectable_table(df: pd.DataFrame, drop_col: str, key: str) -> None:
    """行クリックでチャートへ遷移するテーブルを表示する。"""
    nonce = st.session_state.get("scan_nonce", 0)
    fmt = {"現在値": "{:,.1f}", "スコア": "{:+d}"}
    shown = df.drop(columns=[drop_col]) if drop_col else df
    event = st.dataframe(
        shown.style.format(fmt), use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row", key=f"{key}_{nonce}",
    )
    if event.selection.rows:
        code = df.iloc[event.selection.rows[0]]["コード"]
        # nonceを変えて選択状態をリセットし、戻ってきたとき再遷移しないようにする
        st.session_state["scan_nonce"] = nonce + 1
        goto_chart(code)


def render():
    st.header("🚀 一括スキャン(買い時・売り時の一覧)")
    st.caption("買い時チェックと同じ判定を多数の銘柄に並列適用し、スコア順に候補を一覧表示します。"
               "売買の推奨ではありません。")

    # --- 対象範囲の選択 ---
    df = listings.load_listings()
    if df.empty:
        st.error("上場企業一覧が見つかりません。")
        return

    c1, c2 = st.columns(2)
    market = c1.selectbox("市場・商品区分", listings.markets(),
                          index=listings.markets().index("プライム（内国株式）")
                          if "プライム（内国株式）" in listings.markets() else 0)
    scales = ["すべて"] + sorted(df["規模区分"].dropna().unique().tolist())
    scale = c2.selectbox("規模区分", scales,
                         help="TOPIX Core30=超大型 〜 Small=小型")

    target = df[df["市場・商品区分"] == market]
    if scale != "すべて":
        target = target[target["規模区分"] == scale]
    total = len(target)

    scan_all = st.checkbox(f"✅ 全銘柄をスキャンする(該当 {total}銘柄)", value=False,
                           help="目安: 200銘柄で約10秒、1500銘柄で1〜2分")
    if scan_all:
        codes = target["コード"].tolist()
    else:
        limit = st.slider("スキャン銘柄数(上限)", 20, max(total, 20),
                          min(100, total), step=20)
        codes = target["コード"].head(limit).tolist()
    use_fund = st.checkbox("ファンダメンタル指標(PER/PBR/配当)も加点に含める", value=True,
                           help="外すとテクニカルのみで高速になります")
    st.markdown(f"**対象: {len(codes)} / {total}銘柄**")

    if st.button("🚀 スキャン実行", type="primary"):
        _run_scan(codes, use_fund)

    # --- 結果表示(セッション保持: 行クリックの再実行でも消えない) ---
    state = st.session_state.get("scan_state")
    if not state:
        return
    result, requested, missing = state["result"], state["requested"], state["missing"]
    if result.empty:
        st.warning("判定できる銘柄がありませんでした。")
        return

    if missing:
        with st.expander(f"⚠️ 取得失敗・データ不足で除外: {len(missing)}銘柄(クリックで一覧)"):
            st.caption("上場直後(履歴80日未満)やyfinance未対応の銘柄が該当します。")
            st.write(", ".join(f"{c} {listings.name_of(c)}" for c in missing[:150])
                     + (" …" if len(missing) > 150 else ""))

    buy_df = result[result["スコア"] >= 2].sort_values("スコア", ascending=False)
    sell_df = result[result["スコア"] <= -2].sort_values("スコア")

    c1, c2, c3 = st.columns(3)
    c1.metric("スキャン完了", f"{len(result)} / {requested}銘柄")
    c2.metric("🟢 買い時候補", f"{len(buy_df)}銘柄")
    c3.metric("🔴 売り時候補", f"{len(sell_df)}銘柄")
    st.caption("💡 行をクリックすると、その銘柄の株価チャートへ移動します。")

    tab_buy, tab_sell, tab_all = st.tabs(["🟢 買い時候補", "🔴 売り時候補", "📋 全銘柄"])
    with tab_buy:
        if buy_df.empty:
            st.info("スコア+2以上の銘柄はありませんでした。")
        else:
            _selectable_table(buy_df, "注意材料", "scan_buy")
    with tab_sell:
        if sell_df.empty:
            st.info("スコア-2以下の銘柄はありませんでした。")
        else:
            _selectable_table(sell_df, "買い材料", "scan_sell")
    with tab_all:
        _selectable_table(result.sort_values("スコア", ascending=False), "", "scan_all")

    st.info("⚠️ 教科書的な目安による機械判定です。気になる銘柄は「💡 買い時チェック」で個別に確認し、"
            "ニュース・決算も合わせてご判断ください。")
