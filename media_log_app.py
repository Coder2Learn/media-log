import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound
from datetime import datetime
import random
import re
import html
import uuid

  # ─────────────────────────────────────────────
  #  CONFIG
  # ─────────────────────────────────────────────
SPREADSHEET_TITLE    = "MediaLog"
SERVICE_ACCOUNT_FILE = "media-log-service-account.json"
TMDB_BASE            = "https://api.themoviedb.org/3"
TMDB_IMG_BASE        = "https://image.tmdb.org/t/p/w200"
PAGE_SIZE            = 100

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

PLATFORMS = ["", "Netflix", "Prime Video", "Jio Hotstar", "SonyLiv", "Zee5", "YouTube", "Other"]

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
      "watched_year", "language", "comments", "poster_url", "watched_with",
  ]


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

TMDB_GENRE_MAP = {
      28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
      80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
      14: "Fantasy", 27: "Horror", 10749: "Romance", 878: "Sci-Fi",
      53: "Thriller", 10759: "Action", 10762: "Animation", 10765: "Sci-Fi",
      10766: "Drama", 10767: "Other", 10768: "Other",
  }


  # ─────────────────────────────────────────────
  #  TMDB HELPER (FIX #9: cached with TTL)
  # ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def tmdb_search(title: str, media_type: str) -> list:
      """Return up to 5 results from TMDB. Cached for 1 hour."""
      key = st.secrets.get("tmdb_api_key", "")
      if not key or not title.strip():
          return []
      t = "tv" if media_type == "WebSeries" else "movie"
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
              genres = list(dict.fromkeys(TMDB_GENRE_MAP.get(gid, "Other") for gid in genre_ids[:3]))
              poster = ""
              if item.get("poster_path"):
                  poster = TMDB_IMG_BASE + item["poster_path"]
              name = item.get("title") or item.get("name") or title
              out.append({"year": year, "genres": genres, "poster": poster, "name": name})
          return out
      except Exception:
          return []


@st.cache_data(ttl=3600)
def tmdb_fetch_details(title: str, media_type: str) -> dict:
      key = st.secrets.get("tmdb_api_key", "")
      if not key or not title.strip():
          return {}
      t = "tv" if media_type == "WebSeries" else "movie"
      try:
          sr = requests.get(f"{TMDB_BASE}/search/{t}", params={"api_key": key, "query": title.strip(), "language": "en-US", "page": 1}, timeout=6)
          sr.raise_for_status()
          results = sr.json().get("results", [])
          if not results:
              return {}
          best = _pick_tmdb_result(results, title, None) or results[0]
          tmdb_id = best.get("id")
          if not tmdb_id:
              return {}
          dr = requests.get(f"{TMDB_BASE}/{t}/{tmdb_id}", params={"api_key": key, "language": "en-US", "append_to_response": "credits,videos"}, timeout=8)
          dr.raise_for_status()
          data = dr.json()
          poster_url = ("https://image.tmdb.org/t/p/w342" + data["poster_path"]) if data.get("poster_path") else (("https://image.tmdb.org/t/p/w342" + best["poster_path"]) if best.get("poster_path") else "")
          backdrop_url = ("https://image.tmdb.org/t/p/w1280" + data["backdrop_path"]) if data.get("backdrop_path") else (("https://image.tmdb.org/t/p/w1280" + best["backdrop_path"]) if best.get("backdrop_path") else "")
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
          return {"name": data.get("title") or data.get("name") or title, "overview": data.get("overview", ""), "tagline": data.get("tagline", ""), "poster_url": poster_url, "backdrop_url": backdrop_url, "genres": genres, "release_date": data.get("release_date") or data.get("first_air_date") or "", "language": data.get("original_language", ""), "runtime": data.get("runtime") or (data.get("episode_run_time") or [None])[0], "tmdb_rating": data.get("vote_average"), "tmdb_votes": data.get("vote_count"), "status": data.get("status", ""), "cast": cast, "trailer_url": trailer_url, "number_of_seasons": data.get("number_of_seasons"), "number_of_episodes": data.get("number_of_episodes"), "last_air_date": data.get("last_air_date", ""), "next_episode_to_air": {"name": next_episode.get("name", ""), "air_date": next_episode.get("air_date", ""), "episode_number": next_episode.get("episode_number")}, "seasons": seasons}
      except Exception:
          return {}


  # ─────────────────────────────────────────────
  #  DISPLAY HELPERS
  # ─────────────────────────────────────────────
DETAIL_CSS = """
<style>
.detail-shell{position:relative;border:1px solid rgba(148,163,184,.16);border-radius:24px;overflow:hidden;background:linear-gradient(180deg,rgba(3,7,18,.98) 0,rgba(8,12,20,.98) 100%);box-shadow:0 20px 50px rgba(0,0,0,.30);margin-bottom:18px}.detail-hero{position:relative;min-height:460px}.detail-backdrop{position:absolute;inset:0;background-size:cover;background-position:center;filter:saturate(1.05);opacity:.42}.detail-backdrop:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(6,10,17,.10) 0,rgba(6,10,17,.76) 66%,rgba(6,10,17,.96) 100%),linear-gradient(90deg,rgba(6,10,17,.92) 0,rgba(6,10,17,.55) 38%,rgba(6,10,17,.82) 100%)}.detail-content{position:relative;z-index:2;padding:34px 34px 28px 34px}.detail-poster{width:210px;border-radius:18px;overflow:hidden;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);box-shadow:0 18px 40px rgba(0,0,0,.42)}.detail-poster img{width:100%;display:block}.detail-kicker{color:#cbd5e1;font-size:.88rem;margin-bottom:8px;letter-spacing:.02em}.detail-title{color:#f8fafc;font-size:2.35rem;line-height:1.08;font-weight:850;margin-bottom:10px}.detail-tagline{color:#c084fc;font-size:.98rem;margin-bottom:14px;font-style:italic}.detail-meta{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px}.detail-chip{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.06);color:#e5e7eb;font-size:.78rem;font-weight:650}.detail-overview{color:#dbe4ee;font-size:1rem;line-height:1.72;max-width:880px}.detail-panel{border:1px solid rgba(148,163,184,.12);border-radius:18px;padding:18px;background:linear-gradient(180deg,rgba(17,24,39,.58) 0,rgba(10,14,23,.66) 100%);backdrop-filter:blur(10px);height:100%}.detail-panel h4{color:#f8fafc;margin:0 0 12px 0;font-size:1.06rem;font-weight:800}.detail-fact-label{color:#94a3b8;font-size:.73rem;text-transform:uppercase;letter-spacing:.08em;margin-top:6px}.detail-fact-value{color:#f8fafc;font-size:.95rem;margin-top:2px;margin-bottom:10px}.cast-strip{display:flex;gap:18px;overflow-x:auto;padding-bottom:8px;scrollbar-width:thin;scrollbar-color:rgba(148,163,184,.18) transparent}.cast-strip::-webkit-scrollbar{height:4px}.cast-strip::-webkit-scrollbar-thumb{background:rgba(148,163,184,.18);border-radius:4px}.cast-card{flex:0 0 auto;width:108px;text-align:center}.cast-avatar{width:90px;height:90px;object-fit:cover;border-radius:50%;border:2px solid rgba(148,163,184,.22);background:#1e2a3a;display:block;margin:0 auto}.cast-placeholder{width:90px;height:90px;border-radius:50%;border:2px solid rgba(148,163,184,.18);background:linear-gradient(180deg,#1e2a3a 0,#111827 100%);display:flex;align-items:center;justify-content:center;color:#64748b;font-size:.7rem;margin:0 auto}.cast-name{margin-top:9px;color:#f1f5f9;font-size:.82rem;font-weight:700;line-height:1.25;word-break:break-word}.cast-role{margin-top:3px;color:#64748b;font-size:.72rem;line-height:1.2;word-break:break-word}.season-card{display:flex;gap:14px;border:1px solid rgba(148,163,184,.10);border-radius:18px;padding:12px;background:rgba(255,255,255,.03);margin-bottom:12px}.season-poster{width:92px;min-width:92px;height:132px;object-fit:cover;border-radius:12px;border:1px solid rgba(148,163,184,.10);background:#1f2937}.season-placeholder{width:92px;min-width:92px;height:132px;border-radius:12px;border:1px solid rgba(148,163,184,.10);background:linear-gradient(180deg,#1f2937 0,#111827 100%);display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:.74rem;text-align:center;padding:6px}.season-title{color:#f8fafc;font-size:.98rem;font-weight:780;line-height:1.25}.season-meta{color:#94a3b8;font-size:.78rem;margin-top:4px}.season-overview{color:#dbe4ee;font-size:.9rem;line-height:1.6;margin-top:8px}.hero-meta-grid{display:flex;gap:32px;flex-wrap:wrap;margin-top:18px;margin-bottom:20px}.hero-meta-col{min-width:80px}.hero-meta-label{color:#94a3b8;font-size:.72rem;text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px}.hero-meta-value{color:#f1f5f9;font-size:.97rem;font-weight:600;line-height:1.3}.hero-action-btn{display:inline-flex;align-items:center;gap:8px;padding:12px 22px;border-radius:999px;font-size:.95rem;font-weight:700;cursor:pointer;border:none;text-decoration:none;transition:all .18s}.hero-action-primary{background:#7c3aed;color:#fff}.hero-action-primary:hover{background:#6d28d9}.hero-action-secondary{background:rgba(255,255,255,.10);color:#f1f5f9;border:1px solid rgba(255,255,255,.16)}.hero-action-secondary:hover{background:rgba(255,255,255,.18)}.hero-actions{display:flex;flex-direction:column;gap:10px;min-width:220px;margin-top:10px}
</style>
"""

def render_entry_detail(entry_row, vote_summary):
      import streamlit.components.v1 as _components
      if "my_collection" not in st.session_state:
          st.session_state["my_collection"] = set()
      if "my_watched_list" not in st.session_state:
          st.session_state["my_watched_list"] = set()
      _components.html("""
        <script>
        (function(){
          function go(){
            try{window.parent.scrollTo({top:0,behavior:"instant"});}catch(e){}
            try{window.parent.document.documentElement.scrollTop=0;}catch(e){}
            try{window.parent.document.body.scrollTop=0;}catch(e){}
            try{var c=window.parent.document.querySelector('[data-testid="stAppViewContainer"]');if(c)c.scrollTop=0;}catch(e){}
            try{var m=window.parent.document.querySelector('.main');if(m)m.scrollTop=0;}catch(e){}
          }
          go();setTimeout(go,80);setTimeout(go,250);setTimeout(go,500);
        })();
        </script>
      """, height=1, scrolling=False)
      st.markdown(DETAIL_CSS, unsafe_allow_html=True)
      st.markdown('<div id="detail-top"></div>', unsafe_allow_html=True)
      raw_entry_id = entry_row.get("entry_id", 0)
      try:
          _eid_s = _normalize_entry_id(raw_entry_id)
          entry_id = int(_eid_s) if _eid_s not in ("", "nan", "None") else 0
      except (ValueError, TypeError):
          entry_id = 0
      title = str(entry_row.get("title", "") or "").strip()
      media_type = str(entry_row.get("type", "Movie") or "Movie").strip().title()
      tmdb = tmdb_fetch_details(title, media_type)
      poster_url = tmdb.get("poster_url") or (entry_row.get("poster_url", "") or "")
      backdrop_url = tmdb.get("backdrop_url", "")
      overview = tmdb.get("overview") or str(entry_row.get("comments", "") or "").strip()
      tagline = tmdb.get("tagline", "")
      release_date = tmdb.get("release_date", "")
      release_year = release_date[:4] if release_date else str(entry_row.get("watched_year", "") or "")
      genres = tmdb.get("genres") or [g.strip() for g in str(entry_row.get("genre", "") or "").split(",") if g.strip()]
      counts = vote_summary.get(entry_id, {"yes": 0, "no": 0})
      community_html = community_bar(counts["yes"], counts["no"])
      bar_l, _ = st.columns([1.1, 8.9])
      with bar_l:
          if st.button("← Back", key=f"detail_back_{entry_id}", use_container_width=True):
              st.session_state.pop("selected_entry_id", None)
              st.session_state.pop("selected_entry_title", None)
              st.session_state.pop("selected_entry_type", None)
              st.rerun()
      title_html = html.escape(tmdb.get("name") or title or "Untitled")
      type_html = html.escape(media_type or "—")
      platform_chip_html = _platform_chip_html(entry_row.get("platform", ""))
      status_html = status_badge(entry_row.get("status", ""))
      recommend_html = recommend_badge(entry_row.get("recommend", ""))
      genre_html = "".join(f'<span class="detail-chip">{html.escape(g)}</span>' for g in genres[:6])
      user_rating = tmdb.get("tmdb_rating")
      tmdb_rating_chip = f'<span class="detail-chip">TMDB {round(user_rating, 1)}/10</span>' if user_rating is not None else ""
      runtime = tmdb.get("runtime")
      runtime_chip = f'<span class="detail-chip">{html.escape(str(runtime))} min</span>' if runtime else ""
      season_count = tmdb.get("number_of_seasons")
      episode_count = tmdb.get("number_of_episodes")
      season_chip = f'<span class="detail-chip">{html.escape(str(season_count))} Seasons</span>' if media_type == "Webseries" and season_count else ""
      episode_chip = f'<span class="detail-chip">{html.escape(str(episode_count))} Episodes</span>' if media_type == "Webseries" and episode_count else ""
      meta_html = f'<div class="detail-meta">{platform_chip_html}{tmdb_rating_chip}{runtime_chip}{season_chip}{episode_chip}{status_html}{recommend_html}</div>'
      poster_markup = f'<img src="{html.escape(poster_url)}" alt="poster" loading="lazy">' if poster_url else '<div style="height:315px;display:flex;align-items:center;justify-content:center;color:#94a3b8;">No Poster</div>'
      tag_html = f'<div class="detail-tagline">{html.escape(tagline)}</div>' if tagline else ''
      year_html = f' • {html.escape(release_year)}' if release_year else ''
      hero_bg_style = f'background-image:url("{html.escape(backdrop_url)}");' if backdrop_url else ''
      _director = ""
      if tmdb.get("cast"):
          # grab first crew director from TMDB data if stored; fallback blank
          pass
      _entry_status = str(entry_row.get("status","") or "").strip().lower()
      _is_watched = _entry_status in ("watched",)
      _is_in_collection = entry_id in st.session_state.get("my_collection", set())
      _hero_lang = LANG_NAMES.get(str(tmdb.get("language") or entry_row.get("language","") or "").strip().lower(), str(tmdb.get("language") or entry_row.get("language","") or "—"))
      _runtime_fmt = f"{runtime // 60}h {runtime % 60}m" if runtime else "—"
      _origin_country = (tmdb.get("origin_country") or [""])[0] if isinstance(tmdb.get("origin_country"), list) else ""
      hero_meta_cols = []
      if _director:
          hero_meta_cols.append(f'<div class="hero-meta-col"><div class="hero-meta-label">Directed By</div><div class="hero-meta-value">{html.escape(_director)}</div></div>')
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
      _trailer_btn  = (f'<a href="{_trailer_href}" target="_blank" '
                       f'style="display:inline-flex;align-items:center;gap:6px;padding:10px 18px;'
                       f'border-radius:999px;background:rgba(255,255,255,.10);color:#f1f5f9;'
                       f'border:1px solid rgba(255,255,255,.18);text-decoration:none;font-size:.92rem;font-weight:600;'
                       f'margin-top:6px;">▶ Watch Trailer</a>')\
                       if _trailer_href else ""
      _watch_label = "✓ Watched" if _is_watched else "👁 Mark as Watched"
      _col_label   = "✓ In Collection" if _is_in_collection else "＋ Add to Collection"
      action_html = (
          f'<div class="hero-actions">'
          f'<button class="hero-action-btn hero-action-primary">{_watch_label}</button>'
          f'<button class="hero-action-btn hero-action-secondary">{_col_label}</button>'
          f'{_trailer_btn}'
          f'</div>'
      )
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
          f'<div style="display:flex;flex-direction:column;justify-content:flex-start;padding-top:8px;">{action_html}</div>'
          f'</div>'
          f'</div></div></div>'
      )
      st.markdown(hero_html, unsafe_allow_html=True)
      left_col, right_col = st.columns([2.2, 1])
      with left_col:
          st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
          comments_text = str(entry_row.get("comments", "") or "").strip()
          watched_with = str(entry_row.get("watched_with", "") or "").strip()
          added_by = str(entry_row.get("added_by", "") or "Unknown").strip()
          watched_with_html = f'<div class="detail-fact-label">Watched with</div><div class="detail-fact-value">{html.escape(watched_with)}</div>' if watched_with else ''
          community_panel = f'<div class="detail-panel"><h4>Community</h4><div style="margin-bottom:14px;">{community_html}</div><div class="detail-fact-label">Your rating</div><div class="detail-fact-value">{html.escape(str(entry_row.get("rating", "—") or "—"))} / 10</div><div class="detail-fact-label">Added by</div><div class="detail-fact-value">{html.escape(added_by)}</div>{watched_with_html}<div class="detail-fact-label">Review</div><div style="color:#dbe4ee;line-height:1.75;font-size:0.95rem;white-space:pre-wrap;">{html.escape(comments_text) if comments_text else "No review added yet."}</div></div>'
          st.markdown(community_panel, unsafe_allow_html=True)
          _my_coll  = st.session_state.get("my_collection", set())
          _my_watch = st.session_state.get("my_watched_list", set())
          if _my_coll or _my_watch:
              st.markdown("### My Lists")
          if _my_watch:
              with st.expander(f"👁 My Watched List ({len(_my_watch)})", expanded=False):
                  st.write(", ".join(str(x) for x in _my_watch))
          if _my_coll:
              with st.expander(f"📚 My Collection ({len(_my_coll)})", expanded=False):
                  st.write(", ".join(str(x) for x in _my_coll))
      with right_col:
          if tmdb.get("trailer_url"):
              st.link_button("▶ Watch Trailer", tmdb["trailer_url"], use_container_width=True)
      st.markdown("---")
      _col_in = entry_id in st.session_state.get("my_collection", set())
      _w_in   = entry_id in st.session_state.get("my_watched_list", set())
      if st.button("✓ Watched" if _w_in else "👁 Mark as Watched", key=f"btn_watched_{entry_id}", use_container_width=True):
              st.session_state.setdefault("my_watched_list", set()).add(entry_id)
              st.rerun()
      if st.button("✓ In Collection" if _col_in else "＋ Add to Collection", key=f"btn_collect_{entry_id}", use_container_width=True):
              if _col_in:
                  st.session_state["my_collection"].discard(entry_id)
              else:
                  st.session_state.setdefault("my_collection", set()).add(entry_id)
              st.rerun()
      cast = tmdb.get("cast", [])
      if cast:
          st.markdown("### Cast")
          cast_cards = []
          for person in cast[:12]:
              img = person.get("profile_url", "")
              name = html.escape(person.get("name", "") or "Unknown")
              role = html.escape(person.get("character", "") or "")
              img_html = f'<img class="cast-avatar" src="{html.escape(img)}" alt="{name}" loading="lazy">' if img else '<div class="cast-placeholder">No Image</div>'
              cast_cards.append(f'<div class="cast-card">{img_html}<div class="cast-name">{name}</div><div class="cast-role">{role}</div></div>')
          st.markdown(f'<div class="cast-strip">{"".join(cast_cards)}</div>', unsafe_allow_html=True)
      seasons = tmdb.get("seasons", [])
      if media_type == "Webseries" and seasons:
          st.markdown("### Seasons")
          for season in seasons:
              season_name = html.escape(str(season.get("name") or f"Season {season.get('season_number','')}").strip())
              season_num = season.get("season_number")
              episode_count = season.get("episode_count")
              air_date = html.escape(str(season.get("air_date") or "—"))
              overview_txt = html.escape(str(season.get("overview") or "No season overview available."))
              poster = season.get("poster_url", "")
              meta_line = []
              if season_num is not None:
                  meta_line.append(f"Season {season_num}")
              if episode_count:
                  meta_line.append(f"{episode_count} episodes")
              meta_line.append(air_date)
              meta_html = " • ".join(meta_line)
              poster_html = f'<img class="season-poster" src="{html.escape(poster)}" alt="season poster" loading="lazy">' if poster else '<div class="season-placeholder">No Poster</div>'
              st.markdown(f'<div class="season-card">{poster_html}<div><div class="season-title">{season_name}</div><div class="season-meta">{meta_html}</div><div class="season-overview">{overview_txt}</div></div></div>', unsafe_allow_html=True)


def platform_badge(platform: str) -> str:
      # FIX #6: escape user-supplied values
      p = html.escape((platform or "").strip())
      normalized = {"Disney+ Hotstar": "Jio Hotstar", "SonyLiv": "Sony LIV", "ZEE5": "Zee5", "Zee5": "Zee5"}
      lookup = normalized.get(p, p)
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
          return "—"
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


def _normalize_entry_id(value) -> str:
      s = str(value).strip()
      if s.endswith('.0'):
          s = s[:-2]
      return s


def _platform_chip_html(platform: str) -> str:
      p = (platform or '').strip()
      normalized = {"Disney+ Hotstar": "Jio Hotstar", "SonyLiv": "Sony LIV", "ZEE5": "Zee5", "Zee5": "Zee5"}
      lookup = normalized.get(p, p)
      logo = PLATFORM_LOGOS.get(lookup, '')
      label = html.escape(p or '—')
      if logo:
          return f'<span class="detail-chip"><img src="{html.escape(logo)}" width="14" height="14" style="vertical-align:middle;margin-right:4px;border-radius:2px;"><span style="color:inherit;">{label}</span></span>'
      return f'<span class="detail-chip">{label}</span>'


def _pick_tmdb_result(results: list, title: str, year_hint=None) -> dict:
      if not results:
          return {}
      wanted = str(title or '').strip().lower()
      yh = str(year_hint or '').strip()
      def score(item):
          name = str(item.get('title') or item.get('name') or '').strip().lower()
          s = 0
          if wanted and name == wanted:
              s += 100
          elif wanted and name.startswith(wanted):
              s += 40
          elif wanted and wanted in name:
              s += 20
          date_val = item.get('release_date') or item.get('first_air_date') or ''
          iy = str(date_val)[:4] if date_val else ''
          if yh and iy and yh == iy:
              s += 30
          s += min(float(item.get('vote_count') or 0) / 1000.0, 10)
          return s
      return sorted(results, key=score, reverse=True)[0]


  # ─────────────────────────────────────────────
  #  GOOGLE SHEETS (FIX #8: error handling)
  # ─────────────────────────────────────────────
@st.cache_resource
def get_sheets():
      scopes = [
          "https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive",
      ]
      try:
          if "gcp_service_account" in st.secrets:
              creds = Credentials.from_service_account_info(
                  dict(st.secrets["gcp_service_account"]), scopes=scopes
              )
          else:
              creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
          client  = gspread.authorize(creds)
          sh      = client.open(SPREADSHEET_TITLE)
          entries = sh.sheet1

          try:
              votes = sh.worksheet("Votes")
          except WorksheetNotFound:
              votes = sh.add_worksheet(title="Votes", rows=1000, cols=3)
              votes.append_row(["entry_id", "voter_name", "vote"])

          return entries, votes
      except Exception as e:
          st.cache_resource.clear()
          raise e


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
      # FIX #2: Normalize type/status/recommend to lowercase consistently
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


def append_row(ws, row_dict: dict):
      ws.append_row(
          [row_dict.get(c, "") for c in COLUMNS],
          value_input_option="USER_ENTERED",
      )


def update_row(ws, row_index: int, row_dict: dict):
      """Update an existing row in the sheet (1-indexed, header is row 1)."""
      values = [row_dict.get(c, "") for c in COLUMNS]
      ws.update(f"A{row_index}:{chr(64+len(COLUMNS))}{row_index}", [values],
                value_input_option="USER_ENTERED")


def delete_row(ws, row_index: int):
      """Delete a row from the sheet (1-indexed)."""
      ws.delete_rows(row_index)


def find_row_index(ws, entry_id) -> int:
      """Find the 1-indexed row number for a given entry_id. Returns 0 if not found."""
      try:
          cell = ws.find(str(entry_id), in_column=1)
          return cell.row if cell else 0
      except Exception:
          return 0


  # ─────────────────────────────────────────────
  #  SIDEBAR
  # ─────────────────────────────────────────────
def render_sidebar():
      """Render sidebar navigation + single name input. Returns (page, name)."""
      st.sidebar.markdown(
          '<div style="display:flex;align-items:center;gap:10px;padding:4px 0 12px 0;">'
          '<span style="font-size:1.7rem;">🎬</span>'
          '<span style="font-size:1.15rem;font-weight:800;color:#f1f5f9;">MediaLog</span>'
          '</div>',
          unsafe_allow_html=True,
      )
      if st.sidebar.button("🏠 Home", use_container_width=True, key="logo_home_btn"):
          for _k in ["selected_entry_id","selected_entry_title","selected_entry_type"]:
              st.session_state.pop(_k, None)
          st.rerun()
      page = st.sidebar.radio("Navigate", ["Browse", "Add Entry", "Reports"], index=0)
      st.sidebar.divider()

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

      return page, name


  # ─────────────────────────────────────────────
  #  PAGE: ADD ENTRY (FIX #1: UUID-based ID, Enhancement #2: duplicate detection)
  # ─────────────────────────────────────────────
def page_add_entry(entries_ws, current_name: str):
      st.subheader("Add a new entry")
      st.caption("Fill in what you've watched — takes about 10 seconds.")

      # ── TMDB autofill ──────────────────────────────────────────────
      with st.expander("🔍 Auto-fill from TMDB (optional)", expanded=False):
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
                      st.session_state["pf_year"]   = res.get("year", "")
                      st.session_state["pf_genres"] = res.get("genres", [])
                      st.session_state["pf_type"]   = st.session_state.get("tmdb_type_sel", "Movie")
                      st.session_state["pf_poster"] = res.get("poster", "")
                      st.session_state.pop("tmdb_results", None)
                      st.rerun()

      pf_title  = st.session_state.get("pf_title",  "")
      pf_year   = st.session_state.get("pf_year",   "")
      pf_genres = st.session_state.get("pf_genres", [])
      pf_type   = st.session_state.get("pf_type",   "Movie")
      pf_poster = st.session_state.get("pf_poster", "")

      if pf_poster:
          st.session_state["pending_poster"] = pf_poster

      # ── Main form ───────────────────────────────────────────────────
      with st.form("add_entry_form", clear_on_submit=True):
          c1, c2 = st.columns(2)
          with c1:
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
                  help="Use original title if possible.",
              )

          c3, c4, c5 = st.columns(3)
          with c3:
              type_opts = ["Movie", "WebSeries"]
              type_idx  = type_opts.index(pf_type) if pf_type in type_opts else 0
              media_type = st.selectbox("Type", type_opts, index=type_idx)
          with c4:
              platform = st.selectbox(
                  "Platform", PLATFORMS, index=0,
                  help="Pick the main platform where you watched it.",
              )
          with c5:
              status = st.selectbox("Status", ["Watched", "Watching", "Plan"], index=0)

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

          rating       = None
          recommend    = ""
          watched_year = datetime.now().year

          if status != "Plan":
              c8, c9, c10 = st.columns([2, 1, 1])
              with c8:
                  rating = st.slider("Rating (1–10)", 1, 10, 8)
              with c9:
                  recommend = st.radio(
                      "Recommend?", ["Yes", "No"], horizontal=True, index=0
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
                      step=1,
                  )

          # ENHANCEMENT #10: "Watched with" field
          watched_with = st.text_input(
              "Watched with (optional)",
              placeholder="e.g. Rohan, Priya",
              help="Who did you watch this with?",
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
              # ENHANCEMENT #2: Duplicate detection
              try:
                  existing_df = read_entries(entries_ws)
                  duplicates = existing_df[
                      existing_df["title"].str.strip().str.lower() == title.strip().lower()
                  ]
                  if not duplicates.empty and not st.session_state.get("_confirm_duplicate"):
                      dup_by = duplicates.iloc[0].get("added_by", "someone")
                      st.warning(
                          f"⚠️ **'{title.strip()}'** was already logged by **{dup_by}**. "
                          f"Click Save again to add anyway."
                      )
                      st.session_state["_confirm_duplicate"] = True
                      st.stop()
              except Exception:
                  existing_df = empty_df()

              st.session_state.pop("_confirm_duplicate", None)

              if added_by.strip():
                  st.session_state["user_name"]  = added_by.strip()
                  st.session_state["voter_name"] = added_by.strip()

              poster_url = st.session_state.pop("pending_poster", "")

              # FIX entry_id: 13-digit epoch ms, safe from scientific notation in Sheets
              import time as _time
              next_id = int(_time.time() * 1000)

              row = {
                  "entry_id":     next_id,
                  "timestamp":    datetime.now().isoformat(timespec="seconds"),
                  "added_by":     added_by.strip(),
                  "title":        title.strip(),
                  "type":         media_type.lower(),  # FIX #2: store lowercase
                  "genre":        ", ".join(genre_sel) if genre_sel else "",
                  "platform":     platform.strip(),
                  "status":       status.lower(),  # FIX #2: store lowercase
                  "rating":       rating if rating is not None else "",
                  "recommend":    recommend if status != "Plan" else "",
                  "watched_year": watched_year if status != "Plan" else "",
                  "language":     language,
                  "comments":     comments.strip() if comments else "",
                  "poster_url":   poster_url,
                  "watched_with": watched_with.strip() if watched_with else "",
              }
              try:
                  append_row(entries_ws, row)
                  read_entries.clear()
                  for _k in ("pf_title", "pf_year", "pf_genres", "pf_type", "pf_poster"):
                      st.session_state.pop(_k, None)
                  st.success(f"✅  **{title.strip()}** saved! Add another below.")
              except Exception as e:
                  st.error("Error saving entry.")
                  st.exception(e)


  # ─────────────────────────────────────────────
  #  PAGE: BROWSE (FIX #4: pagination reset, FIX #5: stable picks, Enhancement #3: sort)
  # ─────────────────────────────────────────────
def render_stats_grid(stats):
      st.markdown("""
      <style>
      .stats-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:8px 0 6px 0}
      .stat-card{background:#dfe8ec;border-radius:0;padding:24px 22px;min-height:148px;display:flex;flex-direction:column;justify-content:flex-start;border:1px solid rgba(148,163,184,0.12)}
      .stat-value{font-size:3rem;line-height:0.95;font-weight:300;color:#0f172a;letter-spacing:-0.03em}
      .stat-label{margin-top:12px;font-size:1rem;line-height:1.2;color:#1f2937;font-weight:400;max-width:12ch}
      .back-to-top-wrap{position:fixed;right:18px;bottom:20px;z-index:9998}
      .back-to-top-wrap button{width:48px;height:48px;border-radius:999px;border:none;background:#111827;color:#fff;font-size:1.2rem;box-shadow:0 10px 24px rgba(0,0,0,.28);cursor:pointer}
      @media (max-width: 900px){.stats-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.stat-card{padding:18px 16px;min-height:124px}.stat-value{font-size:2.35rem}.stat-label{font-size:.92rem}}
      </style>
      """, unsafe_allow_html=True)
      cards = []
      for label, value in stats:
          cards.append(f'<div class="stat-card"><div class="stat-value">{html.escape(str(value))}</div><div class="stat-label">{html.escape(str(label))}</div></div>')
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
        win.addEventListener('scroll',check,{passive:true});
        setInterval(check,800);
        check();
      })();
      </script>
      """, unsafe_allow_html=True)


def page_browse(entries_ws, votes_ws):
      st.markdown("""
      <style>
      .browse-toolbar div[data-testid="stHorizontalBlock"] {align-items:end; gap:0.5rem;}
      @media (max-width: 768px) { .browse-toolbar div[data-testid="stHorizontalBlock"] {gap:0.45rem;} }
      </style>
      """, unsafe_allow_html=True)

      search_text = st.session_state.get("browse_search", "")

      df           = read_entries(entries_ws)
      votes_df     = read_votes(votes_ws)
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
              render_entry_detail(selected_df.iloc[0], vote_summary)
              return
          st.session_state.pop("selected_entry_id", None)
          st.session_state.pop("selected_entry_title", None)
          st.session_state.pop("selected_entry_type", None)

      if df.empty:
          st.info("No entries yet. Go to **Add Entry** to log your first movie or series.")
          return

      st.divider()

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
              st.markdown("### 🍿 Tonight's picks")
              st.caption("Top-rated, community-recommended picks (stable for today).")
              sample_size = min(3, len(top_pool))
              # FIX #5: date-based seed so picks stay the same all day
              daily_seed = int(datetime.now().strftime("%Y%m%d"))
              picks = top_pool.sample(n=sample_size, random_state=daily_seed)
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
              st.divider()

      # ── Sidebar filters ───────────────────────────────────────────
      preset = st.sidebar.radio(
          "Quick filter",
          ["All", "Recommended only", "High ratings (≥ 8)", "Plan to Watch"],
          index=0,
          key="browse_preset",
      )

      my_name   = st.session_state.get("user_name", "").strip()
      show_mine = st.sidebar.checkbox("Show only my entries", value=False, key="show_mine_check")

      # ENHANCEMENT #3: Sort control
      sort_choice = st.sidebar.selectbox(
          "Sort by",
          list(SORT_OPTIONS.keys()),
          index=0,
          key="sort_select",
      )

      with st.sidebar.expander("Filters", expanded=False):
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
      elif preset == "Plan to Watch":
          # ENHANCEMENT #5: quick filter for Plan entries
          filtered = filtered[filtered["status"].str.lower() == "plan"]

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

      # ENHANCEMENT #3: Apply sort
      sort_col, sort_asc = SORT_OPTIONS[sort_choice]
      if sort_col == "_total_votes":
          filtered["_total_votes"] = filtered["entry_id"].apply(
              lambda eid: sum(vote_summary.get(int(eid) if pd.notna(eid) else 0, {"yes": 0, "no": 0}).values())
          )
          filtered = filtered.sort_values("_total_votes", ascending=sort_asc).drop(columns=["_total_votes"])
      elif sort_col == "rating" and "rating" in filtered.columns:
          filtered["_rating_num"] = pd.to_numeric(filtered["rating"], errors="coerce").fillna(0)
          filtered = filtered.sort_values("_rating_num", ascending=sort_asc).drop(columns=["_rating_num"])
      elif sort_col in filtered.columns:
          filtered = filtered.sort_values(sort_col, ascending=sort_asc, na_position="last")

      # FIX #4: Detect filter changes and reset pagination
      current_filter_sig = f"{preset}|{show_mine}|{search_text}|{plat_f}|{type_f}|{stat_f}|{rec_f}|{genre_f}|{sort_choice}"
      if st.session_state.get("_last_filter_sig") != current_filter_sig:
          st.session_state["_last_filter_sig"] = current_filter_sig
          for k in list(st.session_state.keys()):
              if k.startswith("browse_page_"):
                  st.session_state[k] = 1

      total = len(df)
      st.caption(f"Showing **{len(filtered)}** of **{total}** entries")

      st.divider()

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
          if v_mode == "Cards":
              _render_cards(page_data, v_summary, v_df, v_ws, entries_ws, render_scope=tab_key)
          else:
              _render_table(page_data, v_summary)

      movies_df = filtered[filtered["type"].str.strip().str.lower() == "movie"] if "type" in filtered.columns else filtered.iloc[0:0]
      series_df = filtered[filtered["type"].str.strip().str.lower() == "webseries"] if "type" in filtered.columns else filtered.iloc[0:0]

      tab_all, tab_movies, tab_series = st.tabs(["🎬 All", "🎥 Movies", "📺 Web Series"])
      with tab_all:
          _paginate_render(filtered, "all", "Cards", vote_summary, votes_df, votes_ws)
      with tab_movies:
          if movies_df.empty:
              st.info("No movies match the current filters.")
          else:
              _paginate_render(movies_df, "movies", "Cards", vote_summary, votes_df, votes_ws)
      with tab_series:
          if series_df.empty:
              st.info("No web series match the current filters.")
          else:
              _paginate_render(series_df, "series", "Cards", vote_summary, votes_df, votes_ws)


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
      render_stats_grid([
          ("Total titles", _r_total),
          ("Movies", _r_movies),
          ("Web series", _r_series),
          ("Avg rating", f"{_r_avg:.1f}" if pd.notna(_r_avg) else "–"),
          ("Recommend %", f"{_r_rec_pct}%"),
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
      padding: 10px 14px;
      margin-bottom: 0px;
      background: var(--background-color, transparent);
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
      if not st.session_state.get("_card_css_injected"):
          st.markdown(CARD_CSS, unsafe_allow_html=True)
          st.session_state["_card_css_injected"] = True


def _render_cards(filtered, vote_summary, votes_df, votes_ws, entries_ws, render_scope="main"):
      _inject_card_css()
      if filtered.empty:
          st.info("No entries match the current filters.")
          return

      voter_name = st.session_state.get("voter_name", "").strip()
      current_user = st.session_state.get("user_name", "").strip()

      for idx, (_, row) in enumerate(filtered.iterrows()):
          raw_entry_id = row.get("entry_id", 0)
          try:
              entry_id = int(_normalize_entry_id(raw_entry_id)) if _normalize_entry_id(raw_entry_id) not in ("", "nan", "None") else idx + 1
          except (ValueError, TypeError):
              entry_id = idx + 1
          title_txt      = row.get("title",    "—")
          type_txt       = (row.get("type",    "") or "").title()
          genre_txt      = row.get("genre",    "") or "—"
          added_by_txt   = row.get("added_by", "") or "Unknown"
          comments_txt   = row.get("comments", "") or ""
          poster_url     = row.get("poster_url", "") or ""
          watched_with   = row.get("watched_with", "") or ""
          platform_html  = platform_badge(row.get("platform", ""))
          rating_html    = rating_stars(row.get("rating"))
          status_html    = status_badge(row.get("status",    ""))
          recommend_html = recommend_badge(row.get("recommend", ""))

          # XSS protection
          title_txt    = html.escape(str(title_txt))
          type_txt     = html.escape(str(type_txt))
          genre_txt    = html.escape(str(genre_txt))
          added_by_txt = html.escape(str(added_by_txt))
          comments_txt = html.escape(str(comments_txt))
          watched_with = html.escape(str(watched_with))

          counts   = vote_summary.get(entry_id, {"yes": 0, "no": 0})
          comm_bar = community_bar(counts["yes"], counts["no"])

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
              watched_with_html = f'<span style="font-size:0.72rem;color:#94a3b8;margin-left:8px;">👥 {watched_with}</span>'

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
  <div class="wlog-card-footer">Added by {added_by_txt}{watched_with_html}</div>"""

          card_html = re.sub(r'\s+', ' ', f'<div class="wlog-card">{card_inner}</div>').strip()
          st.markdown(card_html, unsafe_allow_html=True)

          action_col, _ = st.columns([1.35, 8.65])
          with action_col:
              if st.button("View Details", key=f"view_{entry_id}_{idx}_{render_scope}", use_container_width=True):
                  st.session_state["selected_entry_id"] = _normalize_entry_id(raw_entry_id)
                  st.session_state["selected_entry_title"] = str(row.get("title", "") or "").strip()
                  st.session_state["selected_entry_type"] = str(row.get("type", "") or "").strip()
                  st.rerun()

          # Vote + Edit/Delete row
          _render_vote_widget(entry_id, title_txt, voter_name, votes_df, votes_ws,
                              counts["yes"], counts["no"], idx, render_scope)

          # ENHANCEMENT #1: Edit/Delete (only visible to the entry owner)
          if current_user and current_user.lower() == (row.get("added_by", "") or "").strip().lower():
              _render_edit_delete(entry_id, row, entries_ws, idx, render_scope)

          st.markdown('<hr class="wlog-divider">', unsafe_allow_html=True)


  # ─────────────────────────────────────────────
  #  ENHANCEMENT #1: EDIT/DELETE WIDGET
  # ─────────────────────────────────────────────
def _render_edit_delete(entry_id, row, entries_ws, card_idx, render_scope):
      scope = render_scope or "default"
      edit_key = f"editing_{entry_id}_{scope}"

      col_edit, col_del, _ = st.columns([1, 1, 8])
      with col_edit:
          if st.button("✏️", key=f"edit_btn_{entry_id}_{card_idx}_{scope}",
                       help="Edit this entry"):
              st.session_state[edit_key] = True
              st.rerun()
      with col_del:
          if st.button("🗑", key=f"del_btn_{entry_id}_{card_idx}_{scope}",
                       help="Delete this entry"):
              confirm_key = f"confirm_del_{entry_id}_{scope}"
              st.session_state[confirm_key] = True
              st.rerun()

      # Delete confirmation
      confirm_key = f"confirm_del_{entry_id}_{scope}"
      if st.session_state.get(confirm_key):
          st.warning(f"Are you sure you want to delete **{html.escape(str(row.get('title', '')))}**?")
          c_yes, c_no, _ = st.columns([1, 1, 8])
          with c_yes:
              if st.button("Yes, delete", key=f"confirm_yes_{entry_id}_{scope}", type="primary"):
                  try:
                      row_idx = find_row_index(entries_ws, entry_id)
                      if row_idx:
                          delete_row(entries_ws, row_idx)
                          read_entries.clear()
                          st.session_state.pop(confirm_key, None)
                          st.success("Deleted.")
                          st.rerun()
                      else:
                          st.error("Could not find entry in sheet.")
                  except Exception as e:
                      st.error(f"Delete failed: {e}")
          with c_no:
              if st.button("Cancel", key=f"confirm_no_{entry_id}_{scope}"):
                  st.session_state.pop(confirm_key, None)
                  st.rerun()

      # Inline edit form
      if st.session_state.get(edit_key):
          with st.form(f"edit_form_{entry_id}_{scope}"):
              st.markdown(f"**Editing: {html.escape(str(row.get('title', '')))}**")
              new_title = st.text_input("Title", value=row.get("title", ""))
              ec1, ec2, ec3 = st.columns(3)
              with ec1:
                  new_platform = st.selectbox("Platform", PLATFORMS,
                      index=PLATFORMS.index(row.get("platform", "")) if row.get("platform", "") in PLATFORMS else 0)
              with ec2:
                  status_opts = ["watched", "watching", "plan"]
                  cur_status = (row.get("status", "") or "").lower()
                  new_status = st.selectbox("Status", status_opts,
                      index=status_opts.index(cur_status) if cur_status in status_opts else 0)
              with ec3:
                  cur_rating = row.get("rating", 8)
                  try:
                      cur_rating = int(float(cur_rating)) if pd.notna(cur_rating) else 8
                  except (ValueError, TypeError):
                      cur_rating = 8
                  new_rating = st.slider("Rating", 1, 10, cur_rating)

              new_comments = st.text_area("Review", value=row.get("comments", "") or "")

              sub_col1, sub_col2 = st.columns(2)
              with sub_col1:
                  if st.form_submit_button("💾 Save changes", type="primary"):
                    try:
                        row_idx = find_row_index(entries_ws, entry_id)
                        if row_idx:
         				    # Build updated dict, properly converting pandas types
                            updated = {}
                            for c in COLUMNS:
                                val = row.get(c, "")
          					    # Convert pandas Timestamp to string
                                if isinstance(val, pd.Timestamp):
                                    val = val.isoformat(timespec="seconds") if pd.notna(val) else ""
                                    # Convert NaN/None to empty string
                                elif val is None or (isinstance(val, float) and pd.isna(val)):
                                    val = ""
                                    # Convert numpy int/float to Python native
                                elif hasattr(val, "item"):
                                    val = val.item()
                                updated[c] = val
                            updated["title"] = new_title.strip()
                            updated["platform"] = new_platform
                            updated["status"] = new_status
                            updated["rating"] = new_rating
                            updated["comments"] = new_comments.strip()
                            update_row(entries_ws, row_idx, updated)
                            read_entries.clear()
                            st.session_state.pop(edit_key, None)
                            st.success("Updated!")
                            st.rerun()
                        else:
                            st.error("Could not find entry.")
                    except Exception as e:
                        st.error(f"Update failed: {e}")
              with sub_col2:
                  if st.form_submit_button("Cancel"):
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

      lbl_col, yes_col, no_col, _ = st.columns([3, 1, 1, 5])
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
                  st.exception(e)
      with no_col:
          if st.button("👎", key=f"no_{entry_id}_{card_idx}_{scope}", help=f"Skip {title_txt}"):
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
          eid = row.get("entry_id", 0)
          try:
              eid = int(float(eid))
          except (ValueError, TypeError):
              eid = 0
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
      st.set_page_config(
          page_title="What Am I Watching?",
          page_icon="🎬",
          layout="wide",
      )

      _gs = st.text_input(
          "Search",
          value=st.session_state.get("browse_search", ""),
          placeholder="Search movies or web series...",
          key="global_search_top",
          label_visibility="collapsed",
      )
      st.session_state["browse_search"] = _gs
      st.title("🎬 What Am I Watching?")
      st.caption(
          "A shared log for movies & web series across all OTT platforms. "
          "Share the URL — everyone can add entries and vote."
      )

      try:
          entries_ws, votes_ws = get_sheets()
      except Exception as e:
          st.error("Failed to connect to Google Sheets. Please check your credentials and try again.")
          st.exception(e)
          return

      page, current_name = render_sidebar()

      render_back_to_top_button()
      if page == "Add Entry":
          page_add_entry(entries_ws, current_name)
      elif page == "Reports":
          page_reports(entries_ws)
      else:
          page_browse(entries_ws, votes_ws)
      st.sidebar.divider()
      st.sidebar.markdown(
          "**How it works**\n"
          "- Log what you watch in **Add Entry**\n"
          "- Browse & filter in **Browse**\n"
          "- 👍/👎 vote on any entry\n"
          "- See charts in **Reports**\n"
          "- Share this URL with friends"
      )


if __name__ == "__main__":
      main()
