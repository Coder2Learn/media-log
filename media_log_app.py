import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound
from datetime import datetime
import re
import html
import time
import hashlib

GLOBAL_TOKENS_CSS = """<style>
@import url('https://api.fontshare.com/v2/css?f[]=cabinet-grotesk@700,800&f[]=general-sans@400,500,600&display=swap');
html, body, [class*="css"] { font-family: 'General Sans', sans-serif; }
.detail-title, .stat-value { font-family: 'Cabinet Grotesk', sans-serif; }
/* Force the dark palette even if a user's browser has a saved LIGHT Streamlit
   theme preference (that preference otherwise overrides config.toml's base).
   NOTE: it's not enough to whiten text — Streamlit's widget backgrounds are
   light in light mode, so buttons/inputs must get dark surfaces too or their
   text renders white-on-white (invisible). */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #0b0f17 !important;
    color: #f1f5f9 !important;
}
[data-testid="stSidebar"] { background-color: #0e131c !important; }

/* Buttons (default/secondary): dark surface + readable text */
.stApp [data-testid="stBaseButton-secondary"],
.stApp button[kind="secondary"] {
    background-color: #161c27 !important;
    color: #f1f5f9 !important;
    border: 1px solid rgba(148,163,184,0.22) !important;
}
.stApp [data-testid="stBaseButton-secondary"]:hover,
.stApp button[kind="secondary"]:hover {
    border-color: #7c3aed !important;
    color: #ffffff !important;
}
/* Text inputs, text areas, number inputs, select boxes */
.stApp [data-testid="stTextInput"] input,
.stApp [data-testid="stTextArea"] textarea,
.stApp [data-testid="stNumberInput"] input,
.stApp [data-baseweb="input"], .stApp [data-baseweb="textarea"],
.stApp [data-baseweb="select"] > div {
    background-color: #161c27 !important;
    color: #f1f5f9 !important;
}
.stApp [data-testid="stTextInput"] input::placeholder,
.stApp [data-testid="stTextArea"] textarea::placeholder { color: #6b7789 !important; }
/* Expander + container surfaces */
.stApp [data-testid="stExpander"] { background-color: #11161f !important; }
:root {
  /* Surfaces */
--bg:            #0b0f17;
--surface:       #11161f;
--surface-2:     #161c27;
--surface-3:     #1c2330;
--border:        rgba(148,163,184,0.14);
--border-strong: rgba(148,163,184,0.28);

  /* Text */
--text:          #f1f5f9;
--text-muted:    #a3adc2;
--text-faint:    #6b7789;

  /* Accent */
--accent:        #7c3aed;
--accent-hover:  #6d28d9;
--accent-soft:   rgba(124,58,237,0.14);

  /* Status */
--success:       #22c55e;
--warning:       #f97316;
--info:          #3b82f6;
--danger:        #ef4444;
--neutral:       #94a3b8;

  /* Radius / Shadow */
--radius-sm: 8px;
--radius-md: 12px;
--radius-lg: 18px;
--shadow-sm: 0 2px 8px rgba(0,0,0,0.24);
--shadow-md: 0 8px 24px rgba(0,0,0,0.32);
--shadow-lg: 0 20px 50px rgba(0,0,0,0.40);

  /* Motion */
--ease: cubic-bezier(0.16,1,0.3,1);
--transition: all 0.18s var(--ease);
}

/* Focus visibility for keyboard users (accessibility fix) */
button:focus-visible, [role="button"]:focus-visible,
input:focus-visible, textarea:focus-visible, select:focus-visible {
outline: 2px solid var(--accent) !important;
outline-offset: 2px !important;
border-radius: var(--radius-sm) !important;
}
</style>
<style>
.wlog-divider {
    border: none;
    border-top: 1px solid rgba(148,163,184,0.15);
    margin: 14px 0;
}
</style>
"""

CLICKABLE_CARD_CSS = """
<style>
.wlog-card-clickable {
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.wlog-card-clickable:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
}
.wlog-card-clickable:active {
    transform: translateY(0);
}
</style>
"""

VOTE_CSS = """
<style>
.vote-wrap {
    padding: 10px 12px;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 14px;
    background: rgba(15, 23, 42, 0.22);
    margin-top: 8px;
}
.vote-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #e5e7eb;
    margin-bottom: 8px;
}
.vote-subtle {
    font-size: 0.78rem;
    color: #94a3b8;
}
</style>
"""

MOBILE_CSS = """
<style>
/* ---- Cards: stack poster above content on narrow screens ---- */
@media (max-width: 600px) {
    .wlog-card img {
        width: 46px !important;
        height: 68px !important;
    }
    .wlog-card-title { font-size: 0.92rem !important; }
    .wlog-card-meta { font-size: 0.7rem !important; }
}

/* ---- Detail hero: stack poster + content vertically ---- */
@media (max-width: 768px) {
    .detail-hero { min-height: unset !important; }
    .detail-content > div[style*="display:flex"] {
        flex-direction: column !important;
        align-items: center !important;
        text-align: center;
    }
    .detail-poster { width: 160px !important; margin: 0 auto; }
    .detail-title { font-size: 1.7rem !important; text-align: center; }
    .hero-meta-grid { justify-content: center; }
    .hero-actions {
        flex-direction: row !important;
        flex-wrap: wrap;
        justify-content: center;
        width: 100%;
    }
    .hero-action-btn { flex: 1 1 auto; justify-content: center; }
}

/* ---- Filter toolbar: collapse 5 columns into stacked full-width ---- */
@media (max-width: 768px) {
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }
}

/* ---- Card grid: single column on mobile ---- */
@media (max-width: 640px) {
    /* Force 2-column st.columns card grid to stack */
    section[data-testid="stMain"] div[data-testid="stHorizontalBlock"].card-grid-row
        > div[data-testid="column"] {
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }
    .wlog-card { padding: 10px 10px; }
    .wlog-card-title { font-size: 0.9rem !important; }
}

/* ---- Quick-filter chip bar: allow horizontal scroll on narrow screens ---- */
@media (max-width: 500px) {
    div[data-testid="stHorizontalBlock"].chip-row {
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
    }
}
</style>
"""

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
SPREADSHEET_TITLE    = "MediaLog"
SERVICE_ACCOUNT_FILE = "media-log-service-account.json"
TMDB_BASE            = "https://api.themoviedb.org/3"
TMDB_IMG_BASE        = "https://image.tmdb.org/t/p/w200"
PAGE_SIZE            = 24

PLATFORM_LOGOS = {
    "Netflix":         "https://cdn.simpleicons.org/netflix",
    "Prime Video":     "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7c/Amazon_Prime_Video_blue_logo_1.svg/960px-Amazon_Prime_Video_blue_logo_1.svg.png?_=20230318051251",
    "YouTube":         "https://cdn.simpleicons.org/youtube",
    "Jio Hotstar": "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/jiohotstar.png",
    "Sony LIV": "https://upload.wikimedia.org/wikipedia/commons/f/f7/SonyLIV_2020.png",
    "Zee5": "https://cdn.brandfetch.io/idG83-n-Gw/w/400/h/400/theme/dark/icon.jpeg?c=1dxbfHSJFAPEGdCLU4o5B",
    "Other":           "",
    "":                "",
}

PLATFORMS = ["", "Netflix", "Prime Video", "Jio Hotstar", "Sony LIV", "Zee5", "YouTube", "Other"]
PLATFORM_NAME_ALIASES = {
    "Disney+ Hotstar": "Jio Hotstar",
    "SonyLiv": "Sony LIV",
    "ZEE5": "Zee5",
    # TMDB "networks" field commonly uses these spellings
    "Amazon Prime Video": "Prime Video",
    "JioHotstar": "Jio Hotstar",
    "SonyLIV": "Sony LIV",
}
def _normalize_platform_name(p: str) -> str:
    """Single source of truth for platform name aliasing (M6, L4)."""
    return PLATFORM_NAME_ALIASES.get(p, p)

def _platform_from_tmdb_networks(networks: list) -> str:
    """Map TMDB 'networks' names to a known PLATFORMS entry. First match wins;
    returns '' (safe default, same as an unrecognized genre) if none match."""
    for n in networks or []:
        mapped = _normalize_platform_name((n or "").strip())
        if mapped in PLATFORMS:
            return mapped
    return ""

def _language_from_tmdb_code(code: str) -> str:
    """Map a TMDB original_language ISO code to a known LANGUAGES entry.
    Returns '' if TMDB's language isn't one of the app's dropdown options."""
    name = LANG_NAMES.get((code or "").strip().lower(), "")
    return name if name in LANGUAGES else ""

GENRES_LIST = [
    "Action", "Adventure", "Animation", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "Horror",
    "Romance", "Sci-Fi", "Thriller", "Other",
]

LANGUAGES = ["", "Hindi", "English", "Tamil", "Telugu", "Malayalam",
            "Kannada", "Bengali", "Marathi", "Other"]

COLUMNS = [
    "entry_id", "timestamp", "added_by", "title", "type", "genre",
    "platform", "status", "rating", "recommend",
    "watched_year", "language", "comments", "poster_url", "watched_with", "tmdb_id",
    "release_date",
]

# Month names for the sidebar Year/Month release filter (index 1..12).
MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

DETAIL_VIEW_KEYS = ["selected_entry_id", "selected_entry_title", "selected_entry_type"]

def _clear_detail_view_state():
    """Single source of truth for clearing detail-page navigation state (M12)."""
    for k in DETAIL_VIEW_KEYS:
        st.session_state.pop(k, None)

LANG_NAMES = {
    "en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu",
    "ml": "Malayalam", "kn": "Kannada", "mr": "Marathi", "bn": "Bengali",
    "pa": "Punjabi", "gu": "Gujarati", "ur": "Urdu", "or": "Odia",
    "fr": "French", "de": "German", "es": "Spanish", "it": "Italian",
    "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "pt": "Portuguese",
    "ru": "Russian", "ar": "Arabic", "th": "Thai", "id": "Indonesian",
    "tr": "Turkish", "pl": "Polish", "nl": "Dutch", "sv": "Swedish",
    "no": "Norwegian", "da": "Danish", "fi": "Finnish",
}
VOTE_COLUMNS = ["entry_id", "voter_name", "vote"]

SORT_OPTIONS = {
    "Rating (High → Low)": ("rating", False),
    "Rating (Low → High)": ("rating", True),
    "Recently Added": ("timestamp", False),
    "Oldest First": ("timestamp", True),
    "Title (A → Z)": ("title", True),
    "Title (Z → A)": ("title", False),
    "Most Voted": ("_total_votes", False),
}

def _safe_sort(df: pd.DataFrame, sort_col: str, sort_asc: bool) -> pd.DataFrame:
    """
    Robust sort for the Browse page.
    - For 'title': sort by a normalized string key (lowercase, stripped), so mixed types
      in the column can't break Pandas.
    - For other columns: fall back to normal sort_values.
    """
    if sort_col == "title":
        # Build a temporary normalized key
        tmp = (
            df["title"]
            .fillna("")        # None → empty
            .astype(str)       # anything → string
            .str.strip()
            .str.lower()
        )
        df = df.assign(_title_sort_key=tmp)
        df = df.sort_values("_title_sort_key", ascending=sort_asc, na_position="last")
        return df.drop(columns=["_title_sort_key"])

    # Default path for rating, timestamp, _total_votes, etc.
    return df.sort_values(sort_col, ascending=sort_asc, na_position="last")
TMDB_GENRE_MAP_MOVIE = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10751: "Family", 14: "Fantasy", 27: "Horror",
    10749: "Romance", 878: "Sci-Fi", 53: "Thriller", 10770: "TV Movie", 37: "Western",
    9648: "Mystery", 36: "History", 10402: "Music", 10752: "War",
}
TMDB_GENRE_MAP_TV = {
    10759: "Action & Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10751: "Family", 10762: "Kids",
    9648: "Mystery", 10763: "News", 10764: "Reality", 10765: "Sci-Fi & Fantasy",
    10766: "Soap", 10767: "Talk", 10768: "War & Politics", 37: "Western",
}

MEDIA_TYPE_MOVIE = "Movie"
MEDIA_TYPE_SERIES = "WebSeries"
def normalize_media_type(raw: str) -> str:
    """Single source of truth for movie/series classification (C6).
    Never use .title() on this value — it can't produce 'WebSeries' correctly."""
    val = str(raw or "").strip().lower().replace(" ", "")
    return MEDIA_TYPE_SERIES if val in ("webseries", "tvseries", "tv", "series") else MEDIA_TYPE_MOVIE

# ─────────────────────────────────────────────
#  TMDB HELPER (FIX #9: cached with TTL)
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def tmdb_search(title: str, media_type: str, _v: int = 2) -> list:
    """Return up to 5 results from TMDB. Cached for 1 hour."""
    key = st.secrets.get("tmdb_api_key", "")
    if not key or not title.strip():
        return []
    t = "tv" if media_type == MEDIA_TYPE_SERIES else "movie"
    try:
        r = requests.get(
            f"{TMDB_BASE}/search/{t}",
            params={"api_key": key, "query": title.strip(), "language": "en-US", "page": 1},
            timeout=5,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return []
        date_field = "first_air_date" if t == "tv" else "release_date"
        out = []
        for item in results[:5]:
            year = (item.get(date_field, "") or "")[:4]
            genre_ids = item.get("genre_ids", [])
            genre_map = TMDB_GENRE_MAP_TV if t == "tv" else TMDB_GENRE_MAP_MOVIE
            genres = list(dict.fromkeys(genre_map.get(gid, "Other") for gid in genre_ids[:3]))
            poster = ""
            if item.get("poster_path"):
                poster = TMDB_IMG_BASE + item["poster_path"]
            name = item.get("title") or item.get("name") or title
            out.append({"year": year, "genres": genres, "poster": poster, "name": name, "id": item.get("id")})
        return out
    except Exception:
        return []

def tmdb_get_with_retry(url, params, timeout, retries=1):
    last_exc = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            last_exc = e
            if attempt < retries:
                time.sleep(0.6)
    raise last_exc

def _tmdb_image_url(size_url_base: str, primary: dict, fallback: dict, key: str) -> str:
    """Flatten nested ternary poster/backdrop fallback chains (M11)."""
    if primary.get(key):
        return size_url_base + primary[key]
    if fallback.get(key):
        return size_url_base + fallback[key]
    return ""

@st.cache_data(ttl=3600)
def tmdb_fetch_details(title: str, media_type: str, _v: int = 2) -> dict:
    key = st.secrets.get("tmdb_api_key", "")
    if not key or not title.strip():
        return {}
    t = "tv" if media_type == MEDIA_TYPE_SERIES else "movie"
    try:
        sr = tmdb_get_with_retry(f"{TMDB_BASE}/search/{t}", params={"api_key": key, "query": title.strip(), "language": "en-US", "page": 1}, timeout=6)
        sr.raise_for_status()
        results = sr.json().get("results", [])
        if not results:
            return {}
        best = _pick_tmdb_result(results, title, None) or results[0]
        tmdb_id = best.get("id")
        if not tmdb_id:
            return {}
        dr = tmdb_get_with_retry(f"{TMDB_BASE}/{t}/{tmdb_id}", params={"api_key": key, "language": "en-US", "append_to_response": "credits,videos"}, timeout=8)
        dr.raise_for_status()
        data = dr.json()
        poster_url = _tmdb_image_url("https://image.tmdb.org/t/p/w342", data, best, "poster_path")
        backdrop_url = _tmdb_image_url("https://image.tmdb.org/t/p/w1280", data, best, "backdrop_path")
        videos = data.get("videos", {}).get("results", [])
        trailer_url = ""
        for v in videos:
            if v.get("site") == "YouTube" and v.get("key") and v.get("type") in ("Trailer", "Teaser"):
                trailer_url = f"https://www.youtube.com/watch?v={v['key']}"
                break
        cast = []
        for c in data.get("credits", {}).get("cast", [])[:8]:
            profile_url = ("https://image.tmdb.org/t/p/w185" + c["profile_path"]) if c.get("profile_path") else ""
            cast.append({"name": c.get("name", ""), "character": c.get("character", ""), "profile_url": profile_url})
        genres = [g.get("name", "") for g in data.get("genres", []) if g.get("name")]
        seasons = []
        for s in data.get("seasons", []) or []:
            if not s:
                continue
            season_poster = ("https://image.tmdb.org/t/p/w342" + s["poster_path"]) if s.get("poster_path") else ""
            seasons.append({
                "season_number": s.get("season_number"),
                "name": s.get("name", ""),
                "air_date": s.get("air_date", ""),
                "episode_count": s.get("episode_count"),
                "overview": s.get("overview", ""),
                "poster_url": season_poster,
            })
        next_episode = data.get("next_episode_to_air") or {}
        networks = [n.get("name", "") for n in (data.get("networks") or []) if n.get("name")]
        director = next(
                (c.get("name", "") for c in data.get("credits", {}).get("crew", []) if c.get("job") == "Director"),
                ""
            )
        return {"name": data.get("title") or data.get("name") or title, "tmdb_id": tmdb_id, "overview": data.get("overview", ""), "tagline": data.get("tagline", ""), "poster_url": poster_url, "backdrop_url": backdrop_url, "genres": genres, "release_date": data.get("release_date") or data.get("first_air_date") or "", "language": data.get("original_language", ""), "networks": networks, "runtime": data.get("runtime") or (data.get("episode_run_time") or [None])[0], "tmdb_rating": data.get("vote_average"), "tmdb_votes": data.get("vote_count"), "status": data.get("status", ""), "cast": cast, "director": director, "trailer_url": trailer_url, "number_of_seasons": data.get("number_of_seasons"), "number_of_episodes": data.get("number_of_episodes"), "last_air_date": data.get("last_air_date", ""), "next_episode_to_air": {"name": next_episode.get("name", ""), "air_date": next_episode.get("air_date", ""), "episode_number": next_episode.get("episode_number")}, "seasons": seasons}
    except Exception:
         return {}

@st.cache_data(ttl=3600)
def tmdb_fetch_details_by_id(tmdb_id: str, media_type: str, _v: int = 2) -> dict:
    """Fetch TMDB details by exact ID — avoids remake/title-collision ambiguity (H2)."""
    key = st.secrets.get("tmdb_api_key", "")
    if not key or not tmdb_id:
        return {}
    t = "tv" if media_type == MEDIA_TYPE_SERIES else "movie"
    try:
        dr = requests.get(
            f"{TMDB_BASE}/{t}/{tmdb_id}",
            params={"api_key": key, "language": "en-US", "append_to_response": "credits,videos"},
            timeout=8,
        )
        dr.raise_for_status()
        data = dr.json()
        best = data  # no separate search result needed — data itself has poster/backdrop paths
        poster_url = _tmdb_image_url("https://image.tmdb.org/t/p/w342", data, best, "poster_path")
        backdrop_url = _tmdb_image_url("https://image.tmdb.org/t/p/w1280", data, best, "backdrop_path")
        videos = data.get("videos", {}).get("results", [])
        trailer_url = ""
        for v in videos:
            if v.get("site") == "YouTube" and v.get("key") and v.get("type") in ("Trailer", "Teaser"):
                trailer_url = f"https://www.youtube.com/watch?v={v['key']}"
                break
        cast = []
        for c in data.get("credits", {}).get("cast", [])[:8]:
            profile_url = ("https://image.tmdb.org/t/p/w185" + c["profile_path"]) if c.get("profile_path") else ""
            cast.append({"name": c.get("name", ""), "character": c.get("character", ""), "profile_url": profile_url})
        director = next((c.get("name", "") for c in data.get("credits", {}).get("crew", []) if c.get("job") == "Director"), "")
        genres = [g.get("name", "") for g in data.get("genres", []) if g.get("name")]
        seasons = []
        for s in data.get("seasons", []) or []:
            if not s:
                continue
            season_poster = ("https://image.tmdb.org/t/p/w342" + s["poster_path"]) if s.get("poster_path") else ""
            seasons.append({
                "season_number": s.get("season_number"), "name": s.get("name", ""),
                "air_date": s.get("air_date", ""), "episode_count": s.get("episode_count"),
                "overview": s.get("overview", ""), "poster_url": season_poster,
            })
        next_episode = data.get("next_episode_to_air") or {}
        # networks: TV only — movies have no equivalent "where to stream" field from this endpoint
        networks = [n.get("name", "") for n in (data.get("networks") or []) if n.get("name")]
        return {
            "name": data.get("title") or data.get("name") or "",
            "tmdb_id": tmdb_id,
            "overview": data.get("overview", ""), "tagline": data.get("tagline", ""),
            "poster_url": poster_url, "backdrop_url": backdrop_url, "genres": genres,
            "release_date": data.get("release_date") or data.get("first_air_date") or "",
            "language": data.get("original_language", ""),
            "networks": networks,
            "runtime": data.get("runtime") or (data.get("episode_run_time") or [None])[0],
            "tmdb_rating": data.get("vote_average"), "tmdb_votes": data.get("vote_count"),
            "status": data.get("status", ""), "cast": cast, "director": director,
            "trailer_url": trailer_url, "number_of_seasons": data.get("number_of_seasons"),
            "number_of_episodes": data.get("number_of_episodes"), "last_air_date": data.get("last_air_date", ""),
            "next_episode_to_air": {"name": next_episode.get("name", ""), "air_date": next_episode.get("air_date", ""), "episode_number": next_episode.get("episode_number")},
            "seasons": seasons,
        }
    except Exception:
        return {}

  # ─────────────────────────────────────────────
  #  DISPLAY HELPERS
  # ─────────────────────────────────────────────
DETAIL_CSS = """
<style>
.detail-shell{position:relative;border:1px solid rgba(148,163,184,.16);border-radius:24px;overflow:hidden;background:linear-gradient(180deg,rgba(3,7,18,.98) 0,rgba(8,12,20,.98) 100%);box-shadow:0 20px 50px rgba(0,0,0,.30);margin-bottom:18px}.detail-hero{position:relative;min-height:460px}.detail-backdrop{position:absolute;inset:0;background-size:cover;background-position:center;filter:saturate(1.05);opacity:.42}.detail-backdrop:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(6,10,17,.10) 0,rgba(6,10,17,.76) 66%,rgba(6,10,17,.96) 100%),linear-gradient(90deg,rgba(6,10,17,.92) 0,rgba(6,10,17,.55) 38%,rgba(6,10,17,.82) 100%)}.detail-content{position:relative;z-index:2;padding:34px 34px 28px 34px}.detail-poster{width:210px;border-radius:18px;overflow:hidden;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);box-shadow:0 18px 40px rgba(0,0,0,.42)}.detail-poster img{width:100%;display:block}.detail-kicker{color:#cbd5e1;font-size:.88rem;margin-bottom:8px;letter-spacing:.02em}.detail-title{color:#f8fafc;font-size:2.35rem;line-height:1.08;font-weight:850;margin-bottom:10px}.detail-tagline{color:#c084fc;font-size:1.2rem;margin-bottom:14px;font-style:italic}.detail-meta{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px}.detail-chip{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.06);color:#e5e7eb;font-size:.78rem;font-weight:650}.detail-overview{color:#dbe4ee;font-size:1rem;line-height:1.72;max-width:880px}.detail-panel{border:1px solid rgba(148,163,184,.12);border-radius:18px;padding:18px;background:linear-gradient(180deg,rgba(17,24,39,.58) 0,rgba(10,14,23,.66) 100%);backdrop-filter:blur(10px);height:100%}.detail-panel h4{color:#f8fafc;margin:0 0 12px 0;font-size:1.06rem;font-weight:800}.detail-fact-label{color:#94a3b8;font-size:.73rem;text-transform:uppercase;letter-spacing:.08em;margin-top:6px}.detail-fact-value{color:#f8fafc;font-size:.95rem;margin-top:2px;margin-bottom:10px}.cast-strip{display:flex;gap:18px;overflow-x:auto;padding-bottom:8px;scrollbar-width:thin;scrollbar-color:rgba(148,163,184,.18) transparent}.cast-strip::-webkit-scrollbar{height:4px}.cast-strip::-webkit-scrollbar-thumb{background:rgba(148,163,184,.18);border-radius:4px}.cast-card{flex:0 0 auto;width:108px;text-align:center}.cast-avatar{width:90px;height:90px;object-fit:cover;border-radius:50%;border:2px solid rgba(148,163,184,.22);background:#1e2a3a;display:block;margin:0 auto}.cast-placeholder{width:90px;height:90px;border-radius:50%;border:2px solid rgba(148,163,184,.18);background:linear-gradient(180deg,#1e2a3a 0,#111827 100%);display:flex;align-items:center;justify-content:center;color:#64748b;font-size:.7rem;margin:0 auto}.cast-name{margin-top:9px;color:#f1f5f9;font-size:.82rem;font-weight:700;line-height:1.25;word-break:break-word}.cast-role{margin-top:3px;color:#64748b;font-size:.72rem;line-height:1.2;word-break:break-word}.season-card{display:flex;gap:14px;border:1px solid rgba(148,163,184,.10);border-radius:18px;padding:12px;background:rgba(255,255,255,.03);margin-bottom:12px}.season-poster{width:92px;min-width:92px;height:132px;object-fit:cover;border-radius:12px;border:1px solid rgba(148,163,184,.10);background:#1f2937}.season-placeholder{width:92px;min-width:92px;height:132px;border-radius:12px;border:1px solid rgba(148,163,184,.10);background:linear-gradient(180deg,#1f2937 0,#111827 100%);display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:.74rem;text-align:center;padding:6px}.season-title{color:#f8fafc;font-size:.98rem;font-weight:780;line-height:1.25}.season-meta{color:#94a3b8;font-size:.78rem;margin-top:4px}.season-overview{color:#dbe4ee;font-size:.9rem;line-height:1.6;margin-top:8px}.hero-meta-grid{display:flex;gap:32px;flex-wrap:wrap;margin-top:18px;margin-bottom:20px}.hero-meta-col{min-width:80px}.hero-meta-label{color:#94a3b8;font-size:.72rem;text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px}.hero-meta-value{color:#f1f5f9;font-size:.97rem;font-weight:600;line-height:1.3}.hero-action-btn{display:inline-flex;align-items:center;gap:8px;padding:12px 22px;border-radius:999px;font-size:.95rem;font-weight:700;cursor:pointer;border:none;text-decoration:none;transition:all .18s}.hero-action-primary{background:#7c3aed;color:#fff}.hero-action-primary:hover{background:#6d28d9}.hero-action-secondary{background:rgba(255,255,255,.10);color:#f1f5f9;border:1px solid rgba(255,255,255,.16)}.hero-action-secondary:hover{background:rgba(255,255,255,.18)}.hero-actions{display:flex;flex-direction:column;gap:10px;min-width:220px;margin-top:10px}
</style>
"""

def render_entry_detail(entry_row, vote_summary, entries_ws=None):
      if "my_collection" not in st.session_state:
          st.session_state["my_collection"] = set()
      if "my_watched_list" not in st.session_state:
          st.session_state["my_watched_list"] = set()
      st.markdown(DETAIL_CSS, unsafe_allow_html=True)
      st.markdown('<div id="detail-top"></div>', unsafe_allow_html=True)
      entry_id = _resolve_entry_id(entry_row)
      if entry_id is None:
       st.error("This entry has a corrupted ID and can't be displayed. Please contact an admin.")
       if st.button("← Back", key="detail_back_corrupted"):
        _clear_detail_view_state()
        st.rerun()
       return
      title = str(entry_row.get("title", "") or "").strip()
      media_type = normalize_media_type(entry_row.get("type", "Movie"))
      saved_tmdb_id = str(entry_row.get("tmdb_id", "") or "").strip()
      if saved_tmdb_id:
        tmdb = tmdb_fetch_details_by_id(saved_tmdb_id, media_type)
      else:
        tmdb = tmdb_fetch_details(title, media_type)  
      saved_poster = str(entry_row.get("poster_url", "") or "").strip()
      poster_url = saved_poster or tmdb.get("poster_url") or ""
      backdrop_url = tmdb.get("backdrop_url", "")
      overview = tmdb.get("overview") or str(entry_row.get("comments", "") or "").strip()
      tagline = tmdb.get("tagline", "")
      release_date = tmdb.get("release_date", "")
      release_year = release_date[:4] if release_date else str(entry_row.get("watched_year", "") or "")
      saved_genres = [g.strip() for g in str(entry_row.get("genre", "") or "").split(",") if g.strip()]
      genres = saved_genres or tmdb.get("genres") or []
      counts = vote_summary.get(entry_id, {"yes": 0, "no": 0})
      community_html = community_bar(counts["yes"], counts["no"])
      bar_l, _ = st.columns([1.1, 8.9])
      with bar_l:
          if st.button("← Back", key=f"detail_back_{entry_id}", use_container_width=True):
              _clear_detail_view_state()
              st.rerun()
      title_html = html.escape(title or tmdb.get("name") or "Untitled")
      type_html = html.escape(media_type or "—")
      platform_chip_html = _platform_chip_html(entry_row.get("platform", ""))
      status_html = status_badge(entry_row.get("status", ""))
      recommend_html = recommend_badge(entry_row.get("recommend", ""))
      genre_html = "".join(f'<span class="detail-chip">{html.escape(g)}</span>' for g in genres[:6])
      user_rating = tmdb.get("tmdb_rating")
        # Must check `is not None`, not truthy — a rating of 0.0 is valid but falsy (L10)
      tmdb_rating_chip = f'⭐ TMDB {round(user_rating, 1)}/10' if user_rating is not None else ""
      runtime = tmdb.get("runtime")
      runtime_chip = f'<span class="detail-chip">{html.escape(str(runtime))} min</span>' if runtime else ""
      season_count = tmdb.get("number_of_seasons")
      episode_count = tmdb.get("number_of_episodes")
      season_chip = f'<span class="detail-chip">{html.escape(str(season_count))} Seasons</span>' if media_type == MEDIA_TYPE_SERIES and season_count else ""
      episode_chip = f'<span class="detail-chip">{html.escape(str(episode_count))} Episodes</span>' if media_type == MEDIA_TYPE_SERIES and episode_count else ""
      meta_html = f'<div class="detail-meta">{platform_chip_html}{tmdb_rating_chip}{runtime_chip}{season_chip}{episode_chip}{status_html}{recommend_html}</div>'
      poster_markup = f'<img src="{html.escape(poster_url)}" alt="Poster for {title_html}" role="img" aria-label="Movie poster for {title_html}" loading="lazy">' if poster_url else '<div style="height:315px;display:flex;align-items:center;justify-content:center;color:#94a3b8;" role="img" aria-label="No poster available">No Poster</div>'
      tag_html = f'<div class="detail-tagline">{html.escape(tagline)}</div>' if tagline else ''
      year_html = f' • {html.escape(release_year)}' if release_year else ''
      hero_bg_style = f'background-image:url("{html.escape(backdrop_url)}");' if backdrop_url else ''
      director = tmdb.get("director", "")
      _entry_status = str(entry_row.get("status","") or "").strip().lower()
      _is_watched = _entry_status in ("watched",)
      _is_in_collection = entry_id in st.session_state.get("my_collection", set())
      _hero_lang = LANG_NAMES.get(str(tmdb.get("language") or entry_row.get("language","") or "").strip().lower(), str(tmdb.get("language") or entry_row.get("language","") or "—"))
      _runtime_fmt = f"{runtime // 60}h {runtime % 60}m" if runtime else "—"
      _origin_country = (tmdb.get("origin_country") or [""])[0] if isinstance(tmdb.get("origin_country"), list) else ""
      hero_meta_cols = []
      if director:
          hero_meta_cols.append(f'<div class="hero-meta-col"><div class="hero-meta-label">Directed By</div><div class="hero-meta-value">{html.escape(director)}</div></div>')
      if _origin_country:
          hero_meta_cols.append(f'<div class="hero-meta-col"><div class="hero-meta-label">Country</div><div class="hero-meta-value">{html.escape(_origin_country)}</div></div>')
      if _hero_lang:
          hero_meta_cols.append(f'<div class="hero-meta-col"><div class="hero-meta-label">Language</div><div class="hero-meta-value">{html.escape(_hero_lang)}</div></div>')
      if runtime:
          hero_meta_cols.append(f'<div class="hero-meta-col"><div class="hero-meta-label">Runtime</div><div class="hero-meta-value">{html.escape(_runtime_fmt)}</div></div>')
      hero_meta_row = f'<div class="hero-meta-grid">{"".join(hero_meta_cols)}</div>' if hero_meta_cols else ""
      _platform_str = html.escape(str(entry_row.get("platform", "") or ""))
      _platform_chip = f'<span class="detail-chip">▶&nbsp;{_platform_str}</span>' if _platform_str else ""
      _trailer_href = tmdb.get("trailer_url", "") or ""
      _watch_label = "✓ Watched" if _is_watched else "👁 Mark as Watched"
      _col_label   = "✓ In Collection" if _is_in_collection else "＋ Add to Collection"
      hero_html = (
          f'<div class="detail-shell"><div class="detail-hero">'
          f'<div class="detail-backdrop" style="{hero_bg_style}"></div>'
          f'<div class="detail-content">'
          f'<div style="display:flex;gap:28px;align-items:flex-start;flex-wrap:wrap;min-height:380px;">'
          f'<div class="detail-poster">{poster_markup}</div>'
          f'<div style="flex:1;min-width:260px;">'
          f'<div class="detail-kicker">{type_html}{year_html}</div>'
          f'<div class="detail-title">{title_html}</div>'
          f'{tag_html}'
          f'<div style="margin-bottom:6px;">{_platform_chip}</div>'
          f'<div style="margin-bottom:10px;">{genre_html}</div>'
          f'{hero_meta_row}'
          f'<div class="detail-overview" style="margin-top:14px;max-width:520px;">{html.escape(overview) if overview else ""}</div>'
          f'</div>'
          f'</div>'
          f'</div></div></div>'
      )
      st.markdown(hero_html, unsafe_allow_html=True)

      # ── Below-hero: two-column layout (moctale style) ──────────────
      # Left (2.4): Overview · Cast · Seasons
      # Right (1):  Action buttons · Trailer · Community panel
      body_left, body_right = st.columns([2.4, 1])

      comments_text = html.escape(str(entry_row.get("comments", "") or "").strip())
      watched_with_raw = str(entry_row.get("watched_with", "") or "").strip()
      added_by = str(entry_row.get("added_by", "") or "Unknown").strip()

      with body_left:
          st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

          # Overview
          if overview:
              st.markdown("#### Overview")
              st.markdown(f'<div style="color:#dbe4ee;font-size:1rem;line-height:1.75;margin-bottom:18px;">{html.escape(overview)}</div>', unsafe_allow_html=True)

          # Genre chips
          if genres:
              genre_chips = " ".join(
                  f'<span style="display:inline-block;padding:4px 12px;border-radius:999px;'
                  f'background:rgba(124,58,237,0.18);border:1px solid rgba(124,58,237,0.35);'
                  f'color:#c4b5fd;font-size:0.8rem;font-weight:600;margin:3px 4px 3px 0;">'
                  f'{html.escape(g)}</span>' for g in genres[:8]
              )
              st.markdown(f'<div style="margin-bottom:20px;">{genre_chips}</div>', unsafe_allow_html=True)

          # Cast
          cast = tmdb.get("cast", [])
          if cast:
              st.markdown("#### Cast")
              cast_cards = []
              for person in cast[:12]:
                  img = person.get("profile_url", "")
                  name = html.escape(person.get("name", "") or "Unknown")
                  role = html.escape(person.get("character", "") or "")
                  img_html = f'<img class="cast-avatar" src="{html.escape(img)}" alt="{name}" loading="lazy">' if img else '<div class="cast-placeholder">No Image</div>'
                  cast_cards.append(f'<div class="cast-card">{img_html}<div class="cast-name">{name}</div><div class="cast-role">{role}</div></div>')
              st.markdown(f'<div class="cast-strip">{"".join(cast_cards)}</div>', unsafe_allow_html=True)
              st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

          # Seasons (series only)
          seasons = tmdb.get("seasons", [])
          if media_type == MEDIA_TYPE_SERIES and seasons:
              st.markdown("#### Seasons")
              for season in seasons:
                  season_name = html.escape(str(season.get("name") or f"Season {season.get('season_number','')}").strip())
                  season_num = season.get("season_number")
                  ep_count = season.get("episode_count")
                  air_date = html.escape(str(season.get("air_date") or "—"))
                  overview_txt = html.escape(str(season.get("overview") or "No season overview available."))
                  poster = season.get("poster_url", "")
                  meta_line = []
                  if season_num is not None:
                      meta_line.append(f"Season {season_num}")
                  if ep_count:
                      meta_line.append(f"{ep_count} episodes")
                  meta_line.append(air_date)
                  s_meta_html = " • ".join(meta_line)
                  poster_html = f'<img class="season-poster" src="{html.escape(poster)}" alt="season poster" loading="lazy">' if poster else '<div class="season-placeholder">No Poster</div>'
                  st.markdown(f'<div class="season-card">{poster_html}<div><div class="season-title">{season_name}</div><div class="season-meta">{s_meta_html}</div><div class="season-overview">{overview_txt}</div></div></div>', unsafe_allow_html=True)

      # ── Right column: actions + trailer + community ─────────────────
      with body_right:
          st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

          # Action buttons
          _col_in = entry_id in st.session_state.get("my_collection", set())
          _w_in   = entry_id in st.session_state.get("my_watched_list", set())
          _sheet_watched = _entry_status == "watched"
          _btn_watched_label = "✓ Watched" if (_w_in or _sheet_watched) else "👁 Mark as Watched"
          if st.button(_btn_watched_label, key=f"btn_watched_{entry_id}", use_container_width=True, type="primary"):
              if _w_in or _sheet_watched:
                  st.session_state.setdefault("my_watched_list", set()).discard(entry_id)
              else:
                  st.session_state.setdefault("my_watched_list", set()).add(entry_id)
                  if entries_ws is not None:
                      try:
                          _ridx = find_row_index(entries_ws, entry_id)
                          if _ridx and _ridx > 1:
                              _upd = {c: entry_row.get(c, "") for c in COLUMNS}
                              _upd["status"] = "watched"
                              update_row(entries_ws, _ridx, _upd)
                              read_entries.clear()
                      except Exception as e:
                          # Don't fail silently — the write can still fail (network,
                          # permissions); tell the user rather than pretend it saved.
                          st.toast(f"Couldn't sync 'Watched' to the sheet: {e}", icon="⚠️")
              st.rerun()

          _col_btn_label = "✓ In Collection" if _col_in else "＋ Add to Collection"
          if st.button(_col_btn_label, key=f"btn_collect_{entry_id}", use_container_width=True):
              if _col_in:
                  st.session_state["my_collection"].discard(entry_id)
              else:
                  st.session_state.setdefault("my_collection", set()).add(entry_id)
              st.rerun()

          # Trailer button (single, here only)
          if _trailer_href:
              st.link_button("▶ Watch Trailer", _trailer_href, use_container_width=True)

          st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

          # Community panel
          watched_with_panel_html = (
              f'<div class="detail-fact-label">Watched with</div>'
              f'<div class="detail-fact-value">{html.escape(watched_with_raw)}</div>'
          ) if watched_with_raw else ""
          community_panel = (
              f'<div class="detail-panel">'
              f'<h4>Community</h4>'
              f'<div style="margin-bottom:14px;">{community_html}</div>'
              f'<div class="detail-fact-label">Your rating</div>'
              f'<div class="detail-fact-value">{html.escape(str(entry_row.get("rating", "—") or "—"))} / 10</div>'
              f'<div class="detail-fact-label">Added by</div>'
              f'<div class="detail-fact-value">{html.escape(added_by)}</div>'
              f'{watched_with_panel_html}'
              + (f'<div class="detail-fact-label">Review</div>'
                 f'<div style="color:#dbe4ee;line-height:1.75;font-size:0.88rem;white-space:pre-wrap;margin-top:4px;">{comments_text}</div>'
                 if comments_text else "")
              + f'</div>'
          )
          st.markdown(community_panel, unsafe_allow_html=True)

          # My lists (compact)
          _my_coll  = st.session_state.get("my_collection", set())
          _my_watch = st.session_state.get("my_watched_list", set())
          if _my_watch:
              with st.expander(f"👁 My Watched ({len(_my_watch)})", expanded=False):
                  st.write(", ".join(str(x) for x in _my_watch))
          if _my_coll:
              with st.expander(f"📚 My Collection ({len(_my_coll)})", expanded=False):
                  st.write(", ".join(str(x) for x in _my_coll))


def platform_badge(platform: str) -> str:
      # FIX #6: escape user-supplied values
      p = html.escape((platform or "").strip())
      lookup = _normalize_platform_name(p)
      logo = PLATFORM_LOGOS.get(lookup, "")
      if logo:
          return (
              f'<img src="{html.escape(logo)}" width="14" height="14" '
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
          return "<span style='color:#6b7280;font-size:0.75rem'>—</span>"
      r = max(0.0, min(10.0, r))
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
      key = (status or "").strip().lower()
      color, label = cfg.get(key, ("#9ca3af", (status or "—").title() if status else "—"))
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

def vote_percentages(yes: int, no: int):
    """Single source of truth for vote percentage math (L7)."""
    total = yes + no
    if total == 0:
        return None, None
    pct_yes = int(round(100 * yes / total))
    return pct_yes, 100 - pct_yes

def community_bar(yes_count: int, no_count: int) -> str:
    pct_yes, pct_no = vote_percentages(yes_count, no_count)
    if pct_yes is None:
        return '<span style="font-size:0.75rem;color:#9ca3af;font-style:italic;">No community votes yet</span>'

    return f"""
    <div style="font-size:0.75rem;margin-top:4px;">
      <span style="color:#16a34a;font-weight:600;">{yes_count} yes</span>
      &nbsp;&nbsp;
      <span style="color:#9ca3af;font-weight:600;">{no_count} no</span>
      &nbsp;&nbsp;
      <span style="color:#9ca3af;">{pct_yes}% recommend</span>
      <div style="display:flex;height:4px;border-radius:999px;overflow:hidden;margin-top:3px;background:#374151;">
        <div style="width:{pct_yes}%;background:#16a34a;"></div>
        <div style="width:{pct_no}%;background:#4b5563;"></div>
      </div>
    </div>
    """


def _normalize_entry_id(value) -> str:
      s = str(value).strip()
      if s.endswith('.0'):
          s = s[:-2]
      return s

def _resolve_entry_id(row) -> int | None:
    """Return a valid int entry_id, or None if the row's ID is unusable.
    Never falls back to a positional index — that value can collide with
    a real entry_id and misdirect votes/edit/delete (C1)."""
    raw = row.get("entry_id", "")
    norm = _normalize_entry_id(raw)  # computed once, not twice (L3)
    if norm in ("", "nan", "None"):
        return None
    try:
        return int(norm)
    except (ValueError, TypeError):
        return None
    
def _platform_chip_html(platform: str) -> str:
      p = (platform or '').strip()
      lookup = _normalize_platform_name(p)
      logo = PLATFORM_LOGOS.get(lookup, '')
      label = html.escape(p or '—')
      if logo:
          return f'<span class="detail-chip"><img src="{html.escape(logo)}" width="14" height="14" style="vertical-align:middle;margin-right:4px;border-radius:2px;"><span style="color:inherit;">{label}</span></span>'
      return f'<span class="detail-chip">{label}</span>'


def _pick_tmdb_result(results: list, title: str, year_hint=None) -> dict:
    if not results:
        return {}
    wanted = str(title or "").strip().lower()
    yh = str(year_hint or "").strip()
    def score(item):
        name = str(item.get("title") or item.get("name") or "").strip().lower()
        s = 0
        if wanted and name == wanted: s += 100
        elif wanted and name.startswith(wanted): s += 40
        elif wanted and wanted in name: s += 20
        date_val = item.get("release_date") or item.get("first_air_date") or ""
        iy = str(date_val)[:4] if date_val else ""
        if yh and iy and yh == iy:
            s += 30
        s += min(float(item.get("vote_count") or 0) / 1000.0, 10)
        return s
    return sorted(results, key=score, reverse=True)[0]

class SchemaMismatchError(Exception):
    """Raised when the live Google Sheet's header row doesn't match COLUMNS."""
    pass

def _validate_schema(ws, expected_columns: list, sheet_label: str):
    """Read the live header row once and compare against the expected schema.
    Fails loudly instead of letting append_row/update_row silently write to
    the wrong columns if someone reorders/renames a column in Sheets (C3)."""
    try:
        actual = ws.row_values(1)
    except Exception as e:
        raise SchemaMismatchError(f"Could not read header row for '{sheet_label}': {e}")
    if actual != expected_columns:
        raise SchemaMismatchError(
            f"Schema drift detected in '{sheet_label}' sheet.\n"
            f"Expected columns: {expected_columns}\n"
            f"Found columns: {actual}"
        )
  # ─────────────────────────────────────────────
  #  GOOGLE SHEETS (FIX #8: error handling)
  # ─────────────────────────────────────────────
@st.cache_resource
def get_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
    else:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open(SPREADSHEET_TITLE)
    entries = sh.sheet1

    try:
        votes = sh.worksheet("Votes")
    except WorksheetNotFound:
        votes = sh.add_worksheet(title="Votes", rows=1000, cols=3)
        votes.append_row(["entry_id", "voter_name", "vote"], value_input_option="USER_ENTERED")

    # C3 — validate schema once per connection, fail loudly on drift
    _validate_schema(entries, COLUMNS, "Entries")
    _validate_schema(votes, VOTE_COLUMNS, "Votes")

    return entries, votes


def get_sheets_safe():
    """Wrapper around get_sheets that isolates failures (M8).

    On success:
        returns (entries_ws, votes_ws)

    On failure:
        returns (None, error_message)
    """
    try:
        entries_ws, votes_ws = get_sheets()   # unpack the tuple here
        return entries_ws, votes_ws
    except SchemaMismatchError as e:
        return None, str(e)
    except Exception as e:
        st.cache_resource.clear()
        return None, f"Could not connect to Google Sheets: {e}"


def empty_df():
      # Include the derived release-date helper columns so Browse filtering
      # works even when the sheet is empty.
      return pd.DataFrame(columns=COLUMNS + ["_rel_year", "_rel_month"])


def empty_votes_df():
      return pd.DataFrame(columns=VOTE_COLUMNS)


@st.cache_data(ttl=60)
def read_entries(_ws) -> pd.DataFrame:
    try:
        data = _ws.get_all_records()
    except Exception as e:
        st.warning(f"Could not read Entries sheet ({e}). Showing empty list.")
        return empty_df()
    if not data:
        return empty_df()
    df = pd.DataFrame(data)
    if "rating" in df.columns:
          df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    if "timestamp" in df.columns:
          df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if "entry_id" not in df.columns:
          df.insert(0, "entry_id", range(2, 2 + len(df)))
      # FIX #2: Normalize type/status/recommend to lowercase consistently
    if "type" in df.columns:
          df["type"] = df["type"].str.strip().str.lower()
    if "status" in df.columns:
          df["status"] = df["status"].str.strip().str.lower()
    if "recommend" in df.columns:
          df["recommend"] = df["recommend"].str.strip().str.lower()
    if "platform" in df.columns:
          df["platform"] = df["platform"].str.strip().apply(_normalize_platform_name)
    if "language" in df.columns:
          df["language"] = df["language"].str.strip()
    # release_date stays a raw string (keeps the Sheets write/snapshot path
    # simple); derive numeric year/month helper columns for the sidebar filter.
    if "release_date" in df.columns:
        _rel = pd.to_datetime(df["release_date"], errors="coerce")
        df["_rel_year"] = _rel.dt.year.astype("Int64")
        df["_rel_month"] = _rel.dt.month.astype("Int64")
    else:
        df["_rel_year"] = pd.array([pd.NA] * len(df), dtype="Int64")
        df["_rel_month"] = pd.array([pd.NA] * len(df), dtype="Int64")
    return df


@st.cache_data(ttl=60)
def read_votes(_ws) -> pd.DataFrame:
    try:
        data = _ws.get_all_records()
    except Exception as e:
        st.warning(f"Could not read Votes sheet ({e}). Votes may be temporarily unavailable.")
        return empty_votes_df()
    if not data:
        return empty_votes_df()
    return pd.DataFrame(data)


def build_vote_summary(votes_df: pd.DataFrame) -> dict:
      summary = {}
      if votes_df.empty or "entry_id" not in votes_df.columns:
          return summary
      for _, row in votes_df.iterrows():
          try:
              # FIX #7: safely cast entry_id to int via numeric conversion
              eid  = int(pd.to_numeric(row["entry_id"], errors="coerce"))
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
      # FIX #7: use numeric comparison instead of string
      if votes_df.empty:
          return False
      numeric_ids = pd.to_numeric(votes_df["entry_id"], errors="coerce")
      mask = (
          (numeric_ids == int(entry_id)) &
          (votes_df["voter_name"].str.strip().str.lower() == voter_name.strip().lower())
      )
      return bool(mask.any())


def cast_vote(votes_ws, entry_id: int, voter_name: str, vote: str):
      votes_ws.append_row(
          [entry_id, voter_name.strip(), vote],
          value_input_option="USER_ENTERED",
      )


def _sheet_cell(value):
    """Coerce a single value into something the Google Sheets API can JSON-
    serialize. read_entries() normalizes columns (timestamp → pd.Timestamp,
    rating → float), and pd.Timestamp is NOT JSON-serializable — writing such
    a row back verbatim raised 'Object of type Timestamp is not JSON
    serializable', breaking every edit and 'Mark as watched' write (CR#1)."""
    if value is None:
        return ""
    # pandas NaN / NaT → empty cell (pd.isna on a scalar is safe)
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        # Match the "T"-separated isoformat originally written on create
        return value.isoformat(timespec="seconds")
    if isinstance(value, float) and value.is_integer():
        # rating 8.0 → "8" so the sheet keeps clean integer-looking values
        return int(value)
    return value

def _row_values_for_sheet(row_dict: dict) -> list:
    """Build the ordered, Sheets-safe cell list for a COLUMNS row."""
    return [_sheet_cell(row_dict.get(c, "")) for c in COLUMNS]

def append_row(ws, row_dict: dict):
      ws.append_row(
          _row_values_for_sheet(row_dict),
          value_input_option="USER_ENTERED",
      )

def _row_snapshot_changed(entries_ws, row_idx, original_row) -> bool:
    """Re-read the live row and compare against the snapshot the edit form
    was built from. Returns True if anything changed since page load (C2).

    Both sides are pushed through _sheet_cell so a normalized snapshot
    (pd.Timestamp / float from read_entries) compares equal to the raw string
    the live sheet returns — otherwise this always reported a false conflict
    ('2026-07-10 12:00:00' vs '2026-07-10T12:00:00', '8.0' vs '8') and blocked
    every legitimate edit (CR#2)."""
    try:
        live_values = entries_ws.row_values(row_idx)
        live = dict(zip(COLUMNS, live_values + [""] * (len(COLUMNS) - len(live_values))))
    except Exception:
        return False  # can't verify — fail open, let the save proceed rather than block on a transient read error
    for c in COLUMNS:
        if c == "timestamp":
            # Sheets stores the datetime and echoes it back space-separated
            # ('2026-07-09 11:03:06') while the normalized snapshot is a
            # pd.Timestamp rendered "T"-separated. Compare as parsed datetimes
            # so formatting differences don't register as an edit conflict.
            live_ts = pd.to_datetime(live.get(c, ""), errors="coerce")
            snap_ts = pd.to_datetime(original_row.get(c, ""), errors="coerce")
            if pd.isna(live_ts) and pd.isna(snap_ts):
                continue
            if live_ts != snap_ts:
                return True
            continue
        live_norm = str(_sheet_cell(live.get(c, ""))).strip()
        snap_norm = str(_sheet_cell(original_row.get(c, ""))).strip()
        if live_norm != snap_norm:
            return True
    return False

def update_row(ws, row_index: int, row_dict: dict):
      """Update an existing row in the sheet (1-indexed, header is row 1)."""
      values = _row_values_for_sheet(row_dict)
      ws.update(f"A{row_index}:{chr(64+len(COLUMNS))}{row_index}", [values],
                value_input_option="USER_ENTERED")


def delete_row(ws, row_index: int):
      """Delete a row from the sheet (1-indexed)."""
      ws.delete_rows(row_index)

def delete_votes_for_entry(votes_ws, votes_df, entry_id: int):
    """Remove all Votes rows matching a deleted entry_id, bottom-up so row
    indices don't shift mid-deletion (M5)."""
    if votes_df.empty or "entry_id" not in votes_df.columns:
        return
    ids = pd.to_numeric(votes_df["entry_id"], errors="coerce")
    matches = votes_df[ids == entry_id]
    for sheet_row_num in sorted(matches.index, reverse=True):
        try:
            votes_ws.delete_rows(sheet_row_num + 2)  # +2: header row + 0-index offset
        except Exception:
            pass
    read_votes.clear()

class RowLookupError(Exception):
    """Raised when find_row_index can't determine whether a row exists (H3)."""
    pass

def find_row_index(ws, entry_id) -> int:
    try:
        cell = ws.find(str(entry_id), in_column=1)
    except Exception as e:
        raise RowLookupError(f"Could not verify row for entry_id {entry_id}: {e}")
    return cell.row if cell else None

LANDING_CSS = """
<style>
/* ── Moctale-style welcome landing ────────────────────────────── */
/* Hide the sidebar entirely while the name gate is showing */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
[data-testid="stHeader"] { background: transparent !important; }

/* Near-black cinematic backdrop with a subtle purple glow */
[data-testid="stAppViewContainer"], .stApp {
    background:
        radial-gradient(1100px 520px at 50% -8%, rgba(124,58,237,0.22) 0%, rgba(124,58,237,0) 60%),
        radial-gradient(900px 500px at 85% 110%, rgba(59,130,246,0.12) 0%, rgba(59,130,246,0) 55%),
        #080808 !important;
}
/* Pull the block container to vertical centre */
.stApp [data-testid="stMainBlockContainer"],
.stApp .block-container {
    max-width: 720px;
    padding-top: 12vh;
    padding-bottom: 6vh;
}
.landing-wrap { text-align: center; }
.landing-badge {
    display: inline-block;
    font-size: 0.78rem;
    letter-spacing: 0.32em;
    text-transform: uppercase;
    color: #a78bfa;
    border: 1px solid rgba(167,139,250,0.32);
    background: rgba(124,58,237,0.10);
    padding: 6px 16px;
    border-radius: 999px;
    margin-bottom: 26px;
}
.landing-title {
    font-family: 'Cabinet Grotesk', 'Inter', sans-serif;
    font-size: clamp(2.8rem, 7vw, 4.6rem);
    font-weight: 850;
    line-height: 1.02;
    letter-spacing: -0.02em;
    margin: 0 0 14px 0;
    background: linear-gradient(180deg, #ffffff 0%, #c4b5fd 130%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}
.landing-tagline {
    font-size: clamp(1.05rem, 2.4vw, 1.4rem);
    color: #cbd5e1;
    font-weight: 400;
    margin: 0 auto 6px auto;
    max-width: 34ch;
    line-height: 1.5;
}
.landing-sub {
    font-size: 0.95rem;
    color: #6b7789;
    margin: 0 auto 34px auto;
    max-width: 40ch;
}
/* Style the name input to sit centred and feel like a hero search box */
.stApp [data-testid="stTextInput"] input {
    text-align: center;
    font-size: 1.05rem;
    padding: 14px 18px;
    border-radius: 14px;
    background: #161c27 !important;
    border: 1px solid rgba(148,163,184,0.28) !important;
    color: #f1f5f9 !important;
}
.stApp [data-testid="stTextInput"] input::placeholder { color: #6b7789 !important; }
.stApp [data-testid="stTextInput"] input:focus {
    border-color: var(--accent, #7c3aed);
    box-shadow: 0 0 0 3px rgba(124,58,237,0.25);
}
.stApp [data-testid="stTextInput"] label { justify-content: center; width: 100%; }
/* Hide Streamlit's "Press Enter to submit form" hint — it overlaps the
   centered placeholder on the welcome gate (issues #1/#5). */
.stApp [data-testid="InputInstructions"] { display: none !important; }
.stApp [data-testid="stFormSubmitButton"] button {
    width: 100%;
    border-radius: 14px;
    padding: 12px 0;
    font-weight: 700;
    background: #7c3aed;
    border: none;
    color: #fff;
}
.stApp [data-testid="stFormSubmitButton"] button:hover { background: #6d28d9; }
</style>
"""


def ensure_username() -> bool:
    """Capture and persist the user's name. Returns True when ready."""

    # 1) Make sure the keys exist in session_state
    if "username" not in st.session_state:
        st.session_state["username"] = ""
    if "voter_name" not in st.session_state:
        st.session_state["voter_name"] = st.session_state["username"]

    # 2) If we don't have a name yet, show the centered moctale-style landing
    if not st.session_state["username"].strip():
        st.markdown(GLOBAL_TOKENS_CSS, unsafe_allow_html=True)
        st.markdown(LANDING_CSS, unsafe_allow_html=True)

        # Centre the hero column
        _l, mid, _r = st.columns([1, 3, 1])
        with mid:
            st.markdown(
                """
                <div class="landing-wrap">
                    <div class="landing-badge">🎬 MediaLog</div>
                    <h1 class="landing-title">What Am I<br>Watching?</h1>
                    <p class="landing-tagline">Find tales that matter — logged, rated and recommended by your circle.</p>
                    <p class="landing-sub">Enter your name to start tracking the movies and series you love.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.form("welcome_gate_form", clear_on_submit=False):
                name_input = st.text_input(
                    "Your name",
                    key="name_entry",
                    placeholder="e.g. Pankaj",
                    label_visibility="collapsed",
                )
                submitted = st.form_submit_button("Enter MediaLog →", use_container_width=True)

        # User submitted (Enter or button) with a non-empty name → store & rerun
        if (submitted or name_input.strip()) and name_input.strip():
            cleaned = name_input.strip()
            st.session_state["username"] = cleaned
            st.session_state["voter_name"] = cleaned
            st.rerun()

        # Username not ready yet → tell caller to stop
        return False

    # 3) We DO have a name. The sidebar chrome (name + Change name) is rendered
    #    by render_sidebar() so it sits below the logo/Home — nothing to draw here.
    return True

TOP_NAV_CSS = """
<style>
/* ── Reclaim the big empty band at the top of the main area ─────── */
[data-testid="stMainBlockContainer"] {
    padding-top: 0.6rem !important;
}
/* Tighten the default 1rem gap between stacked elements so the first row
   of the movie list is reachable without scrolling past a tall header. */
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] {
    gap: 0.55rem !important;
}
/* Slimmer horizontal rules */
[data-testid="stMain"] hr,
[data-testid="stMain"] [data-testid="stDivider"] { margin: 0.35rem 0 !important; }
/* Compact the collapsed "Tonight's picks" expander header */
.st-key-tonight_expander summary { font-size: 1.02rem !important; font-weight: 700 !important; }

/* Streamlit's fixed top chrome sits at z-index ~999990 and is 60px tall — it
   would cover a sticky bar pinned to top:0. Make it transparent + non-blocking
   so our tab bar can pin flush to the very top without being hidden behind it. */
[data-testid="stHeader"] {
    background: transparent !important;
    height: 0 !important;
    pointer-events: none;
}
/* keep the built-in toolbar buttons (deploy/menu) clickable */
[data-testid="stHeader"] [data-testid="stToolbar"],
[data-testid="stHeader"] [data-testid="stDecoration"] { pointer-events: auto; }

/* ── Sticky top navigation TABS (Browse / Add Entry / Reports) ───── */
/* Streamlit 1.58 renders st.segmented_control as stButtonGroup; the keyed
   wrapper .st-key-_nav_tabs is the stable hook. z-index must beat Streamlit's
   header (~999990) so the tabs are never hidden behind it while scrolling. */
.st-key-_nav_tabs {
    position: sticky;
    top: 0;
    z-index: 999999;
    background: var(--bg, #0b0f17);
    padding: 10px 0 0 0;
    margin-bottom: 14px;
    border-bottom: 1px solid var(--border, rgba(148,163,184,0.14));
}
.st-key-_nav_tabs [data-testid="stButtonGroup"] { gap: 6px; }
.st-key-_nav_tabs button {
    background: transparent !important;
    border: none !important;
    border-radius: 10px 10px 0 0 !important;
    color: var(--text-muted, #a3adc2) !important;
    font-size: 1.06rem !important;
    font-weight: 700 !important;
    padding: 13px 30px !important;
    border-bottom: 3px solid transparent !important;
    margin-bottom: -1px !important;
    transition: color .15s, border-color .15s, background .15s;
}
.st-key-_nav_tabs button:hover {
    color: var(--text, #f1f5f9) !important;
    background: var(--surface-2, #161c27) !important;
}
.st-key-_nav_tabs button[data-testid="stBaseButton-segmented_controlActive"] {
    color: var(--text, #f1f5f9) !important;
    background: var(--surface-2, #161c27) !important;
    border-bottom: 3px solid var(--accent, #7c3aed) !important;
}

/* ── Rich inline TYPE segmented control (All / Movies / Series) ──── */
.st-key-browse_type_seg [data-testid="stButtonGroup"] {
    display: inline-flex;
    gap: 3px;
    background: var(--surface-2, #161c27);
    border: 1px solid var(--border, rgba(148,163,184,0.14));
    border-radius: 12px;
    padding: 4px;
    box-shadow: var(--shadow-sm, 0 2px 8px rgba(0,0,0,0.24));
}
.st-key-browse_type_seg button {
    background: transparent !important;
    border: none !important;
    border-radius: 9px !important;
    color: var(--text-muted, #a3adc2) !important;
    font-size: 0.96rem !important;
    font-weight: 650 !important;
    padding: 9px 26px !important;
    transition: background .15s, color .15s;
}
.st-key-browse_type_seg button:hover { color: var(--text, #f1f5f9) !important; }
.st-key-browse_type_seg button[data-testid="stBaseButton-segmented_controlActive"] {
    background: var(--accent, #7c3aed) !important;
    color: #fff !important;
    box-shadow: 0 2px 8px rgba(124,58,237,0.35);
}
</style>
"""


def render_top_nav():
    """Render the Browse / Add Entry / Reports navigation as top-of-page tabs.
    Returns the selected page string. Honours forced navigation from dialogs."""
    st.markdown(TOP_NAV_CSS, unsafe_allow_html=True)

    _nav_pages = ["Browse", "Add Entry", "Reports"]
    _nav_icons = {"Browse": "🎬 Browse", "Add Entry": "＋ Add Entry", "Reports": "📊 Reports"}

    # Forced navigation (e.g. after a save) — write the widget key BEFORE render.
    _forced = st.session_state.pop("_force_nav", None)
    if _forced in _nav_pages:
        st.session_state["_nav_tabs"] = _nav_icons[_forced]

    _label = st.segmented_control(
        "Navigate",
        options=[_nav_icons[p] for p in _nav_pages],
        default=_nav_icons["Browse"],
        key="_nav_tabs",
        label_visibility="collapsed",
    )

    # Map the icon label back to the plain page name (segmented_control can
    # return None if somehow deselected — fall back to Browse).
    page = next((p for p in _nav_pages if _nav_icons[p] == _label), "Browse")

    # Remember last page to clear detail view when changing pages
    prev_page = st.session_state.get("prev_page")
    if prev_page is not None and prev_page != page:
        _clear_detail_view_state()
    st.session_state["prev_page"] = page
    return page


  # ─────────────────────────────────────────────
  #  SIDEBAR
  # ─────────────────────────────────────────────
def render_sidebar(entries_df=None):
    """Render sidebar chrome + the Year/Month release filter.
    Returns (current_name, sel_year, sel_month)."""

    # Logo / title
    st.sidebar.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;padding:4px 0 12px 0;">
          <span style="font-size:1.7rem;">🎬</span>
          <span style="font-size:1.15rem;font-weight:800;color:#f1f5f9;">MediaLog</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Home button resets detail view state
    if st.sidebar.button("🏠 Home", use_container_width=True, key="logo_home_btn"):
        for k in ("selected_entry_id", "selected_entry_title", "selected_entry_type"):
            st.session_state.pop(k, None)
        st.rerun()

    # Current username + change-name control (single source; ensure_username()
    # sets the value, the sidebar renders it here).
    current_name = st.session_state.get("username", "").strip()
    if current_name:
        st.sidebar.markdown(f"👤 **{html.escape(current_name)}**")
    if st.sidebar.button("Change name", key="change_name_btn", use_container_width=True):
        st.session_state["username"] = ""
        st.session_state["voter_name"] = ""
        st.rerun()

    # ── Year / Month release filter (moctale-style) ────────────────
    sel_year, sel_month = _render_year_month_filter(entries_df)

    return current_name, sel_year, sel_month


def _render_year_month_filter(entries_df):
    """Sidebar Year + Month pills that filter Browse by TMDB release_date.
    Year-only selection returns the whole year; a month narrows within it.
    Returns (sel_year:int|None, sel_month:int|None)."""
    st.sidebar.divider()
    st.sidebar.markdown("**Release date**")

    # Available years come from the data (release_date backfilled from TMDB).
    years = []
    if entries_df is not None and "_rel_year" in entries_df.columns:
        years = sorted(
            {int(y) for y in entries_df["_rel_year"].dropna().tolist()},
            reverse=True,
        )
    if not years:
        st.sidebar.caption("No release dates available yet.")
        return None, None

    st.sidebar.caption("Year")
    sel_year = st.sidebar.pills(
        "Year", years, selection_mode="single",
        format_func=str, key="rel_year_pills", label_visibility="collapsed",
    )

    sel_month = None
    if sel_year is not None:
        st.sidebar.caption("Month")
        # Only offer months that actually have entries for the chosen year.
        months_present = sorted({
            int(m) for m in entries_df.loc[
                entries_df["_rel_year"] == sel_year, "_rel_month"
            ].dropna().tolist()
        })
        if months_present:
            sel_month = st.sidebar.pills(
                "Month", months_present, selection_mode="single",
                format_func=lambda m: MONTH_ABBR[m], key="rel_month_pills",
                label_visibility="collapsed",
            )
        if st.sidebar.button("Clear year/month", key="clear_rel_filter", use_container_width=True):
            st.session_state.pop("rel_year_pills", None)
            st.session_state.pop("rel_month_pills", None)
            st.rerun()

    return sel_year, sel_month


# ─────────────────────────────────────────────
#  PAGE: ADD ENTRY (FIX #1: UUID-based ID, Enhancement #2: duplicate detection)
# ─────────────────────────────────────────────
def page_add_entry(entries_ws, current_name: str):
    # ── Step indicator ──────────────────────────────────────────────
    _add_step = st.session_state.get("_add_step", 1)
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:0;margin-bottom:18px;">
      <div style="display:flex;align-items:center;gap:8px;padding:6px 16px;border-radius:999px;
           background:{'#7c3aed' if _add_step == 1 else 'rgba(124,58,237,0.18)'};
           color:{'#fff' if _add_step == 1 else '#a78bfa'};font-weight:700;font-size:0.88rem;">
        ① Search &amp; Select
      </div>
      <div style="flex:1;height:2px;background:rgba(148,163,184,0.2);max-width:40px;"></div>
      <div style="display:flex;align-items:center;gap:8px;padding:6px 16px;border-radius:999px;
           background:{'#7c3aed' if _add_step == 2 else 'rgba(124,58,237,0.18)'};
           color:{'#fff' if _add_step == 2 else '#a78bfa'};font-weight:700;font-size:0.88rem;">
        ② Your Details
      </div>
      <div style="flex:1;height:2px;background:rgba(148,163,184,0.2);max-width:40px;"></div>
      <div style="display:flex;align-items:center;gap:8px;padding:6px 16px;border-radius:999px;
           background:rgba(124,58,237,0.18);color:#a78bfa;font-weight:700;font-size:0.88rem;">
        ③ Done
      </div>
    </div>
    """, unsafe_allow_html=True)
    reset_n = st.session_state.get("_add_form_reset", 0)

    # ── Step 1: TMDB search or skip to manual ──────────────────────
    _tmdb_expanded = _add_step == 1
    _skip_col, _spacer = st.columns([2, 8])
    with _skip_col:
        if st.button("Skip → Fill manually", key="skip_tmdb_btn", use_container_width=True):
            st.session_state["_add_step"] = 2
            st.rerun()

    with st.expander("🔍 Step 1 — Auto-fill from TMDB", expanded=_tmdb_expanded):
        af1, af2, af3 = st.columns([4, 1, 1])
        with af1:
            tmdb_q = st.text_input(
                "Search title on TMDB",
                placeholder="e.g. Inception — type then click Search",
                key="tmdb_title_input",
            )
        with af2:
            tmdb_t = st.selectbox("Type", ["Movie", "WebSeries"], key="tmdb_type_input")
        with af3:
            st.write("")
            st.write("")
            do_search = st.button("Search", key="tmdb_search_btn", use_container_width=True)
        if do_search:
            if tmdb_q.strip():
                with st.spinner("Searching TMDB…"):
                    results_list = tmdb_search(tmdb_q.strip(), tmdb_t)
                if results_list:
                    st.session_state["tmdb_results"]   = results_list
                    st.session_state["tmdb_query"]     = tmdb_q.strip()
                    st.session_state["tmdb_type_sel"]  = tmdb_t
                    st.session_state["tmdb_sel_idx"]   = 0
                    st.session_state.pop("tmdb_result", None)
                else:
                    st.warning("No results found. Try a different spelling.")
                    st.session_state.pop("tmdb_results", None)
            else:
                st.warning("Please enter a title to search.")

        if "tmdb_results" in st.session_state:
            results_list = st.session_state["tmdb_results"]
            option_labels = [
                f"{r['name']} ({r['year'] or '?'})" for r in results_list
            ]
            sel_idx = st.selectbox(
                "Select the correct match:",
                options=list(range(len(option_labels))),
                format_func=lambda i: option_labels[i],
                key="tmdb_sel_idx",
            )
            res = results_list[sel_idx]
            rc1, rc2 = st.columns([1, 4])
            with rc1:
                if res.get("poster"):
                    st.image(res["poster"], width=80)
            with rc2:
                st.info(
                    f"**{res.get('name', '')}** ({res.get('year', '?')})  \n"
                    f"Genres: {', '.join(res.get('genres', []))}"
                )
                if st.button("✅  Use this data", key="tmdb_use_btn"):
                    st.session_state["pf_title"]  = res.get("name", st.session_state.get("tmdb_query", ""))
                    st.session_state["pf_tmdb_id"] = res.get("id", "") 
                    st.session_state["pf_year"]   = res.get("year", "")
                    st.session_state["pf_genres"] = res.get("genres", [])
                    st.session_state["pf_type"]   = st.session_state.get("tmdb_type_sel", "Movie")
                    st.session_state["pf_poster"] = res.get("poster", "")

                    # Platform + Language need the full details endpoint (search results
                    # don't carry networks/original_language) — fetch once by ID.
                    with st.spinner("Fetching platform & language…"):
                        details = tmdb_fetch_details_by_id(
                            res.get("id", ""), st.session_state.get("tmdb_type_sel", "Movie")
                        )
                    st.session_state["pf_platform"] = _platform_from_tmdb_networks(details.get("networks", []))
                    st.session_state["pf_language"] = _language_from_tmdb_code(details.get("language", ""))
                    # Capture TMDB release date so the sheet's release_date column
                    # is populated for the Year/Month filter without a later lookup.
                    st.session_state["pf_release_date"] = details.get("release_date", "") or ""
                    st.session_state["_add_form_reset"] = st.session_state.get("_add_form_reset", 0) + 1
                    st.session_state["_add_step"] = 2
                    st.session_state.pop("tmdb_results", None)
                    st.rerun()

    pf_title    = st.session_state.get("pf_title",    "")
    pf_year     = st.session_state.get("pf_year",     "")
    pf_genres   = st.session_state.get("pf_genres",   [])
    pf_type     = st.session_state.get("pf_type",     "Movie")
    pf_poster   = st.session_state.get("pf_poster",   "")
    pf_platform = st.session_state.get("pf_platform", "")
    pf_language = st.session_state.get("pf_language", "")

    if pf_poster:
        st.session_state["pending_poster"] = pf_poster

    # ── Main form ───────────────────────────────────────────────────
    with st.form("add_entry_form", clear_on_submit=False):
        st.markdown("##### 🎬 What did you watch")
        c1, c2 = st.columns(2)
        with c1:
            added_by = st.text_input(
                "Your name *",
                value=current_name,
                placeholder="e.g. Pankaj",
                key=f"add_addedby_{reset_n}",
            )
        with c2:
            title = st.text_input(
                "Title *",
                value=pf_title,
                placeholder="e.g. Mirzapur Season 3",
                help="Use original title if possible.",
                key=f"add_title_{reset_n}",
            )
        c3, c4, c5 = st.columns(3)
        with c3:
            type_opts = ["Movie", "WebSeries"]
            type_idx  = type_opts.index(pf_type) if pf_type in type_opts else 0
            media_type = st.selectbox("Type", type_opts, index=type_idx, key=f"add_type_{reset_n}")
        with c4:
            platform_idx = PLATFORMS.index(pf_platform) if pf_platform in PLATFORMS else 0
            platform = st.selectbox(
                "Platform", PLATFORMS, index=platform_idx,
                help="Pick the main platform where you watched it.",  key=f"add_platform_{reset_n}"
            )
        with c5:
            status = st.selectbox("Status", ["Watched", "Watching", "Plan"], index=0, key=f"add_status_{reset_n}")
        st.divider()
        st.markdown("##### ⭐ Your experience")
        c6, c7 = st.columns(2)
        with c6:
            valid_pf_g = [g for g in pf_genres if g in GENRES_LIST]
            genre_sel  = st.multiselect(
                "Genre",
                options=GENRES_LIST,
                default=valid_pf_g,
                help="Select all genres that apply.", key=f"add_genre_{reset_n}"
            )
        with c7:
            language_idx = LANGUAGES.index(pf_language) if pf_language in LANGUAGES else 0
            language = st.selectbox("Language", LANGUAGES, index=language_idx, key=f"add_language_{reset_n}")
        rating       = None
        recommend    = ""
        watched_year = datetime.now().year

        if status != "Plan": 
            c8, c9, c10 = st.columns([2, 1, 1])
            with c8:
                rating = st.slider("Rating (1–10)", 1, 10, 6, key=f"add_rating_{reset_n}")
            with c9:
                recommend = st.radio(
                    "Recommend?", ["Yes", "No"], horizontal=True, index=0, key=f"add_recommend_{reset_n}"
                ).lower()
            with c10:
                min_year = 1900
                max_year = datetime.now().year + 1
                try:
                    yr_default = int(float(pf_year)) if str(pf_year).strip() else datetime.now().year
                except (ValueError, TypeError):
                    yr_default = datetime.now().year
                yr_default = max(min_year, min(yr_default, max_year))
                watched_year = st.number_input(
                    "Year watched",
                    min_value=min_year,
                    max_value=max_year,
                    value=yr_default,
                    step=1, key=f"add_watchedyear_{reset_n}"
                )
        st.divider()
        # ENHANCEMENT #10: "Watched with" field
        with st.expander("➕ Extra details (watched with, review)", expanded=False):
            watched_with = st.text_input(
            "Watched with (optional)", placeholder="e.g. Rohan, Priya",
            help="Who did you watch this with?", key=f"add_watchedwith_{reset_n}"
            )
            comments = st.text_area("Review / comments", "", label_visibility="collapsed", key=f"add_comments_{reset_n}")
        submitted = st.form_submit_button(
            "💾 Save entry", use_container_width=True, type="primary"
        )
    # CR#3: after "Add anyway" the dialog reruns WITHOUT resubmitting the form,
    # so `submitted` is False and the save block would be skipped — the entry
    # was never actually added. Proceed if the duplicate was just confirmed for
    # this title (widgets retain their values across the rerun).
    _pending_dup_key = f"confirm_duplicate_{title.strip().lower()}"
    if submitted or st.session_state.get(_pending_dup_key):
        errors = []
        if not added_by.strip():
            errors.append("Your name is required.")
        if not title.strip():
            errors.append("Title is required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            dup_key = f"confirm_duplicate_{title.strip().lower()}"
            try:
                existing_df = read_entries(entries_ws)
                duplicates = existing_df[existing_df["title"].str.strip().str.lower() == title.strip().lower()]

                if not duplicates.empty and not st.session_state.get(dup_key):
                    dup_by = duplicates.iloc[0].get("added_by", "someone")

                    @st.dialog("Possible duplicate")
                    def confirm_dup():
                        st.write(f"'{title.strip()}' was already logged by **{dup_by}**.")
                        d1, d2 = st.columns(2)
                        with d1:
                            if st.button("Add anyway", type="primary", use_container_width=True):
                                st.session_state[dup_key] = True
                                st.rerun()
                        with d2:
                            if st.button("Cancel", use_container_width=True):
                                st.rerun()

                    confirm_dup()
                    st.stop()

            except Exception:
                existing_df = empty_df()
                st.session_state.pop(dup_key, None)

            if added_by.strip():
                st.session_state["username"] = added_by.strip()
                st.session_state["voter_name"] = added_by.strip()
                poster_url = st.session_state.pop("pending_poster", "")
                # Millisecond epoch as a unique-enough entry_id. NOT a UUID —
                # two adds within the same millisecond would collide; acceptable
                # for this single-user-at-a-time app.
                next_id = int(time.time() * 1000)

                row = {
                    "entry_id": next_id,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "added_by": added_by.strip(),
                    "title": title.strip(),
                    "type": media_type.lower(),
                    "genre": ", ".join(genre_sel) if genre_sel else "",
                    "platform": platform.strip(),
                    "status": status.lower(),
                    "rating": rating if rating is not None else "",
                    "recommend": recommend if status != "Plan" else "",
                    "watched_year": watched_year if status != "Plan" else "",
                    "language": language,
                    "comments": comments.strip() if comments else "",
                    "poster_url": poster_url,
                    "watched_with": watched_with.strip() if watched_with else "",
                    "tmdb_id": st.session_state.get("pf_tmdb_id", ""),
                    "release_date": st.session_state.get("pf_release_date", ""),
                }
                try:
                    append_row(entries_ws, row)
                    read_entries.clear()
                    st.session_state["_entries_dirty"] = True
                    # Clear TMDB prefill state
                    for k in ("pf_title", "pf_year", "pf_genres", "pf_type", "pf_poster", "pf_platform", "pf_language", "pf_tmdb_id", "pf_release_date"):
                        st.session_state.pop(k, None)
                    st.session_state.pop(dup_key, None)
                    st.session_state["_add_form_reset"] = st.session_state.get("_add_form_reset", 0) + 1
                    st.session_state["_add_step"] = 1
                    st.toast(f"✓ {title.strip()} added to your MediaLog!", icon="🎬")
                    st.session_state["_force_nav"] = "Browse"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving entry: {e}")

# ─────────────────────────────────────────────
#  PAGE: BROWSE (FIX #4: pagination reset, FIX #5: stable picks, Enhancement #3: sort)
# ─────────────────────────────────────────────
def render_stats_grid(stats):
    st.markdown("""
    <style>
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
        margin: 10px 0 18px 0;
    }
    .stat-card {
        background: linear-gradient(180deg, var(--surface-2) 0%, var(--surface) 100%);
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        padding: 22px 20px;
        min-height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        position: relative;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
    }
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
        border-color: var(--border-strong);
    }
    .stat-card::before {
        content: "";
        position: absolute;
        top: 0; left: 0;
        width: 4px; height: 100%;
        background: var(--accent);
        opacity: 0.85;
    }
    .stat-value {
        font-size: 2.6rem;
        line-height: 1;
        font-weight: 700;
        color: var(--text);
        letter-spacing: -0.02em;
    }
    .stat-label {
        margin-top: 10px;
        font-size: 0.85rem;
        line-height: 1.3;
        color: var(--text-muted);
        font-weight: 500;
        max-width: 16ch;
    }
    @media (max-width: 900px) {
        .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
        .stat-card { padding: 18px 16px; min-height: 118px; }
        .stat-value { font-size: 2.1rem; }
        .stat-label { font-size: .82rem; }
    }
    @media (max-width: 480px) {
        .stats-grid { grid-template-columns: 1fr; }
        .stat-card { min-height: 100px; }
    }
    .back-to-top-wrap {
        position: fixed; right: 18px; bottom: 20px; z-index: 9998;
    }
    .back-to-top-wrap button {
        width: 48px; height: 48px; border-radius: 999px; border: none;
        background: var(--accent); color: #fff; font-size: 1.2rem;
        box-shadow: var(--shadow-md); cursor: pointer; transition: var(--transition);
    }
    .back-to-top-wrap button:hover { background: var(--accent-hover); transform: translateY(-2px); }
    </style>
    """, unsafe_allow_html=True)

    cards = []
    for label, value in stats:
        cards.append(
            f'<div class="stat-card">'
            f'<div class="stat-value">{html.escape(str(value))}</div>'
            f'<div class="stat-label">{html.escape(str(label))}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="stats-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_back_to_top_button():
      st.markdown("""
      <style>
      #btt-btn{position:fixed;right:22px;bottom:28px;z-index:9998;width:48px;height:48px;
        border-radius:50%;border:none;background:#1e293b;color:#f1f5f9;font-size:1.3rem;
        box-shadow:0 8px 24px rgba(0,0,0,.4);cursor:pointer;display:flex;
        align-items:center;justify-content:center;transition:opacity .25s,transform .2s;opacity:0.85;}
      #btt-btn:hover{background:#334155;transform:translateY(-3px);opacity:1!important}
      </style>
      <button id="btt-btn" onclick="(window.parent||window).scrollTo({top:0,behavior:'smooth'})" title="Back to top">↑</button>
      <script>
      (function(){
        var win=window.parent||window;
        function check(){
          var btn=document.getElementById('btt-btn');
          if(!btn)return;
          var s=win.scrollY||win.pageYOffset||0;
          btn.style.opacity = s>80 ? '1' : '0.35';
        }
        win.addEventListener('scroll', check, {passive: true});
        check();
      })();
      </script>
      """, unsafe_allow_html=True)


def _stable_daily_picks(pool_df: pd.DataFrame, date_str: str, n: int) -> pd.DataFrame:
    """Deterministic, order-independent 'stable for today' selection (M2).
    Unlike DataFrame.sample(random_state=...), this depends only on which
    entry_ids currently qualify + today's date — not on the pool's row
    order, so it won't silently pick a different set if the pool is
    rebuilt (e.g. after a cache refresh) with the same members in a
    different order."""
    ids = pool_df["entry_id"].apply(_normalize_entry_id)
    ranked = sorted(ids, key=lambda eid: hashlib.md5(f"{date_str}:{eid}".encode()).hexdigest())
    chosen = set(ranked[:n])
    return pool_df[ids.isin(chosen)]

def page_browse(entries_ws, votes_ws, sel_year=None, sel_month=None):
    st.markdown("""
    <style>
    .browse-toolbar div[data-testid="stHorizontalBlock"] {align-items:end; gap:0.5rem;}
    @media (max-width: 768px) { .browse-toolbar div[data-testid="stHorizontalBlock"] {gap:0.45rem;} }
    </style>
    """, unsafe_allow_html=True)

    # BUG-08: if we just navigated here after a save, bust the cache so the
    # new entry is immediately visible (read_entries.clear() after append is
    # correct but the dialog rerun can race against the 30s TTL)
    if st.session_state.pop("_entries_dirty", False):
        read_entries.clear()

    with st.spinner(""):
        ph = st.empty()
        ph.markdown('<div style="display:flex;gap:14px;"><div style="height:100px;width:100%;background:var(--surface-2);border-radius:12px;animation:pulse 1.5s infinite;"></div></div><style>@keyframes pulse{0%{opacity:.6}50%{opacity:1}100%{opacity:.6}}</style>', unsafe_allow_html=True)
        df = read_entries(entries_ws)
        votes_df = read_votes(votes_ws)
        ph.empty()
    vote_summary = build_vote_summary(votes_df)

    selected_entry_id = st.session_state.get("selected_entry_id")
    if selected_entry_id is not None:
        sel_str = _normalize_entry_id(selected_entry_id)
        df_copy = df.copy()
        df_copy["_eid_str"] = df_copy["entry_id"].apply(_normalize_entry_id)
        selected_df = df_copy[df_copy["_eid_str"] == sel_str].drop(columns=["_eid_str"])
        if selected_df.empty:
            sel_title = str(st.session_state.get("selected_entry_title", "") or "").strip().lower()
            sel_type = str(st.session_state.get("selected_entry_type", "") or "").strip().lower()
            if sel_title:
                title_mask = df["title"].astype(str).str.strip().str.lower() == sel_title
                if sel_type and "type" in df.columns:
                    type_mask = df["type"].astype(str).str.strip().str.lower() == sel_type
                    selected_df = df[title_mask & type_mask]
                else:
                    selected_df = df[title_mask]
        if not selected_df.empty:
            render_entry_detail(selected_df.iloc[0], vote_summary, entries_ws)
            return
        _clear_detail_view_state()

    if df.empty:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
            <div style="font-size:4rem;margin-bottom:16px;">🎬</div>
            <div style="font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:8px;">Nothing logged yet</div>
            <div style="color:#94a3b8;font-size:1rem;">Add your first movie or series to get started.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    search_text = st.text_input(
        "🔍 Search titles",
        placeholder="Search by title…",
        key="browse_search",
        label_visibility="collapsed",
        autocomplete="off",
    )

    # ── ENHANCEMENT #4: Activity feed ─────────────────────────────
    if "timestamp" in df.columns:
        recent = df.dropna(subset=["timestamp"]).sort_values("timestamp", ascending=False).head(3)
        if not recent.empty:
            activity_parts = []
            for _, r in recent.iterrows():
                ago = _time_ago(r["timestamp"])
                activity_parts.append(f"**{html.escape(str(r.get('title','')))}** by {html.escape(str(r.get('added_by','')))} ({ago})")
            st.markdown("🆕 Recently added: " + " · ".join(activity_parts))

    # ── FIX #5: Tonight's picks — stable for the day ──────────────
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
            # Collapsed by default so the movie list is visible without scrolling;
            # users can expand to see the daily picks.
            with st.expander("🍿 Tonight's picks — top-rated community recommendations", expanded=False):
                sample_size = min(3, len(top_pool))
                # FIX #5 / M2: deterministic by entry_id + date, independent of row order
                today_str = datetime.now().strftime("%Y%m%d")
                # CR#4: .head(sample_size) guards against >sample_size rows when two
                # entries share a normalized entry_id (isin can match extras) — without
                # it, pcols[i] overflows the columns list and crashes the Browse page.
                picks = _stable_daily_picks(top_pool, today_str, sample_size).head(sample_size)
                pcols = st.columns(sample_size)
                for i, (_, pr) in enumerate(picks.iterrows()):
                    with pcols[i]:
                        poster = pr.get("poster_url", "") or ""
                        if poster:
                            st.image(poster, width=70)
                        st.markdown(
                            f"**{html.escape(str(pr.get('title','–')))}**  \n"
                            f"{platform_badge(pr.get('platform',''))} &nbsp; "
                            f"{rating_stars(pr.get('rating'))}",
                            unsafe_allow_html=True,
                        )
                        pick_eid = _normalize_entry_id(pr.get("entry_id", ""))
                        if st.button("View Details", key=f"tonight_view_{pick_eid}_{i}", use_container_width=True):
                            st.session_state["selected_entry_id"] = pick_eid
                            st.session_state["selected_entry_title"] = str(pr.get("title", "") or "").strip()
                            st.session_state["selected_entry_type"] = str(pr.get("type", "") or "").strip()
                            st.rerun()
    # ── Quick-filter chip bar (always visible) ─────────────────────
    st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"].chip-row > div[data-testid="column"] {
        padding: 0 4px 0 0 !important;
        min-width: unset !important;
        flex: 0 0 auto !important;
    }
    div[data-testid="stHorizontalBlock"].chip-row button {
        border-radius: 999px !important;
        font-size: 0.82rem !important;
        padding: 4px 14px !important;
        white-space: nowrap !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Inline filter row: type segmented control + preset chips + Mine ──
    # (moctale-style: All / Movies / Series sits inline with the filters)
    _TYPE_CHOICES = ["All", "Movies", "Series"]
    type_choice = st.segmented_control(
        "Type", _TYPE_CHOICES, default="All",
        key="browse_type_seg", label_visibility="collapsed",
    ) or "All"

    _preset_chips = ["All", "Recommended only", "High ratings (≥ 8)", "Plan to Watch"]
    _current_preset = st.session_state.get("browse_preset", "All")

    chip_c = st.columns(len(_preset_chips) + 2)
    for _ci, _chip in enumerate(_preset_chips):
        with chip_c[_ci]:
            _active = _current_preset == _chip
            _label = ("✓ " if _active else "") + _chip
            if st.button(_label, key=f"chip_{_ci}", use_container_width=False,
                         type="primary" if _active else "secondary"):
                st.session_state["browse_preset"] = _chip
                st.rerun()
    with chip_c[len(_preset_chips)]:
        show_mine = st.checkbox("Mine only", value=False, key="show_mine_check")

    preset = st.session_state.get("browse_preset", "All")
    my_name = st.session_state.get("username", "").strip()

    # ── Advanced filters in collapsible expander ──────────────────
    with st.expander("⚙ More filters & sort", expanded=False):
        sort_choice = st.selectbox("Sort by", list(SORT_OPTIONS.keys()), index=0, key="sort_select")

        fc1, fc2, fc3, fc4, fc5, fc6 = st.columns(6)
        with fc1:
            plat_f = st.multiselect("Platform", PLATFORMS, key="f_plat")
        with fc2:
            type_f = st.multiselect("Type", ["movie", "webseries"], key="f_type")
        with fc3:
            stat_f = st.multiselect("Status", ["watched", "watching", "plan"], key="f_stat")
        with fc4:
            rec_f = st.multiselect("Rec", ["yes", "no"], key="f_rec")
        with fc5:
            genre_f = st.multiselect("Genre", GENRES_LIST, key="f_genre")
        with fc6:
            lang_f = st.multiselect("Language", LANGUAGES, key="f_lang")

        active_count = sum([
            bool(plat_f),
            bool(type_f),
            bool(stat_f),
            bool(rec_f),
            bool(genre_f),
            bool(lang_f),
            preset != "All",
            show_mine,
        ])
        if active_count:
            st.caption(f"🔧 {active_count} filter(s) active")

      # ── Apply filters ──────────────────────────────────────────────
    filtered = df.copy()

    # Year / Month release filter (from the sidebar). Year-only keeps the whole
    # year; a month narrows within it. Rows without a release_date are excluded
    # when a year is selected (they have no year to match).
    if sel_year is not None and "_rel_year" in filtered.columns:
        filtered = filtered[filtered["_rel_year"] == sel_year]
        if sel_month is not None and "_rel_month" in filtered.columns:
            filtered = filtered[filtered["_rel_month"] == sel_month]

    # Inline type segmented control (All / Movies / Series). Applied here so the
    # "Showing X of Y" count reflects the choice.
    if type_choice != "All" and "type" in filtered.columns:
        _want = "webseries" if type_choice == "Series" else "movie"
        filtered = filtered[filtered["type"].str.strip().str.lower() == _want]

    if preset == "Recommended only":
        filtered = filtered[filtered.get("recommend", pd.Series(dtype=str)).str.lower() == "yes"]
    elif preset == "High ratings (≥ 8)":
        if "rating" in filtered.columns:
            filtered = filtered[pd.to_numeric(filtered["rating"], errors="coerce") >= 8]
    elif preset == "Plan to Watch":
        # ENHANCEMENT #5: quick filter for Plan entries
        filtered = filtered[filtered["status"].str.lower() == "plan"]

    if show_mine and my_name:
        filtered = filtered[filtered["added_by"].str.strip().str.lower() == my_name.lower()]
    if search_text:
        filtered = filtered[filtered["title"].str.contains(search_text, case=False, na=False, regex=False)]
    if plat_f and "platform" in filtered.columns:
        filtered = filtered[filtered["platform"].isin(plat_f)]
    if lang_f and "language" in filtered.columns:
        filtered = filtered[filtered["language"].isin(lang_f)]
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

# ENHANCEMENT #3: Apply sort
    sort_col, sort_asc = SORT_OPTIONS[sort_choice]

    if sort_col == "_total_votes":
        def _safe_eid(eid):
            v = pd.to_numeric(eid, errors="coerce")
            return int(v) if pd.notna(v) else None

        filtered["_total_votes"] = filtered["entry_id"].apply(
            lambda eid: sum(vote_summary.get(_safe_eid(eid), {"yes": 0, "no": 0}).values())
        )
        filtered = (
            filtered.sort_values("_total_votes", ascending=sort_asc)
            .drop(columns=["_total_votes"])
        )
    elif sort_col == "rating" and "rating" in filtered.columns:
        filtered["_rating_num"] = pd.to_numeric(filtered["rating"], errors="coerce").fillna(0)
        filtered = (
            filtered.sort_values("_rating_num", ascending=sort_asc)
            .drop(columns=["_rating_num"])
        )

    elif sort_col == "title" and "title" in filtered.columns:
        filtered = _safe_sort(filtered, "title", sort_asc)

    elif sort_col in filtered.columns:
        filtered = filtered.sort_values(sort_col, ascending=sort_asc, na_position="last")

      # FIX #4: Detect filter changes and reset pagination
    current_filter_sig = f"{preset}|{show_mine}|{search_text}|{plat_f}|{type_f}|{stat_f}|{rec_f}|{genre_f}|{lang_f}|{sort_choice}|{type_choice}|{sel_year}|{sel_month}"
    if st.session_state.get("_last_filter_sig") != current_filter_sig:
        st.session_state["_last_filter_sig"] = current_filter_sig
        for k in list(st.session_state.keys()):
            if k.startswith("browse_page_"):
                st.session_state[k] = 1

    total = len(df)
    st.caption(f"Showing **{len(filtered)}** of **{total}** entries")

    st.divider()
    PAGINATION_CSS = """<style>
    .pagination-wrap button {
        border-radius: 999px !important;
        border: 1px solid var(--border) !important;
        background: var(--surface-2) !important;
        font-weight: 600 !important;
        }
    .pagination-wrap button:hover:not(:disabled) {
        border-color: var(--accent) !important;
        background: var(--accent-soft) !important;
        }
        </style>"""
    # -- Pagination + render helper (FIX #9: explicit params)
    def _paginate_render(tab_df, tab_key, v_mode, v_summary, v_df, v_ws):
        t_total = len(tab_df)
        t_pages = max(1, (t_total + PAGE_SIZE - 1) // PAGE_SIZE)
        pg_key  = "browse_page_" + tab_key
        if pg_key not in st.session_state:
            st.session_state[pg_key] = 1
        st.session_state[pg_key] = min(st.session_state[pg_key], t_pages)
        page_start = (st.session_state[pg_key] - 1) * PAGE_SIZE
        page_data  = tab_df.iloc[page_start : page_start + PAGE_SIZE]
        if t_pages > 1:
            st.markdown(PAGINATION_CSS, unsafe_allow_html=True)
            st.markdown('<div class="pagination-wrap">', unsafe_allow_html=True)
            pg1, pg2, pg3 = st.columns([1, 3, 1])
            with pg1:
                if st.button("◄ Prev", disabled=st.session_state[pg_key] <= 1,
                    key="prev_" + tab_key):
                    st.session_state[pg_key] -= 1
                    st.rerun()
            with pg2:
                st.markdown(
                    "<div style='text-align:center;color:#9ca3af;font-size:0.85rem;"
                    "padding-top:6px;'>Page " + str(st.session_state[pg_key]) +
                    " of " + str(t_pages) + "</div>",
                    unsafe_allow_html=True,
                )
            with pg3:
                if st.button("Next ►", disabled=st.session_state[pg_key] >= t_pages,
                    key="next_" + tab_key):
                    st.session_state[pg_key] += 1
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        if v_mode == "Cards":
            _render_cards(page_data, v_summary, v_df, v_ws, entries_ws, render_scope=tab_key)
        else:
            _render_table(page_data, v_summary)

    # `filtered` is already narrowed by the inline type segmented control, so a
    # single scoped render replaces the old All/Movies/Web Series tabs. The
    # scope key varies by type so pagination state doesn't bleed between views.
    _scope = {"Movies": "movies", "Series": "series"}.get(type_choice, "all")
    if filtered.empty and type_choice != "All":
        _noun = "movies" if type_choice == "Movies" else "web series"
        st.info(f"No {_noun} match the current filters.")
    else:
        _paginate_render(filtered, _scope, "Cards", vote_summary, votes_df, votes_ws)


  # ─────────────────────────────────────────────
  #  PAGE: REPORTS
  # ─────────────────────────────────────────────
def page_reports(entries_ws):
      st.subheader("📊 Reports")
      df = read_entries(entries_ws)
      if df.empty:
          st.info("No data yet.")
          return

      _r_total   = len(df)
      _r_movies  = int((df["type"].str.lower() == "movie").sum()) if "type" in df.columns else 0
      _r_series  = int((df["type"].str.lower() == "webseries").sum()) if "type" in df.columns else 0
      _r_avg     = df["rating"].mean() if "rating" in df.columns else float("nan")
      _r_watched = df[df["status"].str.lower() == "watched"] if "status" in df.columns else df
      _r_rec_pct = int(100 * (_r_watched["recommend"].str.lower() == "yes").sum() / max(len(_r_watched), 1)) if "recommend" in df.columns else 0
      _r_watched_df = df[df["status"].str.lower() == "watched"] if "status" in df.columns else df.iloc[0:0]
      _r_hrs = int(len(_r_watched_df) * 1.8)  # rough estimate: 1.8h avg per title
      render_stats_grid([
          ("Total titles", _r_total),
          ("Movies", _r_movies),
          ("Web series", _r_series),
          ("Avg rating", f"{_r_avg:.1f}" if pd.notna(_r_avg) else "–"),
          ("Recommend %", f"{_r_rec_pct}%"),
          ("Est. hours watched", f"~{_r_hrs}h"),
      ])
      st.divider()

      tab1, tab2, tab3, tab4 = st.tabs(["By Platform", "By Genre", "By Person", "Watched Together"])

      with tab1:
          if "platform" in df.columns:
              pc = (
                  df["platform"].fillna("Unknown").replace("", "Unknown")
                  .value_counts()
                  .rename_axis("Platform").reset_index(name="Count").set_index("Platform")
              )
              with st.container(border=True):
                st.markdown("**By Platform**")
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
              with st.container(border=True):
                st.markdown("**By Genre**")
                st.bar_chart(gc)
                st.dataframe(gc.reset_index(), use_container_width=True)

      with tab3:
          if "added_by" in df.columns:
              ac = (
                  df["added_by"].fillna("Unknown")
                  .value_counts()
                  .rename_axis("Person").reset_index(name="Entries").set_index("Person")
              )
              with st.container(border=True):
                st.markdown("**By AddedBy**")
                st.bar_chart(ac)
                st.dataframe(ac.reset_index(), use_container_width=True)

      # ENHANCEMENT #10: "Watched Together" stats
      with tab4:
          if "watched_with" in df.columns:
              wt = df[df["watched_with"].fillna("").str.strip() != ""]
              if wt.empty:
                  st.info("No 'watched with' data yet. Start adding who you watch with!")
              else:
                  companions = (
                      wt["watched_with"].str.split(",").explode()
                      .str.strip().str.title()
                      .value_counts()
                      .rename_axis("Companion").reset_index(name="Times Watched Together")
                      .set_index("Companion")
                  )
                  with st.container(border=True):
                    st.markdown("**By Companions**")
                    st.bar_chart(companions)
                    st.dataframe(companions.reset_index(), use_container_width=True)
          else:
              st.info("'Watched with' column not available yet.")


  # ─────────────────────────────────────────────
  #  HELPER: time ago
  # ─────────────────────────────────────────────
def _time_ago(dt) -> str:
      if pd.isna(dt):
          return ""
      now = datetime.now()
      try:
          delta = now - dt.to_pydatetime().replace(tzinfo=None)
      except Exception:
          return ""
      seconds = int(delta.total_seconds())
      if seconds < 60:
          return "just now"
      elif seconds < 3600:
          return f"{seconds // 60}m ago"
      elif seconds < 86400:
          return f"{seconds // 3600}h ago"
      else:
          return f"{seconds // 86400}d ago"


  # ─────────────────────────────────────────────
  #  CARD RENDERER (FIX #3: use session_state for CSS injection)
  # ─────────────────────────────────────────────
CARD_CSS = """<style>
  .wlog-card {
      border: 1px solid rgba(148,163,184,0.15);
      border-radius: 10px;
      padding: 12px 14px 14px 14px;
      margin-bottom: 8px;
      background: var(--surface, #11161f);
  }
  .wlog-card-title { font-size:1.0rem; font-weight:700; color:inherit; }
  .wlog-card-meta  { font-size:0.76rem; color:#94a3b8; margin-left:6px; }
  .wlog-card-footer{ margin-top:3px; font-size:0.70rem; color:#6b7280; }
  .wlog-card-review{ margin-top:4px; font-size:0.82rem; color:#cbd5e1; }
  .wlog-divider {
      border: none;
      border-top: 1px solid rgba(148,163,184,0.10);
      margin: 1px 0;
  }
  .wlog-vote-row   { display:flex; align-items:center; gap:8px; margin-top:5px; }
  .wlog-vote-label { font-size:0.72rem; color:#6b7280; }
  div[data-testid="stHorizontalBlock"] { gap: 0 !important; }
  div[data-testid="column"] { padding: 0 4px 0 0 !important; }
  .wlog-vote-strip div[data-testid="stVerticalBlock"]   { gap: 0 !important; }
  .wlog-vote-strip div[data-testid="stHorizontalBlock"] { margin-top: -8px !important; margin-bottom: -6px !important; }
  .wlog-vote-strip button { padding: 2px 8px !important; font-size: 0.78rem !important; height: 28px !important; min-height: 28px !important; }
  section[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
      margin-bottom: 0 !important;
      padding-bottom: 0 !important;
  }
  </style>"""


def _inject_card_css():
      # FIX #3: use session_state instead of fragile module-level global
      if not st.session_state.get("clickable_card_css_injected"):
        # CARD_CSS was defined but never injected — that's why .wlog-card had no
        # padding and the footer collided with the buttons below it (issue #3).
        st.markdown(CARD_CSS, unsafe_allow_html=True)
        st.markdown(CLICKABLE_CARD_CSS, unsafe_allow_html=True)
        st.session_state["clickable_card_css_injected"] = True


def _render_cards(filtered, vote_summary, votes_df, votes_ws, entries_ws, render_scope="main"):
    _inject_card_css()

    if filtered.empty:
        st.markdown("""
        <div style="text-align:center;padding:48px 20px;">
            <div style="font-size:3rem;margin-bottom:12px;">🔍</div>
            <div style="font-size:1.2rem;font-weight:700;color:#f1f5f9;margin-bottom:6px;">No results found</div>
            <div style="color:#94a3b8;font-size:0.95rem;">Try adjusting your search or clearing some filters.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    voter_name = st.session_state.get("voter_name", "").strip()
    current_user = st.session_state.get("username", "").strip()

    _all_rows = list(filtered.iterrows())
    for _pair_start in range(0, len(_all_rows), 2):
        _pair_slice = _all_rows[_pair_start:_pair_start + 2]
        _grid_cols = st.columns(len(_pair_slice))
        for _col_i, (idx, row) in enumerate(_pair_slice):
            with _grid_cols[_col_i]:
                # Basic fields
                raw_title = str(row.get("title", "") or "").strip()
                media_type = normalize_media_type(row.get("type", "Movie"))
                platform = str(row.get("platform", "") or "").strip()
                genre = str(row.get("genre", "") or "").strip()
                raw_status = row.get("status", "")
                status_key = str(raw_status).strip().lower() if pd.notna(raw_status) else ""
                raw_rating = row.get("rating", "")

                # Resolve entry_id and handle corrupted IDs early
                entry_id = _resolve_entry_id(row)
                if entry_id is None:
                    st.markdown(
                        f'<div class="wlog-card"><span style="color:#f87171;font-size:.85rem;">'
                        f'⚠ "{html.escape(raw_title)}" has a corrupted entry_id — '
                        f'skipped. Ask an admin to repair this row.</span></div>',
                        unsafe_allow_html=True,
                    )
                    continue  # skip vote/edit/delete widgets for this row entirely

                # Display text (card body)
                title_txt     = row.get("title", "—") or "—"
                title_raw     = str(title_txt)
                # Use normalized media type for nicer label
                type_txt      = "Movie" if media_type == MEDIA_TYPE_MOVIE else "Web Series"
                genre_txt     = row.get("genre", "") or "—"
                added_by_txt  = row.get("added_by", "") or "Unknown"
                comments_txt  = row.get("comments", "") or ""
                poster_url    = row.get("poster_url", "") or ""
                watched_with  = row.get("watched_with", "") or ""

                platform_html  = platform_badge(row.get("platform", ""))
                rating_html    = rating_stars(row.get("rating"))
                status_html    = status_badge(row.get("status", ""))
                recommend_html = recommend_badge(row.get("recommend", ""))

                # XSS protection
                title_txt     = html.escape(str(title_txt))
                type_txt      = html.escape(str(type_txt))
                genre_txt     = html.escape(str(genre_txt))
                added_by_txt  = html.escape(str(added_by_txt))
                comments_txt  = html.escape(str(comments_txt))
                watched_with  = html.escape(str(watched_with))

                # Vote summary
                counts    = vote_summary.get(entry_id, {"yes": 0, "no": 0})
                comm_bar  = community_bar(counts["yes"], counts["no"])

                # ENHANCEMENT #6: spoiler toggle for reviews
                review_html = ""
                if comments_txt:
                    review_html = (
                        f'<details style="margin-top:4px;">'
                        f'<summary style="font-size:0.78rem;color:#94a3b8;cursor:pointer;">💬 Show review</summary>'
                        f'<div class="wlog-card-review">{comments_txt}</div>'
                        f'</details>'
                    )

                # ENHANCEMENT #10: show "watched with" info
                watched_with_html = ""
                if watched_with:
                    watched_with_html = (
                        f'<span style="font-size:0.72rem;color:#94a3b8;margin-left:8px;">👥 {watched_with}</span>'
                    )

                # Build the inner card layout
                if poster_url:
                    img_html = (
                        f'<img src="{html.escape(poster_url)}" width="54" height="80" '
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
                            <div class="wlog-card-footer">Added by {added_by_txt}{watched_with_html}</div>
                        </div>
                    </div>
                    """
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
                    <div class="wlog-card-footer">Added by {added_by_txt}{watched_with_html}</div>
                    """

                # Wrap inner layout and normalize whitespace → card_html
                raw_card_html = f'<div class="wlog-card">{card_inner}</div>'
                card_html = re.sub(r"\s+", " ", raw_card_html).strip()

                # Render card + actions
                with st.container():
                    st.markdown(card_html, unsafe_allow_html=True)

                    col_a, col_b = st.columns([1, 1])
                    with col_a:
                        if st.button("🔍 View Details", key=f"view_details_{render_scope}_{entry_id}_{idx}", use_container_width=True,):
                            st.session_state["selected_entry_id"] = entry_id
                            st.session_state["selected_entry_title"] = title_raw
                            st.session_state["selected_entry_type"] = media_type
                            st.rerun()

                    with col_b:
                        # Vote + Edit/Delete row
                        with st.expander("Vote / Manage", expanded=False):
                            _render_vote_widget(
                                entry_id,
                                title_txt,
                                voter_name,
                                votes_df,
                                votes_ws,
                                counts["yes"],
                                counts["no"],
                                idx,
                                render_scope,
                            )
                            if (
                                current_user
                                and current_user.lower()
                                == (row.get("added_by", "") or "").strip().lower()
                            ): _render_edit_delete(entry_id, row, entries_ws, votes_ws, idx, render_scope)

        st.markdown('<hr class="wlog-divider">', unsafe_allow_html=True)

def _selectbox_preserve(label, options, current, key=None):
    """Selectbox that never silently discards an off-list current value (H1)."""
    opts = list(options)
    if current and current not in opts:
        opts = opts + [current]
    idx = opts.index(current) if current in opts else 0
    return st.selectbox(label, opts, index=idx, key=key)

  # ─────────────────────────────────────────────
  #  ENHANCEMENT #1: EDIT/DELETE WIDGET
  # ─────────────────────────────────────────────
def _render_edit_delete(entry_id, row, entries_ws, votes_ws, card_idx, render_scope):
    """
    Edit-only controls for an entry. Delete has been removed.
    - entry_id: int ID of the entry
    - row: dict-like record from the entries DataFrame
    - entries_ws: gspread worksheet for Entries
    - votes_ws: gspread worksheet for Votes (currently unused here)
    - card_idx: index of the card in the current page
    - render_scope: string key for scoping widget IDs
    """
    scope = render_scope or "default"
    edit_key = f"editing_{entry_id}_{scope}"

    # Top-level Edit button on the card
    col_edit, _, _ = st.columns([1, 1, 8])
    with col_edit:
        if st.button(
            "✏️ Edit",
            key=f"edit_btn_{entry_id}_{card_idx}_{scope}",
            help="Edit this entry",
        ):
            st.session_state[edit_key] = True
            st.rerun()

    # If not in editing mode, nothing more to do
    if not st.session_state.get(edit_key):
        return

    # Inline edit form
    with st.form(f"edit_form_{entry_id}_{scope}", clear_on_submit=False):
        st.markdown(f"**Editing:** {html.escape(str(row.get('title', '')))}")

        # Row 1: Title
        new_title = st.text_input("Title", value=row.get("title", "") or "")

        # Row 2: Platform / Status / Rating
        col1, col2, col3 = st.columns(3)
        with col1:
            new_platform = _selectbox_preserve(
                "Platform",
                PLATFORMS,
                row.get("platform", ""),
                key=f"edit_platform_{entry_id}_{scope}",
            )
        with col2:
            current_status = str(row.get("status", "") or "").strip().lower()
            new_status = _selectbox_preserve(
                "Status",
                ["watched", "watching", "plan"],
                current_status,
                key=f"edit_status_{entry_id}_{scope}",
            )
        with col3:
            raw_rating = row.get("rating", "")
            try:
                _raw_str = str(raw_rating).strip()
                base_rating = int(float(_raw_str)) if _raw_str not in ("", "nan", "None", "<NA>") else 8
                base_rating = max(1, min(10, base_rating))
            except (ValueError, TypeError):
                base_rating = 8
            new_rating = st.slider("Rating", 1, 10, base_rating)

        # Row 3: Genre / Language
        col4, col5 = st.columns(2)
        with col4:
            current_genres = [g.strip() for g in str(row.get("genre", "") or "").split(",") if g.strip()]
            valid_genres = [g for g in current_genres if g in GENRES_LIST]
            new_genre = st.multiselect("Genre", GENRES_LIST, default=valid_genres,
                                       key=f"edit_genre_{entry_id}_{scope}")
        with col5:
            current_lang = str(row.get("language", "") or "").strip()
            new_language = _selectbox_preserve(
                "Language", LANGUAGES, current_lang,
                key=f"edit_language_{entry_id}_{scope}",
            )

        # Row 4: Recommend / Watched Year / Watched With (only for non-plan)
        current_rec = str(row.get("recommend", "") or "").strip().lower()
        rec_options = ["", "yes", "no"]
        rec_idx = rec_options.index(current_rec) if current_rec in rec_options else 0

        col6, col7, col8 = st.columns(3)
        with col6:
            new_recommend = st.selectbox(
                "Recommend?", rec_options,
                index=rec_idx,
                format_func=lambda x: "—" if x == "" else x.capitalize(),
                key=f"edit_rec_{entry_id}_{scope}",
            )
        with col7:
            min_year, max_year = 1900, datetime.now().year + 1
            try:
                wy_default = int(float(str(row.get("watched_year", "") or ""))) if str(row.get("watched_year", "") or "").strip() else datetime.now().year
                wy_default = max(min_year, min(wy_default, max_year))
            except (ValueError, TypeError):
                wy_default = datetime.now().year
            new_watched_year = st.number_input(
                "Year watched", min_value=min_year, max_value=max_year,
                value=wy_default, step=1,
                key=f"edit_wy_{entry_id}_{scope}",
            )
        with col8:
            new_watched_with = st.text_input(
                "Watched with",
                value=str(row.get("watched_with", "") or ""),
                key=f"edit_ww_{entry_id}_{scope}",
            )

        # Comments
        new_comments = st.text_area(
            "Review / comments",
            value=row.get("comments", "") or "",
        )

        save_clicked = st.form_submit_button("Save changes", type="primary")
        cancel_clicked = st.form_submit_button("Cancel")

    # SAVE branch — outside the form so st.rerun() works correctly
    if save_clicked:
        if not new_title.strip():
            st.error("Title cannot be empty.")
        else:
            row_idx = None
            try:
                row_idx = find_row_index(entries_ws, entry_id)
            except RowLookupError as e:
                st.error(f"Could not find or verify the entry: {e}")

            if row_idx is not None:
                if row_idx <= 1:
                    st.error("Cannot overwrite the header row — entry ID may be corrupted.")
                elif _row_snapshot_changed(entries_ws, row_idx, row):
                    st.warning("This entry was modified by someone else while you had it open. Close the form and try again.")
                else:
                    try:
                        updated = {c: row.get(c, "") for c in COLUMNS}
                        updated["title"] = new_title.strip()
                        updated["platform"] = (new_platform or "").strip()
                        updated["status"] = (new_status or "").strip().lower()
                        updated["comments"] = new_comments.strip()
                        updated["genre"] = ", ".join(new_genre) if new_genre else ""
                        updated["language"] = new_language or ""
                        updated["watched_with"] = new_watched_with.strip()

                        if updated["status"] == "plan":
                            updated["rating"] = ""
                            updated["recommend"] = ""
                            updated["watched_year"] = ""
                        else:
                            updated["rating"] = new_rating
                            updated["recommend"] = new_recommend
                            updated["watched_year"] = new_watched_year

                        update_row(entries_ws, row_idx, updated)
                        read_entries.clear()
                        st.session_state.pop(edit_key, None)
                        st.success("Updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Update failed: {e}")

    # CANCEL branch
    if cancel_clicked:
        st.session_state.pop(edit_key, None)
        st.rerun()


  # ─────────────────────────────────────────────
  #  VOTE WIDGET
  # ─────────────────────────────────────────────
def _render_vote_widget(entry_id, title_txt, voter_name,
                          votes_df, votes_ws, yes_cnt, no_cnt, card_idx, render_scope=None):
      scope = render_scope or "default"
      voted_key        = f"voted_{entry_id}"
      voted_in_sheet   = voter_name and already_voted(votes_df, entry_id, voter_name)
      voted_in_session = st.session_state.get(voted_key, None)

      if not voter_name:
          return

      if voted_in_sheet or voted_in_session:
          prior = voted_in_session or "previously"
          st.markdown(
              f'<span style="font-size:0.75rem;color:#9ca3af;">Your vote: <strong>{prior}</strong></span>',
              unsafe_allow_html=True,
          )
          return

      st.markdown(VOTE_CSS, unsafe_allow_html=True)
      lbl_col, yes_col, no_col, _ = st.columns([2, 1, 1, 4])
      with lbl_col:
          st.markdown(
              '<span style="font-size:0.75rem;color:#9ca3af;">Your vote:</span>',
              unsafe_allow_html=True,
          )
      with yes_col:
          if st.button("👍", key=f"yes_{entry_id}_{card_idx}_{scope}", help=f"Recommend {title_txt}"):
              try:
                  cast_vote(votes_ws, entry_id, voter_name, "yes")
                  st.session_state[voted_key] = "👍 yes"
                  read_votes.clear()
                  st.rerun()
              except Exception as e:
                  st.error("Could not save vote.")
      with no_col:
          if st.button("👎", key=f"no_{entry_id}_{card_idx}_{scope}", help=f"Skip {title_txt}"):
              try:
                  cast_vote(votes_ws, entry_id, voter_name, "no")
                  st.session_state[voted_key] = "👎 no"
                  read_votes.clear()
                  st.rerun()
              except Exception as e:
                  st.error("Could not save vote. Please try again.")

  # ─────────────────────────────────────────────
  #  TABLE RENDERER
  # ─────────────────────────────────────────────
def _render_table(filtered, vote_summary):
      if filtered.empty:
          st.info("No entries match the current filters.")
          return

      df_display = filtered.copy()

      def _comm_votes(row):
          eid = row.get("entry_id", 0)
          try:
              eid = int(float(eid))
          except (ValueError, TypeError):
              eid = 0
          counts = vote_summary.get(eid, {"yes": 0, "no": 0})
          total  = counts["yes"] + counts["no"]
          if total == 0:
              return "—"
          pct_yes, _ = vote_percentages(counts["yes"], counts["no"])
          return f'👍{counts["yes"]} / 👎{counts["no"]} ({pct_yes}%)'

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
          # CR polish: .title() turns "webseries" → "Webseries"; use the
          # canonical normalizer so it reads "Web Series".
          df_display["type"] = df_display["type"].apply(
              lambda t: "Web Series" if normalize_media_type(t) == MEDIA_TYPE_SERIES else "Movie"
          )

      col_order = ["title", "type", "genre", "platform", "rating",
                   "recommend", "community_votes", "status", "language",
                   "added_by", "watched_year", "watched_with"]
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
    # 1) Streamlit page config
    st.set_page_config(
        page_title="What Am I Watching?",
        page_icon="🎬",
        layout="wide",
    )

    # 1b) Global design tokens + responsive rules (define the --surface/--accent
    #     CSS variables and fonts the rest of the app's inline styles depend on).
    st.markdown(GLOBAL_TOKENS_CSS, unsafe_allow_html=True)
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)

    # 2) Welcome / username gate
    ready = ensure_username()
    if not ready:
        # Still on the welcome screen; don't render the rest yet
        return

    # 3) Connect to Google Sheets
    entries_ws, votes_ws_or_error = get_sheets_safe()
    if entries_ws is None:
        # votes_ws_or_error here is actually the error message
        st.error(votes_ws_or_error or "Could not connect to Google Sheets.")
        return
    votes_ws = votes_ws_or_error

    # 4) Top-tab navigation (Browse / Add Entry / Reports)
    page = render_top_nav()

    # 5) Sidebar chrome + Year/Month release filter (needs the entries df so
    #    the year list reflects real data). Cheap: read_entries is cached.
    _entries_for_filter = read_entries(entries_ws)
    current_name, sel_year, sel_month = render_sidebar(_entries_for_filter)
    render_back_to_top_button()

    # 6) Route to selected page
    if page == "Add Entry":
        page_add_entry(entries_ws, current_name)
    elif page == "Reports":
        page_reports(entries_ws)
    else:  # "Browse"
        page_browse(entries_ws, votes_ws, sel_year, sel_month)

if __name__ == "__main__":
      main()