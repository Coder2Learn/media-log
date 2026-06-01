import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

PLATFORM_LOGOS = {
    "Netflix":          "https://cdn.simpleicons.org/netflix/E50914",
    "Prime Video":      "https://cdn.simpleicons.org/primevideo/00A8E1",
    "Disney+ Hotstar":  "https://cdn.simpleicons.org/disneyplus/113CCF",
    "JioCinema":        "https://cdn.simpleicons.org/jio/0078FF",
    "YouTube":          "https://cdn.simpleicons.org/youtube/FF0000",
    "Other":            "",
    "":                 "",
}


def platform_badge(platform: str) -> str:
    """Return HTML for platform logo + name."""
    logo_url = PLATFORM_LOGOS.get(platform, "")
    if logo_url:
        return (
            f'<img src="{logo_url}" '
            f'style="vertical-align:middle; margin-right:4px;" '
            f'width="18" height="18">'
            f'{platform}'
        )
    return platform or ""

# -------- CONFIG --------
SPREADSHEET_TITLE = "MediaLog"   # Google Sheets file name
SERVICE_ACCOUNT_FILE = "media-log-service-account.json"  # your JSON key filename


@st.cache_resource
def get_worksheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # Prefer secrets (Streamlit Cloud), fall back to local JSON for dev
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

    # Basic type cleanup
    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    return df


def append_row(ws, row_dict):
    # Order must match the header row in the sheet
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


def main():
    st.set_page_config(page_title="Media Log", layout="wide")
    st.title("🎬 Media Log")

    ws = get_worksheet()
    page = st.sidebar.radio(
    "Go to",
    ["Add Entry", "Browse"],
    index=1,   # 0 = Add Entry, 1 = Browse
    )

    if page == "Add Entry":
        st.subheader("Add a new movie / series")

        with st.form("add_entry_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                added_by = st.text_input("Your name *")
                title = st.text_input("Title *")
                media_type = st.selectbox("Type *", ["Movie", "WebSeries"])
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
                    ["", "Netflix", "Prime Video", "Disney+ Hotstar", "SonyLiv", "YouTube", "Zee5", "Other"],
                    index=0,
                )
                status = st.selectbox(
                    "Status",
                    ["Watched", "Watching Currently", "Plan to Watch"],
                    index=0,
                )
                rating = st.slider("Rating", 1, 10, 8)
                recommend = st.selectbox("Would you recommend it?", ["Yes", "NO"])

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
                    "rating": rating,
                    "recommend": recommend,
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

        df = read_sheet_as_df(ws)

        if df.empty:
            st.info("No entries yet. Go to 'Add Entry' and create the first one.")
        else:
            # --- Summary metrics ---
            total = len(df)
            movies = (df["type"] == "movie").sum()
            series = (df["type"] == "series").sum()
            avg_rating = df["rating"].mean()
            recommended_count = (df["recommend"] == "yes").sum()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total entries", total)
            c2.metric("Movies", int(movies))
            c3.metric("Series", int(series))
            c4.metric("Avg rating", f"{avg_rating:.1f}" if pd.notna(avg_rating) else "–")

            # --- Filters + search ---
            with st.expander("Filters", expanded=False):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    platform_filter = st.multiselect(
                        "Platform", sorted(df["platform"].dropna().unique().tolist())
                    )
                with col2:
                    type_filter = st.multiselect(
                        "Type", sorted(df["type"].dropna().unique().tolist())
                    )
                with col3:
                    status_filter = st.multiselect(
                        "Status", sorted(df["status"].dropna().unique().tolist())
                    )
                with col4:
                    recommend_filter = st.multiselect(
                        "Recommend", sorted(df["recommend"].dropna().unique().tolist())
                    )

                col5, col6 = st.columns([2, 1])
                with col5:
                    search_text = st.text_input("Search in title", "").strip()
                with col6:
                    genre_filter = st.multiselect(
                        "Genre", sorted(df["genre"].dropna().unique().tolist())
                    )

            filtered = df.copy()
            if platform_filter:
                filtered = filtered[filtered["platform"].isin(platform_filter)]
            if type_filter:
                filtered = filtered[filtered["type"].isin(type_filter)]
            if status_filter:
                filtered = filtered[filtered["status"].isin(status_filter)]
            if recommend_filter:
                filtered = filtered[filtered["recommend"].isin(recommend_filter)]
            if genre_filter:
                filtered = filtered[filtered["genre"].isin(genre_filter)]
            if search_text:
                filtered = filtered[filtered["title"].str.contains(search_text, case=False, na=False)]

            st.write(f"Total entries: {len(df)} | After filters: {len(filtered)}")

            # Sort by timestamp descending if available
            if "timestamp" in filtered.columns:
                filtered = filtered.sort_values("timestamp", ascending=False)

            # Prepare a display copy so we don't mess with the raw data
            df_display = filtered.copy()

            # Apply platform logos
            if "platform" in df_display.columns:
                df_display["platform"] = df_display["platform"].apply(platform_badge)

            # Optionally hide technical columns from the table
            for col_to_drop in ["timestamp"]:
                if col_to_drop in df_display.columns:
                    df_display = df_display.drop(columns=[col_to_drop])

            # Render as HTML so the <img> tags are honored
            st.markdown(
                df_display.to_html(escape=False, index=False),
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()