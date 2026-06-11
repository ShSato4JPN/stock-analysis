"""株式ポートフォリオ管理アプリ(Streamlit)。

サイドバーで6つの機能を切り替える。
データはyfinance(非公式・遅延あり)から取得する。
"""
import streamlit as st

from utils.ui import render_sidebar_memo
from features import (
    backtest,
    buysignal,
    chart,
    compare,
    dividend,
    forecast,
    news,
    portfolio,
    risk,
    screening,
    similar,
    watchlist,
)

st.set_page_config(page_title="株式ポートフォリオ管理", page_icon="📈", layout="wide")

PAGES = {
    "📊 ポートフォリオ管理": portfolio.render,
    "🕯 株価チャート": chart.render,
    "🔍 スクリーニング": screening.render,
    "💰 配当金シミュレーター": dividend.render,
    "⭐ アラート・ウォッチリスト": watchlist.render,
    "🔁 バックテスト": backtest.render,
    "🔮 株価予測": forecast.render,
    "📰 ニュース・決算": news.render,
    "📊 銘柄比較": compare.render,
    "⚖️ リスク指標": risk.render,
    "🔗 類似銘柄検索": similar.render,
    "💡 買い時チェック": buysignal.render,
}


def main():
    st.sidebar.title("📈 株式ポートフォリオ管理")
    st.sidebar.caption("日本株は数字コード(例: 7203)、米国株はティッカー(例: AAPL)")
    choice = st.sidebar.radio("機能を選択", list(PAGES.keys()))
    st.sidebar.divider()
    st.sidebar.warning("⚠️ 株価データはyfinance由来で15〜20分程度の遅延があります。投資判断は自己責任で。")
    render_sidebar_memo()  # 画面左下: 注目企業の一時メモ

    PAGES[choice]()


if __name__ == "__main__":
    main()
