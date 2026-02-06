"""
BanglaBias Annotation Tool
Interactive Streamlit app for political stance labeling of Bangla news articles.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

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

/* Sentence buttons: make them look like colored blocks */
.stMainBlockContainer [data-testid="stVerticalBlock"] .sentence-btn-wrap button {
    text-align: left !important;
    justify-content: flex-start !important;
    font-family: 'Noto Sans Bengali', sans-serif !important;
    font-size: 15px !important;
    padding: 10px 14px !important;
    white-space: normal !important;
    word-wrap: break-word !important;
    line-height: 1.6 !important;
    min-height: 44px !important;
    border-radius: 6px !important;
    transition: all 0.15s ease !important;
}
.stMainBlockContainer [data-testid="stVerticalBlock"] .sentence-btn-wrap button:hover {
    filter: brightness(0.93) !important;
}
.stMainBlockContainer [data-testid="stVerticalBlock"] .sentence-btn-wrap button p {
    text-align: left !important;
}
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
.selected-sentence {
    outline: 3px solid #f59e0b;
    outline-offset: 1px;
}

/* Article label button styling */
div[data-testid="stHorizontalBlock"] button {
    font-size: 15px !important;
    font-weight: 600 !important;
    padding: 8px 20px !important;
    border-radius: 8px !important;
    transition: all 0.15s ease !important;
}
</style>
"""


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
    nav_cols = st.columns([1, 1, 2, 1, 1])
    with nav_cols[0]:
        if st.button("◀ Prev", use_container_width=True, disabled=(idx == 0)):
            st.session_state.current_idx -= 1
            st.session_state.selected_sentence = -1
            st.rerun()
    with nav_cols[1]:
        if st.button("Next ▶", use_container_width=True, disabled=(idx >= total - 1)):
            st.session_state.current_idx += 1
            st.session_state.selected_sentence = -1
            st.rerun()
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
            st.session_state.current_idx = int(goto) - 1
            st.session_state.selected_sentence = -1
            st.rerun()

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

            if is_active and lbl_key != "unlabeled":
                st.markdown(
                    f"<div style='background:{color}; color:#fff; text-align:center; "
                    f"padding:8px 16px; border-radius:8px; font-weight:700; font-size:15px; "
                    f"margin-bottom:4px;'>{lbl_text} ✓</div>",
                    unsafe_allow_html=True,
                )
            elif is_active and lbl_key == "unlabeled":
                st.markdown(
                    f"<div style='background:{color}; color:#fff; text-align:center; "
                    f"padding:8px 16px; border-radius:8px; font-weight:700; font-size:15px; "
                    f"margin-bottom:4px;'>Unlabeled ✓</div>",
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

    # ----- Sentences Panel -----
    st.markdown("**Sentences** (click a sentence to label it)")

    sents = article.get("sentences", [])
    if not sents:
        st.caption("No sentences found in this article.")
    else:
        for sent in sents:
            sid = sent["id"]
            slabel = sent.get("label", "unlabeled")
            scolor = LABEL_COLORS[slabel]
            is_selected = (st.session_state.selected_sentence == sid)

            # Inject per-sentence color styling + make the button the sentence
            outline = "outline:3px solid #f59e0b; outline-offset:2px;" if is_selected else ""
            st.markdown(
                f'<style>'
                f'.sent-btn-{sid} button {{'
                f'  background: {scolor}18 !important;'
                f'  border-left: 4px solid {scolor} !important;'
                f'  {outline}'
                f'}}'
                f'.sent-btn-{sid} button:hover {{'
                f'  background: {scolor}30 !important;'
                f'}}'
                f'</style>'
                f'<div class="sentence-btn-wrap sent-btn-{sid}">',
                unsafe_allow_html=True,
            )

            # The sentence itself is the clickable element
            btn_text = f"#{sid}  {sent['text']}  [{LABEL_DISPLAY[slabel]}]"
            if st.button(
                btn_text,
                key=f"sent_select_{sid}",
                use_container_width=True,
            ):
                if is_selected:
                    st.session_state.selected_sentence = -1
                else:
                    st.session_state.selected_sentence = sid
                st.rerun()

            # Close the wrapper div
            st.markdown("</div>", unsafe_allow_html=True)

            # Show inline label buttons if this sentence is selected
            if is_selected:
                sl_cols = st.columns(4)
                sent_labels = [
                    ("govt_leaning", "Govt Leaning"),
                    ("govt_critique", "Govt Critique"),
                    ("neutral", "Neutral"),
                    ("unlabeled", "Clear"),
                ]
                for j, (sl_key, sl_text) in enumerate(sent_labels):
                    with sl_cols[j]:
                        is_current = (slabel == sl_key)
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
