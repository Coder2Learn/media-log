import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# -------- CONFIG --------
SPREADSHEET_TITLE = "MediaLog"   # Google Sheets file name
SERVICE_ACCOUNT_FILE = "media-log-service-account.json"  # local JSON key (for dev)


# -------- PLATFORM ICONS (Simple Icons via jsDelivr) --------
PLATFORM_LOGOS = {
    "Netflix":          "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/netflix.svg",
    "Prime Video":      "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/primevideo.svg",
    "Disney+ Hotstar":  "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/disneyplus.svg",
    "JioCinema":        "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/jio.svg",
    "YouTube":          "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/youtube.svg",
    "Other":            "",
    "":                 "",
}


def platform_badge(platform: str) -> str:
    """Return HTML for platform logo + name."""
    platform = (platform or "").strip()
    logo_url = PLATFORM_LOGOS.get(platform, "")
    if logo_url:
        return (
            f'<img src="{logo_url}" '
            f'style="vertical-align:middle; margin-right:4px;" '
            f'width="18" height="18">'
            f'{platform}'
        )
    return platform


def rating_stars(rating) -> str:
    """Convert numeric rating (1-10) to 5-star HTML."""
    if rating is None or pd.isna(rating):
        return ""
    try:
        r = float(rating)
    except ValueError:
        return ""
    # Map 1–10 to 1–5 stars (rounded)
    stars = int(round(max(1.0, min(10.0, r)) / 2.0))
    stars = max(1, min(5, stars))
    filled = "★" * stars
    empty = "☆" * (5 - stars)
    return f'<span style="color:#facc15; font-weight:600;">{filled}{empty}</span> ' \
           f'<span style="font-size:0.8rem; color:#6b7280;">({int(r)})</span>'


def status_badge(status: str) -> str:
    """Colored pill for status."""
    s = (status or "").lower()
    if s == "watched":
        color = "#16a34a"   # green
        label = "Watched"
    elif s == "watching":
        color = "#f97316"   # orange
        label = "Watching"
    elif s == "plan":
        color = "#3b82f6"   # blue
        label = "Plan"
    else:
        color = "#6b7280"
        label = status or "Unknown"
    return (
        f'<span style="background-color:{color}; color:white; '
        f'padding:2px 8px; border-radius:999px; font-size:0.75rem;">'
        f'{label}</span>'
    )


def recommend_badge(recommend: str) -> str:
    """Badge for recommend yes/no."""
    r = (recommend or "").lower()
    if r == "yes":
        return (
            '<span style="background-color:#16a34a; color:white; '
            'padding:2px 8px; border-radius:999px; font-size:0.75rem;">'
            'Recommended</span>'
        )
    elif r == "no":
        return (
            '<span style="background-color:#6b7280; color:white; '
            'padding:2px 8px; border-radius:999px; font-size:0.75rem;">'
            'Skip</span>'
        )
    return ""


# -------- GOOGLE SHEETS HELPERS --------

@st.cache_resource
def get_worksheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # On Streamlit Cloud, use secrets; locally, use JSON file
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=scopes
        )
    else:
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=scopes
        )

    client = gspread.authorize(creds)
    sh = client.open(SPREADSHEET_TITLE)
    ws = sh.sheet1
    return ws


def empty_df():
    return pd.DataFrame(
        columns=[
            "timestamp",
            "added_by",
            "title",
            "type",
            "genre",
            "platform",
            "status",
            "rating",
            "recommend",
            "watched_year",
            "language",
            "comments",
        ]
    )


def read_sheet_as_df(ws):
    data = ws.get_all_records()
    if not data:
        return empty_df()
    df = pd.DataFrame(data)

    # Type cleanup
    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    return df


def append_row(ws, row_dict):
    values = [
        row_dict.get("timestamp", ""),
        row_dict.get("added_by", ""),
        row_dict.get("title", ""),
        row_dict.get("type", ""),
        row_dict.get("genre", ""),
        row_dict.get("platform", ""),
        row_dict.get("status", ""),
        row_dict.get("rating", ""),
        row_dict.get("recommend", ""),
        row_dict.get("watched_year", ""),
        row_dict.get("language", ""),
        row_dict.get("comments", ""),
    ]
    ws.append_row(values, value_input_option="USER_ENTERED")


# -------- MAIN APP --------

def main():
    st.set_page_config(page_title="Media Log", layout="wide")
    st.title("🎬 What Am I Watching?")

    ws = get_worksheet()

    # Default landing page: Browse
    page = st.sidebar.radio(
        "Go to",
        ["Add Entry", "Browse"],
        index=1,
    )

    if page == "Add Entry":
        st.subheader("Add a new movie / series")

        with st.form("add_entry_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                added_by = st.text_input("Your name *")
                title = st.text_input("Title *")
                media_type = st.selectbox("Type *", ["movie", "series"])
                genre = st.selectbox(
                    "Genre",
                    [
                        "",
                        "Action",
                        "Adventure",
                        "Comedy",
                        "Drama",
                        "Thriller",
                        "Horror",
                        "Romance",
                        "Sci-Fi",
                        "Fantasy",
                        "Documentary",
                        "Animation",
                        "Crime",
                        "Family",
                        "Other",
                    ],
                    index=0,
                )
            with col2:
                platform = st.selectbox(
                    "Platform",
                    ["", "Netflix", "Prime Video", "Disney+ Hotstar", "JioCinema", "YouTube", "Other"],
                    index=0,
                )
                status = st.selectbox(
                    "Status",
                    ["watched", "watching", "plan"],
                    index=0,
                )

            # Rating and recommend only if not "plan"
            rating = None
            recommend = ""
            if status != "plan":
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    rating = st.slider("Rating (1–10)", 1, 10, 8)
                with col_r2:
                    recommend = st.selectbox("Would you recommend it?", ["yes", "no"])

            watched_year = st.number_input(
                "Watched year (optional)",
                min_value=1900,
                max_value=2100,
                value=datetime.now().year,
            )
            language = st.text_input("Language (optional)", "")
            comments = st.text_area("Short review / comments", "")

            submitted = st.form_submit_button("Save entry")

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
                row = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "added_by": added_by.strip(),
                    "title": title.strip(),
                    "type": media_type,
                    "genre": genre.strip(),
                    "platform": platform.strip(),
                    "status": status,
                    "rating": rating if rating is not None else "",
                    "recommend": recommend if status != "plan" else "",
                    "watched_year": int(watched_year) if watched_year else "",
                    "language": language.strip(),
                    "comments": comments.strip(),
                }
                try:
                    append_row(ws, row)
                    st.success("Entry saved to Google Sheet.")
                except Exception as e:
                    st.error("Error saving entry.")
                    st.exception(e)

    else:  # Browse
        st.subheader("Browse all entries")

        # Refresh button
        refresh_col, _ = st.columns([1, 5])
        with refresh_col:
            if st.button("🔄 Refresh data"):
                st.cache_resource.clear()
                st.rerun()

        df = read_sheet_as_df(ws)

        if df.empty:
            st.info("No entries yet. Go to 'Add Entry' and create the first one.")
        else:
            # --- Summary metrics ---
            total = len(df)
            movies = (df["type"] == "movie").sum() if "type" in df.columns else 0
            series = (df["type"] == "series").sum() if "type" in df.columns else 0
            avg_rating = df["rating"].mean() if "rating" in df.columns else float("nan")
            recommended_count = (df["recommend"] == "yes").sum() if "recommend" in df.columns else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total entries", total)
            c2.metric("Movies", int(movies))
            c3.metric("Series", int(series))
            c4.metric("Avg rating", f"{avg_rating:.1f}" if pd.notna(avg_rating) else "–")

            # Simple platform count bar chart
            if "platform" in df.columns:
                platform_counts = (
                    df["platform"]
                    .fillna("Unknown")
                    .value_counts()
                    .rename_axis("platform")
                    .reset_index(name="count")
                    .set_index("platform")
                )
                st.bar_chart(platform_counts)

            # --- Filters + search ---
            with st.expander("Filters", expanded=False):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    platform_filter = st.multiselect(
                        "Platform", sorted(df["platform"].dropna().unique().tolist())
                    ) if "platform" in df.columns else []
                with col2:
                    type_filter = st.multiselect(
                        "Type", sorted(df["type"].dropna().unique().tolist())
                    ) if "type" in df.columns else []
                with col3:
                    status_filter = st.multiselect(
                        "Status", sorted(df["status"].dropna().unique().tolist())
                    ) if "status" in df.columns else []
                with col4:
                    recommend_filter = st.multiselect(
                        "Recommend", sorted(df["recommend"].dropna().unique().tolist())
                    ) if "recommend" in df.columns else []

                col5, col6 = st.columns([2, 1])
                with col5:
                    search_text = st.text_input("Search in title", "").strip()
                with col6:
                    genre_filter = st.multiselect(
                        "Genre", sorted(df["genre"].dropna().unique().tolist())
                    ) if "genre" in df.columns else []

            filtered = df.copy()
            if platform_filter and "platform" in filtered.columns:
                filtered = filtered[filtered["platform"].isin(platform_filter)]
            if type_filter and "type" in filtered.columns:
                filtered = filtered[filtered["type"].isin(type_filter)]
            if status_filter and "status" in filtered.columns:
                filtered = filtered[filtered["status"].isin(status_filter)]
            if recommend_filter and "recommend" in filtered.columns:
                filtered = filtered[filtered["recommend"].isin(recommend_filter)]
            if genre_filter and "genre" in filtered.columns:
                filtered = filtered[filtered["genre"].isin(genre_filter)]
            if search_text and "title" in filtered.columns:
                filtered = filtered[filtered["title"].str.contains(search_text, case=False, na=False)]

            st.write(f"Total entries: {len(df)} | After filters: {len(filtered)}")

            # Sort by timestamp descending if available
            if "timestamp" in filtered.columns:
                filtered = filtered.sort_values("timestamp", ascending=False)

            # View mode: table vs cards
            view_mode = st.radio(
                "View mode",
                ["Table", "Cards"],
                horizontal=True,
            )

            if view_mode == "Table":
                df_display = filtered.copy()

                # Apply logos, stars, badges for display only
                if "platform" in df_display.columns:
                    df_display["platform"] = df_display["platform"].apply(platform_badge)
                if "rating" in df_display.columns:
                    df_display["rating"] = df_display["rating"].apply(rating_stars)
                if "status" in df_display.columns:
                    df_display["status"] = df_display["status"].apply(status_badge)
                if "recommend" in df_display.columns:
                    df_display["recommend"] = df_display["recommend"].apply(recommend_badge)

                # Drop technical columns and reorder for readability
                cols_order = [
                    "title",
                    "type",
                    "genre",
                    "platform",
                    "rating",
                    "recommend",
                    "status",
                    "language",
                    "comments",
                    "added_by",
                    "watched_year",
                ]
                existing = [c for c in cols_order if c in df_display.columns]
                df_display = df_display[existing]

                # Render as HTML so logos/badges show
                st.markdown(
                    df_display.to_html(escape=False, index=False),
                    unsafe_allow_html=True,
                )

            else:  # Cards view
                for _, row in filtered.iterrows():
                    title = row.get("title", "")
                    platform_html = platform_badge(row.get("platform", ""))
                    type_txt = (row.get("type", "") or "").title()
                    genre_txt = row.get("genre", "") or "—"
                    rating_html = rating_stars(row.get("rating")) if "rating" in row else ""
                    status_html = status_badge(row.get("status", "")) if "status" in row else ""
                    recommend_html = recommend_badge(row.get("recommend", "")) if "recommend" in row else ""
                    comments_txt = row.get("comments", "") or ""
                    added_by_txt = row.get("added_by", "") or "Unknown"

                    card_html = f"""
<div style="
    border-radius:12px;
    padding:12px 16px;
    margin-bottom:12px;
    background-color:rgba(15,23,42,0.02);
    border:1px solid #e5e7eb;">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <div style="font-weight:600; font-size:1rem;">{title}</div>
    <div>{platform_html}</div>
  </div>
  <div style="margin-top:4px; font-size:0.9rem; color:#6b7280;">
    {type_txt} · {genre_txt}
  </div>
  <div style="margin-top:6px; display:flex; flex-wrap:wrap; gap:6px; align-items:center;">
    {rating_html}
    {recommend_html}
    {status_html}
  </div>
  <div style="margin-top:6px; font-size:0.85rem; color:#4b5563;">
    {comments_txt}
  </div>
  <div style="margin-top:4px; font-size:0.8rem; color:#9ca3af;">
    Added by {added_by_txt}
  </div>
</div>
"""
                    st.markdown(card_html, unsafe_allow_html=True)


if __name__ == "__main__":
    main()