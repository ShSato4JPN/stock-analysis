"""テクニカル指標の計算ヘルパー。"""
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    """単純移動平均。"""
    return close.rolling(window).mean()


def bollinger(close: pd.Series, window: int = 20, sigma: float = 2.0):
    """ボリンジャーバンド(中央線, 上限, 下限)を返す。"""
    mid = close.rolling(window).mean()
    std = close.rolling(window).std()
    return mid, mid + sigma * std, mid - sigma * std
