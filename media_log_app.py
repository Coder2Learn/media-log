import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound
from datetime import datetime
import random

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
SPREADSHEET_TITLE    = "MediaLog"
SERVICE_ACCOUNT_FILE = "media-log-service-account.json"
TMDB_BASE            = "https://api.themoviedb.org/3"
TMDB_IMG_BASE        = "https://image.tmdb.org/t/p/w200"
PAGE_SIZE            = 100

PLATFORM_LOGOS = {
    "Netflix":         "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/netflix.svg",
    "Prime Video":     "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/primevideo.svg",
    "YouTube":         "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/youtube.svg",
    "JioHotstar":      "",
    "SonyLiv":         "",
    "ZEE5":            "",
    "Disney+ Hotstar": "",
    "Other":           "",
    "":                "",
}

PLATFORMS = ["", "Netflix", "Prime Video", "JioHotstar", "SonyLiv", "ZEE5", "YouTube", "Other"]

GENRES_LIST = [
    "Action", "Adventure", "Animation", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "Horror",
    "Romance", "Sci-Fi", "Thriller", "Other",
]

LANGUAGES = ["", "Hindi", "English", "Tamil", "Telugu", "Malayalam",
             "Kannada", "Bengali", "Marathi", "Other"]

COLUMNS = [
    "timestamp", "added_by", "title", "type", "genre",
    "platform", "status", "rating", "recommend",
    "watched_year", "language", "comments", "poster_url",
]

VOTE_COLUMNS = ["entry_id", "voter_name", "vote"]

# TMDB genre id map
TMDB_GENRE_MAP = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 27: "Horror", 10749: "Romance", 878: "Sci-Fi",
    53: "Thriller", 10759: "Action", 10762: "Animation", 10765: "Sci-Fi",
    10766: "Drama", 10767: "Other", 10768: "Other",
}


# ─────────────────────────────────────────────
#  TMDB HELPER
# ─────────────────────────────────────────────
def tmdb_search(title: str, media_type: str) -> dict:
    key = st.secrets.get("tmdb_api_key", "")
    if not key or not title.strip():
        return {}
    t = "tv" if media_type == "series" else "movie"
    try:
        r = requests.get(
            f"{TMDB_BASE}/search/{t}",
            params={"api_key": key, "query": title.strip(), "language": "en-US", "page": 1},
            timeout=5,
        )
        results = r.json().get("results", [])
        if not results:
            return {}
        top = results[0]
        date_field = "first_air_date" if t == "tv" else "release_date"
        year = (top.get(date_field, "") or "")[:4]
        genre_ids = top.get("genre_ids", [])
        genres = list(dict.fromkeys(TMDB_GENRE_MAP.get(gid, "Other") for gid in genre_ids[:3]))
        poster = ""
        if top.get("poster_path"):
            poster = TMDB_IMG_BASE + top["poster_path"]
        name = top.get("title") or top.get("name") or title
        return {"year": year, "genres": genres, "poster": poster, "name": name}
    except Exception:
        return {}


# ─────────────────────────────────────────────
#  DISPLAY HELPERS
# ─────────────────────────────────────────────
def platform_badge(platform: str) -> str:
    p = (platform or "").strip()
    lookup = "JioHotstar" if p == "Disney+ Hotstar" else p
    logo = PLATFORM_LOGOS.get(lookup, "")
    if logo:
        return (
            f'<img src="{logo}" width="14" height="14" '
            f'style="vertical-align:middle;margin-right:4px;border-radius:2px;">'
            f'<span style="color:inherit;">{p}</span>'
        )
    return f'<span style="color:inherit;">{p}</span>' if p else "—"


def rating_stars(rating) -> str:
    if rating is None or (isinstance(rating, float) and pd.isna(rating)):
        return "—"
    try:
        r = float(rating)
    except (ValueError, TypeError):
        return "—"
    stars = max(1, min(5, int(round(r / 2.0))))
    return (
        f'<span style="color:#f59e0b;">{"★"*stars}{"☆"*(5-stars)}</span>'
        f'<span style="font-size:0.75rem;color:#6b7280;margin-left:3px;">({int(r)})</span>'
    )


def status_badge(status: str) -> str:
    cfg = {
        "watched":  ("#16a34a", "✓ Watched"),
        "watching": ("#f97316", "▶ Watching"),
        "plan":     ("#3b82f6", "☰ Plan"),
    }
    color, label = cfg.get((status or "").lower(), ("#9ca3af", status or "—"))
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:999px;font-size:0.72rem;font-weight:500;">{label}</span>'
    )


def recommend_badge(recommend: str) -> str:
    r = (recommend or "").lower()
    if r == "yes":
        return '<span style="background:#16a34a;color:#fff;padding:2px 8px;border-radius:999px;font-size:0.72rem;font-weight:500;">👍 Yes</span>'
    if r == "no":
        return '<span style="background:#6b7280;color:#fff;padding:2px 8px;border-radius:999px;font-size:0.72rem;font-weight:500;">👎 No</span>'
    return ""


def community_bar(yes_count: int, no_count: int) -> str:
    total = yes_count + no_count
    if total == 0:
        return '<span style="font-size:0.75rem;color:#9ca3af;font-style:italic;">No community votes yet</span>'
    pct_yes = int(round(100 * yes_count / total))
    pct_no  = 100 - pct_yes
    return f"""
<div style="font-size:0.75rem;margin-top:4px;">
  <span style="color:#16a34a;font-weight:600;">👍 {yes_count}</span>
  &nbsp;·&nbsp;<span style="color:#9ca3af;font-weight:600;">👎 {no_count}</span>
  &nbsp;·&nbsp;<span style="color:#9ca3af;">{pct_yes}% recommend</span>
  <div style="display:flex;height:4px;border-radius:999px;overflow:hidden;margin-top:3px;background:#374151;">
    <div style="width:{pct_yes}%;background:#16a34a;"></div>
    <div style="width:{pct_no}%;background:#4b5563;"></div>
  </div>
</div>"""


# ─────────────────────────────────────────────
#  GOOGLE SHEETS
# ─────────────────────────────────────────────
@st.cache_resource
def get_sheets():
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
    client  = gspread.authorize(creds)
    sh      = client.open(SPREADSHEET_TITLE)
    entries = sh.sheet1

    # Auto-create Votes tab if missing
    try:
        votes = sh.worksheet("Votes")
    except WorksheetNotFound:
        votes = sh.add_worksheet(title="Votes", rows=1000, cols=3)
        votes.append_row(["entry_id", "voter_name", "vote"])

    return entries, votes


def empty_df():
    return pd.DataFrame(columns=COLUMNS)


def empty_votes_df():
    return pd.DataFrame(columns=VOTE_COLUMNS)


@st.cache_data(ttl=30)
def read_entries(_ws) -> pd.DataFrame:
    data = _ws.get_all_records()
    if not data:
        return empty_df()
    df = pd.DataFrame(data)
    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if "entry_id" not in df.columns:
        df.insert(0, "entry_id", range(2, 2 + len(df)))
    # Normalise type column to lowercase for consistent counting
    if "type" in df.columns:
        df["type"] = df["type"].str.strip().str.lower()
    if "status" in df.columns:
        df["status"] = df["status"].str.strip().str.lower()
    if "recommend" in df.columns:
        df["recommend"] = df["recommend"].str.strip().str.lower()
    return df


@st.cache_data(ttl=30)
def read_votes(_ws) -> pd.DataFrame:
    data = _ws.get_all_records()
    if not data:
        return empty_votes_df()
    return pd.DataFrame(data)


def build_vote_summary(votes_df: pd.DataFrame) -> dict:
    summary = {}
    if votes_df.empty or "entry_id" not in votes_df.columns:
        return summary
    for _, row in votes_df.iterrows():
        try:
            eid  = int(row["entry_id"])
            vote = str(row.get("vote", "")).strip().lower()
        except (ValueError, TypeError):
            continue
        if eid not in summary:
            summary[eid] = {"yes": 0, "no": 0}
        if vote == "yes":
            summary[eid]["yes"] += 1
        elif vote == "no":
            summary[eid]["no"] += 1
    return summary


def already_voted(votes_df: pd.DataFrame, entry_id: int, voter_name: str) -> bool:
    if votes_df.empty:
        return False
    mask = (
        (votes_df["entry_id"].astype(str) == str(entry_id)) &
        (votes_df["voter_name"].str.strip().str.lower() == voter_name.strip().lower())
    )
    return bool(mask.any())


def cast_vote(votes_ws, entry_id: int, voter_name: str, vote: str):
    votes_ws.append_row(
        [entry_id, voter_name.strip(), vote],
        value_input_option="USER_ENTERED",
    )


def append_row(ws, row_dict: dict):
    ws.append_row(
        [row_dict.get(c, "") for c in COLUMNS],
        value_input_option="USER_ENTERED",
    )


# ─────────────────────────────────────────────
#  SIDEBAR  (shared across all pages)
# ─────────────────────────────────────────────
def render_sidebar():
    """Render sidebar navigation + single name input. Returns (page, name)."""
    page = st.sidebar.radio("Navigate", ["Browse", "Add Entry", "Reports"], index=0)
    st.sidebar.divider()

    # Single name field — syncs to saved_name, voter_name everywhere
    stored = st.session_state.get("user_name", "")
    name_in = st.sidebar.text_input(
        "Your name",
        value=stored,
        placeholder="e.g. Pankaj",
        help="Used for adding entries and for voting. Enter once.",
        key="sidebar_name_widget",
    )
    name = name_in.strip()
    if name:
        st.session_state["user_name"]    = name
        st.session_state["saved_name"]   = name
        st.session_state["voter_name"]   = name
        st.session_state["sidebar_name"] = name

    st.sidebar.divider()
    st.sidebar.markdown(
        "**How it works**\n"
        "- Log what you watch in **Add Entry**\n"
        "- Browse & filter in **Browse**\n"
        "- 👍/👎 vote on any entry\n"
        "- See charts in **Reports**\n"
        "- Share this URL with friends"
    )
    return page, name


# ─────────────────────────────────────────────
#  PAGE: ADD ENTRY
# ─────────────────────────────────────────────
def page_add_entry(entries_ws, current_name: str):
    st.subheader("Add a new entry")
    st.caption("Fill in what you've watched — takes about 10 seconds.")

    # ── TMDB autofill (outside form — needs interactivity) ──────────
    with st.expander("🔍 Auto-fill from TMDB (optional)", expanded=False):
        af1, af2, af3 = st.columns([4, 1, 1])
        with af1:
            tmdb_q = st.text_input(
                "Search title on TMDB",
                placeholder="e.g. Inception — type then click Search",
                key="tmdb_title_input",
            )
        with af2:
            tmdb_t = st.selectbox("Type", ["movie", "series"], key="tmdb_type_input")
        with af3:
            st.write("")
            st.write("")
            do_search = st.button("Search", key="tmdb_search_btn", use_container_width=True)

        # FIX #6: trigger search on button click only (Enter on text_input
        # inside an expander cannot reliably fire; button is the clear trigger)
        if do_search:
            if tmdb_q.strip():
                with st.spinner("Searching TMDB…"):
                    result = tmdb_search(tmdb_q.strip(), tmdb_t)
                if result:
                    st.session_state["tmdb_result"]    = result
                    st.session_state["tmdb_query"]     = tmdb_q.strip()
                    st.session_state["tmdb_type_sel"]  = tmdb_t
                else:
                    st.warning("No results found. Try a different spelling.")
                    st.session_state.pop("tmdb_result", None)
            else:
                st.warning("Please enter a title to search.")

        # Show result card if we have one
        if "tmdb_result" in st.session_state:
            res = st.session_state["tmdb_result"]
            rc1, rc2 = st.columns([1, 4])
            with rc1:
                if res.get("poster"):
                    st.image(res["poster"], width=80)
            with rc2:
                st.success(
                    f"**{res.get('name', st.session_state.get('tmdb_query',''))}** "
                    f"({res.get('year', '?')})  \n"
                    f"Genres: {', '.join(res.get('genres', []))}"
                )
                # FIX #7: use_data button sets session state then reruns
                #          so the form below picks up prefill values
                if st.button("✅ Use this data", key="tmdb_use_btn"):
                    st.session_state["pf_title"]  = res.get("name", st.session_state.get("tmdb_query", ""))
                    st.session_state["pf_year"]   = res.get("year", "")
                    st.session_state["pf_genres"] = res.get("genres", [])
                    st.session_state["pf_type"]   = st.session_state.get("tmdb_type_sel", "movie")
                    st.session_state["pf_poster"] = res.get("poster", "")
                    st.session_state.pop("tmdb_result", None)
                    st.rerun()

    # Read pre-fill values (set by "Use this data" or cleared after use)
    pf_title  = st.session_state.pop("pf_title",  "")
    pf_year   = st.session_state.pop("pf_year",   "")
    pf_genres = st.session_state.pop("pf_genres", [])
    pf_type   = st.session_state.pop("pf_type",   "movie")
    pf_poster = st.session_state.pop("pf_poster", "")

    # If prefill triggered, store poster separately so form can pass it through
    if pf_poster:
        st.session_state["pending_poster"] = pf_poster

    # ── Main form ───────────────────────────────────────────────────
    with st.form("add_entry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            # FIX #3: name pre-filled from sidebar; field is editable but defaults to sidebar value
            added_by = st.text_input(
                "Your name *",
                value=current_name,
                placeholder="e.g. Pankaj",
            )
        with c2:
            title = st.text_input(
                "Title *",
                value=pf_title,
                placeholder="e.g. Mirzapur Season 3",
                help="Use original title if possible. Check if entry is already added.",
            )

        c3, c4, c5 = st.columns(3)
        with c3:
            type_opts = ["movie", "series"]
            type_idx  = type_opts.index(pf_type) if pf_type in type_opts else 0
            media_type = st.selectbox("Type", type_opts, index=type_idx)
        with c4:
            platform = st.selectbox(
                "Platform", PLATFORMS, index=0,
                help="Pick the main platform where you watched it.",
            )
        with c5:
            status = st.selectbox("Status", ["watched", "watching", "plan"], index=0)

        c6, c7 = st.columns(2)
        with c6:
            valid_pf_g = [g for g in pf_genres if g in GENRES_LIST]
            genre_sel  = st.multiselect(
                "Genre",
                options=GENRES_LIST,
                default=valid_pf_g,
                help="Select all genres that apply.",
            )
        with c7:
            language = st.selectbox("Language", LANGUAGES, index=0)

        # Hide rating / recommend / year for "plan"
        rating       = None
        recommend    = ""
        watched_year = datetime.now().year

        if status != "plan":
            c8, c9, c10 = st.columns([2, 1, 1])
            with c8:
                rating = st.slider("Rating (1–10)", 1, 10, 8)
            with c9:
                recommend = st.radio(
                    "Recommend?", ["Yes", "No"], horizontal=True, index=0
                ).lower()
            with c10:
                try:
                    yr_default = int(pf_year) if pf_year else datetime.now().year
                except ValueError:
                    yr_default = datetime.now().year
                watched_year = st.number_input(
                    "Year watched",
                    min_value=1990,
                    max_value=datetime.now().year + 1,
                    value=yr_default,
                    step=1,
                )

        with st.expander("Add a short review (optional)"):
            comments = st.text_area("Review / comments", "", label_visibility="collapsed")

        submitted = st.form_submit_button(
            "💾 Save entry", use_container_width=True, type="primary"
        )

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
            # Update sidebar name if user changed it in form
            if added_by.strip():
                st.session_state["user_name"]  = added_by.strip()
                st.session_state["voter_name"] = added_by.strip()

            # Retrieve poster that was stashed before form render
            poster_url = st.session_state.pop("pending_poster", "")

            row = {
                "timestamp":    datetime.now().isoformat(timespec="seconds"),
                "added_by":     added_by.strip(),
                "title":        title.strip(),
                "type":         media_type,
                "genre":        ", ".join(genre_sel) if genre_sel else "",
                "platform":     platform.strip(),
                "status":       status,
                "rating":       rating if rating is not None else "",
                "recommend":    recommend if status != "plan" else "",
                "watched_year": watched_year if status != "plan" else "",
                "language":     language,
                "comments":     comments.strip() if comments else "",
                "poster_url":   poster_url,
            }
            try:
                append_row(entries_ws, row)
                read_entries.clear()
                st.success(f"✅ **{title.strip()}** saved! Add another below.")
            except Exception as e:
                st.error("Error saving entry.")
                st.exception(e)


# ─────────────────────────────────────────────
#  PAGE: BROWSE
# ─────────────────────────────────────────────
def page_browse(entries_ws, votes_ws):
    col_r, _ = st.columns([1, 9])
    with col_r:
        if st.button("🔄 Refresh"):
            read_entries.clear()
            read_votes.clear()
            st.rerun()

    df           = read_entries(entries_ws)
    votes_df     = read_votes(votes_ws)
    vote_summary = build_vote_summary(votes_df)

    if df.empty:
        st.info("No entries yet. Go to **Add Entry** to log your first movie or series.")
        return

    # ── FIX #1: correct movie/series count ────────────────────────
    # After read_entries normalises to lowercase, compare lowercase
    total  = len(df)
    movies = int((df["type"].str.lower() == "movie").sum())  if "type" in df.columns else 0
    series = int((df["type"].str.lower() == "series").sum()) if "type" in df.columns else 0
    avg_r  = df["rating"].mean() if "rating" in df.columns else float("nan")
    watched = df[df.get("status", pd.Series(dtype=str)).str.lower() == "watched"] \
        if "status" in df.columns else df
    rec_pct = (
        int(100 * (watched["recommend"].str.lower() == "yes").sum() / max(len(watched), 1))
        if "recommend" in df.columns else 0
    )
    total_cvotes = sum(v["yes"] + v["no"] for v in vote_summary.values())

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total",           total)
    m2.metric("Movies",          movies)
    m3.metric("Series",          series)
    m4.metric("Avg Rating",      f"{avg_r:.1f}" if pd.notna(avg_r) else "–")
    m5.metric("Recommend %",     f"{rec_pct}%")
    m6.metric("Community Votes", total_cvotes)

    st.divider()

    # ── FIX #2: Tonight's picks — truly random, excludes current user ──
    voter_name = st.session_state.get("voter_name", "").strip()
    if all(c in df.columns for c in ["recommend", "status", "rating"]):
        top_pool = df[
            (df["status"].str.lower() == "watched") &
            (df["recommend"].str.lower() == "yes") &
            (pd.to_numeric(df["rating"], errors="coerce") >= 8)
        ]
        # Exclude entries added by the current user
        if voter_name and "added_by" in top_pool.columns:
            top_pool = top_pool[top_pool["added_by"].str.strip().str.lower() != voter_name.lower()]

        if not top_pool.empty:
            st.markdown("### 🍿 Tonight's picks")
            st.caption("Top-rated, community-recommended picks (not added by you).")
            # Use random.sample for true randomness on every page load
            sample_size = min(3, len(top_pool))
            picks = top_pool.sample(n=sample_size, random_state=random.randint(0, 99999))
            pcols = st.columns(sample_size)
            for i, (_, pr) in enumerate(picks.iterrows()):
                with pcols[i]:
                    poster = pr.get("poster_url", "") or ""
                    if poster:
                        st.image(poster, width=70)
                    st.markdown(
                        f"**{pr.get('title','–')}**  \n"
                        f"{platform_badge(pr.get('platform',''))} &nbsp; "
                        f"{rating_stars(pr.get('rating'))}",
                        unsafe_allow_html=True,
                    )
            st.divider()

    # ── Quick preset + my entries ──────────────────────────────────
    preset = st.radio(
        "Quick filter",
        ["All", "Recommended only", "High ratings (≥ 8)"],
        horizontal=True,
        key="browse_preset",
    )

    my_name   = st.session_state.get("user_name", "").strip()
    show_mine = st.checkbox("Show only my entries", value=False, key="show_mine_check")

    # ── Search ─────────────────────────────────────────────────────
    search_text = st.text_input("🔍 Search title", "", placeholder="Search title…")

    # ── Compact filters ────────────────────────────────────────────
    with st.expander("Filters", expanded=False):
        fc1, fc2, fc3, fc4, fc5 = st.columns(5)
        with fc1:
            plat_opts = sorted(df["platform"].dropna().replace("", "Unknown").unique().tolist()) \
                if "platform" in df.columns else []
            plat_f = st.multiselect("Platform", plat_opts, key="f_plat")
        with fc2:
            type_opts2 = sorted(df["type"].dropna().unique().tolist()) if "type" in df.columns else []
            type_f = st.multiselect("Type", type_opts2, key="f_type")
        with fc3:
            stat_opts = sorted(df["status"].dropna().unique().tolist()) if "status" in df.columns else []
            stat_f = st.multiselect("Status", stat_opts, key="f_stat")
        with fc4:
            rec_opts = sorted(df["recommend"].dropna().unique().tolist()) if "recommend" in df.columns else []
            rec_f = st.multiselect("Rec", rec_opts, key="f_rec")
        with fc5:
            all_genres = sorted(set(
                g.strip()
                for gs in df.get("genre", pd.Series(dtype=str)).dropna()
                for g in str(gs).split(",") if g.strip()
            ))
            genre_f = st.multiselect("Genre", all_genres, key="f_genre")

    # ── Apply filters ──────────────────────────────────────────────
    filtered = df.copy()

    if preset == "Recommended only":
        filtered = filtered[filtered.get("recommend", pd.Series(dtype=str)).str.lower() == "yes"]
    elif preset == "High ratings (≥ 8)":
        if "rating" in filtered.columns:
            filtered = filtered[pd.to_numeric(filtered["rating"], errors="coerce") >= 8]

    if show_mine and my_name:
        filtered = filtered[filtered["added_by"].str.strip().str.lower() == my_name.lower()]
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
        filtered = filtered[
            filtered["genre"].apply(
                lambda g: any(
                    sel.lower() in [x.strip().lower() for x in str(g).split(",")]
                    for sel in genre_f
                )
            )
        ]

    if "timestamp" in filtered.columns:
        filtered = filtered.sort_values("timestamp", ascending=False)

    st.caption(f"Showing **{len(filtered)}** of **{total}** entries")

    # ── Voter name ─────────────────────────────────────────────────
    # FIX #3: shown only if sidebar name is empty, so no duplicate prompt
    if not voter_name:
        voter_input = st.text_input(
            "Your name (for voting)",
            placeholder="Enter your name to vote",
            key="voter_name_input_browse",
        )
        if voter_input.strip():
            st.session_state["voter_name"] = voter_input.strip()
            st.session_state["user_name"]  = voter_input.strip()
    else:
        st.caption(f"Voting as: **{voter_name}**")

    # ── FIX #4: Export + View on same row, properly aligned ────────
    ec, vc = st.columns([2, 3])
    with ec:
        st.download_button(
            "⬇ Export CSV",
            filtered.to_csv(index=False).encode("utf-8"),
            "watchlist.csv",
            "text/csv",
            use_container_width=True,
        )
    with vc:
        view_mode = st.radio("View", ["Cards", "Table"], horizontal=True, key="view_radio")

    st.divider()

    # ── Pagination ─────────────────────────────────────────────────
    total_filtered = len(filtered)
    total_pages    = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
    if "browse_page" not in st.session_state:
        st.session_state.browse_page = 1
    st.session_state.browse_page = min(st.session_state.browse_page, total_pages)

    page_start = (st.session_state.browse_page - 1) * PAGE_SIZE
    page_data  = filtered.iloc[page_start : page_start + PAGE_SIZE]

    if total_pages > 1:
        pg1, pg2, pg3 = st.columns([1, 3, 1])
        with pg1:
            if st.button("◀ Prev", disabled=st.session_state.browse_page <= 1):
                st.session_state.browse_page -= 1
                st.rerun()
        with pg2:
            st.markdown(
                f"<div style='text-align:center;color:#9ca3af;font-size:0.85rem;padding-top:6px;'>"
                f"Page {st.session_state.browse_page} of {total_pages}</div>",
                unsafe_allow_html=True,
            )
        with pg3:
            if st.button("Next ▶", disabled=st.session_state.browse_page >= total_pages):
                st.session_state.browse_page += 1
                st.rerun()

    # ── Render ─────────────────────────────────────────────────────
    if view_mode == "Cards":
        _render_cards(page_data, vote_summary, votes_df, votes_ws)
    else:
        _render_table(page_data, vote_summary)


# ─────────────────────────────────────────────
#  PAGE: REPORTS
# ─────────────────────────────────────────────
def page_reports(entries_ws):
    st.subheader("📊 Reports")
    df = read_entries(entries_ws)
    if df.empty:
        st.info("No data yet.")
        return

    tab1, tab2, tab3 = st.tabs(["By Platform", "By Genre", "By Person"])

    with tab1:
        if "platform" in df.columns:
            pc = (
                df["platform"].fillna("Unknown").replace("", "Unknown")
                .value_counts()
                .rename_axis("Platform").reset_index(name="Count").set_index("Platform")
            )
            st.bar_chart(pc)
            st.dataframe(pc.reset_index(), use_container_width=True)

    with tab2:
        if "genre" in df.columns:
            exploded = (
                df["genre"].fillna("").apply(
                    lambda g: [x.strip() for x in str(g).split(",") if x.strip()]
                ).explode()
            )
            gc = (
                exploded.value_counts()
                .rename_axis("Genre").reset_index(name="Count").set_index("Genre")
            )
            st.bar_chart(gc)
            st.dataframe(gc.reset_index(), use_container_width=True)

    with tab3:
        if "added_by" in df.columns:
            ac = (
                df["added_by"].fillna("Unknown")
                .value_counts()
                .rename_axis("Person").reset_index(name="Entries").set_index("Person")
            )
            st.bar_chart(ac)
            avg_by = df.groupby("added_by")["rating"].mean().round(1).rename("Avg Rating")
            st.dataframe(avg_by.reset_index(), use_container_width=True)


# ─────────────────────────────────────────────
#  CARD RENDERER  (FIX #5: poster image shown)
# ─────────────────────────────────────────────
CARD_CSS = """<style>
.wlog-card{border:1px solid rgba(148,163,184,0.18);border-radius:10px;
  padding:10px 14px;margin-bottom:3px;background:var(--background-color,transparent);}
.wlog-card-title{font-size:1.02rem;font-weight:700;color:inherit;}
.wlog-card-meta{font-size:0.78rem;color:#94a3b8;margin-left:6px;}
.wlog-card-footer{margin-top:4px;font-size:0.72rem;color:#94a3b8;}
.wlog-card-review{margin-top:5px;font-size:0.83rem;color:#cbd5e1;}
.wlog-divider{border:none;border-top:1px solid rgba(148,163,184,0.10);margin:4px 0;}
</style>"""

_card_css_injected = False
def _inject_card_css():
    global _card_css_injected
    if not _card_css_injected:
        st.markdown(CARD_CSS, unsafe_allow_html=True)
        _card_css_injected = True


def _render_cards(filtered, vote_summary, votes_df, votes_ws):
    _inject_card_css()
    if filtered.empty:
        st.info("No entries match the current filters.")
        return

    voter_name = st.session_state.get("voter_name", "").strip()

    for idx, (_, row) in enumerate(filtered.iterrows()):
        entry_id       = int(row.get("entry_id", 0))
        title_txt      = row.get("title",    "—")
        type_txt       = (row.get("type",    "") or "").title()
        genre_txt      = row.get("genre",    "") or "—"
        added_by_txt   = row.get("added_by", "") or "Unknown"
        comments_txt   = row.get("comments", "") or ""
        poster_url     = row.get("poster_url", "") or ""
        platform_html  = platform_badge(row.get("platform", ""))
        rating_html    = rating_stars(row.get("rating"))
        status_html    = status_badge(row.get("status",    ""))
        recommend_html = recommend_badge(row.get("recommend", ""))

        counts   = vote_summary.get(entry_id, {"yes": 0, "no": 0})
        comm_bar = community_bar(counts["yes"], counts["no"])
        review_html = (
            f'<div class="wlog-card-review">💬 {comments_txt}</div>'
            if comments_txt else ""
        )

        # FIX #5: show poster thumbnail if available
        if poster_url:
            img_html = (
                f'<img src="{poster_url}" width="54" height="80" '
                f'style="border-radius:5px;object-fit:cover;flex-shrink:0;" '
                f'alt="poster" loading="lazy">'
            )
            card_inner = f"""
<div style="display:flex;gap:12px;align-items:flex-start;">
  {img_html}
  <div style="flex:1;min-width:0;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
      <div>
        <span class="wlog-card-title">{title_txt}</span>
        <span class="wlog-card-meta">{type_txt} · {genre_txt}</span>
      </div>
      <div style="display:flex;align-items:center;gap:5px;">{platform_html}</div>
    </div>
    <div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:5px;align-items:center;">
      {rating_html} {recommend_html} {status_html}
    </div>
    {review_html}
    <div style="margin-top:6px;">{comm_bar}</div>
    <div class="wlog-card-footer">Added by {added_by_txt}</div>
  </div>
</div>"""
        else:
            card_inner = f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start;">
  <div>
    <span class="wlog-card-title">{title_txt}</span>
    <span class="wlog-card-meta">{type_txt} · {genre_txt}</span>
  </div>
  <div style="display:flex;align-items:center;gap:5px;">{platform_html}</div>
</div>
<div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:5px;align-items:center;">
  {rating_html} {recommend_html} {status_html}
</div>
{review_html}
<div style="margin-top:6px;">{comm_bar}</div>
<div class="wlog-card-footer">Added by {added_by_txt}</div>"""

        st.markdown(
            f'<div class="wlog-card">{card_inner}</div>',
            unsafe_allow_html=True,
        )

        _render_vote_widget(entry_id, title_txt, voter_name,
                            votes_df, votes_ws, counts["yes"], counts["no"], idx)
        st.markdown('<hr class="wlog-divider">', unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  VOTE WIDGET
# ─────────────────────────────────────────────
def _render_vote_widget(entry_id, title_txt, voter_name,
                        votes_df, votes_ws, yes_cnt, no_cnt, card_idx):
    voted_key        = f"voted_{entry_id}"
    voted_in_sheet   = voter_name and already_voted(votes_df, entry_id, voter_name)
    voted_in_session = st.session_state.get(voted_key, None)

    lbl_col, yes_col, no_col, _ = st.columns([3, 1, 1, 5])

    with lbl_col:
        if not voter_name:
            st.markdown(
                '<span style="font-size:0.75rem;color:#9ca3af;">Enter name to vote</span>',
                unsafe_allow_html=True,
            )
        elif voted_in_sheet or voted_in_session:
            prior = voted_in_session or "previously"
            st.markdown(
                f'<span style="font-size:0.75rem;color:#9ca3af;">Your vote: <strong>{prior}</strong></span>',
                unsafe_allow_html=True,
            )

    if voter_name and not voted_in_sheet and not voted_in_session:
        with yes_col:
            if st.button("👍", key=f"yes_{entry_id}_{card_idx}", help=f"Recommend {title_txt}"):
                try:
                    cast_vote(votes_ws, entry_id, voter_name, "yes")
                    st.session_state[voted_key] = "👍 yes"
                    read_votes.clear()
                    st.rerun()
                except Exception as e:
                    st.error("Could not save vote.")
                    st.exception(e)
        with no_col:
            if st.button("👎", key=f"no_{entry_id}_{card_idx}", help=f"Skip {title_txt}"):
                try:
                    cast_vote(votes_ws, entry_id, voter_name, "no")
                    st.session_state[voted_key] = "👎 no"
                    read_votes.clear()
                    st.rerun()
                except Exception as e:
                    st.error("Could not save vote.")
                    st.exception(e)


# ─────────────────────────────────────────────
#  TABLE RENDERER
# ─────────────────────────────────────────────
def _render_table(filtered, vote_summary):
    if filtered.empty:
        st.info("No entries match the current filters.")
        return

    df_display = filtered.copy()

    def _comm_votes(row):
        eid    = int(row.get("entry_id", 0))
        counts = vote_summary.get(eid, {"yes": 0, "no": 0})
        total  = counts["yes"] + counts["no"]
        if total == 0:
            return "—"
        pct = int(round(100 * counts["yes"] / total))
        return f'👍{counts["yes"]} / 👎{counts["no"]} ({pct}%)'

    df_display["community_votes"] = df_display.apply(_comm_votes, axis=1)

    if "platform"  in df_display.columns:
        df_display["platform"]  = df_display["platform"].apply(platform_badge)
    if "rating"    in df_display.columns:
        df_display["rating"]    = df_display["rating"].apply(rating_stars)
    if "status"    in df_display.columns:
        df_display["status"]    = df_display["status"].apply(status_badge)
    if "recommend" in df_display.columns:
        df_display["recommend"] = df_display["recommend"].apply(recommend_badge)
    if "type" in df_display.columns:
        df_display["type"] = df_display["type"].str.title()

    col_order = ["title", "type", "genre", "platform", "rating",
                 "recommend", "community_votes", "status", "language",
                 "added_by", "watched_year"]
    existing   = [c for c in col_order if c in df_display.columns]
    df_display = df_display[existing]
    df_display.columns = [c.replace("_", " ").title() for c in df_display.columns]

    st.markdown(
        "<style>"
        "table{width:100%;border-collapse:collapse;font-size:0.84rem;}"
        "th{background:rgba(148,163,184,0.1);padding:7px 10px;text-align:left;}"
        "td{padding:6px 10px;border-bottom:1px solid rgba(148,163,184,0.12);vertical-align:middle;}"
        "tr:hover td{background:rgba(148,163,184,0.05);}"
        "</style>",
        unsafe_allow_html=True,
    )
    st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="What Am I Watching?",
        page_icon="🎬",
        layout="wide",
    )

    st.title("🎬 What Am I Watching?")
    st.caption(
        "A shared log for movies & web series across all OTT platforms. "
        "Share the URL — everyone can add entries and vote."
    )

    entries_ws, votes_ws = get_sheets()

    page, current_name = render_sidebar()

    if page == "Add Entry":
        page_add_entry(entries_ws, current_name)
    elif page == "Reports":
        page_reports(entries_ws)
    else:
        page_browse(entries_ws, votes_ws)


if __name__ == "__main__":
    main()
