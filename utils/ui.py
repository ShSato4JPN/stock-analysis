"""共通UIウィジェット。"""
import streamlit as st
import streamlit.components.v1 as components

from utils import listings


def _copy_button(text: str):
    """クリップボードにコピーするボタン(JSコンポーネント)。

    Streamlit標準のst.buttonと同じ見た目(枠線・角丸・高さ・ホバー色)に
    スタイルを合わせている。
    """
    components.html(f"""
    <style>
      html, body {{ margin: 0; padding: 0; }}
      .copy-btn {{
        width: 100%; height: 38px;
        background: transparent; color: inherit;
        border: 1px solid rgba(128, 128, 128, .35);
        border-radius: .5rem;
        cursor: pointer; font-size: 14px; line-height: 1; padding: 0;
        transition: border-color .15s, color .15s;
      }}
      .copy-btn:hover {{ border-color: #ff4b4b; color: #ff4b4b; }}
    </style>
    <button class="copy-btn" title="{text} をコピー"
      onclick="(function(btn){{
        function flash() {{ btn.innerText='✓'; setTimeout(function() {{ btn.innerText='📋'; }}, 800); }}
        function fallback() {{
          var ta=document.createElement('textarea'); ta.value='{text}';
          document.body.appendChild(ta); ta.select();
          document.execCommand('copy'); document.body.removeChild(ta); flash();
        }}
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText('{text}').then(flash, fallback);
        }} else {{ fallback(); }}
      }})(this)">📋</button>
    """, height=38)


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


def _add_memo():
    """注目メモへの追加コールバック。追加後は選択をプレースホルダに戻す。"""
    sel = st.session_state.get("memo_add")
    if sel and sel not in st.session_state["memo_codes"]:
        st.session_state["memo_codes"].append(sel)
    st.session_state["memo_add"] = None


def render_sidebar_memo():
    """サイドバー下部の「注目メモ」。セッション中だけ保持される一時メモ。"""
    codes = st.session_state.setdefault("memo_codes", [])
    st.sidebar.divider()
    st.sidebar.markdown("**📌 注目メモ**")

    df = listings.load_listings()
    if df.empty:
        st.sidebar.info("上場企業一覧が見つかりません。")
        return

    labels = dict(zip(df["コード"], df["コード"] + " " + df["銘柄名"]))
    st.sidebar.selectbox(
        "企業を追加", df["コード"].tolist(), index=None,
        placeholder="企業名 or コードで追加...",
        format_func=lambda c: labels.get(c, c),
        key="memo_add", on_change=_add_memo,
        label_visibility="collapsed",
    )

    if not codes:
        st.sidebar.caption("比較したい企業を一時的に控えられます(アプリを閉じると消えます)。"
                           "「📊 銘柄比較」でまとめて取り込めます。")
        return

    # 1銘柄=1行: 銘柄名 + 📋コピー + ✕削除
    for code in list(codes):
        name = listings.name_of(code)
        c1, c2, c3 = st.sidebar.columns([5, 1, 1], vertical_alignment="center")
        c1.markdown(f"`{code}` {name}")
        with c2:
            _copy_button(code)
        if c3.button("✕", key=f"memo_del_{code}", help=f"{name} をメモから外す"):
            codes.remove(code)
            st.rerun()

    if st.sidebar.button("🗑 すべてクリア", key="memo_clear"):
        codes.clear()
        st.rerun()


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
