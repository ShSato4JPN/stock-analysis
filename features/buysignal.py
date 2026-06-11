"""機能12: 買い時チェック。

テクニカル指標とファンダメンタル指標を機械的に判定し、
「買い寄り / 中立 / 注意」のシグナル一覧と総合判定を表示する。
教科書的な目安に基づくチェックであり、売買の推奨ではない。
"""
import pandas as pd
import streamlit as st

from utils.data_fetch import dividend_yield_pct, get_history, get_info
from utils.indicators import bollinger, macd, rsi, sma
from utils.ui import symbol_picker

BUY, NEUTRAL, CAUTION = "buy", "neutral", "caution"
_MARK = {BUY: "✅ 買い寄り", NEUTRAL: "➖ 中立", CAUTION: "⚠️ 注意"}


def _technical_checks(close: pd.Series) -> list[tuple]:
    """テクニカル指標のチェック一覧 (名前, 現在値, 判定, 解説) を返す。"""
    checks = []
    price = float(close.iloc[-1])

    # RSI(14)
    r = float(rsi(close).iloc[-1])
    verdict = BUY if r <= 30 else CAUTION if r >= 70 else NEUTRAL
    checks.append(("RSI(14)", f"{r:.1f}", verdict,
                   "30以下=売られすぎ(買い目線) / 70以上=買われすぎ"))

    # 移動平均トレンド(25日 vs 75日)
    s25, s75 = sma(close, 25), sma(close, 75)
    if not pd.isna(s75.iloc[-1]):
        golden = s25.iloc[-1] > s75.iloc[-1]
        above = price > s25.iloc[-1]
        if golden and above:
            v, note = BUY, "短期>長期かつ株価>25日線で上昇トレンド"
        elif not golden and not above:
            v, note = CAUTION, "短期<長期かつ株価<25日線で下降トレンド"
        else:
            v, note = NEUTRAL, "トレンド転換の可能性がある中間状態"
        checks.append(("移動平均(25/75日)",
                       "ゴールデンクロス中" if golden else "デッドクロス中", v, note))

    # 25日移動平均乖離率
    if not pd.isna(s25.iloc[-1]):
        dev = (price / float(s25.iloc[-1]) - 1) * 100
        verdict = BUY if dev <= -10 else CAUTION if dev >= 10 else NEUTRAL
        checks.append(("25日線乖離率", f"{dev:+.1f}%", verdict,
                       "-10%以下=売られすぎ / +10%以上=過熱の目安"))

    # ボリンジャーバンド位置
    _, upper, lower = bollinger(close)
    if not pd.isna(lower.iloc[-1]):
        if price <= lower.iloc[-1]:
            v, pos = BUY, "-2σ以下"
        elif price >= upper.iloc[-1]:
            v, pos = CAUTION, "+2σ以上"
        else:
            v, pos = NEUTRAL, "バンド内"
        checks.append(("ボリンジャーバンド(20日)", pos, v,
                       "-2σ以下=統計的に売られすぎ / +2σ以上=過熱"))

    # MACD
    macd_line, signal_line, hist = macd(close)
    h_now, h_prev = float(hist.iloc[-1]), float(hist.iloc[-2])
    if h_now > 0 and h_prev <= 0:
        v, s = BUY, "ゴールデンクロス直後"
    elif h_now > 0:
        v, s = NEUTRAL, "シグナル線より上(上昇基調)"
    elif h_now < 0 and h_prev >= 0:
        v, s = CAUTION, "デッドクロス直後"
    else:
        v, s = NEUTRAL, "シグナル線より下(下降基調)"
    checks.append(("MACD(12,26,9)", s, v, "シグナル線の上抜けは買いの教科書的サイン"))

    # 52週高値・安値からの位置
    high52, low52 = float(close.max()), float(close.min())
    pos_pct = (price - low52) / (high52 - low52) * 100 if high52 > low52 else 50
    verdict = BUY if pos_pct <= 25 else CAUTION if pos_pct >= 90 else NEUTRAL
    checks.append(("52週レンジ位置", f"{pos_pct:.0f}%(安値0〜高値100)", verdict,
                   "安値圏は割安の可能性(下落継続リスクもあり) / 高値圏は高値掴みに注意"))

    return checks


def _fundamental_checks(info: dict) -> list[tuple]:
    """ファンダメンタル指標のチェック一覧を返す。"""
    checks = []
    per = info.get("trailingPE")
    if per is not None:
        verdict = BUY if per <= 15 else CAUTION if per >= 30 else NEUTRAL
        checks.append(("PER", f"{per:.1f}倍", verdict, "15倍以下=割安の目安 / 30倍以上=割高の目安"))
    pbr = info.get("priceToBook")
    if pbr is not None:
        verdict = BUY if pbr <= 1.0 else CAUTION if pbr >= 3.0 else NEUTRAL
        checks.append(("PBR", f"{pbr:.2f}倍", verdict, "1倍以下=解散価値割れ(割安) / 3倍以上=割高の目安"))
    dy = dividend_yield_pct(info)
    if dy is not None:
        verdict = BUY if dy >= 3.0 else NEUTRAL
        checks.append(("配当利回り", f"{dy:.2f}%", verdict, "3%以上=高配当の目安(下支え効果)"))
    return checks


def render():
    st.header("💡 買い時チェック")
    st.caption("テクニカル・ファンダメンタルの定番指標を機械的に判定し、現在の状態を採点します。"
               "教科書的な目安によるチェックであり、売買の推奨ではありません。")

    symbol = symbol_picker(key="buy", default_code="7203")
    if not symbol or not st.button("チェック実行"):
        return

    with st.spinner("データを取得・分析中..."):
        df = get_history(symbol, period="1y")
        if df.empty or len(df) < 80:
            st.error("分析に十分な過去データを取得できませんでした。")
            return
        close = df["Close"].dropna()
        info = get_info(symbol)
        checks = _technical_checks(close) + _fundamental_checks(info)

    # --- 総合判定 ---
    n_buy = sum(1 for c in checks if c[2] == BUY)
    n_caution = sum(1 for c in checks if c[2] == CAUTION)
    score = n_buy - n_caution

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("現在値", f"{float(close.iloc[-1]):,.2f}")
    c2.metric("買い寄りシグナル", f"{n_buy} / {len(checks)}")
    c3.metric("注意シグナル", f"{n_caution} / {len(checks)}")
    c4.metric("スコア", f"{score:+d}")

    if score >= 3:
        st.success("🟢 **買いシグナル優勢** — 複数の指標が買い目線を示しています。")
    elif score >= 1:
        st.info("🟡 **やや買い寄り** — 一部の指標が買い目線ですが決め手は弱めです。")
    elif score <= -3:
        st.error("🔴 **注意シグナル優勢** — 過熱・下落トレンドの指標が多く、様子見が無難です。")
    elif score <= -1:
        st.warning("🟠 **やや注意寄り** — 慎重に判断したい状態です。")
    else:
        st.info("⚪ **中立** — 明確なシグナルは出ていません。")

    # --- チェック一覧 ---
    table = pd.DataFrame(
        [(name, value, _MARK[v], note) for name, value, v, note in checks],
        columns=["指標", "現在の状態", "判定", "目安"],
    )

    def color_verdict(v):
        if "買い寄り" in v:
            return "color: #2ecc71"
        if "注意" in v:
            return "color: #e74c3c"
        return ""

    st.dataframe(table.style.map(color_verdict, subset=["判定"]),
                 use_container_width=True, hide_index=True)

    st.info("⚠️ 各判定は一般的な経験則の目安です。決算・地合い・材料は反映されません。"
            "複数の機能(チャート/ニュース/リスク指標)と合わせてご判断ください。")
