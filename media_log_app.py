import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# -------- CONFIG --------
SPREADSHEET_TITLE = "MediaLog"
SERVICE_ACCOUNT_FILE = "media-log-service-account.json"

# -------- PLATFORM LOGOS (base64 embedded — no external CDN dependency) --------
# Netflix & YouTube via jsDelivr (allowlisted CDN in Streamlit)
# JioHotstar, SonyLiv, ZEE5 — base64 embedded
# To regenerate base64: open assets/<name>.png, base64 encode, paste below

PLATFORM_LOGOS = {
    "Netflix":      "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/netflix.svg",
    "Prime Video":  "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/primevideo.svg",
    "YouTube":      "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/youtube.svg",
    # Paste your base64 strings below (generated from assets/ folder):
    "JioHotstar":   "",   # REPLACE with: data:image/png;base64,<your_b64>
    "SonyLiv":      "",   # REPLACE with: data:image/png;base64,<your_b64>
    "ZEE5":         "",   # REPLACE with: data:image/png;base64,<your_b64>
    "Disney+ Hotstar": "", # alias for old entries — same as JioHotstar b64
    "Other":        "",
    "":             "",
}

PLATFORMS = ["", "Netflix", "Prime Video", "JioHotstar", "SonyLiv", "ZEE5", "YouTube", "Other"]

GENRES = [
    "", "Action", "Adventure", "Animation", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "Horror",
    "Romance", "Sci-Fi", "Thriller", "Other",
]

LANGUAGES = ["", "Hindi", "English", "Tamil", "Telugu", "Malayalam",
             "Kannada", "Bengali", "Marathi", "Other"]


# -------- DISPLAY HELPERS --------

def platform_badge(platform: str) -> str:
    platform = (platform or "").strip()
    # Alias old name → new logo
    lookup = platform if platform != "Disney+ Hotstar" else "JioHotstar"
    logo_url = PLATFORM_LOGOS.get(lookup, "")
    if logo_url:
        return (
            f'<img src="{logo_url}" '
            f'style="vertical-align:middle;margin-right:5px;border-radius:3px;" '
            f'width="18" height="18">'
            f'<span>{platform}</span>'
        )
    return platform


def rating_stars(rating) -> str:
    if rating is None or (isinstance(rating, float) and pd.isna(rating)):
        return "–"
    try:
        r = float(rating)
    except (ValueError, TypeError):
        return "–"
    stars = max(1, min(5, int(round(r / 2.0))))
    return (
        f'<span style="color:#f59e0b;font-size:1rem;">{"★"*stars}{"☆"*(5-stars)}</span>'
        f'<span style="font-size:0.75rem;color:#6b7280;margin-left:3px;">({int(r)})</span>'
    )


def status_badge(status: str) -> str:
    s = (status or "").lower()
    cfg = {
        "watched":  ("#16a34a", "✓ Watched"),
        "watching": ("#f97316", "▶ Watching"),
        "plan":     ("#3b82f6", "☰ Plan"),
    }
    color, label = cfg.get(s, ("#9ca3af", status or "–"))
    return (
        f'<span style="background:{color};color:#fff;padding:2px 9px;'
        f'border-radius:999px;font-size:0.72rem;font-weight:500;">{label}</span>'
    )


def recommend_badge(recommend: str) -> str:
    r = (recommend or "").lower()
    if r == "yes":
        return '<span style="background:#16a34a;color:#fff;padding:2px 9px;border-radius:999px;font-size:0.72rem;">👍 Yes</span>'
    if r == "no":
        return '<span style="background:#6b7280;color:#fff;padding:2px 9px;border-radius:999px;font-size:0.72rem;">👎 No</span>'
    return ""


# -------- GOOGLE SHEETS HELPERS --------

@st.cache_resource
def get_worksheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=scopes
        )
    else:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_TITLE).sheet1


COLUMNS = ["timestamp", "added_by", "title", "type", "genre",
           "platform", "status", "rating", "recommend",
           "watched_year", "language", "comments"]


def empty_df():
    return pd.DataFrame(columns=COLUMNS)


def read_sheet_as_df(ws):
    data = ws.get_all_records()
    if not data:
        return empty_df()
    df = pd.DataFrame(data)
    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def append_row(ws, row_dict):
    ws.append_row(
        [row_dict.get(c, "") for c in COLUMNS],
        value_input_option="USER_ENTERED"
    )


# -------- PAGE: ADD ENTRY --------

def page_add_entry(ws):
    st.subheader("Add a new entry")
    st.caption("Fill in what you've watched — takes about 10 seconds.")

    # ---- Name persistence via session state ----
    if "saved_name" not in st.session_state:
        st.session_state.saved_name = ""

    with st.form("add_entry_form", clear_on_submit=True):

        # Row 1: Name + Title side by side
        c1, c2 = st.columns(2)
        with c1:
            added_by = st.text_input("Your name *", value=st.session_state.saved_name,
                                     placeholder="e.g. Pankaj")
        with c2:
            title = st.text_input("Title *", placeholder="e.g. Mirzapur Season 3")

        # Row 2: Type + Platform + Status — all in one row
        c3, c4, c5 = st.columns(3)
        with c3:
            media_type = st.selectbox("Type", ["movie", "series"])
        with c4:
            platform = st.selectbox("Platform", PLATFORMS, index=0)
        with c5:
            status = st.selectbox("Status", ["watched", "watching", "plan"], index=0)

        # Row 3: Genre + Language side by side
        c6, c7 = st.columns(2)
        with c6:
            genre = st.selectbox("Genre", GENRES, index=0)
        with c7:
            language = st.selectbox("Language", LANGUAGES, index=0)

        # Row 4: Rating + Recommend — only if watched/watching
        rating = None
        recommend = ""
        if status != "plan":
            c8, c9 = st.columns([2, 1])
            with c8:
                rating = st.slider("Rating (1–10)", 1, 10, 8)
            with c9:
                recommend = st.radio("Recommend?", ["Yes", "No"],
                                     horizontal=True, index=0)
                recommend = recommend.lower()

        # Row 5: Comments (full width, optional — collapsed)
        with st.expander("Add a short review (optional)"):
            comments = st.text_area("Review / comments", "", label_visibility="collapsed")

        submitted = st.form_submit_button("💾 Save entry", use_container_width=True,
                                          type="primary")

    if submitted:
        errors = []
        if not added_by.strip():
            errors.append("Your name is required.")
        if not title.strip():
            errors.append("Title is required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            # Persist name for next entry
            st.session_state.saved_name = added_by.strip()

            row = {
                "timestamp":    datetime.now().isoformat(timespec="seconds"),
                "added_by":     added_by.strip(),
                "title":        title.strip(),
                "type":         media_type,
                "genre":        genre,
                "platform":     platform.strip(),
                "status":       status,
                "rating":       rating if rating is not None else "",
                "recommend":    recommend if status != "plan" else "",
                "watched_year": datetime.now().year,
                "language":     language,
                "comments":     comments.strip() if 'comments' in dir() else "",
            }
            try:
                append_row(ws, row)
                st.success(f"✅ **{title.strip()}** saved! Add another below.")
            except Exception as e:
                st.error("Error saving entry.")
                st.exception(e)


# -------- PAGE: BROWSE --------

def page_browse(ws):
    st.subheader("Browse all entries")

    # Refresh
    col_r, _ = st.columns([1, 6])
    with col_r:
        if st.button("🔄 Refresh"):
            st.cache_resource.clear()
            st.rerun()

    df = read_sheet_as_df(ws)

    if df.empty:
        st.info("No entries yet. Go to **Add Entry** to log your first movie or series.")
        return

    # ---- Metrics ----
    total   = len(df)
    movies  = int((df["type"] == "movie").sum())  if "type"   in df.columns else 0
    series  = int((df["type"] == "series").sum()) if "type"   in df.columns else 0
    avg_r   = df["rating"].mean()                 if "rating" in df.columns else float("nan")
    rec_pct = int(100 * (df["recommend"] == "yes").sum() / max(len(df[df["status"]=="watched"]),1)) \
              if "recommend" in df.columns else 0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total", total)
    m2.metric("Movies", movies)
    m3.metric("Series", series)
    m4.metric("Avg rating", f"{avg_r:.1f}" if pd.notna(avg_r) else "–")
    m5.metric("Recommend %", f"{rec_pct}%")

    # ---- Platform bar chart ----
    if "platform" in df.columns:
        pc = (df["platform"].fillna("Unknown")
              .replace("", "Unknown")
              .value_counts()
              .rename_axis("Platform")
              .reset_index(name="Count")
              .set_index("Platform"))
        st.bar_chart(pc)

    st.divider()

    # ---- Tonight's picks ----
    if "recommend" in df.columns and "status" in df.columns and "rating" in df.columns:
        top = df[
            (df["status"] == "watched") &
            (df["recommend"] == "yes") &
            (df["rating"] >= 8)
        ]
        if not top.empty:
            picks = top.sample(min(3, len(top)))
            st.markdown("### 🍿 Tonight's picks")
            pcols = st.columns(len(picks))
            for i, (_, row) in enumerate(picks.iterrows()):
                with pcols[i]:
                    st.markdown(
                        f"**{row.get('title','–')}**  \n"
                        f"{platform_badge(row.get('platform',''))} &nbsp; "
                        f"{rating_stars(row.get('rating'))}",
                        unsafe_allow_html=True,
                    )
            st.divider()

    # ---- Search (above filters) ----
    search_text = st.text_input("🔍 Search title", "", placeholder="Type to filter by title...")

    # ---- Filters ----
    with st.expander("Filters", expanded=False):
        fc1, fc2, fc3, fc4, fc5 = st.columns(5)
        with fc1:
            plat_f = st.multiselect("Platform",
                sorted(df["platform"].dropna().replace("","Unknown").unique().tolist()))
        with fc2:
            type_f = st.multiselect("Type",
                sorted(df["type"].dropna().unique().tolist()) if "type" in df.columns else [])
        with fc3:
            stat_f = st.multiselect("Status",
                sorted(df["status"].dropna().unique().tolist()) if "status" in df.columns else [])
        with fc4:
            rec_f  = st.multiselect("Recommend",
                sorted(df["recommend"].dropna().unique().tolist()) if "recommend" in df.columns else [])
        with fc5:
            genre_f = st.multiselect("Genre",
                sorted(df["genre"].dropna().replace("","Unknown").unique().tolist()) if "genre" in df.columns else [])

    # ---- Apply filters ----
    filtered = df.copy()
    if search_text:
        filtered = filtered[filtered["title"].str.contains(search_text, case=False, na=False)]
    if plat_f and "platform" in filtered.columns:
        filtered = filtered[filtered["platform"].isin(plat_f)]
    if type_f and "type" in filtered.columns:
        filtered = filtered[filtered["type"].isin(type_f)]
    if stat_f and "status" in filtered.columns:
        filtered = filtered[filtered["status"].isin(stat_f)]
    if rec_f and "recommend" in filtered.columns:
        filtered = filtered[filtered["recommend"].isin(rec_f)]
    if genre_f and "genre" in filtered.columns:
        filtered = filtered[filtered["genre"].isin(genre_f)]

    if "timestamp" in filtered.columns:
        filtered = filtered.sort_values("timestamp", ascending=False)

    st.caption(f"Showing **{len(filtered)}** of **{total}** entries")

    # ---- Export ----
    export_col, view_col = st.columns([1, 2])
    with export_col:
        csv_data = filtered.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Export CSV", csv_data, "watchlist.csv", "text/csv",
                           use_container_width=True)
    with view_col:
        view_mode = st.radio("View", ["Cards", "Table"], horizontal=True)

    st.divider()

    # ---- Render ----
    if view_mode == "Cards":
        _render_cards(filtered)
    else:
        _render_table(filtered)


def _render_cards(filtered):
    if filtered.empty:
        st.info("No entries match the current filters.")
        return

    for _, row in filtered.iterrows():
        title_txt     = row.get("title", "–")
        type_txt      = (row.get("type", "") or "").title()
        genre_txt     = row.get("genre", "") or "–"
        added_by_txt  = row.get("added_by", "") or "Unknown"
        comments_txt  = row.get("comments", "") or ""
        platform_html = platform_badge(row.get("platform", ""))
        rating_html   = rating_stars(row.get("rating"))
        status_html   = status_badge(row.get("status", ""))
        recommend_html= recommend_badge(row.get("recommend", ""))

        st.markdown(f"""
<div style="border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;
            margin-bottom:10px;background:#fafafa;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <span style="font-size:1.05rem;font-weight:600;">{title_txt}</span>
      <span style="font-size:0.82rem;color:#6b7280;margin-left:8px;">{type_txt} · {genre_txt}</span>
    </div>
    <div>{platform_html}</div>
  </div>
  <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
    {rating_html}
    {recommend_html}
    {status_html}
  </div>
  {"<div style='margin-top:7px;font-size:0.85rem;color:#374151;'>"+comments_txt+"</div>" if comments_txt else ""}
  <div style="margin-top:6px;font-size:0.75rem;color:#9ca3af;">Added by {added_by_txt}</div>
</div>
""", unsafe_allow_html=True)


def _render_table(filtered):
    if filtered.empty:
        st.info("No entries match the current filters.")
        return

    df_display = filtered.copy()

    if "platform"  in df_display.columns:
        df_display["platform"]  = df_display["platform"].apply(platform_badge)
    if "rating"    in df_display.columns:
        df_display["rating"]    = df_display["rating"].apply(rating_stars)
    if "status"    in df_display.columns:
        df_display["status"]    = df_display["status"].apply(status_badge)
    if "recommend" in df_display.columns:
        df_display["recommend"] = df_display["recommend"].apply(recommend_badge)

    col_order = ["title", "type", "genre", "platform", "rating",
                 "recommend", "status", "language", "added_by", "watched_year", "comments"]
    existing  = [c for c in col_order if c in df_display.columns]
    df_display = df_display[existing]

    # Rename headers for display
    df_display.columns = [c.replace("_", " ").title() for c in df_display.columns]

    st.markdown(
        "<style>table{width:100%;border-collapse:collapse;font-size:0.85rem;}"
        "th{background:#f3f4f6;padding:8px 10px;text-align:left;}"
        "td{padding:7px 10px;border-bottom:1px solid #f0f0f0;vertical-align:middle;}"
        "tr:hover{background:#f9fafb;}</style>",
        unsafe_allow_html=True,
    )
    st.markdown(
        df_display.to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )


# -------- MAIN --------

def main():
    st.set_page_config(page_title="What Am I Watching?", page_icon="🎬", layout="wide")

    # App header
    st.title("🎬 What Am I Watching?")
    st.caption("A shared log for movies & web series across all OTT platforms. "
               "Share the URL with friends — everyone can add entries.")

    ws = get_worksheet()

    page = st.sidebar.radio("Navigate", ["Browse", "Add Entry"], index=0)

    st.sidebar.divider()
    st.sidebar.markdown(
        "**How it works**\n"
        "- Log what you watch in **Add Entry**\n"
        "- Browse and filter in **Browse**\n"
        "- Share this URL with friends to collaborate"
    )

    if page == "Add Entry":
        page_add_entry(ws)
    else:
        page_browse(ws)


if __name__ == "__main__":
    main()
