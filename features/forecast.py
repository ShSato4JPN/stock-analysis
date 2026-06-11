"""機能7: 株価予測(複数の統計モデルを選択可能)。

過去の値動きから将来価格を確率的にシミュレーションする。
モデルによって前提(正規性・トレンド・平均回帰)が異なるため、
selectboxで切り替えて比較できる。いずれも過去の統計に基づく
確率的見通しであり、将来を保証するものではない。

実装モデル:
  - GBM(幾何ブラウン運動): リターンが正規分布に従うと仮定
  - ヒストリカル・ブートストラップ: 過去の実リターンを復元抽出(正規性を仮定しない)
  - 線形トレンド回帰: 対数価格の最小二乗回帰 + 残差による予測区間
  - 平均回帰(Ornstein-Uhlenbeck): 長期平均へ回帰する性質をモデル化
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_fetch import get_history
from utils.ui import symbol_picker

_PERIODS = {"1年": "1y", "2年": "2y", "5年": "5y"}
_TRADING_DAYS = 252  # 年間営業日数
_HORIZONS = {"1ヶ月": 21, "3ヶ月": 63, "6ヶ月": 126, "1年": 252}

_MODELS = {
    "GBM(幾何ブラウン運動)": "gbm",
    "ヒストリカル・ブートストラップ": "bootstrap",
    "線形トレンド回帰": "trend",
    "平均回帰(Ornstein-Uhlenbeck)": "ou",
}

_MODEL_DESC = {
    "gbm": "リターンが独立同分布の正規分布に従うと仮定する最も標準的なモデル"
           "(Black-Scholesの基礎)。トレンド転換や急変は表現できません。",
    "bootstrap": "過去に実際に起きた日次リターンをランダムに復元抽出して将来を生成。"
                 "正規分布を仮定しないため、過去の偏り(ファットテール等)を反映します。",
    "trend": "対数価格を時間の一次関数とみなして最小二乗回帰し、残差のばらつきで"
             "予測区間を作ります。一定方向のトレンドが続く前提です。",
    "ou": "価格が長期平均に引き戻される『平均回帰』を仮定するモデル。"
          "レンジ相場や行き過ぎの修正を想定する場合に向きます。",
}


# --- 各モデル: (n_sims, horizon+1) の価格パス配列を返す ---

def _gbm(close, s0, horizon, n_sims, rng):
    log_ret = np.log(close / close.shift(1)).dropna()
    mu_d, sigma_d = float(log_ret.mean()), float(log_ret.std())
    shocks = rng.normal(mu_d - 0.5 * sigma_d ** 2, sigma_d, size=(n_sims, horizon))
    paths = s0 * np.exp(np.cumsum(shocks, axis=1))
    params = {"年率μ": mu_d * _TRADING_DAYS, "年率σ": sigma_d * np.sqrt(_TRADING_DAYS)}
    return _prepend(paths, s0), params


def _bootstrap(close, s0, horizon, n_sims, rng):
    log_ret = np.log(close / close.shift(1)).dropna().values
    sampled = rng.choice(log_ret, size=(n_sims, horizon), replace=True)
    paths = s0 * np.exp(np.cumsum(sampled, axis=1))
    params = {"年率μ(実績平均)": log_ret.mean() * _TRADING_DAYS,
              "年率σ(実績)": log_ret.std() * np.sqrt(_TRADING_DAYS)}
    return _prepend(paths, s0), params


def _trend(close, s0, horizon, n_sims, rng):
    y = np.log(close.values)
    t = np.arange(len(y))
    b, a = np.polyfit(t, y, 1)            # y ≈ a + b*t
    resid_std = float(np.std(y - (a + b * t)))
    # 現在値を起点にトレンドの傾きで外挿する(回帰線の水準にジャンプさせない)
    steps = np.arange(1, horizon + 1)
    mean_future = np.log(s0) + b * steps
    noise = rng.normal(0, resid_std, size=(n_sims, horizon))
    paths = np.exp(mean_future + noise)
    params = {"年率トレンド": b * _TRADING_DAYS, "残差σ": resid_std}
    return _prepend(paths, s0), params


def _ou(close, s0, horizon, n_sims, rng):
    # 対数価格 x の平均回帰: dx = alpha*(theta - x) dt + sigma dW
    x = np.log(close.values)
    dx = np.diff(x)
    x_prev = x[:-1]
    # dx = beta0 + beta1*x_prev + noise を回帰 → alpha=-beta1, theta=beta0/alpha
    beta1, beta0 = np.polyfit(x_prev, dx, 1)
    alpha = -beta1
    # alpha<=0 は平均回帰が検出できない状態(発散を防ぐためランダムウォークに退化)
    if alpha <= 0:
        alpha = 0.0
        theta = float(x.mean())
    else:
        theta = beta0 / alpha
    sigma = float(np.std(dx - (beta0 + beta1 * x_prev)))
    paths = np.empty((n_sims, horizon))
    cur = np.full(n_sims, np.log(s0))
    for h in range(horizon):
        cur = cur + alpha * (theta - cur) + rng.normal(0, sigma, size=n_sims)
        paths[:, h] = np.exp(cur)
    params = {"回帰速度α": alpha, "長期平均(価格)": float(np.exp(theta)), "σ": sigma}
    return _prepend(paths, s0), params


def _prepend(paths, s0):
    """起点(現在値)を先頭に付与する。"""
    return np.hstack([np.full((paths.shape[0], 1), s0), paths])


_DISPATCH = {"gbm": _gbm, "bootstrap": _bootstrap, "trend": _trend, "ou": _ou}


def render():
    st.header("🔮 株価予測(統計モデル)")
    st.caption("過去の値動きから将来価格の確率分布を推定します。複数のモデルを切り替えて比較できます。"
               "いずれも確率的な見通しであり、将来を保証するものではありません。")

    symbol = symbol_picker(key="fc", default_code="7203")

    model_label = st.selectbox("予測モデル", list(_MODELS.keys()))
    model_key = _MODELS[model_label]
    st.info(f"📘 **{model_label}**: {_MODEL_DESC[model_key]}")

    c1, c2, c3 = st.columns(3)
    period_label = c1.selectbox("学習期間(過去データ)", list(_PERIODS.keys()), index=1)
    horizon_label = c2.selectbox("予測期間", list(_HORIZONS.keys()), index=1)
    n_sims = int(c3.number_input("シミュレーション回数", min_value=100, max_value=5000,
                                 value=1000, step=100))

    if not symbol or not st.button("予測を実行"):
        return

    df = get_history(symbol, period=_PERIODS[period_label])
    if df.empty or len(df) < 30:
        st.error("予測に十分な過去データを取得できませんでした。")
        return

    close = df["Close"].dropna()
    s0 = float(close.iloc[-1])
    horizon = _HORIZONS[horizon_label]
    rng = np.random.default_rng(42)

    paths, params = _DISPATCH[model_key](close, s0, horizon, n_sims, rng)

    # パーセンタイル(80%信頼区間)
    p10 = np.percentile(paths, 10, axis=0)
    p50 = np.percentile(paths, 50, axis=0)
    p90 = np.percentile(paths, 90, axis=0)

    final = paths[:, -1]
    exp_price = float(np.mean(final))
    prob_up = float(np.mean(final > s0)) * 100
    exp_return = (exp_price / s0 - 1) * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("現在値", f"{s0:,.2f}")
    c2.metric(f"予測期待値({horizon_label}後)", f"{exp_price:,.2f}", f"{exp_return:+.2f}%")
    c3.metric("上昇確率", f"{prob_up:.1f}%")
    c4.metric("予測レンジ(80%)", f"{p10[-1]:,.0f}〜{p90[-1]:,.0f}")

    with st.expander("📐 推定パラメータと前提"):
        for k, v in params.items():
            if "率" in k or "トレンド" in k or "α" in k:
                st.markdown(f"- **{k}**: {v * 100:+.2f}%" if abs(v) < 5 else f"- **{k}**: {v:,.4f}")
            else:
                st.markdown(f"- **{k}**: {v:,.4f}")
        st.markdown(f"- 学習データ: 過去 {len(close)} 営業日")
        st.caption(_MODEL_DESC[model_key])

    # 期間別予測テーブル(シミュレーション分位点)
    rows = []
    for label, h in _HORIZONS.items():
        if h > horizon:
            continue
        col = paths[:, h]
        rows.append({
            "予測期間": label,
            "中央値": np.percentile(col, 50),
            "下限(10%)": np.percentile(col, 10),
            "上限(90%)": np.percentile(col, 90),
            "上昇確率(%)": float(np.mean(col > s0)) * 100,
        })
    st.markdown("**期間別予測(80%信頼区間)**")
    st.dataframe(
        pd.DataFrame(rows).style.format({
            "中央値": "{:,.2f}", "下限(10%)": "{:,.2f}",
            "上限(90%)": "{:,.2f}", "上昇確率(%)": "{:.1f}",
        }),
        use_container_width=True,
    )

    # ファンチャート
    future_idx = list(range(horizon + 1))
    fig = go.Figure()
    hist = close.tail(120)
    hist_x = list(range(-len(hist) + 1, 1))
    fig.add_trace(go.Scatter(x=hist_x, y=hist.values, name="過去株価", line=dict(color="#888")))
    fig.add_trace(go.Scatter(x=future_idx, y=p90, line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=future_idx, y=p10, name="80%信頼区間", fill="tonexty",
                             fillcolor="rgba(31,119,180,0.2)", line=dict(width=0)))
    fig.add_trace(go.Scatter(x=future_idx, y=p50, name="予測中央値",
                             line=dict(color="#1f77b4", width=2)))
    fig.update_layout(
        height=550, title=f"{symbol} 予測ファンチャート({model_label} / 0=現在)",
        xaxis_title="営業日(0=現在)", yaxis_title="株価", legend=dict(orientation="h"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.info("⚠️ この予測は過去の統計に基づく確率的シミュレーションです。"
            "実際の株価は決算・経済情勢・地政学リスク等で大きく変動します。投資判断は自己責任で。")
