"""機能8: 関連ニュース・決算カレンダー。"""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from utils.data_fetch import get_earnings_dates, get_news
from utils.ui import symbol_picker


def _fmt_news_item(item: dict) -> dict | None:
    """yfinanceのニュース要素を表示用に整形する。形式差異を吸収。"""
    content = item.get("content", item)  # 新形式はcontent配下
    title = content.get("title") or item.get("title")
    if not title:
        return None
    # リンク
    link = (content.get("canonicalUrl") or {}).get("url") if isinstance(
        content.get("canonicalUrl"), dict) else item.get("link")
    # 媒体
    provider = content.get("provider") or {}
    publisher = provider.get("displayName") if isinstance(provider, dict) else item.get("publisher")
    # 日時
    ts = item.get("providerPublishTime")
    pub = content.get("pubDate") or content.get("displayTime")
    when = ""
    if ts:
        when = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    elif pub:
        when = str(pub)[:16].replace("T", " ")
    return {"title": title, "link": link, "publisher": publisher, "when": when}


def render():
    st.header("📰 関連ニュース・決算カレンダー")
    st.caption("銘柄に関するニュース見出しと、直近・次回の決算予定日を表示します。"
               "(yfinance由来。米国系媒体が中心で、銘柄により取得できない場合があります)")

    symbol = symbol_picker(key="news", default_code="7203")
    if not symbol:
        return

    col_news, col_earn = st.columns([3, 2])

    # --- ニュース ---
    with col_news:
        st.subheader("📰 関連ニュース")
        news = get_news(symbol)
        items = [x for x in (_fmt_news_item(n) for n in news) if x]
        if not items:
            st.info("ニュースを取得できませんでした。")
        for it in items:
            meta = " ・ ".join(x for x in [it["publisher"], it["when"]] if x)
            if it["link"]:
                st.markdown(f"**[{it['title']}]({it['link']})**")
            else:
                st.markdown(f"**{it['title']}**")
            if meta:
                st.caption(meta)
            st.divider()

    # --- 決算カレンダー ---
    with col_earn:
        st.subheader("📅 決算予定日")
        earn = get_earnings_dates(symbol)
        if earn.empty:
            st.info("決算日を取得できませんでした。")
            return

        now = pd.Timestamp.now(tz=earn.index.tz)
        upcoming = earn[earn.index >= now].sort_index()
        if not upcoming.empty:
            next_date = upcoming.index[0]
            days = (next_date - now).days
            st.metric("次回決算(予定)", next_date.strftime("%Y-%m-%d"), f"あと約{days}日")

        # 一覧(過去はEPS実績/予想を表示)
        disp = earn.copy()
        disp.index = disp.index.strftime("%Y-%m-%d")
        rename = {
            "EPS Estimate": "EPS予想", "Reported EPS": "EPS実績",
            "Surprise(%)": "サプライズ(%)",
        }
        disp = disp.rename(columns={k: v for k, v in rename.items() if k in disp.columns})
        st.dataframe(disp, use_container_width=True)
        st.caption("過去分はEPSの予想/実績、将来分は予定日です。")
