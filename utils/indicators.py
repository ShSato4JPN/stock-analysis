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


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """RSI(相対力指数)。30以下で売られすぎ、70以上で買われすぎの目安。"""
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss
    return 100 - 100 / (1 + rs)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD(MACD線, シグナル線, ヒストグラム)を返す。"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line
