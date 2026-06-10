"""国内上場企業一覧(JPXのCSV)の読み込みと検索。

プロジェクト直下の「上場企業一覧.csv」を読み込み、企業名・コード・
市場区分でフィルタリングできるようにする。
"""
import os
import unicodedata

import pandas as pd
import streamlit as st


def _norm(text: str) -> str:
    """検索用に正規化する。全角/半角・大文字/小文字の差を吸収。"""
    return unicodedata.normalize("NFKC", str(text)).casefold()

_CSV = os.path.join(os.path.dirname(os.path.dirname(__file__)), "上場企業一覧.csv")


@st.cache_data(show_spinner=False)
def load_listings() -> pd.DataFrame:
    """上場企業一覧を読み込む。コードは文字列に統一する。失敗時は空DataFrame。"""
    if not os.path.exists(_CSV):
        return pd.DataFrame()
    try:
        df = pd.read_csv(_CSV, dtype={"コード": str})
    except Exception:
        return pd.DataFrame()
    df["コード"] = df["コード"].astype(str).str.strip()
    df["銘柄名"] = df["銘柄名"].astype(str).str.strip()
    return df


def markets() -> list[str]:
    """市場・商品区分の一覧を返す。"""
    df = load_listings()
    if df.empty:
        return []
    return sorted(df["市場・商品区分"].dropna().unique().tolist())


def search(keyword: str = "", market: str | None = None) -> pd.DataFrame:
    """企業名/コードのキーワードと市場区分で絞り込む。"""
    df = load_listings()
    if df.empty:
        return df
    if market and market != "すべて":
        df = df[df["市場・商品区分"] == market]
    kw = _norm(keyword.strip())
    if kw:
        code_n = df["コード"].map(_norm)
        name_n = df["銘柄名"].map(_norm)
        mask = code_n.str.contains(kw, regex=False, na=False) | \
            name_n.str.contains(kw, regex=False, na=False)
        df = df[mask]
    return df


def name_of(code: str) -> str:
    """コードから銘柄名を引く。見つからなければ空文字。"""
    df = load_listings()
    if df.empty:
        return ""
    hit = df[df["コード"] == str(code).strip()]
    return hit["銘柄名"].iloc[0] if not hit.empty else ""
