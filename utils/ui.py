"""共通UIウィジェット。"""
import streamlit as st

from utils import listings


def symbol_picker(label: str = "銘柄を検索", key: str = "sym", default_code: str | None = None):
    """企業名/コード/市場区分で検索して1銘柄を選ぶウィジェット。

    選択された銘柄のコード(文字列)を返す。一覧CSVが無い場合は
    フリーテキスト入力にフォールバックする。
    """
    df = listings.load_listings()
    if df.empty:
        return st.text_input(f"{label}(コード/ティッカー)", value=default_code or "", key=f"{key}_txt")

    # 市場区分 + キーワードで候補を絞り込み(キーワードは大文字小文字を区別しない)
    c1, c2 = st.columns([1, 2])
    market = c1.selectbox("市場・商品区分で絞り込み", ["すべて"] + listings.markets(), key=f"{key}_mkt")
    keyword = c2.text_input("キーワード絞り込み(企業名 or コード / 大文字小文字を区別しない)",
                            key=f"{key}_kw", placeholder="例: toyota / トヨタ / 7203")
    result = listings.search(keyword, market)
    if result.empty:
        st.warning("該当する銘柄がありません。")
        return None

    options = result["コード"].tolist()
    labels = {r["コード"]: f"{r['コード']}  {r['銘柄名']}  [{r['市場・商品区分']}]"
              for _, r in result.iterrows()}

    index = options.index(default_code) if default_code in options else None
    # selectboxは企業名・コードを入力して絞り込みも、一覧から選択も可能
    code = st.selectbox(
        f"{label}(企業名 or コードを入力、または一覧から選択 / {len(result)}件)",
        options, index=index, placeholder="例: トヨタ / 7203",
        format_func=lambda c: labels.get(c, c), key=f"{key}_sel",
    )
    return code


def symbol_multipicker(label: str = "銘柄を選択(複数可)", key: str = "syms",
                       default_codes: list | None = None, max_n: int = 4):
    """複数銘柄を選ぶウィジェット。選択コードのリストを返す。

    一覧CSVが無い場合はカンマ区切りのフリーテキスト入力にフォールバック。
    """
    df = listings.load_listings()
    if df.empty:
        raw = st.text_input(f"{label}(コード/ティッカーをカンマ区切り)",
                            value=", ".join(default_codes or []), key=f"{key}_txt")
        return [s.strip() for s in raw.split(",") if s.strip()][:max_n]

    market = st.selectbox("市場・商品区分で絞り込み", ["すべて"] + listings.markets(), key=f"{key}_mkt")
    keyword = st.text_input("キーワード絞り込み(大文字小文字を区別しない)", key=f"{key}_kw",
                            placeholder="例: toyota / トヨタ / 7203")
    result = listings.search(keyword, market)
    if result.empty:
        st.warning("該当する銘柄がありません。")
        return []

    options = result["コード"].tolist()
    labels = {r["コード"]: f"{r['コード']}  {r['銘柄名']}"
              for _, r in result.iterrows()}
    valid_defaults = [c for c in (default_codes or []) if c in options]
    selected = st.multiselect(
        f"{label}(最大{max_n}銘柄)", options, default=valid_defaults,
        format_func=lambda c: labels.get(c, c), key=f"{key}_sel",
    )
    if len(selected) > max_n:
        st.warning(f"最大{max_n}銘柄まで。先頭{max_n}件を使用します。")
        selected = selected[:max_n]
    return selected
