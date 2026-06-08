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

# FIX 3: Expanded platform logos — covers all common spellings
PLATFORM_LOGOS = {
    "Netflix":           "https://cdn.simpleicons.org/netflix",
    "Prime Video":       "https://cdn.simpleicons.org/primevideo",
    "Amazon Prime":      "https://cdn.simpleicons.org/primevideo",
    "YouTube":           "https://cdn.simpleicons.org/youtube",
    "JioHotstar":        "https://cdn.simpleicons.org/hotstar",
    "Hotstar":           "https://cdn.simpleicons.org/hotstar",
    "Disney+ Hotstar":   "https://cdn.simpleicons.org/hotstar",
    "Disney+":           "https://cdn.simpleicons.org/disneyplus",
    "Sony LIV":          "https://cdn.simpleicons.org/sonyliv",
    "SonyLiv":           "https://cdn.simpleicons.org/sonyliv",
    "ZEE5":              "https://cdn.simpleicons.org/zee5",
    "Zee5":              "https://cdn.simpleicons.org/zee5",
    "Apple TV+":         "https://cdn.simpleicons.org/appletv",
}

# FIX 3: Featured platforms for "Don't Miss" sections — includes JioHotstar
FEATURED_PLATFORMS = ["Netflix", "Prime Video", "JioHotstar", "Sony LIV", "ZEE5"]

# Platform name normalizer — maps all variants to canonical name
PLATFORM_NORMALIZE = {
    "amazon prime":      "Prime Video",
    "amazon prime video":"Prime Video",
    "prime video":       "Prime Video",
    "hotstar":           "JioHotstar",
    "disney+ hotstar":   "JioHotstar",
    "jiohotstar":        "JioHotstar",
    "disney+":           "Disney+",
    "sonyliv":           "Sony LIV",
    "sony liv":          "Sony LIV",
    "zee5":              "ZEE5",
    "netflix":           "Netflix",
    "youtube":           "YouTube",
    "apple tv+":         "Apple TV+",
    "apple tv":          "Apple TV+",
}

PLATFORMS    = ["", "Netflix", "Prime Video", "JioHotstar", "Sony LIV", "ZEE5",
                "YouTube", "Disney+", "Apple TV+", "Other"]
GENRES_LIST  = ["Action","Adventure","Animation","Comedy","Crime","Documentary",
                "Drama","Family","Fantasy","Horror","Romance","Sci-Fi","Thriller","Other"]
LANGUAGES    = ["", "Hindi","English","Tamil","Telugu","Malayalam","Kannada",
                "Bengali","Marathi","Other"]

COLUMNS      = ["timestamp","added_by","title","type","genre","platform","status",
                "rating","recommend","watched_year","language","comments","poster_url"]
VOTE_COLUMNS = ["entry_id","voter_name","vote"]

TMDB_GENRE_MAP = {
    28:"Action", 12:"Adventure", 16:"Animation", 35:"Comedy", 80:"Crime",
    99:"Documentary", 18:"Drama", 10751:"Family", 14:"Fantasy", 27:"Horror",
    10749:"Romance", 878:"Sci-Fi", 53:"Thriller",
    10759:"Action", 10762:"Animation", 10765:"Sci-Fi",
    10766:"Drama", 10767:"Other", 10768:"Other",
}


# ─────────────────────────────────────────────
#  TMDB SEARCH — returns list of results
# ─────────────────────────────────────────────
def tmdb_search(title: str, media_type: str) -> list:
    """Return up to 10 TMDB results as a list of dicts."""
    key = st.secrets.get("tmdb_api_key", "")
    if not key or not title.strip():
        return []
    t = "tv" if "series" in media_type.lower() else "movie"
    try:
        r = requests.get(
            f"{TMDB_BASE}/search/{t}",
            params={
                "api_key":       key,
                "query":         title.strip(),
                "language":      "en-US",
                "page":          1,
                "include_adult": False,
            },
            timeout=8,
        )
        r.raise_for_status()
        results = r.json().get("results", [])[:10]
        out = []
        for item in results:
            date_field = "first_air_date" if t == "tv" else "release_date"
            year       = (item.get(date_field) or "")[:4]
            genre_ids  = item.get("genre_ids", [])
            genres     = list(dict.fromkeys(TMDB_GENRE_MAP.get(gid, "Other") for gid in genre_ids[:3]))
            poster     = (TMDB_IMG_BASE + item["poster_path"]) if item.get("poster_path") else ""
            name       = item.get("title") or item.get("name") or title
            out.append({"year": year, "genres": genres, "poster": poster, "name": name})
        return out
    except requests.HTTPError as e:
        st.warning(f"TMDB error {e.response.status_code} — check your API key.")
        return []
    except Exception:
        return []


# ─────────────────────────────────────────────
#  DISPLAY HELPERS
# ─────────────────────────────────────────────
def normalize_platform(platform: str) -> str:
    """Return canonical platform name for logo lookup."""
    return PLATFORM_NORMALIZE.get((platform or "").strip().lower(), (platform or "").strip())


def platform_badge(platform: str) -> str:
    """Return HTML badge with logo icon + platform name."""
    p      = (platform or "").strip()
    lookup = normalize_platform(p)
    logo   = PLATFORM_LOGOS.get(lookup, PLATFORM_LOGOS.get(p, ""))
    if logo:
        return (
            f'<img src="{logo}" width="14" height="14" '
            f'style="vertical-align:middle;margin-right:4px;border-radius:2px;" '
            f'alt="{p}">'
            f'<span style="color:inherit;font-size:0.8rem;">{p}</span>'
        )
    return f'<span style="color:inherit;font-size:0.8rem;">{p}</span>' if p else ""


def platform_logo_url(platform: str) -> str:
    """Return just the logo URL for a platform, or empty string."""
    lookup = normalize_platform(platform)
    return PLATFORM_LOGOS.get(lookup, PLATFORM_LOGOS.get((platform or "").strip(), ""))


def rating_stars(rating) -> str:
    if rating is None or (isinstance(rating, float) and pd.isna(rating)):
        return ""
    try:
        r = float(rating)
    except (ValueError, TypeError):
        return ""
    r     = max(0.0, min(10.0, r))
    stars = max(1, min(5, int(round(r / 2.0))))
    return (
        f'<span style="color:#f59e0b">{"★" * stars}{"☆" * (5 - stars)}</span>'
        f'<span style="font-size:0.75rem;color:#6b7280;margin-left:3px;">{int(r)}</span>'
    )


def status_badge(status: str) -> str:
    cfg   = {"watched": ("#16a34a","Watched"), "watching": ("#f97316","Watching"), "plan": ("#3b82f6","Plan")}
    key   = (status or "").strip().lower()
    color, label = cfg.get(key, ("#9ca3af", (status or "").title() if status else ""))
    if not label:
        return ""
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:999px;font-size:0.72rem;font-weight:500">{label}</span>'
    )


def recommend_badge(recommend: str) -> str:
    r = (recommend or "").lower()
    if r == "yes":
        return '<span style="background:#16a34a;color:#fff;padding:2px 8px;border-radius:999px;font-size:0.72rem;font-weight:500">👍 Yes</span>'
    if r == "no":
        return '<span style="background:#6b7280;color:#fff;padding:2px 8px;border-radius:999px;font-size:0.72rem;font-weight:500">👎 No</span>'
    return ""


def community_bar_html(yes_count: int, no_count: int) -> str:
    """Return community vote bar as pure HTML string."""
    total = yes_count + no_count
    if total == 0:
        return '<span class="wlog-community" style="color:#9ca3af;font-style:italic">No community votes yet</span>'
    pct_yes = int(round(100 * yes_count / total))
    pct_no  = 100 - pct_yes
    return (
        f'<div class="wlog-community">'
        f'<span style="color:#16a34a;font-weight:600">👍 {yes_count}</span>'
        f'<span style="color:#6b7280;font-weight:600">👎 {no_count}</span>'
        f'<span style="color:#9ca3af">{pct_yes}% recommend</span>'
        f'</div>'
        f'<div class="wlog-bar-wrap">'
        f'<div class="wlog-bar-yes" style="width:{pct_yes}%"></div>'
        f'<div class="wlog-bar-no" style="width:{pct_no}%"></div>'
        f'</div>'
    )


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
    client   = gspread.authorize(creds)
    sh       = client.open(SPREADSHEET_TITLE)
    entries  = sh.sheet1
    try:
        votes_ws = sh.worksheet("Votes")
    except WorksheetNotFound:
        votes_ws = sh.add_worksheet(title="Votes", rows="1000", cols="5")
        votes_ws.append_row(VOTE_COLUMNS)
    return entries, votes_ws


def empty_df()       -> pd.DataFrame: return pd.DataFrame(columns=COLUMNS)
def empty_votes_df() -> pd.DataFrame: return pd.DataFrame(columns=VOTE_COLUMNS)


@st.cache_data(ttl=60)
def read_entries(_ws) -> pd.DataFrame:
    try:
        records = _ws.get_all_records()
        if not records:
            return empty_df()
        df = pd.DataFrame(records)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        # Safe entry_id handling
        if "entry_id" not in df.columns:
            df.insert(0, "entry_id", range(1, len(df) + 1))
        else:
            df["entry_id"] = pd.to_numeric(df["entry_id"], errors="coerce").fillna(0).astype(int)
            bad = df["entry_id"] == 0
            if bad.any():
                max_id = df["entry_id"].max()
                df.loc[bad, "entry_id"] = range(max_id + 1, max_id + 1 + bad.sum())
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        # Normalize platform names to canonical form
        if "platform" in df.columns:
            df["platform"] = df["platform"].apply(
                lambda p: normalize_platform(p) if pd.notna(p) and str(p).strip() else p
            )
        return df
    except Exception as e:
        st.error(f"Could not load entries: {e}")
        return empty_df()


@st.cache_data(ttl=30)
def read_votes(_ws) -> pd.DataFrame:
    try:
        records = _ws.get_all_records()
        if not records:
            return empty_votes_df()
        df = pd.DataFrame(records)
        for col in VOTE_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df["entry_id"] = pd.to_numeric(df["entry_id"], errors="coerce").fillna(0).astype(int)
        return df
    except Exception:
        return empty_votes_df()


def build_vote_summary(votes_df: pd.DataFrame) -> dict:
    summary = {}
    if votes_df.empty:
        return summary
    for eid, grp in votes_df.groupby("entry_id"):
        yes = int((grp["vote"].str.lower() == "yes").sum())
        no  = int((grp["vote"].str.lower() == "no").sum())
        summary[int(eid)] = {"yes": yes, "no": no}
    return summary


def already_voted(votes_df: pd.DataFrame, entry_id: int, voter_name: str) -> bool:
    if votes_df.empty or not voter_name:
        return False
    mask = (
        (votes_df["entry_id"] == entry_id) &
        (votes_df["voter_name"].str.strip().str.lower() == voter_name.strip().lower())
    )
    return bool(mask.any())


def cast_vote(votes_ws, entry_id: int, voter_name: str, vote: str):
    if not voter_name or not voter_name.strip():
        raise ValueError("Voter name is required.")
    if not entry_id:
        raise ValueError("entry_id is required.")
    votes_ws.append_row([int(entry_id), voter_name.strip(), vote.lower()])


def append_row(ws, row: dict):
    ws.append_row([row.get(c, "") for c in COLUMNS])


# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
def render_sidebar():
    page    = st.sidebar.radio("Navigate", ["Browse", "Add Entry", "Reports"], index=0)
    st.sidebar.divider()
    stored  = st.session_state.get("user_name", "")
    name_in = st.sidebar.text_input(
        "Your name",
        value=stored,
        placeholder="e.g. Pankaj",
        help="Used for adding entries and voting. Enter once.",
        key="sidebar_name_widget",
    )
    name = name_in.strip()
    if name:
        st.session_state["user_name"]    = name
        st.session_state["voter_name"]   = name
        st.session_state["sidebar_name"] = name
    st.sidebar.divider()
    st.sidebar.markdown(
        "**How it works**\n"
        "- Log what you watch in *Add Entry*\n"
        "- Browse & filter in *Browse*\n"
        "- Vote 👍 👎 on any entry\n"
        "- See charts in *Reports*\n"
        "- Share the URL with friends"
    )
    return page, name


# ─────────────────────────────────────────────
#  CARD CSS  — session_state injection flag; radio fix included
# ─────────────────────────────────────────────
CARD_CSS = """<style>
.wlog-card{
  border:1px solid rgba(148,163,184,0.18);
  border-radius:10px;
  padding:12px 16px;
  margin-bottom:8px;
  background:var(--background-color,transparent);
}
.wlog-card-title{font-size:1.05rem;font-weight:700;color:inherit;display:block;margin-bottom:2px;}
.wlog-card-meta{font-size:0.78rem;color:#94a3b8;margin-left:6px;}
.wlog-card-footer{margin-top:6px;font-size:0.72rem;color:#94a3b8;}
.wlog-card-review{margin-top:6px;font-size:0.83rem;color:#cbd5e1;font-style:italic;}
.wlog-divider{border:none;border-top:1px solid rgba(148,163,184,0.10);margin:6px 0;}
.wlog-community{font-size:0.75rem;margin-top:5px;}
.wlog-community span{margin-right:8px;}
.wlog-bar-wrap{display:flex;height:4px;border-radius:999px;overflow:hidden;margin-top:4px;background:#374151;}
.wlog-bar-yes{background:#16a34a;}
.wlog-bar-no{background:#4b5563;}
/* FIX: prevent radio buttons from distorting */
div[data-testid="stRadio"]>div{
  display:flex!important;flex-direction:row!important;
  flex-wrap:wrap!important;gap:8px!important;align-items:center!important;
}
div[data-testid="stRadio"] label{white-space:nowrap!important;}
</style>"""


def _inject_card_css():
    """Inject card CSS once per session (survives hot-reloads)."""
    if not st.session_state.get("_card_css_injected", False):
        st.markdown(CARD_CSS, unsafe_allow_html=True)
        st.session_state["_card_css_injected"] = True


# ─────────────────────────────────────────────
#  CARD RENDERER
#  FIX 1: comm_bar rendered as SEPARATE st.markdown call — not embedded in HTML
#  FIX 2/4: tonight's picks use pure HTML (no ** markdown mixing)
# ─────────────────────────────────────────────
def _render_cards(filtered, vote_summary, votes_df, votes_ws):
    _inject_card_css()
    if filtered.empty:
        st.info("No entries match the current filters.")
        return

    voter_name = st.session_state.get("voter_name", "").strip()

    for idx, (_, row) in enumerate(filtered.iterrows()):
        # Safe entry_id extraction
        raw_entry_id = row.get("entry_id", None)
        try:
            entry_id = int(float(raw_entry_id)) if (
                raw_entry_id is not None and
                str(raw_entry_id).strip() not in ("", "nan", "None", "0")
            ) else idx + 1
        except (ValueError, TypeError):
            entry_id = idx + 1

        title_txt      = str(row.get("title",    "") or "—")
        type_txt       = str(row.get("type",     "") or "").title()
        genre_txt      = str(row.get("genre",    "") or "—")
        added_by_txt   = str(row.get("added_by", "") or "Unknown")
        comments_txt   = str(row.get("comments", "") or "").strip()
        poster_url     = str(row.get("poster_url","") or "").strip()
        platform_html  = platform_badge(row.get("platform", ""))
        rating_html    = rating_stars(row.get("rating"))
        status_html    = status_badge(row.get("status",    ""))
        recommend_html = recommend_badge(row.get("recommend",""))

        counts      = vote_summary.get(entry_id, {"yes": 0, "no": 0})
        review_html = (
            f'<div class="wlog-card-review">💬 {comments_txt}</div>'
            if comments_txt else ""
        )

        if poster_url:
            img_html   = (
                f'<img src="{poster_url}" width="54" height="80" '
                f'style="border-radius:5px;object-fit:cover;flex-shrink:0;" '
                f'alt="poster" loading="lazy">'
            )
            card_html = f"""
<div class="wlog-card">
  <div style="display:flex;gap:12px;align-items:flex-start;">
    {img_html}
    <div style="flex:1;min-width:0;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:4px;">
        <div>
          <span class="wlog-card-title">{title_txt}</span>
          <span class="wlog-card-meta">{type_txt} &middot; {genre_txt}</span>
        </div>
        <div style="display:flex;align-items:center;gap:5px;">{platform_html}</div>
      </div>
      <div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:5px;align-items:center;">
        {rating_html} {recommend_html} {status_html}
      </div>
      {review_html}
      <div class="wlog-card-footer">Added by {added_by_txt}</div>
    </div>
  </div>
</div>"""
        else:
            card_html = f"""
<div class="wlog-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:4px;">
    <div>
      <span class="wlog-card-title">{title_txt}</span>
      <span class="wlog-card-meta">{type_txt} &middot; {genre_txt}</span>
    </div>
    <div style="display:flex;align-items:center;gap:5px;">{platform_html}</div>
  </div>
  <div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:5px;align-items:center;">
    {rating_html} {recommend_html} {status_html}
  </div>
  {review_html}
  <div class="wlog-card-footer">Added by {added_by_txt}</div>
</div>"""

        # Render card HTML (no comm_bar inside — avoids HTML escape issue)
        st.markdown(card_html, unsafe_allow_html=True)

        # FIX 1: community bar as its OWN st.markdown call — never embedded in card HTML
        st.markdown(
            community_bar_html(counts["yes"], counts["no"]),
            unsafe_allow_html=True,
        )

        _render_vote_widget(
            entry_id, title_txt, voter_name,
            votes_df, votes_ws, counts["yes"], counts["no"], idx
        )
        st.markdown('<hr class="wlog-divider">', unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  VOTE WIDGET
# ─────────────────────────────────────────────
def _render_vote_widget(entry_id, title_txt, voter_name,
                        votes_df, votes_ws, yes_cnt, no_cnt, card_idx):
    if not voter_name:
        return   # name only comes from sidebar — no inline prompt

    voted_key        = f"voted_{entry_id}"
    voted_in_sheet   = already_voted(votes_df, entry_id, voter_name)
    voted_in_session = st.session_state.get(voted_key, None)

    lbl_col, yes_col, no_col, _ = st.columns([3, 1, 1, 5])

    with lbl_col:
        if voted_in_sheet or voted_in_session:
            prior = voted_in_session or "previously"
            st.markdown(
                f'<span style="font-size:0.75rem;color:#9ca3af;">Your vote: '
                f'<strong>{prior}</strong></span>',
                unsafe_allow_html=True,
            )

    if not voted_in_sheet and not voted_in_session:
        with yes_col:
            if st.button("👍", key=f"yes_{entry_id}_{card_idx}",
                         help=f"Recommend {title_txt}"):
                try:
                    cast_vote(votes_ws, entry_id, voter_name, "yes")
                    st.session_state[voted_key] = "👍 yes"
                    read_votes.clear()
                    st.rerun()
                except Exception as e:
                    st.error("Could not save vote.")
                    st.exception(e)
        with no_col:
            if st.button("👎", key=f"no_{entry_id}_{card_idx}",
                         help=f"Skip {title_txt}"):
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

    def comm_votes_row(row):
        eid    = int(row.get("entry_id", 0))
        counts = vote_summary.get(eid, {"yes": 0, "no": 0})
        total  = counts["yes"] + counts["no"]
        if total == 0:
            return "—"
        pct = int(round(100 * counts["yes"] / total))
        return f'{counts["yes"]}👍 {counts["no"]}👎 {pct}%'

    df_display["community_votes"] = df_display.apply(comm_votes_row, axis=1)
    if "platform"  in df_display.columns: df_display["platform"]  = df_display["platform"].apply(platform_badge)
    if "rating"    in df_display.columns: df_display["rating"]    = df_display["rating"].apply(rating_stars)
    if "status"    in df_display.columns: df_display["status"]    = df_display["status"].apply(status_badge)
    if "recommend" in df_display.columns: df_display["recommend"] = df_display["recommend"].apply(recommend_badge)
    if "type"      in df_display.columns: df_display["type"]      = df_display["type"].str.title()

    col_order = ["title","type","genre","platform","rating","recommend",
                 "community_votes","status","language","added_by","watched_year"]
    existing  = [c for c in col_order if c in df_display.columns]
    df_display = df_display[existing]
    df_display.columns = [c.replace("_"," ").title() for c in df_display.columns]

    st.markdown(
        "<style>table{width:100%;border-collapse:collapse;font-size:0.84rem;}"
        "th{background:rgba(148,163,184,0.1);padding:7px 10px;text-align:left;}"
        "td{padding:6px 10px;border-bottom:1px solid rgba(148,163,184,0.12);vertical-align:middle;}"
        "tr:hover td{background:rgba(148,163,184,0.05);}</style>",
        unsafe_allow_html=True,
    )
    st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  PAGE: ADD ENTRY
# ─────────────────────────────────────────────
def page_add_entry(entries_ws, current_name: str):
    st.subheader("Add a new entry")
    st.caption("Fill in what you've watched — takes about 10 seconds.")

    with st.expander("🔍 Auto-fill from TMDB (optional)", expanded=False):
        af1, af2, af3 = st.columns([4, 1, 1])
        with af1:
            tmdb_q = st.text_input(
                "Search title on TMDB",
                placeholder="e.g. Inception — type then click Search",
                key="tmdb_title_input",
            )
        with af2:
            tmdb_t = st.selectbox("Type", ["Movie", "Web Series"], key="tmdb_type_input")
        with af3:
            st.write("")
            st.write("")
            do_search = st.button("Search", key="tmdb_search_btn", use_container_width=True)

        if do_search:
            if tmdb_q.strip():
                with st.spinner("Searching TMDB…"):
                    results = tmdb_search(tmdb_q.strip(), tmdb_t)
                if results:
                    st.session_state["tmdb_results"]  = results
                    st.session_state["tmdb_query"]    = tmdb_q.strip()
                    st.session_state["tmdb_type_sel"] = tmdb_t
                else:
                    st.warning("No results found. Try a different spelling.")
                    st.session_state.pop("tmdb_results", None)
            else:
                st.warning("Please enter a title to search.")

        if "tmdb_results" in st.session_state:
            results = st.session_state["tmdb_results"]
            st.markdown("**Select the correct match:**")
            for i, res in enumerate(results):
                c_img, c_info, c_btn = st.columns([1, 6, 2])
                with c_img:
                    if res.get("poster"):
                        st.image(res["poster"], width=48)
                with c_info:
                    st.markdown(
                        f"**{res.get('name','')}** ({res.get('year','?')})  \n"
                        f"*{', '.join(res.get('genres', []))}*"
                    )
                with c_btn:
                    if st.button("✅ Use", key=f"tmdb_pick_{i}"):
                        st.session_state["pf_title"]  = res.get("name", "")
                        st.session_state["pf_year"]   = res.get("year", "")
                        st.session_state["pf_genres"] = res.get("genres", [])
                        st.session_state["pf_type"]   = st.session_state.get("tmdb_type_sel","Movie")
                        st.session_state["pf_poster"] = res.get("poster", "")
                        st.session_state.pop("tmdb_results", None)
                        st.rerun()

    pf_title  = st.session_state.pop("pf_title",  "")
    pf_year   = st.session_state.pop("pf_year",   "")
    pf_genres = st.session_state.pop("pf_genres", [])
    pf_type   = st.session_state.pop("pf_type",   "Movie")
    pf_poster = st.session_state.pop("pf_poster", "")
    if pf_poster:
        st.session_state["pending_poster"] = pf_poster

    with st.form("add_entry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            added_by = st.text_input("Your name *", value=current_name, placeholder="e.g. Pankaj")
        with c2:
            title = st.text_input("Title *", value=pf_title, placeholder="e.g. Mirzapur Season 3")

        c3, c4, c5 = st.columns(3)
        with c3:
            type_opts  = ["Movie", "Web Series"]
            type_idx   = type_opts.index(pf_type) if pf_type in type_opts else 0
            media_type = st.selectbox("Type", type_opts, index=type_idx)
        with c4:
            platform = st.selectbox("Platform", PLATFORMS, index=0)
        with c5:
            status = st.selectbox("Status", ["Watched", "Watching", "Plan"], index=0)

        c6, c7 = st.columns(2)
        with c6:
            valid_pf_g = [g for g in pf_genres if g in GENRES_LIST]
            genre_sel  = st.multiselect("Genre", options=GENRES_LIST, default=valid_pf_g)
        with c7:
            language = st.selectbox("Language", LANGUAGES, index=0)

        rating       = None
        recommend    = ""
        watched_year = datetime.now().year

        if status != "Plan":
            c8, c9, c10 = st.columns([2, 1, 1])
            with c8:
                rating = st.slider("Rating (1–10)", 1, 10, 8)
            with c9:
                recommend = st.radio("Recommend?", ["Yes", "No"], horizontal=True, index=0).lower()
            with c10:
                try:
                    yr_default = int(pf_year) if pf_year else datetime.now().year
                except ValueError:
                    yr_default = datetime.now().year
                watched_year = st.number_input(
                    "Year watched", min_value=1990,
                    max_value=datetime.now().year + 1,
                    value=yr_default, step=1,
                )

        with st.expander("Add a short review (optional)"):
            comments = st.text_area("Review / comments", "", label_visibility="collapsed")

        submitted = st.form_submit_button("💾 Save entry", use_container_width=True, type="primary")

    if submitted:
        errors = []
        if not added_by.strip(): errors.append("Your name is required.")
        if not title.strip():    errors.append("Title is required.")
        for e in errors:
            st.error(e)
        if not errors:
            if added_by.strip():
                st.session_state["user_name"]  = added_by.strip()
                st.session_state["voter_name"] = added_by.strip()
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
                "recommend":    recommend if status != "Plan" else "",
                "watched_year": watched_year if status != "Plan" else "",
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
def _render_dont_miss_section(df: pd.DataFrame):
    """
    FIX 2 + 3 + 4: 'Don't Miss These on X' sections.
    - Pure HTML titles — no ** markdown mixed with HTML
    - Platform icons rendered via platform_logo_url()
    - JioHotstar included in featured list
    - Title text is HTML-escaped, no asterisks
    """
    top_pool = df[
        (df["status"].str.lower() == "watched") &
        (df["recommend"].str.lower() == "yes") &
        (pd.to_numeric(df["rating"], errors="coerce") >= 7)
    ] if all(c in df.columns for c in ["status", "recommend", "rating"]) else pd.DataFrame()

    if top_pool.empty:
        return

    rendered_any = False
    for plat in FEATURED_PLATFORMS:
        subset = top_pool[
            top_pool["platform"].str.strip().str.lower() == plat.lower()
        ] if "platform" in top_pool.columns else pd.DataFrame()
        if subset.empty:
            continue

        rendered_any = True
        logo_url = platform_logo_url(plat)

        # FIX 2 + 4: Pure HTML header — NO markdown ** syntax
        if logo_url:
            header_html = (
                f'<div style="display:flex;align-items:center;gap:8px;margin:16px 0 8px;">'
                f'<img src="{logo_url}" width="22" height="22" '
                f'style="vertical-align:middle;border-radius:3px;" alt="{plat}">'
                f'<span style="font-size:1.1rem;font-weight:700;">Don\'t Miss These on {plat}</span>'
                f'</div>'
            )
        else:
            header_html = (
                f'<div style="margin:16px 0 8px;">'
                f'<span style="font-size:1.1rem;font-weight:700;">Don\'t Miss These on {plat}</span>'
                f'</div>'
            )
        st.markdown(header_html, unsafe_allow_html=True)

        sample_size = min(5, len(subset))
        picks       = subset.sample(n=sample_size, random_state=random.randint(0, 99999))
        cols        = st.columns(sample_size)
        for i, (_, pr) in enumerate(picks.iterrows()):
            with cols[i]:
                poster = str(pr.get("poster_url", "") or "").strip()
                if poster:
                    st.image(poster, use_container_width=True)
                else:
                    st.markdown(
                        '<div style="background:#374151;border-radius:6px;height:120px;'
                        'display:flex;align-items:center;justify-content:center;'
                        'color:#9ca3af;font-size:0.7rem;">No poster</div>',
                        unsafe_allow_html=True,
                    )
                # FIX 4: pure HTML — title never goes through Markdown processing
                title_safe  = str(pr.get("title", "–") or "–").replace("<","&lt;").replace(">","&gt;")
                type_safe   = str(pr.get("type",  "") or "").title()
                year_safe   = str(pr.get("watched_year", "") or "")
                type_year   = " &bull; ".join(filter(None, [type_safe, year_safe]))
                st.markdown(
                    f'<div style="margin-top:4px;">'
                    f'<div style="font-weight:700;font-size:0.9rem;line-height:1.3">{title_safe}</div>'
                    f'<div style="font-size:0.75rem;color:#9ca3af;margin-top:2px">{type_year}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    if rendered_any:
        st.divider()


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

    total   = len(df)
    movies  = int((df["type"].str.lower() == "movie").sum())    if "type"   in df.columns else 0
    series  = int((df["type"].str.lower().isin(["web series","webseries"])).sum()) if "type" in df.columns else 0
    avg_r   = df["rating"].mean() if "rating" in df.columns else float("nan")
    watched = df[df["status"].str.lower() == "watched"] if "status" in df.columns else df
    rec_pct = (
        int(100 * (watched["recommend"].str.lower() == "yes").sum() / max(len(watched), 1))
        if "recommend" in df.columns else 0
    )
    total_cvotes = sum(v["yes"] + v["no"] for v in vote_summary.values())

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total",           total)
    m2.metric("Movies",          movies)
    m3.metric("Web Series",      series)
    m4.metric("Avg Rating",      f"{avg_r:.1f}" if pd.notna(avg_r) else "–")
    m5.metric("Recommend %",     f"{rec_pct}%")
    m6.metric("Community Votes", total_cvotes)

    st.divider()

    # "Don't Miss These on X" — platform showcase (FIX 2, 3, 4)
    _render_dont_miss_section(df)

    # Tonight's picks (general — not platform-specific)
    voter_name = st.session_state.get("voter_name", "").strip()
    if all(c in df.columns for c in ["recommend", "status", "rating"]):
        top_pool = df[
            (df["status"].str.lower() == "watched") &
            (df["recommend"].str.lower() == "yes") &
            (pd.to_numeric(df["rating"], errors="coerce") >= 8)
        ]
        if voter_name and "added_by" in top_pool.columns:
            top_pool = top_pool[top_pool["added_by"].str.strip().str.lower() != voter_name.lower()]
        if not top_pool.empty:
            st.markdown("### 🍿 Tonight's picks")
            st.caption("Top-rated picks not added by you.")
            sample_size = min(3, len(top_pool))
            picks = top_pool.sample(n=sample_size, random_state=random.randint(0, 99999))
            pcols = st.columns(sample_size)
            for i, (_, pr) in enumerate(picks.iterrows()):
                with pcols[i]:
                    poster = str(pr.get("poster_url", "") or "").strip()
                    if poster:
                        st.image(poster, width=70)
                    # FIX 2 + 4: pure HTML — no mixed ** markdown + HTML
                    title_safe = str(pr.get("title", "–") or "–").replace("<","&lt;").replace(">","&gt;")
                    plat_safe  = platform_badge(pr.get("platform",""))
                    rate_safe  = rating_stars(pr.get("rating"))
                    st.markdown(
                        f'<div style="margin-top:4px;">'
                        f'<div style="font-weight:700;font-size:0.9rem">{title_safe}</div>'
                        f'<div style="margin-top:3px;display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
                        f'{plat_safe} {rate_safe}'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
            st.divider()

    # FIX: voter name ONLY as caption — no extra input widget in Browse
    if voter_name:
        st.caption(f"Voting as: **{voter_name}**")
    else:
        st.caption("💡 Enter your name in the sidebar to vote on entries.")

    preset = st.radio(
        "Quick filter",
        ["All", "Recommended only", "High ratings (≥ 8)"],
        horizontal=True,
        key="browse_preset",
    )
    my_name     = st.session_state.get("user_name", "").strip()
    show_mine   = st.checkbox("Show only my entries", value=False, key="show_mine_check")
    search_text = st.text_input("🔍 Search title", "", placeholder="Search title…")

    with st.expander("Filters", expanded=False):
        fc1, fc2, fc3, fc4, fc5 = st.columns(5)
        with fc1:
            plat_opts = sorted(df["platform"].dropna().replace("","Unknown").unique().tolist()) \
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

    exp_col, view_col = st.columns([2, 5])
    with exp_col:
        st.download_button(
            "⬇ Export CSV",
            filtered.to_csv(index=False).encode("utf-8"),
            "watchlist.csv", "text/csv",
            use_container_width=False,
        )
    with view_col:
        view_mode = st.radio("View", ["Cards", "Table"], horizontal=True, key="view_radio")

    st.divider()

    total_filtered = len(filtered)
    total_pages    = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
    if "browse_page" not in st.session_state:
        st.session_state.browse_page = 1
    st.session_state.browse_page = min(st.session_state.browse_page, total_pages)
    page_start = (st.session_state.browse_page - 1) * PAGE_SIZE
    page_data  = filtered.iloc[page_start: page_start + PAGE_SIZE]

    if total_pages > 1:
        pg1, pg2, pg3 = st.columns([1, 3, 1])
        with pg1:
            if st.button("◀ Prev", disabled=st.session_state.browse_page <= 1):
                st.session_state.browse_page -= 1; st.rerun()
        with pg2:
            st.markdown(
                f"<div style='text-align:center;color:#9ca3af;font-size:0.85rem;padding-top:6px;'>"
                f"Page {st.session_state.browse_page} of {total_pages}</div>",
                unsafe_allow_html=True,
            )
        with pg3:
            if st.button("Next ▶", disabled=st.session_state.browse_page >= total_pages):
                st.session_state.browse_page += 1; st.rerun()

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
                df["platform"].fillna("Unknown").replace("","Unknown")
                .value_counts().rename_axis("Platform").reset_index(name="Count").set_index("Platform")
            )
            st.bar_chart(pc)
            st.dataframe(pc.reset_index(), use_container_width=True)
    with tab2:
        if "genre" in df.columns:
            exploded = (
                df["genre"].fillna("").apply(lambda g: [x.strip() for x in str(g).split(",") if x.strip()])
                .explode().value_counts()
                .rename_axis("Genre").reset_index(name="Count").set_index("Genre")
            )
            st.bar_chart(exploded)
            st.dataframe(exploded.reset_index(), use_container_width=True)
    with tab3:
        if "added_by" in df.columns:
            pc2 = (
                df["added_by"].fillna("Unknown").replace("","Unknown")
                .value_counts().rename_axis("Person").reset_index(name="Count").set_index("Person")
            )
            st.bar_chart(pc2)
            avg_by = df.groupby("added_by")["rating"].mean().round(1).rename("Avg Rating")
            st.dataframe(avg_by.reset_index(), use_container_width=True)


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
    page, current_name   = render_sidebar()

    if page == "Add Entry":
        page_add_entry(entries_ws, current_name)
    elif page == "Reports":
        page_reports(entries_ws)
    else:
        page_browse(entries_ws, votes_ws)


if __name__ == "__main__":
    main()