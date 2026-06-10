"""yfinanceのラッパー。キャッシュとエラーハンドリングを集約する。

yfinanceは非公式ライブラリのため取得失敗が起こりうる。各関数は
例外を握りつぶして空のデータ/Noneを返し、UI側で安全に扱えるようにする。
"""
import pandas as pd
import streamlit as st
import yfinance as yf


def normalize_symbol(symbol: str) -> str:
    """銘柄コードを正規化する。数字のみの場合は日本株とみなし .T を付与。"""
    s = symbol.strip().upper()
    if s.isdigit():
        return f"{s}.T"
    return s


@st.cache_data(ttl=600, show_spinner=False)
def get_history(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """過去株価を取得する。失敗時は空のDataFrame。"""
    sym = normalize_symbol(symbol)
    try:
        df = yf.Ticker(sym).history(period=period, interval=interval)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def get_info(symbol: str) -> dict:
    """銘柄の基本情報(PER/PBR/配当など)を取得する。失敗時は空dict。"""
    sym = normalize_symbol(symbol)
    try:
        return yf.Ticker(sym).info or {}
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def get_price(symbol: str):
    """現在株価(直近終値)を取得する。失敗時はNone。"""
    df = get_history(symbol, period="5d")
    if df.empty:
        return None
    return float(df["Close"].iloc[-1])


@st.cache_data(ttl=1800, show_spinner=False)
def get_news(symbol: str) -> list:
    """関連ニュースを取得する。失敗時は空リスト。"""
    sym = normalize_symbol(symbol)
    try:
        return yf.Ticker(sym).news or []
    except Exception:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def get_earnings_dates(symbol: str) -> pd.DataFrame:
    """決算予定日(過去・将来)を取得する。失敗時は空DataFrame。"""
    sym = normalize_symbol(symbol)
    try:
        df = yf.Ticker(sym).get_earnings_dates(limit=12)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_dividends(symbol: str) -> pd.Series:
    """配当履歴を取得する。失敗時は空のSeries。"""
    sym = normalize_symbol(symbol)
    try:
        div = yf.Ticker(sym).dividends
        if div is None or div.empty:
            return pd.Series(dtype=float)
        return div
    except Exception:
        return pd.Series(dtype=float)
