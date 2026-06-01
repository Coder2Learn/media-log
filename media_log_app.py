import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
# TEMPORARY — remove after copying output
import base64, os
if os.path.exists("assets/jiohotstar.png"):
    for name, path in [("JioHotstar","assets/jiohotstar.png"),
                       ("Sony LIV","assets/sonyliv.png"),
                       ("ZEE5","assets/zee5.png")]:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.code(f'"{name}": "data:image/png;base64,{b64}"')
    st.stop()
# -------- CONFIG --------
SPREADSHEET_TITLE = "MediaLog"   # Google Sheets file name
SERVICE_ACCOUNT_FILE = "media-log-service-account.json"  # local JSON key (for dev)


# -------- PLATFORM ICONS (Simple Icons via jsDelivr) --------
GITHUB_RAW = "https://github.com/Coder2Learn/media-log/tree/de1ba4a9320278ae26cad8c0dc4061ce15b53338/assets"
PLATFORM_LOGOS = {
    "Netflix":          "https://cdn.simpleicons.org/netflix/E50914",
    "Prime Video":      "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/primevideo.svg",
    "YouTube":          "https://cdn.simpleicons.org/youtube/FF0000",
    "ZEE5": "data:image/png;base64,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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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"
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
                    ["", "Netflix", "Prime Video", "JioHotstar", "Sony LIV", "ZEE5", "YouTube", "Other"],
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