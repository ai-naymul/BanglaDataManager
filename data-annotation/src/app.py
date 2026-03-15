"""
BanglaBias Annotation Tool
Interactive Streamlit app for political stance labeling of Bangla news articles.
Supports sentence-level labeling and span-level text highlighting.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from text_highlighter import text_highlighter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LABELS = ["govt_leaning", "govt_critique", "neutral", "unlabeled"]
LABEL_COLORS = {
    "govt_leaning": "#22c55e",   # green
    "govt_critique": "#ef4444",  # red
    "neutral": "#3b82f6",        # blue
    "unlabeled": "#9ca3af",      # gray
}
LABEL_DISPLAY = {
    "govt_leaning": "Govt Leaning",
    "govt_critique": "Govt Critique",
    "neutral": "Neutral",
    "unlabeled": "Unlabeled",
}
HIGHLIGHTER_LABELS = [
    ("Govt Leaning", "#22c55e"),
    ("Govt Critique", "#ef4444"),
    ("Neutral", "#3b82f6"),
]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATE_PATH = DATA_DIR / "annotations_state.json"

# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

def split_sentences(text: str) -> list[str]:
    """Split Bangla text on ।  .  or newline, keeping non-empty segments."""
    if not text or not isinstance(text, str):
        return []
    parts = re.split(r"(?<=।)|(?<=\.)\s|(?:\r?\n)+", text)
    sentences = [s.strip() for s in parts if s and s.strip()]
    return sentences


# ---------------------------------------------------------------------------
# CSV → articles list
# ---------------------------------------------------------------------------

def csv_to_articles(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame (from the annotation CSV) to the internal articles list."""
    articles = []
    for idx, row in df.iterrows():
        label = "unlabeled"
        if str(row.get("Govt Leaning", "")).strip().lower() == "yes":
            label = "govt_leaning"
        elif str(row.get("Govt Critique", "")).strip().lower() == "yes":
            label = "govt_critique"
        elif str(row.get("Neutral", "")).strip().lower() == "yes":
            label = "neutral"

        body = str(row.get("News Body", ""))
        sentences = split_sentences(body)

        articles.append({
            "id": int(idx),
            "year": str(row.get("Year", "")),
            "ruling_party": str(row.get("Ruling Party ", row.get("Ruling Party", ""))).strip(),
            "event": str(row.get("Event", "")),
            "headline": str(row.get("News Headline", "")),
            "news_body": body,
            "source_link": str(row.get("Source Link", "")),
            "date": str(row.get("Date", "")),
            "news_corpora_name": str(row.get("News Corpora Name", "")),
            "article_label": label,
            "sentences": [
                {"id": i, "text": s, "label": "unlabeled"}
                for i, s in enumerate(sentences)
            ],
            "highlights": [],
        })
    return articles


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def make_empty_state() -> dict:
    return {
        "annotator_name": "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "source_csv": "",
        "articles": [],
    }


def save_state(state: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return make_empty_state()


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_json(state: dict) -> str | None:
    if not state.get("articles"):
        return None
    out = DATA_DIR / "annotations_export.json"
    out.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)


def export_csv(state: dict) -> str | None:
    if not state.get("articles"):
        return None
    rows = []
    for a in state["articles"]:
        row = {
            "Year": a["year"],
            "Ruling Party": a["ruling_party"],
            "Event": a["event"],
            "News Headline": a["headline"],
            "News Body": a["news_body"],
            "Source Link": a["source_link"],
            "Date": a["date"],
            "News Corpora Name": a["news_corpora_name"],
            "Govt Leaning": "Yes" if a["article_label"] == "govt_leaning" else "No",
            "Govt Critique": "Yes" if a["article_label"] == "govt_critique" else "No",
            "Neutral": "Yes" if a["article_label"] == "neutral" else "No",
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    out = DATA_DIR / "annotations_export.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return str(out)


# ---------------------------------------------------------------------------
# Filtering helper
# ---------------------------------------------------------------------------

def get_event_list(state: dict) -> list[str]:
    events = sorted({a.get("event", "") for a in state.get("articles", [])})
    return ["(All Events)"] + [e for e in events if e]


def filtered_indices(state: dict, event_val: str) -> list[int]:
    articles = state.get("articles", [])
    if not event_val or event_val == "(All Events)":
        return list(range(len(articles)))
    return [i for i, a in enumerate(articles) if a.get("event", "") == event_val]


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

def init_session_state():
    if "state" not in st.session_state:
        st.session_state.state = load_state()
    if "current_idx" not in st.session_state:
        st.session_state.current_idx = 0
    if "selected_sentence" not in st.session_state:
        st.session_state.selected_sentence = -1
    if "event_filter" not in st.session_state:
        st.session_state.event_filter = "(All Events)"


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Bengali:wght@400;600;700&display=swap');

/* Per-sentence button CSS is injected dynamically in render_sentence_panel */
.article-meta {
    font-family: 'Noto Sans Bengali', sans-serif;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    font-size: 14px;
    color: #888;
    margin-bottom: 8px;
}
.article-meta b { color: #aaa; }
.article-headline {
    font-family: 'Noto Sans Bengali', sans-serif;
    font-size: 22px;
    font-weight: 700;
    margin: 10px 0;
}
.label-badge {
    display: inline-block;
    color: #fff;
    padding: 3px 12px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
}

/* Article label button styling */
div[data-testid="stHorizontalBlock"] button {
    font-size: 15px !important;
    font-weight: 600 !important;
    padding: 8px 20px !important;
    border-radius: 8px !important;
    transition: all 0.15s ease !important;
}

/* Text highlighter container */
.highlight-container {
    font-family: 'Noto Sans Bengali', sans-serif;
    font-size: 16px;
    line-height: 2;
}
</style>
"""


# ---------------------------------------------------------------------------
# Sentence annotation panel (st.button based — reliable click handling)
# ---------------------------------------------------------------------------

def render_sentence_panel(article: dict, state: dict):
    """Render the sentence-level annotation panel using st.button per sentence."""
    sents = article.get("sentences", [])
    if not sents:
        st.caption("No sentences found in this article.")
        return

    selected_sid = st.session_state.selected_sentence

    # Consolidate all per-sentence CSS into a single style block
    css_rules = []
    for sent in sents:
        sid = sent["id"]
        scolor = LABEL_COLORS[sent.get("label", "unlabeled")]
        is_selected = (selected_sid == sid)
        outline = (
            f"outline: 3px solid #f59e0b; outline-offset: 2px; "
            f"box-shadow: 0 0 8px rgba(245,158,11,0.3);"
            if is_selected else ""
        )
        css_rules.append(
            f'.sent-{sid} button {{'
            f'  background: {scolor}18 !important;'
            f'  border-left: 5px solid {scolor} !important;'
            f'  text-align: left !important;'
            f'  justify-content: flex-start !important;'
            f'  font-family: "Noto Sans Bengali", sans-serif !important;'
            f'  font-size: 15px !important;'
            f'  padding: 10px 14px !important;'
            f'  white-space: normal !important;'
            f'  word-wrap: break-word !important;'
            f'  line-height: 1.8 !important;'
            f'  min-height: 44px !important;'
            f'  border-radius: 8px !important;'
            f'  margin-bottom: 2px !important;'
            f'  {outline}'
            f'}}'
            f'.sent-{sid} button:hover {{'
            f'  background: {scolor}30 !important;'
            f'  filter: brightness(0.95) !important;'
            f'}}'
            f'.sent-{sid} button p {{'
            f'  text-align: left !important;'
            f'}}'
        )
    st.markdown(f'<style>{"".join(css_rules)}</style>', unsafe_allow_html=True)

    # Render each sentence as a clickable button
    for sent in sents:
        sid = sent["id"]
        slabel = sent.get("label", "unlabeled")
        scolor = LABEL_COLORS[slabel]
        is_selected = (selected_sid == sid)

        # Wrap each button in a div with a per-sentence CSS class
        st.markdown(f'<div class="sent-{sid}">', unsafe_allow_html=True)
        btn_text = f"#{sid}  {sent['text']}  [{LABEL_DISPLAY[slabel]}]"
        if st.button(btn_text, key=f"sent_select_{sid}", use_container_width=True):
            if is_selected:
                st.session_state.selected_sentence = -1
            else:
                st.session_state.selected_sentence = sid
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Show inline label buttons if this sentence is selected
        if is_selected:
            sl_cols = st.columns(5)
            sent_labels = [
                ("govt_leaning", "Govt Leaning"),
                ("govt_critique", "Govt Critique"),
                ("neutral", "Neutral"),
                ("unlabeled", "Clear"),
            ]
            current_slabel = sent.get("label", "unlabeled")
            for j, (sl_key, sl_text) in enumerate(sent_labels):
                with sl_cols[j]:
                    is_current = (current_slabel == sl_key)
                    if st.button(
                        f"● {sl_text}" if is_current else sl_text,
                        key=f"sent_label_{sid}_{sl_key}",
                        use_container_width=True,
                        type="primary" if is_current else "secondary",
                    ):
                        sent["label"] = sl_key
                        save_state(state)
                        st.session_state.selected_sentence = -1
                        st.rerun()
            with sl_cols[4]:
                if st.button("Close", key=f"sent_close_{sid}",
                             use_container_width=True, type="secondary"):
                    st.session_state.selected_sentence = -1
                    st.rerun()


# ---------------------------------------------------------------------------
# Text highlighting panel
# ---------------------------------------------------------------------------

def render_highlight_panel(article: dict, state: dict, real_idx: int):
    """Render the span-level text highlighting panel."""
    body = article.get("news_body", "")
    if not body.strip():
        st.caption("No article body text available.")
        return

    st.markdown(
        "Select text with your mouse, pick a label, and the highlight will be saved. "
        "Existing highlights are shown in color."
    )

    # Load existing highlights for this article
    existing = article.get("highlights", [])

    # Convert stored highlights to text-highlighter format (start/end/tag only)
    annotations = [
        {"start": h["start"], "end": h["end"], "tag": h["tag"]}
        for h in existing
    ]

    result = text_highlighter(
        text=body,
        labels=HIGHLIGHTER_LABELS,
        annotations=annotations if len(annotations) > 0 else None,
        key=f"highlighter_{real_idx}",
        show_label_selector=True,
    )

    # Save highlights when they change
    if result is not None and len(result) > 0:
        new_highlights = []
        for ann in result:
            start = int(ann.get("start", 0) if isinstance(ann, dict) else getattr(ann, "start", 0))
            end = int(ann.get("end", 0) if isinstance(ann, dict) else getattr(ann, "end", 0))
            tag = str(ann.get("tag", "") if isinstance(ann, dict) else getattr(ann, "tag", ""))
            new_highlights.append({
                "start": start,
                "end": end,
                "tag": tag,
                "text": body[start:end],
            })

        # Compare by normalized tuples to avoid format mismatch
        existing_set = {(h["start"], h["end"], h["tag"]) for h in existing}
        new_set = {(h["start"], h["end"], h["tag"]) for h in new_highlights}
        if new_set != existing_set:
            article["highlights"] = new_highlights
            save_state(state)
    elif result is not None and len(result) == 0 and len(existing) > 0:
        # User cleared all highlights via the component
        article["highlights"] = []
        save_state(state)

    # Show highlight summary
    highlights = article.get("highlights", [])
    if highlights:
        st.markdown("---")
        st.markdown(f"**Highlights ({len(highlights)}):**")
        for i, h in enumerate(highlights):
            tag = h.get("tag", "Unknown")
            text = h.get("text", body[h["start"]:h["end"]])
            # Find color for this tag
            tag_color = "#9ca3af"
            for lbl_name, lbl_color in HIGHLIGHTER_LABELS:
                if lbl_name == tag:
                    tag_color = lbl_color
                    break
            st.markdown(
                f'<div style="padding:6px 10px; margin:3px 0; border-left:3px solid {tag_color}; '
                f'background:{tag_color}15; border-radius:4px; font-family: Noto Sans Bengali, sans-serif;">'
                f'<span style="font-size:11px; color:{tag_color}; font-weight:600;">[{tag}]</span> '
                f'{text}</div>',
                unsafe_allow_html=True,
            )

        if st.button("Clear All Highlights", key="clear_highlights", type="secondary"):
            article["highlights"] = []
            save_state(state)
            st.rerun()


# ---------------------------------------------------------------------------
# Streamlit App
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="BanglaBias Annotation Tool",
        page_icon="📝",
        layout="wide",
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    init_session_state()

    state = st.session_state.state
    articles = state.get("articles", [])
    indices = filtered_indices(state, st.session_state.event_filter)

    # =================================================================
    # SIDEBAR
    # =================================================================
    with st.sidebar:
        st.title("BanglaBias Annotator")

        # Annotator name
        annotator = st.text_input(
            "Annotator Name",
            value=state.get("annotator_name", ""),
            key="annotator_input",
        )
        if annotator != state.get("annotator_name", ""):
            state["annotator_name"] = annotator
            save_state(state)

        st.divider()

        # CSV upload
        csv_file = st.file_uploader("Upload CSV", type=["csv"], key="csv_uploader")
        if csv_file is not None:
            csv_key = f"loaded_csv_{csv_file.name}_{csv_file.size}"
            if st.session_state.get("_last_csv_key") != csv_key:
                df = pd.read_csv(csv_file, encoding="utf-8")
                new_articles = csv_to_articles(df)
                st.session_state.state = {
                    "annotator_name": annotator or "",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "source_csv": csv_file.name,
                    "articles": new_articles,
                }
                save_state(st.session_state.state)
                st.session_state.current_idx = 0
                st.session_state.selected_sentence = -1
                st.session_state.event_filter = "(All Events)"
                st.session_state._last_csv_key = csv_key
                st.rerun()

        # JSON state upload
        json_file = st.file_uploader("Load JSON State", type=["json"], key="json_uploader")
        if json_file is not None:
            json_key = f"loaded_json_{json_file.name}_{json_file.size}"
            if st.session_state.get("_last_json_key") != json_key:
                data = json.loads(json_file.read().decode("utf-8"))
                st.session_state.state = data
                save_state(data)
                st.session_state.current_idx = 0
                st.session_state.selected_sentence = -1
                st.session_state.event_filter = "(All Events)"
                st.session_state._last_json_key = json_key
                st.rerun()

        st.divider()

        # Event filter
        events = get_event_list(state)
        event_val = st.selectbox(
            "Filter by Event",
            options=events,
            index=events.index(st.session_state.event_filter) if st.session_state.event_filter in events else 0,
            key="event_select",
        )
        if event_val != st.session_state.event_filter:
            st.session_state.event_filter = event_val
            st.session_state.current_idx = 0
            st.session_state.selected_sentence = -1
            st.rerun()

        st.divider()

        # Progress
        total = len(indices)
        labeled = sum(
            1 for i in indices
            if articles[i].get("article_label", "unlabeled") != "unlabeled"
        ) if articles else 0
        total_all = len(articles)
        labeled_all = sum(1 for a in articles if a.get("article_label", "unlabeled") != "unlabeled")

        if total_all > 0:
            st.progress(labeled_all / total_all)
            st.caption(f"**{labeled_all} / {total_all}** articles labeled ({int(labeled_all / total_all * 100)}%)")
            if total != total_all:
                st.caption(f"Filtered: **{labeled} / {total}** in current view")
        else:
            st.info("No articles loaded yet.")

        st.caption(f"Source: **{state.get('source_csv', 'N/A')}**")

        st.divider()

        # Export
        st.subheader("Export")
        col_ej, col_ec = st.columns(2)
        with col_ej:
            if st.button("Export JSON", use_container_width=True):
                path = export_json(state)
                if path:
                    with open(path, "rb") as f:
                        st.session_state._export_json_data = f.read()
                        st.session_state._export_json_name = os.path.basename(path)

        with col_ec:
            if st.button("Export CSV", use_container_width=True):
                path = export_csv(state)
                if path:
                    with open(path, "rb") as f:
                        st.session_state._export_csv_data = f.read()
                        st.session_state._export_csv_name = os.path.basename(path)

        if st.session_state.get("_export_json_data"):
            st.download_button(
                "Download JSON",
                data=st.session_state._export_json_data,
                file_name=st.session_state._export_json_name,
                mime="application/json",
                use_container_width=True,
            )
        if st.session_state.get("_export_csv_data"):
            st.download_button(
                "Download CSV",
                data=st.session_state._export_csv_data,
                file_name=st.session_state._export_csv_name,
                mime="text/csv",
                use_container_width=True,
            )

    # =================================================================
    # MAIN AREA
    # =================================================================

    # Refresh indices after potential state changes
    state = st.session_state.state
    articles = state.get("articles", [])
    indices = filtered_indices(state, st.session_state.event_filter)
    total = len(indices)

    if not articles:
        st.title("BanglaBias Annotation Tool")
        st.info("Upload a CSV or load a JSON state from the sidebar to begin.")
        return

    if not indices:
        st.warning("No articles match the current event filter.")
        return

    # Clamp index
    if st.session_state.current_idx >= total:
        st.session_state.current_idx = total - 1
    if st.session_state.current_idx < 0:
        st.session_state.current_idx = 0

    idx = st.session_state.current_idx
    real_idx = indices[idx]
    article = articles[real_idx]

    # Ensure highlights field exists (for older state files)
    if "highlights" not in article:
        article["highlights"] = []

    # ----- Article Header -----
    meta_html = f"""
    <div class="article-meta">
        <span><b>Year:</b> {article.get('year','')}</span>
        <span><b>Party:</b> {article.get('ruling_party','')}</span>
        <span><b>Date:</b> {article.get('date','')}</span>
        <span><b>Source:</b> {article.get('news_corpora_name','')}</span>
    </div>
    <div style="font-size:13px; color:#aaa; margin-bottom:4px;">
        <b>Event:</b> {article.get('event','')}
    </div>
    <div class="article-headline">{article.get('headline','')}</div>
    """
    st.markdown(meta_html, unsafe_allow_html=True)

    # ----- Navigation Row -----
    def _navigate(new_idx):
        """Navigate to a new article index, clearing selection state."""
        st.session_state.current_idx = new_idx
        st.session_state.selected_sentence = -1
        st.rerun()

    nav_cols = st.columns([1, 1, 2, 1, 1])
    with nav_cols[0]:
        if st.button("◀ Prev", use_container_width=True, disabled=(idx == 0)):
            _navigate(idx - 1)
    with nav_cols[1]:
        if st.button("Next ▶", use_container_width=True, disabled=(idx >= total - 1)):
            _navigate(idx + 1)
    with nav_cols[2]:
        st.markdown(
            f"<div style='text-align:center; padding:8px; font-size:16px;'>"
            f"Article <b>{idx + 1}</b> / {total} &nbsp; (global #{real_idx})</div>",
            unsafe_allow_html=True,
        )
    with nav_cols[3]:
        goto = st.number_input("Go to #", min_value=1, max_value=max(total, 1), value=idx + 1, step=1, key="goto_input", label_visibility="collapsed")
    with nav_cols[4]:
        if st.button("Go", use_container_width=True):
            _navigate(int(goto) - 1)

    st.divider()

    # ----- Article Label Row -----
    current_label = article.get("article_label", "unlabeled")

    st.markdown("**Article Label:**")
    label_cols = st.columns(4)
    label_options = [
        ("govt_leaning", "Govt Leaning"),
        ("govt_critique", "Govt Critique"),
        ("neutral", "Neutral"),
        ("unlabeled", "Clear Label"),
    ]

    for i, (lbl_key, lbl_text) in enumerate(label_options):
        with label_cols[i]:
            is_active = (current_label == lbl_key)
            color = LABEL_COLORS[lbl_key]

            if is_active:
                display = lbl_text if lbl_key != "unlabeled" else "Unlabeled"
                st.markdown(
                    f"<div style='background:{color}; color:#fff; text-align:center; "
                    f"padding:8px 16px; border-radius:8px; font-weight:700; font-size:15px; "
                    f"margin-bottom:4px;'>{display} ✓</div>",
                    unsafe_allow_html=True,
                )

            if st.button(
                lbl_text if not is_active else f"● {lbl_text}",
                key=f"art_label_{lbl_key}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                article["article_label"] = lbl_key
                save_state(state)
                st.rerun()

    # Show current label badge
    badge_color = LABEL_COLORS[current_label]
    st.markdown(
        f'<span class="label-badge" style="background:{badge_color};">'
        f'Current: {LABEL_DISPLAY[current_label]}</span>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ----- Tabbed Annotation Panels -----
    tab_sent, tab_highlight = st.tabs([
        "Sentence Annotation",
        "Text Highlighting",
    ])

    with tab_sent:
        st.markdown("Click a sentence to label it.")
        render_sentence_panel(article, state)

    with tab_highlight:
        st.markdown("Highlight text spans in the article body and assign labels.")
        render_highlight_panel(article, state, real_idx)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
