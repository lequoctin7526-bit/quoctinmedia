import os
import sys

# Configure UTF-8 for console output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import glob
import json
import re
import unicodedata
import uuid
import time
import shutil
import zipfile
import threading
import subprocess
import io
from PIL import Image
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import requests
from flask import Flask, request, jsonify, send_file, send_from_directory, make_response
from werkzeug.utils import secure_filename
import yt_dlp
import mutagen
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TDRC
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from ytmusicapi import YTMusic

# Initialize YTMusic for high-precision Spotify track matching
try:
    ytmusic = YTMusic()
except Exception as e:
    print(f"[!] Warning: Could not initialize YTMusic: {e}")
    ytmusic = None

# Setup Paths & Environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

def find_ffmpeg():
    # 1. System PATH
    cmd = shutil.which("ffmpeg")
    if cmd:
        return cmd
    # 2. Winget yt-dlp.FFmpeg packages
    patterns = [
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\*ffmpeg*\**\ffmpeg.exe"),
        r"C:\Program Files\ffmpeg*\**\ffmpeg.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\ffmpeg*\**\ffmpeg.exe")
    ]
    for p in patterns:
        matches = glob.glob(p, recursive=True)
        if matches:
            return matches[0]
    return None

FFMPEG_EXE = find_ffmpeg()
if FFMPEG_EXE:
    ffmpeg_bin_dir = os.path.dirname(FFMPEG_EXE)
    if ffmpeg_bin_dir not in os.environ["PATH"]:
        os.environ["PATH"] = ffmpeg_bin_dir + os.pathsep + os.environ["PATH"]
    print(f"[*] FFmpeg active: {FFMPEG_EXE}")
else:
    print("[!] Warning: FFmpeg not detected in standard paths.")

app = Flask(__name__, static_folder=".", static_url_path="")

# Enable CORS for file:// and cross-origin access including Private Network Access
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

@app.before_request
def handle_options_preflight():
    if request.method == "OPTIONS":
        res = make_response()
        res.headers["Access-Control-Allow-Origin"] = "*"
        res.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        res.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
        res.headers["Access-Control-Allow-Private-Network"] = "true"
        return res, 204

# In-memory storage for active download tasks
JOBS = {}
JOBS_LOCK = threading.Lock()

# ==========================================
# YOUTUBE ANTI-BOT & COOKIE ENGINE
# ==========================================
COOKIE_FILE_CANDIDATES = ["cookies.txt", "youtube_cookies.txt", "cookie.txt"]

def get_cookie_file():
    """Detect local cookies file if present."""
    for filename in COOKIE_FILE_CANDIDATES:
        p = os.path.join(BASE_DIR, filename)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return None

def get_youtube_extractor_args(clients=None):
    """
    Returns client configurations that bypass 'Sign in to confirm you’re not a bot'.
    Using 'web_embedded', 'android', 'ios' Innertube clients.
    """
    if not clients:
        clients = ["web_embedded", "android", "ios"]
    return {
        "youtube": {
            "player_client": clients,
            "player_skip": ["configs"]
        }
    }

def apply_youtube_opts(opts, is_youtube=True, clients=None):
    """Injects anti-bot extractor args, timeouts, and cookies into yt-dlp options."""
    if not opts:
        opts = {}
    if is_youtube:
        if "extractor_args" not in opts:
            opts["extractor_args"] = {}
        opts["extractor_args"].update(get_youtube_extractor_args(clients))
        opts["socket_timeout"] = opts.get("socket_timeout", 30)
        opts["retries"] = opts.get("retries", 10)
        opts["fragment_retries"] = opts.get("fragment_retries", 10)
    
    cookie_p = get_cookie_file()
    if cookie_p and "cookiefile" not in opts:
        opts["cookiefile"] = cookie_p
    return opts

def extract_info_safe(base_opts, url, download=False):
    """
    Safely extract info with intelligent multi-strategy fallback for YouTube bot blocks:
    Strategy 1: web_embedded + android + ios (primary anti-bot)
    Strategy 2: android + ios
    Strategy 3: ios only
    Strategy 4: default
    """
    is_yt = any(d in url.lower() for d in ["youtube.com", "youtu.be"])
    if not is_yt:
        opts = apply_youtube_opts(dict(base_opts), is_youtube=False)
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=download)

    strategies = [
        ["web_embedded", "android", "ios"],
        ["android", "ios"],
        ["ios"],
        ["web_embedded"]
    ]
    last_error = None
    for clients in strategies:
        opts = apply_youtube_opts(dict(base_opts), is_youtube=True, clients=clients)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=download)
                if info:
                    return info
        except Exception as e:
            last_error = e
            err_msg = str(e).lower()
            if "private video" in err_msg or "video unavailable" in err_msg or "not found" in err_msg:
                raise e

    if last_error:
        raise last_error
    raise Exception("Không thể trích xuất dữ liệu từ YouTube.")

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()

def format_media_filename(title_or_name, ext=None):
    clean = sanitize_filename(title_or_name).strip()
    if not clean:
        clean = "Media"
    if not clean.lower().startswith("quoctinmedia"):
        clean = f"QuocTinMedia - {clean}"
    if ext:
        ext = ext.lstrip(".")
        return f"{clean}.{ext}"
    return clean

def parse_duration_str(d_str):
    if not d_str:
        return 0
    try:
        parts = d_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except:
        pass
    return 0

def clean_match_text(text):
    if not text:
        return ''
    text = unicodedata.normalize('NFC', str(text).lower())
    text = re.sub(r'[\[\]\(\)\-_:,\.!\?\|/\\\'\"]', ' ', text)
    return ' '.join(text.split())

def get_match_keywords(text):
    noise = {
        'official', 'audio', 'video', 'mv', 'lyrics', 'lyric', 'nhạc', 'mp3',
        'hd', '4k', 'full', 'hq', 'topic', 'visualizer', 'release', 'bản', 'gốc',
        'chính', 'thức', 'm/v', 'feat', 'ft', 'featuring', 'with', 'prod', 'by'
    }
    words = clean_match_text(text).split()
    return [w for w in words if w not in noise]

def calculate_spotify_match_score(target_title, target_artists, target_dur, cand_title, cand_uploader, cand_artists, cand_dur):
    t_words = set(get_match_keywords(target_title))
    c_words = set(get_match_keywords(cand_title))
    if not t_words:
        return -9999.0

    matched_title_words = t_words.intersection(c_words)
    title_ratio = len(matched_title_words) / len(t_words)

    # 1. Strictest rule: Must match at least 50% of core title words to prevent wrong song matching
    if title_ratio < 0.5:
        return -9999.0

    score = 100.0 * title_ratio

    # 2. Artist verification
    t_art_list = target_artists if isinstance(target_artists, list) else [target_artists]
    c_art_str = (' '.join(cand_artists or []) + ' ' + (cand_uploader or '')).lower()
    c_clean_title = clean_match_text(cand_title)
    
    artist_matched = False
    for art in t_art_list:
        art_clean = clean_match_text(art)
        if art_clean and (art_clean in c_art_str or art_clean in c_clean_title):
            artist_matched = True
            break

    if artist_matched:
        score += 35.0
    else:
        score -= 40.0

    # 3. Unwanted/Mismatched Version Modifiers Check
    # Tags that fundamentally change the sound and style of a song:
    low_t = target_title.lower()
    low_c = cand_title.lower()

    style_tags = [
        'remix', 'lofi', 'lo-fi', 'acoustic', 'live', 'concert', 'fancam',
        'speed up', 'sped up', 'slowed', 'reverb', 'nightcore', 'vinahouse',
        'cover', 'karaoke', 'beat', 'instrumental', 'parody', 'reaction',
        'bass boost', '8d', 'mashup', 'medley', 'dance ver', 'extended', 'remake'
    ]
    for tag in style_tags:
        # If candidate has this style modifier but Spotify song does NOT, penalize heavily
        if tag in low_c and tag not in low_t:
            score -= 85.0
        # If Spotify song explicitly requested this modifier (e.g. Remix) and candidate has it, reward!
        elif tag in low_t and tag in low_c:
            score += 25.0
        # If Spotify song requested it (e.g. Remix) but candidate lacks it, penalize
        elif tag in low_t and tag not in low_c:
            score -= 50.0

    # 4. Duration comparison (Precision <= 3s is studio audio)
    if target_dur and cand_dur:
        diff = abs(target_dur - cand_dur)
        if diff <= 3:
            score += 40.0
        elif diff <= 6:
            score += 20.0
        elif diff <= 12:
            score += 5.0
        elif diff <= 25:
            score -= 30.0
        else:
            score -= min(diff * 4, 85.0)

    # 5. Channel and audio type bonuses
    uploader_low = (cand_uploader or '').lower()
    if 'topic' in uploader_low:
        score += 30.0
    if 'official audio' in low_c or 'official audio' in uploader_low:
        score += 25.0

    return score

def find_exact_spotify_audio_match(title, artist, target_duration):
    """
    Finds the 100% exact studio master audio on YouTube Music / YouTube Topic matching the Spotify track.
    Implements multi-source traversal without premature breaks and detailed console logging.
    """
    target_dur = int(round(float(target_duration))) if target_duration else 0
    t_art_list = [a.strip() for a in str(artist).split(',')] if isinstance(artist, str) else list(artist)
    artist_str = ", ".join(t_art_list)

    best_candidate = None
    best_score = -9999.0
    seen_vids = set()

    # Pass 1: YouTube Music Official Song Catalog (filter="songs")
    if ytmusic:
        queries = [
            f"{artist_str} - {title}",
            f"{title} {artist_str}",
            f"{t_art_list[0]} {title}" if t_art_list else title,
            title
        ]
        for q in queries:
            try:
                results = ytmusic.search(q, filter="songs")
                if results:
                    for r in results[:8]:
                        v_id = r.get('videoId')
                        if not v_id or v_id in seen_vids:
                            continue
                        seen_vids.add(v_id)
                        
                        r_title = r.get('title', '')
                        r_artists = [a.get('name', '') for a in r.get('artists', [])]
                        r_dur = parse_duration_str(r.get('duration', ''))
                        
                        score = calculate_spotify_match_score(
                            title, t_art_list, target_dur,
                            r_title, '', r_artists, r_dur
                        )
                        
                        if score > best_score:
                            best_score = score
                            best_candidate = {
                                "id": v_id,
                                "title": r_title,
                                "uploader": ", ".join(r_artists) if r_artists else "YouTube Music",
                                "duration": r_dur,
                                "source": "YouTube Music (Song)"
                            }

                    # Ngưỡng hoàn hảo tuyệt đối: nếu >= 195 điểm (khớp 100% title, ca sĩ, dur <= 3s, official), có thể dừng sớm
                    if best_score >= 195.0:
                        break
            except Exception as e:
                print(f"[!] YTMusic query error for '{q}': {e}")

    # Pass 2: YouTube Official Topic & Official Audio Channels (ytsearch)
    if best_score < 195.0:
        ydl_opts = apply_youtube_opts({'skip_download': True, 'quiet': True, 'extract_flat': True})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            topic_queries = [
                f"{artist_str} {title} Official Audio",
                f"{artist_str} {title} Topic",
                f"{t_art_list[0]} {title} Topic" if t_art_list else f"{title} Topic",
                f"{artist_str} - {title}"
            ]
            for yq in topic_queries:
                try:
                    res = ydl.extract_info(f"ytsearch6:{yq}", download=False)
                    entries = res.get('entries', []) if res else []
                    for e in entries:
                        if not e:
                            continue
                        v_id = e.get('id')
                        if not v_id or v_id in seen_vids:
                            continue
                        seen_vids.add(v_id)

                        v_title = e.get('title', '')
                        v_uploader = e.get('uploader', '')
                        v_dur = int(e.get('duration') or 0)
                        
                        score = calculate_spotify_match_score(
                            title, t_art_list, target_dur,
                            v_title, v_uploader, [v_uploader], v_dur
                        )
                        
                        if score > best_score:
                            best_score = score
                            best_candidate = {
                                "id": v_id,
                                "title": v_title,
                                "uploader": v_uploader,
                                "duration": v_dur,
                                "source": "YouTube Topic / Audio"
                            }

                    if best_score >= 195.0:
                        break
                except Exception as e:
                    print(f"[!] Fallback search error for '{yq}': {e}")

    # Kiểm tra ứng viên tốt nhất với ngưỡng tin cậy
    if best_candidate and best_score > 40.0:
        print(f"[*] Spotify Match Engine v3.0: [Spotify: '{title}' - '{artist_str}' - {target_dur}s] -> [YouTube Chọn: '{best_candidate['title']}' - '{best_candidate['uploader']}' - {best_candidate['duration']}s - Score: {best_score:.1f} ({best_candidate['source']})]")
        return f"https://www.youtube.com/watch?v={best_candidate['id']}"

    # Fallback tiêu chuẩn nếu không tìm được ứng viên vượt ngưỡng
    print(f"[!] Cảnh báo: Không tìm thấy ứng viên vượt ngưỡng tin cậy (Điểm cao nhất: {best_score:.1f}). Dùng fallback: ytsearch1:{artist_str} - {title} Official Audio")
    return f"ytsearch1:{artist_str} - {title} Official Audio"

def clean_youtube_url(url):
    """Normalize scheme and clean radio/mix parameters that cause yt-dlp to hang or loop indefinitely"""
    url = url.strip()
    if not url.startswith(("http://", "https://", "spotify:")):
        url = "https://" + url
    if "list=RD" in url or "start_radio=1" in url:
        # Strip list=RD... and start_radio=1, keeping v=
        cleaned = re.sub(r'([?&])list=RD[^&]*', '', url)
        cleaned = re.sub(r'([?&])start_radio=[^&]*', '', cleaned)
        cleaned = re.sub(r'\?&', '?', cleaned).rstrip('?&')
        return cleaned
    return url

# ==================== KARAOKE SEPARATION ENGINES ====================

def separate_karaoke_mvsep(job_id, audio_path, api_token, output_format="1", add_opt1="8", add_opt2="1"):
    """
    Submits audio to MVSep API using sep_type=49 (MVSep Karaoke lead/back vocals)
    with BS Roformer by MVSep Team. Polls status via /api/separation/get and downloads all stems.
    """
    job_folder = os.path.join(DOWNLOAD_DIR, job_id)
    os.makedirs(job_folder, exist_ok=True)
    
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "Đang gửi file âm thanh lên máy chủ AI MVSep (BS Roformer)..."
        JOBS[job_id]["percent"] = 20

    url = "https://mvsep.com/api/separation/create"
    data = {
        "api_token": api_token.strip(),
        "sep_type": "49",          # MVSep Karaoke (lead/back vocals)
        "add_opt1": str(add_opt1), # Model type (8: BS Roformer 124 bands / 6: BS Roformer MVSep Team)
        "add_opt2": str(add_opt2), # Extraction type (1: Extract vocals first -> 3 stems)
        "output_format": str(output_format), # 1: WAV 16-bit, 0: MP3 320k
        "is_demo": "0"
    }

    print(f"[*] Submitting separation task to MVSep: {url} (sep_type=49, add_opt1={add_opt1}, add_opt2={add_opt2})")
    with open(audio_path, "rb") as f:
        files = {"audiofile": f}
        resp = requests.post(url, data=data, files=files, timeout=300)

    try:
        res_json = resp.json()
    except Exception:
        raise Exception(f"Không thể kết nối API MVSep: {resp.text[:200]}")

    print(f"[*] MVSep Create response: {resp.status_code} - {res_json}")

    if not res_json.get("success"):
        raw_err = res_json.get("data", {}).get("message") or res_json.get("errors") or res_json.get("message") or ""
        err_str = str(raw_err)
        if "premium" in err_str.lower():
            print("[*] Premium option requested on standard account. Auto-falling back to Standard Free model (add_opt1=0, add_opt2=0)...")
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "Đang tự động chuyển sang mô hình AI miễn phí (Model by viperx & aufr33)..."
            data["add_opt1"] = "0"
            data["add_opt2"] = "0"
            with open(audio_path, "rb") as f:
                resp = requests.post(url, data=data, files={"audiofile": f}, timeout=300)
            try:
                res_json = resp.json()
            except Exception:
                raise Exception(f"Không thể kết nối API MVSep: {resp.text[:200]}")
            print(f"[*] MVSep Fallback response: {resp.status_code} - {res_json}")

        if not res_json.get("success"):
            err_msg = res_json.get("data", {}).get("message") or res_json.get("errors") or res_json.get("message") or "Lỗi xác thực Token MVSep!"
            raise Exception(f"MVSep lỗi: {err_msg}")

    file_hash = res_json.get("data", {}).get("hash") or res_json.get("hash")
    if not file_hash:
        raise Exception("MVSep không trả về mã tác vụ (hash).")

    # Determine polling URL: standard MVSep API uses /api/separation/get (NOT get-remote)
    poll_link = res_json.get("data", {}).get("link")
    if poll_link and "/separation/get" in poll_link:
        poll_url = poll_link
    else:
        poll_url = f"https://mvsep.com/api/separation/get?hash={file_hash}"

    print(f"[*] Polling MVSep task at: {poll_url}")

    max_wait_seconds = 900
    start_time = time.time()
    poll_resp = None
    not_found_count = 0

    while time.time() - start_time < max_wait_seconds:
        time.sleep(5)
        try:
            # Send api_token in query to avoid unauthorized or mirror issues
            params = {"hash": file_hash, "api_token": api_token.strip()}
            poll_resp = requests.get(poll_url, params=params, timeout=30).json()
            print(f"[*] MVSep Poll ({int(time.time() - start_time)}s): status={poll_resp.get('status')}")
        except Exception as e:
            print(f"[!] MVSep Poll connection warning: {e}")
            continue

        status = poll_resp.get("status")
        p_data = poll_resp.get("data") or {}

        if status == "done":
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "AI đã tách xong! Đang tải các stems (Beat, Lead Vocal, Backing Vocal) về máy..."
                JOBS[job_id]["percent"] = 88
            break
        elif status == "not_found":
            not_found_count += 1
            print(f"[*] Status 'not_found' ({not_found_count}/5), waiting for task registration...")
            if not_found_count >= 5:
                raise Exception("MVSep không tìm thấy tác vụ (Status: not_found). Có thể hàng đợi máy chủ MVSep đang quá tải.")
            continue
        elif status in ["error", "failed"]:
            err_msg = p_data.get("message") or poll_resp.get("message") or f"Lỗi không xác định (Status: {status})"
            raise Exception(f"MVSep xử lý thất bại: {err_msg}")
        elif status in ["queue", "waiting"]:
            not_found_count = 0
            q_pos = p_data.get("current_order") or p_data.get("queue_count") or p_data.get("queue_position") or ""
            pos_text = f" (Hàng đợi: #{q_pos})" if q_pos else ""
            with JOBS_LOCK:
                JOBS[job_id]["status"] = f"Đang chờ trong hàng đợi AI MVSep{pos_text}..."
                JOBS[job_id]["percent"] = 30
        elif status == "distributing":
            not_found_count = 0
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "Đang phân phối xử lý bóc tách âm thanh..."
                JOBS[job_id]["percent"] = 42
        elif status == "processing":
            not_found_count = 0
            progress = p_data.get("progress") or 0
            with JOBS_LOCK:
                pct = min(35 + int(progress * 0.5), 85) if progress else 60
                JOBS[job_id]["status"] = f"Mô hình BS Roformer đang bóc tách âm thanh ({progress}%)..."
                JOBS[job_id]["percent"] = pct

    if not poll_resp or poll_resp.get("status") != "done":
        raise Exception("Quá thời gian xử lý trên MVSep. Vui lòng thử lại sau.")

    p_data = poll_resp.get("data") or {}
    stems_data = p_data.get("files") or poll_resp.get("files") or {}
    file_map = {}
    if isinstance(stems_data, dict):
        file_map = stems_data
    elif isinstance(stems_data, list):
        for idx, item in enumerate(stems_data):
            if isinstance(item, dict):
                name = item.get("name") or item.get("title") or f"Stem_{idx+1}"
                url_item = item.get("url") or item.get("link") or item.get("download")
                if url_item:
                    file_map[name] = url_item
            elif isinstance(item, str) and item.startswith("http"):
                file_map[f"Stem_{idx+1}"] = item

    if not file_map:
        raise Exception("Không tìm thấy link tải các file đã tách từ MVSep.")

    downloaded_stems = []
    used_names = set()
    has_beat = False

    for stem_name, stem_url in file_map.items():
        if not stem_url or not isinstance(stem_url, str):
            continue

        url_filename = os.path.basename(stem_url.split("?")[0])
        combined_text = f"{stem_name} {url_filename}".lower()

        if any(k in combined_text for k in ["instrumental", "music", "karaoke", "accompaniment", "instr", "beat"]):
            clean_stem = "Beat_Instrumental"
            friendly_title = "🎵 Nhạc nền Beat (Instrumental - Không lời)"
            badge_color = "gold"
            has_beat = True
        elif any(k in combined_text for k in ["back", "bvocals", "harmony", "chorus"]):
            clean_stem = "Backing_Vocals"
            friendly_title = "🎶 Giọng bè / Hòa âm (Backing Vocals)"
            badge_color = "blue"
        elif "lead" in combined_text:
            clean_stem = "Lead_Vocals"
            friendly_title = "🎤 Giọng hát chính (Lead Vocals)"
            badge_color = "purple"
        elif "vocal" in combined_text:
            clean_stem = "Lead_Vocals"
            friendly_title = "🎤 Giọng hát chính (Lead Vocals)"
            badge_color = "purple"
        else:
            clean_stem = sanitize_filename(stem_name) or "Stem"
            friendly_title = f"🔊 {clean_stem}"
            badge_color = "gray"

        # Determine file extension safely
        url_ext = os.path.splitext(url_filename)[1].replace(".", "").lower()
        final_ext = url_ext if url_ext in ["wav", "mp3", "flac", "ogg", "m4a"] else ("wav" if str(output_format) == "1" else "mp3")

        # Guarantee unique filenames
        stem_filename = f"{clean_stem}.{final_ext}"
        counter = 1
        while stem_filename in used_names:
            stem_filename = f"{clean_stem}_{counter}.{final_ext}"
            counter += 1
        used_names.add(stem_filename)

        stem_path = os.path.join(job_folder, stem_filename)

        print(f"[*] Downloading separated stem: {stem_name} -> {stem_filename}")
        stem_res = requests.get(stem_url, stream=True, timeout=180)
        stem_res.raise_for_status()
        with open(stem_path, "wb") as sf:
            for chunk in stem_res.iter_content(chunk_size=16384):
                if chunk:
                    sf.write(chunk)

        downloaded_stems.append({
            "name": friendly_title,
            "filename": stem_filename,
            "badge_color": badge_color,
            "url": f"/api/file/{job_id}?stem={stem_filename}"
        })

    # If the model only returned Lead and Backing Vocals, automatically synthesize Beat from source audio
    if not has_beat and FFMPEG_EXE and os.path.exists(audio_path):
        try:
            print("[*] Model output lead/back only; synthesizing Beat_Instrumental from source via FFmpeg...")
            beat_ext = "wav" if str(output_format) == "1" else "mp3"
            beat_filename = f"Beat_Instrumental.{beat_ext}"
            beat_path = os.path.join(job_folder, beat_filename)
            cmd_synth = [
                FFMPEG_EXE, "-y", "-i", audio_path,
                "-af", "stereotools=mlev=0.015625:slev=1.3",
                "-b:a", "320k", beat_path
            ]
            subprocess.run(cmd_synth, check=True, capture_output=True)
            if os.path.exists(beat_path):
                downloaded_stems.append({
                    "name": "🎵 Nhạc nền Beat (Instrumental - Tách lọc âm thanh)",
                    "filename": beat_filename,
                    "badge_color": "gold",
                    "url": f"/api/file/{job_id}?stem={beat_filename}"
                })
        except Exception as e:
            print(f"[!] Warning synthesizing beat: {e}")

    # Sort stems: Beat first, then Lead Vocals, then Backing Vocals
    def stem_sort_key(s):
        name = s["name"]
        if "Beat" in name or "Instrumental" in name: return 0
        if "Lead" in name: return 1
        if "Backing" in name: return 2
        return 3
    downloaded_stems.sort(key=stem_sort_key)

    # Create ZIP of all stems
    zip_filename = "All_Karaoke_Stems.zip"
    zip_path = os.path.join(job_folder, zip_filename)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for s in downloaded_stems:
            fpath = os.path.join(job_folder, s["filename"])
            if os.path.exists(fpath):
                zipf.write(fpath, s["filename"])

    return downloaded_stems, zip_filename

def separate_karaoke_local(job_id, audio_path, target_ext="mp3"):
    """
    Fast offline vocal suppressor using FFmpeg stereotools filter.
    Generates both Beat_Instrumental and extracted Vocal track in 2-3 seconds.
    Zero token required.
    """
    job_folder = os.path.join(DOWNLOAD_DIR, job_id)
    os.makedirs(job_folder, exist_ok=True)
    
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "Đang tách Beat Karaoke và Vocals bằng FFmpeg..."
        JOBS[job_id]["percent"] = 40

    inst_name = f"Beat_Instrumental.{target_ext}"
    inst_path = os.path.join(job_folder, inst_name)
    
    # 1. Beat: Mute center vocal frequencies
    cmd_inst = [
        FFMPEG_EXE, "-y", "-i", audio_path,
        "-af", "stereotools=mlev=0.015625:slev=1.3",
        "-b:a", "320k", inst_path
    ]
    subprocess.run(cmd_inst, check=True, capture_output=True)

    # 2. Vocals: Center vocal extraction with bandpass filter
    voc_name = f"Lead_Vocals.{target_ext}"
    voc_path = os.path.join(job_folder, voc_name)
    cmd_voc = [
        FFMPEG_EXE, "-y", "-i", audio_path,
        "-af", "pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1,highpass=f=180,lowpass=f=4500",
        "-b:a", "320k", voc_path
    ]
    try:
        subprocess.run(cmd_voc, check=True, capture_output=True)
        has_voc = os.path.exists(voc_path)
    except Exception:
        has_voc = False

    with JOBS_LOCK:
        JOBS[job_id]["percent"] = 85

    stems = [
        {
            "name": "🎵 Nhạc nền Beat (Instrumental - Tách nhanh FFmpeg)",
            "filename": inst_name,
            "badge_color": "gold",
            "url": f"/api/file/{job_id}?stem={inst_name}"
        }
    ]
    if has_voc:
        stems.append({
            "name": "🎤 Giọng hát bóc tách (Vocals - Lọc tâm âm thanh)",
            "filename": voc_name,
            "badge_color": "purple",
            "url": f"/api/file/{job_id}?stem={voc_name}"
        })

    zip_filename = "All_Karaoke_Stems.zip"
    zip_path = os.path.join(job_folder, zip_filename)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(inst_path, inst_name)
        if has_voc:
            zipf.write(voc_path, voc_name)

    return stems, zip_filename

def get_spotify_track_info(track_id):
    """Fetch high-res metadata from Spotify embed page & oEmbed API"""
    url = f"https://open.spotify.com/embed/track/{track_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', resp.text)
        if m:
            data = json.loads(m.group(1))
            entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
            if entity:
                title = entity.get('name') or entity.get('title')
                artists = [a.get('name') for a in entity.get('artists', [])]
                album = entity.get('album', {}).get('name') or ''
                
                # Extract highest resolution cover image
                cover = None
                vis_images = entity.get('visualIdentity', {}).get('image', [])
                if vis_images:
                    vis_images.sort(key=lambda x: x.get('maxWidth', 0), reverse=True)
                    cover = vis_images[0].get('url')
                if not cover:
                    alb_images = entity.get('album', {}).get('images', [])
                    if alb_images:
                        cover = alb_images[0].get('url')

                duration_sec = entity.get('duration', 0) / 1000.0
                rel_date = entity.get('releaseDate', {}).get('isoString', '') or ''
                year = rel_date[:4] if rel_date else ''

                return {
                    'title': title,
                    'artists': artists,
                    'artist_str': ", ".join(artists) if artists else 'Unknown Artist',
                    'album': album,
                    'cover': cover,
                    'duration': duration_sec,
                    'year': year
                }
    except Exception as e:
        print(f"[!] Error scraping Spotify embed: {e}")

    # Fallback oEmbed
    try:
        oembed_url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{track_id}"
        oembed = requests.get(oembed_url, timeout=10).json()
        return {
            'title': oembed.get('title', 'Spotify Track'),
            'artists': [oembed.get('author_name', 'Spotify Artist')],
            'artist_str': oembed.get('author_name', 'Spotify Artist'),
            'album': '',
            'cover': oembed.get('thumbnail_url'),
            'duration': 0,
            'year': ''
        }
    except Exception as e:
        print(f"[!] Error fetching Spotify oembed: {e}")
        return None

def get_spotify_collection_info(coll_type, coll_id):
    """Fetch album or playlist info from Spotify embed page"""
    url = f"https://open.spotify.com/embed/{coll_type}/{coll_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', resp.text)
        if m:
            data = json.loads(m.group(1))
            entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
            title = entity.get('title') or entity.get('name')
            subtitle = entity.get('subtitle') or ''
            
            cover = None
            vis_images = entity.get('visualIdentity', {}).get('image', [])
            if vis_images:
                vis_images.sort(key=lambda x: x.get('maxWidth', 0), reverse=True)
                cover = vis_images[0].get('url')

            raw_tracks = entity.get('trackList', [])
            tracks = []
            for t in raw_tracks:
                tracks.append({
                    'title': t.get('title', 'Track'),
                    'author': t.get('subtitle', subtitle),
                    'duration': t.get('duration', 0) / 1000.0,
                    'uri': t.get('uri')
                })

            return {
                'title': title,
                'author': subtitle,
                'cover': cover,
                'tracks': tracks,
                'count': len(tracks)
            }
    except Exception as e:
        print(f"[!] Error scraping Spotify collection: {e}")
    return None

def get_nct_track_info(url):
    """
    Extracts metadata and direct 320kbps MP3 stream URL from NhacCuaTui (NCT).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.nhaccuatui.com/"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            return None
        html = resp.text

        title = ""
        artists = ""
        thumb = ""

        m_schema = re.search(r'\{"@context":"https?://schema\.org","@type":"MusicRecording"[^}]+\}', html)
        if m_schema:
            try:
                s_data = json.loads(m_schema.group(0))
                title = s_data.get("name", "")
                thumb = s_data.get("image", "")
            except:
                pass

        og_img_match = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html)
        if og_img_match:
            raw_thumb = og_img_match.group(1).strip()
            if not thumb:
                thumb = raw_thumb
            if "_300.jpg" in thumb:
                thumb = thumb.replace("_300.jpg", "_600.jpg")

        m_title = re.search(r'<title>(.*?)\s*-\s*mp3 download', html, re.IGNORECASE)
        if m_title:
            raw_t = m_title.group(1).strip()
            parts = raw_t.split(" - ")
            if len(parts) >= 2:
                if not title:
                    title = parts[0].strip()
                artists = parts[1].strip()
            elif not title:
                title = raw_t

        if not title:
            m_gen_title = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            if m_gen_title:
                title = m_gen_title.group(1).split('|')[0].strip()

        stream_urls = re.findall(r'(https?://(?:stream|a01)\.nct\.vn/[^\s"\'<>]+\.mp3\?[^\s"\'<>]*)', html)
        best_stream = None
        for s_url in stream_urls:
            if "_hq.mp3" in s_url and "download=true" in s_url:
                best_stream = s_url
                break
        if not best_stream:
            for s_url in stream_urls:
                if "_hq.mp3" in s_url:
                    best_stream = s_url
                    break
        if not best_stream and stream_urls:
            best_stream = stream_urls[0]

        duration = 0
        m_dur = re.search(r'"duration":\s*(\d+)', html)
        if m_dur:
            duration = int(m_dur.group(1))

        return {
            "title": title or "NhacCuaTui Track",
            "artist": artists or "NhacCuaTui Artist",
            "thumbnail": thumb,
            "duration": duration,
            "stream_url": best_stream,
            "url": url
        }
    except Exception as e:
        print(f"[!] NCT extraction error: {e}")
        return None

def get_zingmp3_track_info(url):
    """
    Extracts metadata from Zing MP3. Uses yt-dlp, or falls back to slug parsing + YouTube Music matching.
    """
    m = re.search(r'zingmp3\.vn/(?:bai-hat|video-clip|album)/([^/]+)/([a-zA-Z0-9]+)\.html', url)
    slug = ""
    song_id = ""
    if m:
        slug = m.group(1)
        song_id = m.group(2)
    else:
        m2 = re.search(r'zingmp3\.vn/(?:bai-hat|video-clip|album)/([a-zA-Z0-9]+)', url)
        if m2:
            song_id = m2.group(1)

    title = ""
    artist = ""
    duration = 0
    thumbnail = ""

    try:
        info = extract_info_safe({'quiet': True, 'skip_download': True, 'no_warnings': True}, url, download=False)
        if info:
            title = info.get("title") or ""
            artist = info.get("uploader") or info.get("artist") or ""
            duration = int(info.get("duration") or 0)
            thumbnail = info.get("thumbnail") or ""
    except Exception:
        pass

    if not title and slug:
        clean_query = slug.replace('-', ' ')
        try:
            ytm = YTMusic()
            results = ytm.search(clean_query, filter='songs')
            if results:
                best = results[0]
                title = best.get("title", "")
                artist = ", ".join([a.get("name", "") for a in best.get("artists", [])])
                duration = best.get("duration_seconds", 0)
                if not duration and best.get("duration"):
                    dur_str = best.get("duration", "0:00")
                    pts = dur_str.split(":")
                    if len(pts) == 2:
                        duration = int(pts[0]) * 60 + int(pts[1])
                    elif len(pts) == 3:
                        duration = int(pts[0]) * 3600 + int(pts[1]) * 60 + int(pts[2])
                thumbs = best.get("thumbnails", [])
                if thumbs:
                    thumbnail = thumbs[-1].get("url", "")
                    thumbnail = re.sub(r'=w\d+-h\d+', '=w800-h800', thumbnail)
                    thumbnail = re.sub(r'=s\d+', '=s800', thumbnail)
        except Exception as ye:
            print(f"[!] YTMusic fallback search error for Zing: {ye}")

    if not title:
        if slug:
            parts = slug.split('-')
            title = ' '.join(parts).title()
            artist = "Zing MP3 Artist"
        else:
            title = f"Zing MP3 Track ({song_id})" if song_id else "Zing MP3 Track"
            artist = "Zing MP3"

    return {
        "title": title,
        "artist": artist,
        "duration": duration,
        "thumbnail": thumbnail,
        "song_id": song_id,
        "slug": slug,
        "url": url
    }

def resolve_tiktok_url(url):
    """
    Expands short TikTok links (vt.tiktok.com, vm.tiktok.com) to full canonical URL.
    """
    try:
        if any(d in url.lower() for d in ["vt.tiktok.com", "vm.tiktok.com"]):
            resp = requests.head(
                url,
                allow_redirects=True,
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            if resp.url:
                return resp.url
    except Exception as e:
        print(f"[!] resolve_tiktok_url redirect error: {e}")
    return url

def get_tiktok_info(url):
    """
    Extracts TikTok metadata, no-watermark video stream URL, and audio stream URL.
    Uses TikWM API as primary engine (fast & no-watermark) with yt-dlp fallback.
    """
    resolved_url = resolve_tiktok_url(url)

    # 1. Primary Engine: TikWM API
    try:
        resp = requests.get(
            "https://www.tikwm.com/api/",
            params={"url": resolved_url, "hd": 1},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            timeout=12
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0 and data.get("data"):
                d = data["data"]
                title = d.get("title") or "TikTok Video"
                title = " ".join(title.split())
                author_obj = d.get("author") or {}
                author = author_obj.get("nickname") or author_obj.get("unique_id") or "TikTok Creator"

                video_url = d.get("hdplay") or d.get("play")
                if video_url and not video_url.startswith("http"):
                    video_url = f"https://www.tikwm.com{video_url}"

                audio_url = d.get("music")
                if audio_url and not audio_url.startswith("http"):
                    audio_url = f"https://www.tikwm.com{audio_url}"

                cover = d.get("cover")
                if cover and not cover.startswith("http"):
                    cover = f"https://www.tikwm.com{cover}"

                duration = int(d.get("duration", 0) or 0)

                return {
                    "title": title,
                    "author": author,
                    "duration": duration,
                    "thumbnail": cover or "",
                    "video_url": video_url,
                    "audio_url": audio_url,
                    "source": "tikwm"
                }
    except Exception as e:
        print(f"[!] TikWM API error: {e}")

    # 2. Fallback Engine: yt-dlp
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(resolved_url, download=False)
            if info:
                title = info.get("title") or "TikTok Video"
                title = " ".join(title.split())
                return {
                    "title": title,
                    "author": info.get("uploader") or info.get("creator") or "TikTok Creator",
                    "duration": int(info.get("duration", 0) or 0),
                    "thumbnail": info.get("thumbnail") or "",
                    "video_url": None,
                    "audio_url": None,
                    "source": "yt-dlp"
                }
    except Exception as e:
        print(f"[!] yt-dlp TikTok fallback error: {e}")

    return None

# ==================== ROUTES ====================

@app.route("/")
def index():
    return send_file(os.path.join(BASE_DIR, "index.html"))

@app.route("/api/health")
def health():
    cookie_p = get_cookie_file()
    return jsonify({
        "status": "online",
        "ffmpeg": bool(FFMPEG_EXE),
        "ffmpeg_path": FFMPEG_EXE,
        "ytdlp_version": yt_dlp.version.__version__,
        "has_cookies": bool(cookie_p),
        "cookie_file": os.path.basename(cookie_p) if cookie_p else None
    })

@app.route("/api/cookies/status", methods=["GET"])
def get_cookies_status():
    cookie_p = get_cookie_file()
    if not cookie_p:
        return jsonify({
            "has_cookies": False,
            "filename": None,
            "cookie_count": 0,
            "youtube_cookies": 0,
            "mode": "Tự động chống Bot (web_embedded + mobile active)"
        })
    try:
        count = 0
        yt_count = 0
        with open(cookie_p, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    count += 1
                    if "youtube.com" in line or "google.com" in line:
                        yt_count += 1
        return jsonify({
            "has_cookies": True,
            "filename": os.path.basename(cookie_p),
            "cookie_count": count,
            "youtube_cookies": yt_count,
            "mode": "Sử dụng Cookie xác thực cá nhân"
        })
    except Exception as e:
        return jsonify({
            "has_cookies": True,
            "filename": os.path.basename(cookie_p),
            "error": str(e)
        })

@app.route("/api/cookies/upload", methods=["POST"])
def upload_cookies():
    try:
        content = ""
        if "file" in request.files:
            f = request.files["file"]
            content = f.read().decode("utf-8", errors="ignore")
        elif request.is_json:
            content = request.json.get("cookies_text", "")
        else:
            content = request.form.get("cookies_text", "")
            
        if not content.strip():
            return jsonify({"success": False, "error": "Không có nội dung cookie nào được gửi!"}), 400
            
        target_path = os.path.join(BASE_DIR, "cookies.txt")
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
            
        yt_count = sum(1 for line in content.splitlines() if ("youtube.com" in line or "google.com" in line) and not line.startswith("#"))
        return jsonify({
            "success": True,
            "message": f"Đã lưu cookies.txt thành công ({yt_count} cookies YouTube)!",
            "youtube_cookies": yt_count
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Lỗi lưu cookie: {str(e)}"}), 500

@app.route("/api/cookies/delete", methods=["POST"])
def delete_cookies():
    deleted = []
    for f in COOKIE_FILE_CANDIDATES:
        p = os.path.join(BASE_DIR, f)
        if os.path.exists(p):
            try:
                os.remove(p)
                deleted.append(f)
            except Exception:
                pass
    return jsonify({"success": True, "message": f"Đã xóa {len(deleted)} file cookie.", "deleted": deleted})

@app.route("/api/info", methods=["POST"])
def get_info():
    data = request.get_json() or {}
    raw_url = data.get("url", "").strip()

    if not raw_url:
        return jsonify({"success": False, "error": "Vui lòng nhập đường dẫn URL hợp lệ!"}), 400

    url = clean_youtube_url(raw_url)
    lower_url = url.lower()

    # 1. SPOTIFY HANDLING (supports intl-vi, intl-en, web links, etc.)
    if "spotify.com" in lower_url or lower_url.startswith("spotify:"):
        match_spotify = re.search(r"spotify\.com/(?:intl-[a-zA-Z-]+/)?(track|album|playlist)/([a-zA-Z0-9]+)", url)
        if not match_spotify:
            match_spotify = re.search(r"spotify:(track|album|playlist):([a-zA-Z0-9]+)", url)

        if match_spotify:
            sp_type = match_spotify.group(1)
            sp_id = match_spotify.group(2)

            if sp_type == "track":
                info = get_spotify_track_info(sp_id)
                if not info:
                    return jsonify({"success": False, "error": "Không thể lấy dữ liệu bài hát từ Spotify!"}), 400
                return jsonify({
                    "success": True,
                    "platform": "spotify",
                    "is_playlist": False,
                    "is_album": False,
                    "title": info["title"],
                    "author": info["artist_str"],
                    "duration": info["duration"],
                    "thumbnail": info["cover"],
                    "url": url,
                    "extra": f"Năm phát hành: {info['year']}" if info.get('year') else "Spotify Master Audio"
                })

            elif sp_type in ["album", "playlist"]:
                info = get_spotify_collection_info(sp_type, sp_id)
                if not info:
                    return jsonify({"success": False, "error": f"Không thể lấy dữ liệu {sp_type} từ Spotify!"}), 400

                return jsonify({
                    "success": True,
                    "platform": "spotify",
                    "is_playlist": True,
                    "is_album": sp_type == "album",
                    "title": info["title"],
                    "author": info["author"],
                    "duration": sum(t["duration"] for t in info["tracks"]),
                    "thumbnail": info["cover"],
                    "url": url,
                    "tracks": info["tracks"],
                    "extra": f"{len(info['tracks'])} bài hát"
                })
        else:
            return jsonify({"success": False, "error": "Liên kết Spotify không hợp lệ. Vui lòng cung cấp link Track, Album hoặc Playlist!"}), 400

    # 2. YOUTUBE HANDLING
    elif any(d in lower_url for d in ["youtube.com", "youtu.be"]):
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "playlist_items": "1-50"
        }
        try:
            info = extract_info_safe(ydl_opts, url, download=False)
            
            is_playlist = "_type" in info and info["_type"] == "playlist"
            is_short = "/shorts/" in url

            if is_playlist:
                entries = info.get("entries", [])
                tracks = []
                for e in entries:
                    if e:
                        tracks.append({
                            "title": e.get("title", "YouTube Video"),
                            "author": e.get("uploader", info.get("uploader", "")),
                            "duration": e.get("duration", 0),
                            "id": e.get("id"),
                            "url": f"https://www.youtube.com/watch?v={e.get('id')}"
                        })

                return jsonify({
                    "success": True,
                    "platform": "youtube",
                    "is_playlist": True,
                    "is_short": False,
                    "title": info.get("title", "YouTube Playlist"),
                    "author": info.get("uploader", "YouTube Channel"),
                    "duration": sum(t["duration"] for t in tracks if t.get("duration")),
                    "thumbnail": info.get("thumbnails", [{}])[-1].get("url") if info.get("thumbnails") else "",
                    "url": url,
                    "tracks": tracks,
                    "extra": f"{len(tracks)} video trong danh sách"
                })
            else:
                # Pick highest resolution thumbnail available
                thumb = info.get("thumbnail", "")
                if info.get("thumbnails"):
                    valid_thumbs = [t for t in info["thumbnails"] if t.get("url")]
                    if valid_thumbs:
                        valid_thumbs.sort(key=lambda x: (x.get("width") or 0) * (x.get("height") or 0), reverse=True)
                        thumb = valid_thumbs[0].get("url") or thumb

                return jsonify({
                    "success": True,
                    "platform": "youtube",
                    "is_playlist": False,
                    "is_short": is_short,
                    "title": info.get("title", "YouTube Video"),
                    "author": info.get("uploader", "YouTube Channel"),
                    "duration": info.get("duration", 0),
                    "thumbnail": thumb,
                    "url": url,
                    "extra": f"{info.get('view_count', 0):,} lượt xem" if info.get("view_count") else ""
                })
        except Exception as e:
            err_raw = str(e)
            err_lower = err_raw.lower()
            if "not a bot" in err_lower or "sign in" in err_lower:
                friendly_err = (
                    "YouTube kích hoạt cơ chế xác minh chống Bot với địa chỉ IP này. "
                    "Hệ thống đã tự động thử các kênh dự phòng (web_embedded, mobile) nhưng chưa vượt qua được. "
                    "Vui lòng nạp file 'cookies.txt' từ trình duyệt của bạn (dùng tiện ích mở rộng 'Get cookies.txt LOCALLY') "
                    "hoặc nhấn nút 'Cài đặt Cookies' bên dưới để tải không giới hạn."
                )
                return jsonify({"success": False, "error": friendly_err, "is_bot_error": True, "raw_error": err_raw}), 400
            return jsonify({"success": False, "error": f"Lỗi phân tích YouTube: {err_raw}"}), 400

    # 3. SOUNDCLOUD HANDLING
    elif any(d in lower_url for d in ["soundcloud.com", "on.soundcloud.com"]):
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "playlist_items": "1-50"
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                is_playlist = info.get("_type") == "playlist" or "/sets/" in lower_url

                # Get best high-res thumbnail
                thumb = info.get("thumbnail") or ""
                if thumb and "-large.jpg" in thumb:
                    thumb = thumb.replace("-large.jpg", "-t500x500.jpg")

                if is_playlist and info.get("entries"):
                    entries = info.get("entries", [])
                    tracks = []
                    for e in entries:
                        if e:
                            t_thumb = e.get("thumbnail") or thumb
                            if t_thumb and "-large.jpg" in t_thumb:
                                t_thumb = t_thumb.replace("-large.jpg", "-t500x500.jpg")
                            tracks.append({
                                "title": e.get("title", "SoundCloud Track"),
                                "author": e.get("uploader", info.get("uploader", "SoundCloud Artist")),
                                "duration": int(e.get("duration", 0)),
                                "id": str(e.get("id", "")),
                                "url": e.get("webpage_url") or e.get("url") or url,
                                "thumbnail": t_thumb
                            })

                    return jsonify({
                        "success": True,
                        "platform": "soundcloud",
                        "is_playlist": True,
                        "is_album": False,
                        "title": info.get("title", "SoundCloud Playlist"),
                        "author": info.get("uploader", "SoundCloud Artist"),
                        "duration": sum(t["duration"] for t in tracks if t.get("duration")),
                        "thumbnail": thumb,
                        "url": url,
                        "tracks": tracks,
                        "extra": f"{len(tracks)} bài hát trong Playlist"
                    })
                else:
                    return jsonify({
                        "success": True,
                        "platform": "soundcloud",
                        "is_playlist": False,
                        "title": info.get("title", "SoundCloud Track"),
                        "author": info.get("uploader", "SoundCloud Artist"),
                        "duration": int(info.get("duration", 0)),
                        "thumbnail": thumb,
                        "url": url,
                        "extra": f"{info.get('view_count', 0):,} lượt nghe" if info.get("view_count") else "SoundCloud High Quality"
                    })
        except Exception as e:
            return jsonify({"success": False, "error": f"Lỗi phân tích SoundCloud: {str(e)}"}), 400

    # 4. ZING MP3 HANDLING
    elif any(d in lower_url for d in ["zingmp3.vn", "mp3.zing.vn"]):
        try:
            info = get_zingmp3_track_info(url)
            if not info or not info.get("title"):
                return jsonify({"success": False, "error": "Không thể lấy thông tin bài hát từ liên kết Zing MP3 này."}), 400

            return jsonify({
                "success": True,
                "platform": "zingmp3",
                "is_playlist": False,
                "title": info.get("title", "Zing MP3 Track"),
                "author": info.get("artist", "Zing MP3 Artist"),
                "duration": int(info.get("duration", 0)),
                "thumbnail": info.get("thumbnail", ""),
                "url": url,
                "extra": "Zing MP3 320kbps HD Audio"
            })
        except Exception as e:
            return jsonify({"success": False, "error": f"Lỗi phân tích Zing MP3: {str(e)}"}), 400

    # 5. NHACCUATUI HANDLING
    elif any(d in lower_url for d in ["nhaccuatui.com", "nct.vn"]):
        try:
            info = get_nct_track_info(url)
            if not info or not info.get("title"):
                return jsonify({"success": False, "error": "Không thể lấy thông tin bài hát từ liên kết NhacCuaTui này."}), 400

            return jsonify({
                "success": True,
                "platform": "nhaccuatui",
                "is_playlist": False,
                "title": info.get("title", "NhacCuaTui Track"),
                "author": info.get("artist", "NhacCuaTui Artist"),
                "duration": int(info.get("duration", 0)),
                "thumbnail": info.get("thumbnail", ""),
                "url": url,
                "extra": "NhacCuaTui 320kbps Lossless Source"
            })
        except Exception as e:
            return jsonify({"success": False, "error": f"Lỗi phân tích NhacCuaTui: {str(e)}"}), 400

    # 6. TIKTOK HANDLING
    elif any(d in lower_url for d in ["tiktok.com", "douyin.com"]):
        try:
            info = get_tiktok_info(url)
            if not info or not info.get("title"):
                return jsonify({"success": False, "error": "Không thể lấy thông tin video TikTok. Vui lòng kiểm tra lại đường link."}), 400

            return jsonify({
                "success": True,
                "platform": "tiktok",
                "is_playlist": False,
                "title": info.get("title", "TikTok Video"),
                "author": info.get("author", "TikTok Creator"),
                "duration": int(info.get("duration", 0)),
                "thumbnail": info.get("thumbnail", ""),
                "url": url,
                "extra": "TikTok Không Logo & Âm thanh Studio"
            })
        except Exception as e:
            return jsonify({"success": False, "error": f"Lỗi phân tích TikTok: {str(e)}"}), 400

    else:
        return jsonify({"success": False, "error": "Chỉ hỗ trợ liên kết YouTube, TikTok, Spotify, SoundCloud, Zing MP3 hoặc NhacCuaTui!"}), 400

# ==================== DOWNLOAD WORKER ====================

def download_worker(job_id, payload):
    url = clean_youtube_url(payload.get("url", ""))
    platform = payload.get("platform", "").strip().lower()
    
    # Auto-detect platform from URL if omitted or mismatched
    lower_u = url.lower()
    if any(d in lower_u for d in ["spotify.com", "spotify:"]):
        platform = "spotify"
    elif any(d in lower_u for d in ["soundcloud.com", "on.soundcloud.com"]):
        platform = "soundcloud"
    elif any(d in lower_u for d in ["zingmp3.vn"]):
        platform = "zingmp3"
    elif any(d in lower_u for d in ["nhaccuatui.com", "nct.vn"]):
        platform = "nhaccuatui"
    elif any(d in lower_u for d in ["tiktok.com", "douyin.com"]):
        platform = "tiktok"
    elif not platform:
        platform = "youtube"

    mode = payload.get("mode", "audio")
    req_format = payload.get("format", "mp3")
    quality = payload.get("quality", "320")
    selected_tracks = payload.get("selected_tracks", [])
    custom_title = payload.get("title", "")

    job_folder = os.path.join(DOWNLOAD_DIR, job_id)
    os.makedirs(job_folder, exist_ok=True)

    def progress_hook(d):
        with JOBS_LOCK:
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                percent = (downloaded / total * 100) if total > 0 else 30
                speed = d.get('speed')
                speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed else "Đang tính..."
                eta = d.get('eta')
                eta_str = f"{eta}s" if eta else "Đang tính..."
                
                JOBS[job_id].update({
                    "percent": min(max(percent * 0.85, 10), 90),
                    "status": "Đang tải dữ liệu chất lượng cao...",
                    "speed": speed_str,
                    "eta": eta_str
                })
            elif d['status'] == 'finished':
                JOBS[job_id].update({
                    "percent": 92,
                    "status": "Đang xử lý âm thanh với FFmpeg (320kbps / Gắn thẻ ID3)...",
                    "speed": "Xử lý...",
                    "eta": "Vài giây"
                })

    try:
        # CASE 1: SOUNDCLOUD DOWNLOAD (HIGH-RES 320k MP3, FLAC, M4A, WAV + EMBEDDED ARTWORK)
        if platform == "soundcloud":
            target_ext = req_format if req_format in ['mp3', 'flac', 'm4a', 'wav'] else 'mp3'

            # Playlist / Set handling with tracks selection
            if selected_tracks or "/sets/" in url:
                JOBS[job_id]["status"] = "Đang phân tích danh sách phát SoundCloud..."
                JOBS[job_id]["percent"] = 10

                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'skip_download': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    entries = info.get("entries", [])
                    playlist_title = info.get("title", "SoundCloud Playlist")

                if entries:
                    targets = [entries[i] for i in selected_tracks if i < len(entries)] if selected_tracks else entries[:10]
                    total_t = len(targets)

                    for idx, entry in enumerate(targets):
                        t_url = entry.get("webpage_url") or entry.get("url")
                        t_title = entry.get("title", f"Track_{idx+1}")
                        JOBS[job_id]["status"] = f"Đang tải ({idx+1}/{total_t}): {t_title}..."
                        JOBS[job_id]["percent"] = int((idx / total_t) * 85) + 10

                        ydl_track_opts = {
                            "format": "bestaudio/best",
                            "outtmpl": os.path.join(job_folder, f"{idx+1:02d} - %(title)s.%(ext)s"),
                            "quiet": True,
                            "no_warnings": True,
                            "ffmpeg_location": FFMPEG_EXE,
                            "writethumbnail": True,
                        }
                        postprocessors = []
                        if target_ext == 'mp3':
                            postprocessors.extend([
                                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'},
                                {'key': 'FFmpegMetadata', 'add_metadata': True},
                                {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
                            ])
                        elif target_ext == 'flac':
                            postprocessors.extend([
                                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'flac'},
                                {'key': 'FFmpegMetadata', 'add_metadata': True}
                            ])
                        elif target_ext == 'm4a':
                            postprocessors.extend([
                                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a', 'preferredquality': '256'},
                                {'key': 'FFmpegMetadata', 'add_metadata': True}
                            ])
                        elif target_ext == 'wav':
                            postprocessors.extend([
                                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}
                            ])
                        ydl_track_opts['postprocessors'] = postprocessors

                        try:
                            with yt_dlp.YoutubeDL(ydl_track_opts) as ydl_t:
                                ydl_t.download([t_url])
                        except Exception as te:
                            print(f"[!] Error downloading SoundCloud track {t_title}: {te}")

                    out_files = [os.path.join(job_folder, f) for f in os.listdir(job_folder) if f.endswith(f".{target_ext}")]
                    if not out_files:
                        raise Exception("Không tải được bài hát nào từ danh sách SoundCloud.")

                    zip_name = format_media_filename(playlist_title, "zip")
                    zip_path = os.path.join(job_folder, zip_name)
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for f in out_files:
                            zipf.write(f, os.path.basename(f))

                    JOBS[job_id].update({
                        "percent": 100,
                        "finished": True,
                        "status": "Hoàn tất toàn bộ danh sách SoundCloud!",
                        "filename": zip_name,
                        "filepath": zip_path,
                        "download_url": f"/api/file/{job_id}"
                    })
                    return

            # Single track SoundCloud download
            JOBS[job_id]["status"] = "Đang tải bài hát SoundCloud chất lượng cao (320kbps)..."
            JOBS[job_id]["percent"] = 15

            out_template = os.path.join(job_folder, "QuocTinMedia - %(title)s.%(ext)s")
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": out_template,
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": True,
                "ffmpeg_location": FFMPEG_EXE,
                "writethumbnail": True
            }

            postprocessors = []
            if target_ext == "mp3":
                postprocessors.extend([
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
                    {"key": "FFmpegMetadata", "add_metadata": True},
                    {"key": "EmbedThumbnail", "already_have_thumbnail": False}
                ])
            elif target_ext == "flac":
                postprocessors.extend([
                    {"key": "FFmpegExtractAudio", "preferredcodec": "flac"},
                    {"key": "FFmpegMetadata", "add_metadata": True}
                ])
            elif target_ext == "m4a":
                postprocessors.extend([
                    {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "256"},
                    {"key": "FFmpegMetadata", "add_metadata": True}
                ])
            elif target_ext == "wav":
                postprocessors.extend([
                    {"key": "FFmpegExtractAudio", "preferredcodec": "wav"}
                ])
            ydl_opts["postprocessors"] = postprocessors

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            files = [f for f in os.listdir(job_folder) if not f.endswith(('.temp', '.part', '.ytdl', '.jpg', '.png', '.webp'))]
            media_files = [f for f in files if f.endswith(f".{target_ext}")]
            if not media_files:
                media_files = [f for f in files if f.endswith(('.mp3', '.flac', '.wav', '.m4a', '.opus'))]
            if not media_files:
                raise Exception("Không tìm thấy file sau khi tải SoundCloud.")

            final_file = os.path.join(job_folder, media_files[0])
            base_name = os.path.basename(final_file)
            if not base_name.lower().startswith("quoctinmedia"):
                target_name = f"QuocTinMedia - {base_name}"
                target_path = os.path.join(job_folder, target_name)
                try:
                    os.rename(final_file, target_path)
                    final_file = target_path
                except Exception:
                    pass

            JOBS[job_id].update({
                "percent": 100,
                "finished": True,
                "status": "Hoàn tất!",
                "filename": os.path.basename(final_file),
                "filepath": final_file,
                "download_url": f"/api/file/{job_id}"
            })
            return

        # CASE 2: SPOTIFY TRACK DOWNLOAD
        elif platform == "spotify":
            match_spotify = re.search(r"spotify\.com/(?:intl-[a-zA-Z-]+/)?(track|album|playlist)/([a-zA-Z0-9]+)", url)
            if not match_spotify:
                match_spotify = re.search(r"spotify:(track|album|playlist):([a-zA-Z0-9]+)", url)

            if not match_spotify:
                raise Exception("Không tìm thấy mã bài hát / album Spotify hợp lệ.")

            sp_type = match_spotify.group(1)
            sp_id = match_spotify.group(2)

            if sp_type == "track":
                track_info = get_spotify_track_info(sp_id)
                if not track_info:
                    raise Exception("Không thể lấy thông tin bài hát từ Spotify.")

                JOBS[job_id]["status"] = f"Đang dò tìm bản thu Studio gốc trên YouTube Music: {track_info['title']}..."
                JOBS[job_id]["percent"] = 15

                # Find exact master audio matching Spotify duration and official label release
                best_source_url = find_exact_spotify_audio_match(
                    track_info['title'],
                    track_info['artist_str'],
                    track_info.get('duration', 0)
                )

                JOBS[job_id]["status"] = f"Đang tải bản thu gốc chất lượng cao nhất: {track_info['title']}..."
                JOBS[job_id]["percent"] = 25

                ydl_opts = apply_youtube_opts({
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(job_folder, "%(title)s.%(ext)s"),
                    "progress_hooks": [progress_hook],
                    "quiet": True,
                    "no_warnings": True,
                    "ffmpeg_location": FFMPEG_EXE
                }, is_youtube=True)

                target_ext = req_format if req_format in ['mp3', 'flac', 'm4a', 'wav'] else 'mp3'
                postprocessors = []
                
                if target_ext == 'mp3':
                    postprocessors.append({
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320', # True CBR 320kbps
                    })
                elif target_ext == 'flac':
                    postprocessors.append({
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'flac',
                    })
                elif target_ext == 'm4a':
                    postprocessors.append({
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'm4a',
                        'preferredquality': '256',
                    })
                elif target_ext == 'wav':
                    postprocessors.append({
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'wav',
                    })

                ydl_opts['postprocessors'] = postprocessors

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([best_source_url])

                files = os.listdir(job_folder)
                audio_files = [f for f in files if f.endswith(f".{target_ext}")]
                if not audio_files:
                    raise Exception("Không tìm thấy file âm thanh sau khi tải.")

                final_file = os.path.join(job_folder, audio_files[0])

                # Inject high-resolution Spotify Cover Art & ID3 Tags using mutagen
                JOBS[job_id]["status"] = "Đang nhúng ảnh bìa HD và thông tin bản quyền ID3 Tag..."
                JOBS[job_id]["percent"] = 95

                cover_bytes = None
                if track_info.get("cover"):
                    try:
                        cover_resp = requests.get(track_info["cover"], timeout=10)
                        if cover_resp.status_code == 200:
                            cover_bytes = cover_resp.content
                    except Exception as e:
                        print(f"[!] Failed to fetch cover art: {e}")

                if target_ext == 'mp3':
                    try:
                        audio = ID3(final_file)
                    except:
                        audio = ID3()
                    
                    audio.add(TIT2(encoding=3, text=track_info['title']))
                    audio.add(TPE1(encoding=3, text=track_info['artist_str']))
                    if track_info.get('album'):
                        audio.add(TALB(encoding=3, text=track_info['album']))
                    if track_info.get('year'):
                        audio.add(TDRC(encoding=3, text=str(track_info['year'])))
                    if cover_bytes:
                        audio.add(APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,
                            desc='Cover',
                            data=cover_bytes
                        ))
                    audio.save(final_file, v2_version=3)

                elif target_ext == 'flac':
                    try:
                        audio = FLAC(final_file)
                        audio["title"] = track_info['title']
                        audio["artist"] = track_info['artist_str']
                        if track_info.get('album'):
                            audio["album"] = track_info['album']
                        if track_info.get('year'):
                            audio["date"] = str(track_info['year'])
                        if cover_bytes:
                            pic = Picture()
                            pic.type = 3
                            pic.mime = 'image/jpeg'
                            pic.desc = 'Front Cover'
                            pic.data = cover_bytes
                            audio.clear_pictures()
                            audio.add_picture(pic)
                        audio.save()
                    except Exception as e:
                        print(f"[!] FLAC tag error: {e}")

                elif target_ext == 'm4a':
                    try:
                        audio = MP4(final_file)
                        audio["\xa9nam"] = track_info['title']
                        audio["\xa9ART"] = track_info['artist_str']
                        if track_info.get('album'):
                            audio["\xa9alb"] = track_info['album']
                        if track_info.get('year'):
                            audio["\xa9day"] = str(track_info['year'])
                        if cover_bytes:
                            audio["covr"] = [MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
                        audio.save()
                    except Exception as e:
                        print(f"[!] M4A tag error: {e}")

                clean_name = format_media_filename(f"{track_info['artist_str']} - {track_info['title']}", target_ext)
                renamed_path = os.path.join(job_folder, clean_name)
                os.rename(final_file, renamed_path)

                JOBS[job_id].update({
                    "percent": 100,
                    "finished": True,
                    "status": "Hoàn tất!",
                    "filename": clean_name,
                    "filepath": renamed_path,
                    "download_url": f"/api/file/{job_id}"
                })
                return

            elif sp_type in ["album", "playlist"]:
                coll_info = get_spotify_collection_info(sp_type, sp_id)
                if not coll_info:
                    raise Exception("Không thể đọc danh sách bài hát từ Spotify.")

                all_tracks = coll_info["tracks"]
                targets = [all_tracks[i] for i in selected_tracks if i < len(all_tracks)] if selected_tracks else all_tracks[:10]

                downloaded_files = []
                total_t = len(targets)

                for idx, t in enumerate(targets):
                    JOBS[job_id]["status"] = f"Đang đối soát bài {idx+1}/{total_t}: {t['title']}..."
                    JOBS[job_id]["percent"] = int(((idx) / total_t) * 90) + 5
                    
                    best_source_url = find_exact_spotify_audio_match(
                        t['title'],
                        t.get('author', ''),
                        t.get('duration', 0)
                    )

                    target_ext = req_format if req_format in ['mp3', 'flac', 'm4a'] else 'mp3'

                    ydl_opts = apply_youtube_opts({
                        "format": "bestaudio/best",
                        "outtmpl": os.path.join(job_folder, f"{idx+1}_{sanitize_filename(t['title'])}.%(ext)s"),
                        "quiet": True,
                        "no_warnings": True,
                        "ffmpeg_location": FFMPEG_EXE,
                        "postprocessors": [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': target_ext,
                            'preferredquality': '320' if target_ext == 'mp3' else None,
                        }]
                    }, is_youtube=True)
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([best_source_url])
                    except Exception as e:
                        print(f"[!] Error on track {t['title']}: {e}")

                out_files = [os.path.join(job_folder, f) for f in os.listdir(job_folder) if f.endswith(f".{target_ext}")]
                if not out_files:
                    raise Exception("Không tải được bài hát nào.")

                zip_name = format_media_filename(coll_info['title'], "zip")
                zip_path = os.path.join(job_folder, zip_name)
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for f in out_files:
                        zipf.write(f, os.path.basename(f))

                JOBS[job_id].update({
                    "percent": 100,
                    "finished": True,
                    "status": "Hoàn tất toàn bộ danh sách phát!",
                    "filename": zip_name,
                    "filepath": zip_path,
                    "download_url": f"/api/file/{job_id}"
                })
                return

        # CASE 4: NHACCUATUI (NCT) DOWNLOAD
        elif platform == "nhaccuatui":
            nct_info = get_nct_track_info(url)
            if not nct_info:
                raise Exception("Không thể trích xuất thông tin bài hát từ NhacCuaTui.")

            track_title = custom_title or nct_info.get("title", "NhacCuaTui Track")
            track_artist = nct_info.get("artist", "NhacCuaTui Artist")
            target_ext = req_format if req_format in ['mp3', 'flac', 'm4a', 'wav'] else 'mp3'

            JOBS[job_id]["status"] = f"Đang chuẩn bị tải bài hát: {track_title}..."
            JOBS[job_id]["percent"] = 15

            stream_url = nct_info.get("stream_url")
            raw_audio_file = os.path.join(job_folder, "nct_raw.mp3")

            download_succeeded = False
            if stream_url:
                try:
                    JOBS[job_id]["status"] = f"Đang tải trực tiếp từ máy chủ NhacCuaTui (320kbps): {track_title}..."
                    s_headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Referer": "https://www.nhaccuatui.com/"
                    }
                    r = requests.get(stream_url, headers=s_headers, stream=True, timeout=25)
                    if r.status_code == 200:
                        total_bytes = int(r.headers.get("content-length", 0))
                        downloaded_bytes = 0
                        with open(raw_audio_file, "wb") as f_out:
                            for chunk in r.iter_content(chunk_size=65536):
                                if chunk:
                                    f_out.write(chunk)
                                    downloaded_bytes += len(chunk)
                                    if total_bytes > 0:
                                        pct = min(15 + int((downloaded_bytes / total_bytes) * 65), 80)
                                        JOBS[job_id]["percent"] = pct
                        download_succeeded = os.path.exists(raw_audio_file) and os.path.getsize(raw_audio_file) > 100000
                except Exception as nct_dl_err:
                    print(f"[!] Direct NCT stream download failed: {nct_dl_err}")
                    download_succeeded = False

            # If direct download failed, fallback to studio matching
            if not download_succeeded:
                JOBS[job_id]["status"] = f"Đang dò tìm bản thu Studio gốc: {track_title}..."
                JOBS[job_id]["percent"] = 30
                best_source_url = find_exact_spotify_audio_match(
                    track_title,
                    track_artist,
                    nct_info.get("duration", 0)
                )
                JOBS[job_id]["status"] = f"Đang tải bản thu Studio chất lượng cao: {track_title}..."
                JOBS[job_id]["percent"] = 45

                ydl_opts = apply_youtube_opts({
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(job_folder, "source.%(ext)s"),
                    "progress_hooks": [progress_hook],
                    "quiet": True,
                    "no_warnings": True,
                    "ffmpeg_location": FFMPEG_EXE
                }, is_youtube=True)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([best_source_url])

                src_files = [f for f in os.listdir(job_folder) if not f.endswith(('.temp', '.part', '.ytdl', '.jpg', '.png'))]
                if not src_files:
                    raise Exception("Không tải được bản thu cho bài hát NhacCuaTui.")
                raw_audio_file = os.path.join(job_folder, src_files[0])

            # Convert to target format using FFmpeg
            JOBS[job_id]["status"] = f"Đang xử lý âm thanh ({target_ext.upper()}) với FFmpeg..."
            JOBS[job_id]["percent"] = 85

            safe_name = format_media_filename(f"{track_title} - {track_artist}")
            final_file = os.path.join(job_folder, f"{safe_name}.{target_ext}")

            cmd = [FFMPEG_EXE or "ffmpeg", "-y", "-i", raw_audio_file]
            if target_ext == "mp3":
                cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "44100"])
            elif target_ext == "flac":
                cmd.extend(["-c:a", "flac"])
            elif target_ext == "m4a":
                cmd.extend(["-c:a", "aac", "-b:a", "256k"])
            elif target_ext == "wav":
                cmd.extend(["-c:a", "pcm_s16le"])
            cmd.append(final_file)

            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode != 0 or not os.path.exists(final_file):
                if target_ext == "mp3" and os.path.exists(raw_audio_file):
                    shutil.copy2(raw_audio_file, final_file)
                else:
                    raise Exception(f"Lỗi chuyển đổi âm thanh: {res.stderr.decode('utf-8', errors='ignore')[:200]}")

            # Inject Cover Art and ID3 Metadata Tags
            JOBS[job_id]["status"] = "Đang gắn nhãn bản quyền & ảnh bìa HD..."
            JOBS[job_id]["percent"] = 95

            cover_bytes = None
            if nct_info.get("thumbnail"):
                try:
                    c_resp = requests.get(nct_info["thumbnail"], headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nhaccuatui.com/"}, timeout=10)
                    if c_resp.status_code == 200:
                        cover_bytes = c_resp.content
                except Exception as ce:
                    print(f"[!] NCT cover fetch error: {ce}")

            if target_ext == "mp3":
                try:
                    audio = ID3(final_file)
                except:
                    audio = ID3()
                audio.add(TIT2(encoding=3, text=track_title))
                audio.add(TPE1(encoding=3, text=track_artist))
                audio.add(TALB(encoding=3, text="NhacCuaTui"))
                if cover_bytes:
                    audio.add(APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,
                        desc='Cover',
                        data=cover_bytes
                    ))
                audio.save(final_file, v2_version=3)
            elif target_ext == "flac":
                try:
                    audio = FLAC(final_file)
                    audio["title"] = track_title
                    audio["artist"] = track_artist
                    audio["album"] = "NhacCuaTui"
                    if cover_bytes:
                        pic = Picture()
                        pic.type = 3
                        pic.mime = 'image/jpeg'
                        pic.desc = 'Front Cover'
                        pic.data = cover_bytes
                        audio.add_picture(pic)
                    audio.save()
                except Exception as fe:
                    print(f"[!] FLAC tag error: {fe}")

            JOBS[job_id].update({
                "percent": 100,
                "finished": True,
                "status": "Hoàn tất!",
                "filename": os.path.basename(final_file),
                "filepath": final_file,
                "download_url": f"/api/file/{job_id}"
            })
            return

        # CASE 5: ZING MP3 DOWNLOAD
        elif platform == "zingmp3":
            zing_info = get_zingmp3_track_info(url)
            if not zing_info:
                raise Exception("Không thể trích xuất thông tin bài hát từ Zing MP3.")

            track_title = custom_title or zing_info.get("title", "Zing MP3 Track")
            track_artist = zing_info.get("artist", "Zing MP3 Artist")
            target_ext = req_format if req_format in ['mp3', 'flac', 'm4a', 'wav'] else 'mp3'

            download_succeeded = False
            raw_audio_file = os.path.join(job_folder, "zing_raw.mp3")

            JOBS[job_id]["status"] = f"Đang kiểm tra luồng phát Zing MP3: {track_title}..."
            JOBS[job_id]["percent"] = 15

            try:
                ydl_opts_zing = {
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(job_folder, "direct.%(ext)s"),
                    "quiet": True,
                    "no_warnings": True,
                    "ffmpeg_location": FFMPEG_EXE
                }
                with yt_dlp.YoutubeDL(ydl_opts_zing) as ydl:
                    ydl.download([url])

                f_list = [f for f in os.listdir(job_folder) if not f.endswith(('.temp', '.part', '.ytdl', '.jpg', '.png'))]
                if f_list:
                    raw_audio_file = os.path.join(job_folder, f_list[0])
                    download_succeeded = True
            except Exception as ze:
                print(f"[!] yt-dlp Zing direct download failed (VIP restriction): {ze}")
                download_succeeded = False

            if not download_succeeded:
                JOBS[job_id]["status"] = f"Đang dò tìm bản thu Studio gốc chất lượng cao: {track_title}..."
                JOBS[job_id]["percent"] = 30

                best_source_url = find_exact_spotify_audio_match(
                    track_title,
                    track_artist,
                    zing_info.get("duration", 0)
                )

                JOBS[job_id]["status"] = f"Đang tải bản thu Studio chất lượng cao: {track_title}..."
                JOBS[job_id]["percent"] = 45

                ydl_opts = apply_youtube_opts({
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(job_folder, "source.%(ext)s"),
                    "progress_hooks": [progress_hook],
                    "quiet": True,
                    "no_warnings": True,
                    "ffmpeg_location": FFMPEG_EXE
                }, is_youtube=True)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([best_source_url])

                src_files = [f for f in os.listdir(job_folder) if not f.endswith(('.temp', '.part', '.ytdl', '.jpg', '.png'))]
                if not src_files:
                    raise Exception("Không tải được bản thu âm cho bài hát Zing MP3.")
                raw_audio_file = os.path.join(job_folder, src_files[0])

            JOBS[job_id]["status"] = f"Đang xử lý âm thanh ({target_ext.upper()}) với FFmpeg..."
            JOBS[job_id]["percent"] = 85

            safe_name = format_media_filename(f"{track_title} - {track_artist}")
            final_file = os.path.join(job_folder, f"{safe_name}.{target_ext}")

            cmd = [FFMPEG_EXE or "ffmpeg", "-y", "-i", raw_audio_file]
            if target_ext == "mp3":
                cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "44100"])
            elif target_ext == "flac":
                cmd.extend(["-c:a", "flac"])
            elif target_ext == "m4a":
                cmd.extend(["-c:a", "aac", "-b:a", "256k"])
            elif target_ext == "wav":
                cmd.extend(["-c:a", "pcm_s16le"])
            cmd.append(final_file)

            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode != 0 or not os.path.exists(final_file):
                if target_ext == "mp3" and os.path.exists(raw_audio_file):
                    shutil.copy2(raw_audio_file, final_file)
                else:
                    raise Exception(f"Lỗi chuyển đổi định dạng âm thanh: {res.stderr.decode('utf-8', errors='ignore')[:200]}")

            JOBS[job_id]["status"] = "Đang gắn nhãn bản quyền & ảnh bìa HD..."
            JOBS[job_id]["percent"] = 95

            cover_bytes = None
            if zing_info.get("thumbnail"):
                try:
                    c_resp = requests.get(zing_info["thumbnail"], headers={"User-Agent": "Mozilla/5.0", "Referer": "https://zingmp3.vn/"}, timeout=10)
                    if c_resp.status_code == 200:
                        cover_bytes = c_resp.content
                except Exception as ce:
                    print(f"[!] Zing cover fetch error: {ce}")

            if target_ext == "mp3":
                try:
                    audio = ID3(final_file)
                except:
                    audio = ID3()
                audio.add(TIT2(encoding=3, text=track_title))
                audio.add(TPE1(encoding=3, text=track_artist))
                audio.add(TALB(encoding=3, text="Zing MP3"))
                if cover_bytes:
                    audio.add(APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,
                        desc='Cover',
                        data=cover_bytes
                    ))
                audio.save(final_file, v2_version=3)
            elif target_ext == "flac":
                try:
                    audio = FLAC(final_file)
                    audio["title"] = track_title
                    audio["artist"] = track_artist
                    audio["album"] = "Zing MP3"
                    if cover_bytes:
                        pic = Picture()
                        pic.type = 3
                        pic.mime = 'image/jpeg'
                        pic.desc = 'Front Cover'
                        pic.data = cover_bytes
                        audio.add_picture(pic)
                    audio.save()
                except Exception as fe:
                    print(f"[!] FLAC tag error: {fe}")

            JOBS[job_id].update({
                "percent": 100,
                "finished": True,
                "status": "Hoàn tất!",
                "filename": os.path.basename(final_file),
                "filepath": final_file,
                "download_url": f"/api/file/{job_id}"
            })
            return

        # CASE 6: TIKTOK DOWNLOAD (NO-LOGO VIDEO & HQ AUDIO)
        elif platform == "tiktok":
            tt_info = get_tiktok_info(url)
            if not tt_info:
                raise Exception("Không thể trích xuất thông tin video từ TikTok.")

            title = custom_title or tt_info.get("title", "TikTok Video")
            author = tt_info.get("author", "TikTok Creator")

            if mode == "video":
                # DOWNLOAD NO-LOGO HD VIDEO (MP4)
                safe_name = format_media_filename(f"{author} - {title}", "mp4")
                final_file = os.path.join(job_folder, safe_name)
                video_url = tt_info.get("video_url")
                dl_success = False

                if video_url:
                    JOBS[job_id]["status"] = "Đang tải video TikTok không logo (Full HD)..."
                    JOBS[job_id]["percent"] = 20
                    try:
                        v_resp = requests.get(
                            video_url,
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                            stream=True,
                            timeout=45
                        )
                        if v_resp.status_code == 200:
                            total_bytes = int(v_resp.headers.get("content-length", 0))
                            downloaded_bytes = 0
                            with open(final_file, "wb") as f_out:
                                for chunk in v_resp.iter_content(chunk_size=65536):
                                    if chunk:
                                        f_out.write(chunk)
                                        downloaded_bytes += len(chunk)
                                        if total_bytes > 0:
                                            pct = min(20 + int((downloaded_bytes / total_bytes) * 70), 92)
                                            JOBS[job_id]["percent"] = pct
                            dl_success = os.path.exists(final_file) and os.path.getsize(final_file) > 100000
                    except Exception as ve:
                        print(f"[!] TikWM video direct download failed: {ve}")
                        dl_success = False

                if not dl_success:
                    JOBS[job_id]["status"] = "Đang tải video TikTok với bộ xử lý dự phòng..."
                    JOBS[job_id]["percent"] = 35
                    ydl_opts = {
                        "format": "bestvideo+bestaudio/best",
                        "outtmpl": os.path.join(job_folder, "source.%(ext)s"),
                        "merge_output_format": "mp4",
                        "ffmpeg_location": FFMPEG_EXE,
                        "progress_hooks": [progress_hook],
                        "quiet": True,
                        "no_warnings": True
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])

                    src_files = [f for f in os.listdir(job_folder) if f.endswith(('.mp4', '.mkv', '.webm'))]
                    if not src_files:
                        raise Exception("Không tải được video TikTok.")
                    os.rename(os.path.join(job_folder, src_files[0]), final_file)

                JOBS[job_id].update({
                    "percent": 100,
                    "finished": True,
                    "status": "Hoàn tất! Video đã được xóa sạch logo watermark.",
                    "filename": os.path.basename(final_file),
                    "filepath": final_file,
                    "download_url": f"/api/file/{job_id}"
                })
                return

            else:
                # DOWNLOAD AUDIO (MP3 320k, FLAC, M4A, WAV)
                target_ext = req_format if req_format in ['mp3', 'flac', 'm4a', 'wav'] else 'mp3'
                raw_audio_file = os.path.join(job_folder, "tiktok_raw_audio.mp3")
                dl_success = False
                audio_url = tt_info.get("audio_url")

                if audio_url:
                    JOBS[job_id]["status"] = f"Đang tải luồng âm thanh gốc TikTok: {title}..."
                    JOBS[job_id]["percent"] = 25
                    try:
                        a_resp = requests.get(
                            audio_url,
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                            stream=True,
                            timeout=30
                        )
                        if a_resp.status_code == 200:
                            with open(raw_audio_file, "wb") as f_out:
                                for chunk in a_resp.iter_content(chunk_size=32768):
                                    if chunk:
                                        f_out.write(chunk)
                            dl_success = os.path.exists(raw_audio_file) and os.path.getsize(raw_audio_file) > 10000
                    except Exception as ae:
                        print(f"[!] TikWM audio direct download failed: {ae}")
                        dl_success = False

                if not dl_success:
                    video_url = tt_info.get("video_url")
                    if video_url:
                        temp_vid = os.path.join(job_folder, "temp_vid.mp4")
                        try:
                            v_resp = requests.get(video_url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=30)
                            if v_resp.status_code == 200:
                                with open(temp_vid, "wb") as f_v:
                                    for chk in v_resp.iter_content(chunk_size=65536):
                                        if chk:
                                            f_v.write(chk)
                                raw_audio_file = temp_vid
                                dl_success = True
                        except Exception:
                            dl_success = False

                if not dl_success:
                    JOBS[job_id]["status"] = "Đang trích xuất âm thanh TikTok với bộ xử lý dự phòng..."
                    JOBS[job_id]["percent"] = 40
                    ydl_opts = {
                        "format": "bestaudio/best",
                        "outtmpl": os.path.join(job_folder, "source.%(ext)s"),
                        "ffmpeg_location": FFMPEG_EXE,
                        "progress_hooks": [progress_hook],
                        "quiet": True,
                        "no_warnings": True
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    src_files = [f for f in os.listdir(job_folder) if not f.endswith(('.temp', '.part', '.ytdl', '.jpg', '.png'))]
                    if not src_files:
                        raise Exception("Không trích xuất được âm thanh từ TikTok.")
                    raw_audio_file = os.path.join(job_folder, src_files[0])

                # Convert using FFmpeg
                JOBS[job_id]["status"] = f"Đang xử lý âm thanh ({target_ext.upper()}) chuẩn Studio với FFmpeg..."
                JOBS[job_id]["percent"] = 80

                safe_name = format_media_filename(f"{author} - {title}", target_ext)
                final_file = os.path.join(job_folder, safe_name)

                cmd = [FFMPEG_EXE or "ffmpeg", "-y", "-i", raw_audio_file]
                if target_ext == "mp3":
                    cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "44100"])
                elif target_ext == "flac":
                    cmd.extend(["-c:a", "flac"])
                elif target_ext == "m4a":
                    cmd.extend(["-c:a", "aac", "-b:a", "256k"])
                elif target_ext == "wav":
                    cmd.extend(["-c:a", "pcm_s16le"])
                cmd.append(final_file)

                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode != 0 or not os.path.exists(final_file):
                    if target_ext == "mp3" and os.path.exists(raw_audio_file) and raw_audio_file.endswith(".mp3"):
                        shutil.copy2(raw_audio_file, final_file)
                    else:
                        raise Exception(f"Lỗi chuyển đổi âm thanh FFmpeg: {res.stderr.decode('utf-8', errors='ignore')[:200]}")

                # Cover Art & Metadata
                JOBS[job_id]["status"] = "Đang gắn nhãn bản quyền & ảnh bìa TikTok..."
                JOBS[job_id]["percent"] = 95

                cover_bytes = None
                if tt_info.get("thumbnail"):
                    try:
                        c_resp = requests.get(tt_info["thumbnail"], headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                        if c_resp.status_code == 200:
                            cover_bytes = c_resp.content
                    except Exception as ce:
                        print(f"[!] TikTok cover fetch error: {ce}")

                if target_ext == "mp3":
                    try:
                        audio = ID3(final_file)
                    except:
                        audio = ID3()
                    audio.add(TIT2(encoding=3, text=title))
                    audio.add(TPE1(encoding=3, text=author))
                    audio.add(TALB(encoding=3, text="TikTok Audio"))
                    if cover_bytes:
                        audio.add(APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,
                            desc='Cover',
                            data=cover_bytes
                        ))
                    audio.save(final_file, v2_version=3)
                elif target_ext == "flac":
                    try:
                        audio = FLAC(final_file)
                        audio["title"] = title
                        audio["artist"] = author
                        audio["album"] = "TikTok Audio"
                        if cover_bytes:
                            pic = Picture()
                            pic.type = 3
                            pic.mime = 'image/jpeg'
                            pic.desc = 'Front Cover'
                            pic.data = cover_bytes
                            audio.add_picture(pic)
                        audio.save()
                    except Exception as fe:
                        print(f"[!] TikTok FLAC tag error: {fe}")
                elif target_ext == "m4a":
                    try:
                        audio = MP4(final_file)
                        audio["\xa9nam"] = title
                        audio["\xa9ART"] = author
                        audio["\xa9alb"] = "TikTok Audio"
                        if cover_bytes:
                            audio["covr"] = [MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
                        audio.save()
                    except Exception as me:
                        print(f"[!] TikTok M4A tag error: {me}")

                JOBS[job_id].update({
                    "percent": 100,
                    "finished": True,
                    "status": "Hoàn tất! Đã trích xuất âm thanh chất lượng cao.",
                    "filename": os.path.basename(final_file),
                    "filepath": final_file,
                    "download_url": f"/api/file/{job_id}"
                })
                return

        # CASE 2: YOUTUBE DOWNLOAD (VIDEO OR AUDIO)
        elif platform == "youtube":
            out_template = os.path.join(job_folder, "QuocTinMedia - %(title)s.%(ext)s")

            ydl_opts = apply_youtube_opts({
                "outtmpl": out_template,
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": True,
                "ffmpeg_location": FFMPEG_EXE
            }, is_youtube=True)

            if mode == "audio":
                ydl_opts["format"] = "bestaudio/best"
                
                if req_format == "original":
                    pass
                elif req_format == "flac":
                    ydl_opts["postprocessors"] = [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "flac"
                    }, {
                        "key": "FFmpegMetadata",
                        "add_metadata": True
                    }]
                elif req_format == "wav":
                    ydl_opts["postprocessors"] = [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "wav"
                    }]
                elif req_format == "m4a":
                    ydl_opts["postprocessors"] = [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "m4a",
                        "preferredquality": "256"
                    }, {
                        "key": "FFmpegMetadata",
                        "add_metadata": True
                    }]
                else: # Default: MP3 320kbps Studio Master
                    ydl_opts["writethumbnail"] = True
                    ydl_opts["postprocessors"] = [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "320" # 320kbps CBR
                        },
                        {
                            "key": "FFmpegMetadata",
                            "add_metadata": True
                        },
                        {
                            "key": "EmbedThumbnail",
                            "already_have_thumbnail": False
                        }
                    ]

            elif mode == "video":
                height = 1080
                if quality == "2160":
                    height = 2160
                elif quality == "1440":
                    height = 1440
                elif quality == "720":
                    height = 720

                ydl_opts["format"] = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
                ydl_opts["merge_output_format"] = "mp4"
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegMetadata",
                    "add_metadata": True
                }]

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as dl_err:
                err_msg = str(dl_err).lower()
                if "not a bot" in err_msg or "sign in" in err_msg or "format is not available" in err_msg:
                    print(f"[*] Retrying YouTube download with alternative mobile clients...")
                    retry_opts = dict(ydl_opts)
                    retry_opts = apply_youtube_opts(retry_opts, is_youtube=True, clients=["android", "ios"])
                    with yt_dlp.YoutubeDL(retry_opts) as ydl_retry:
                        ydl_retry.download([url])
                else:
                    raise dl_err

            files = [f for f in os.listdir(job_folder) if not f.endswith(('.temp', '.part', '.ytdl'))]
            if not files:
                raise Exception("Không tìm thấy file sau khi tải.")

            media_files = [f for f in files if f.endswith(('.mp3', '.flac', '.wav', '.m4a', '.opus', '.mp4', '.webm', '.mkv'))]
            final_file = os.path.join(job_folder, media_files[0] if media_files else files[0])
            base_name = os.path.basename(final_file)
            if not base_name.lower().startswith("quoctinmedia"):
                target_name = f"QuocTinMedia - {base_name}"
                target_path = os.path.join(job_folder, target_name)
                try:
                    os.rename(final_file, target_path)
                    final_file = target_path
                except Exception:
                    pass

            JOBS[job_id].update({
                "percent": 100,
                "finished": True,
                "status": "Hoàn tất!",
                "filename": os.path.basename(final_file),
                "filepath": final_file,
                "download_url": f"/api/file/{job_id}"
            })

    except Exception as e:
        print(f"[!] Job {job_id} error: {e}")
        JOBS[job_id].update({
            "error": str(e),
            "finished": False,
            "status": f"Lỗi: {str(e)}"
        })

@app.route("/api/thumbnail/download", methods=["GET", "POST"])
def download_thumbnail_file():
    if request.method == "POST":
        data = request.get_json() or {}
        img_url = data.get("url", "").strip()
        title = data.get("title", "thumbnail").strip()
        fmt = data.get("format", "jpg").lower()
    else:
        img_url = request.args.get("url", "").strip()
        title = request.args.get("title", "thumbnail").strip()
        fmt = request.args.get("format", "jpg").lower()

    if not img_url:
        return jsonify({"success": False, "error": "Thiếu đường dẫn hình ảnh!"}), 400

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if "nct.vn" in img_url:
        headers["Referer"] = "https://www.nhaccuatui.com/"
    elif any(d in img_url for d in ["zadn.vn", "zmdcdn.me", "zingmp3"]):
        headers["Referer"] = "https://zingmp3.vn/"
    elif any(d in img_url for d in ["tiktokcdn.com", "byteoversea.com", "ibytedtos.com", "tikwm.com"]):
        headers["Referer"] = "https://www.tiktok.com/"

    try:
        resp = requests.get(img_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return jsonify({"success": False, "error": f"Không thể tải ảnh từ nguồn (Mã lỗi {resp.status_code})"}), 400

        content_bytes = resp.content
        safe_name = sanitize_filename(title) if title else "thumbnail"
        if not safe_name:
            safe_name = "thumbnail"

        if fmt == "original":
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            ext = "jpg"
            if "webp" in content_type:
                ext = "webp"
            elif "png" in content_type:
                ext = "png"
            elif img_url.endswith(".png"):
                ext = "png"
            elif img_url.endswith(".webp"):
                ext = "webp"

            return send_file(
                io.BytesIO(content_bytes),
                mimetype=content_type,
                as_attachment=True,
                download_name=format_media_filename(f"{safe_name}_thumbnail", ext)
            )

        img = Image.open(io.BytesIO(content_bytes))
        out_io = io.BytesIO()

        if fmt == "png":
            img.save(out_io, format="PNG")
            out_io.seek(0)
            return send_file(
                out_io,
                mimetype="image/png",
                as_attachment=True,
                download_name=format_media_filename(f"{safe_name}_thumbnail", "png")
            )
        else: # Default JPG
            if img.mode in ("RGBA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    bg.paste(img, mask=img.split()[3])
                else:
                    bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
                bg.save(out_io, format="JPEG", quality=95)
            else:
                img.convert("RGB").save(out_io, format="JPEG", quality=95)
            out_io.seek(0)
            return send_file(
                out_io,
                mimetype="image/jpeg",
                as_attachment=True,
                download_name=format_media_filename(f"{safe_name}_thumbnail", "jpg")
            )

    except Exception as e:
        print(f"[!] Error downloading thumbnail: {e}")
        return jsonify({"success": False, "error": f"Lỗi xử lý ảnh: {str(e)}"}), 500

@app.route("/api/karaoke/upload", methods=["POST"])
def upload_karaoke_audio():
    if "audiofile" not in request.files:
        return jsonify({"success": False, "error": "Chưa chọn file âm thanh!"}), 400
    file = request.files["audiofile"]
    if file.filename == "":
        return jsonify({"success": False, "error": "Tên file rỗng!"}), 400

    file_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(file.filename)[1].lower()
    if not ext:
        ext = ".mp3"
    save_filename = f"{file_id}{ext}"
    save_path = os.path.join(UPLOAD_DIR, save_filename)
    file.save(save_path)

    size_mb = os.path.getsize(save_path) / (1024 * 1024)

    return jsonify({
        "success": True,
        "uploaded_file_id": save_filename,
        "original_filename": file.filename,
        "size_str": f"{size_mb:.1f} MB"
    })

@app.route("/api/download", methods=["POST"])
def start_download():
    payload = request.get_json() or {}
    url = payload.get("url", "").strip()
    uploaded_file_id = payload.get("uploaded_file_id")

    if not url and not uploaded_file_id:
        return jsonify({"success": False, "error": "Vui lòng nhập URL hoặc tải lên file âm thanh!"}), 400

    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "Đang kết nối...",
            "percent": 5,
            "speed": "0 KB/s",
            "eta": "Đang tính toán...",
            "finished": False,
            "error": None,
            "filename": None,
            "filepath": None,
            "stems": [],
            "is_karaoke": False,
            "created_at": time.time()
        }

    thread = threading.Thread(target=download_worker, args=(job_id, payload), daemon=True)
    thread.start()

    return jsonify({"success": True, "job_id": job_id})

@app.route("/api/progress")
def get_progress():
    job_id = request.args.get("job_id", "")
    with JOBS_LOCK:
        job = JOBS.get(job_id)

    if not job:
        return jsonify({"success": False, "error": "Không tìm thấy tác vụ tải."}), 404

    if job.get("error"):
        return jsonify({"success": False, "error": job["error"]})

    return jsonify({
        "success": True,
        "percent": job["percent"],
        "status": job["status"],
        "speed": job["speed"],
        "eta": job["eta"],
        "finished": job["finished"],
        "download_url": job.get("download_url"),
        "filename": job.get("filename"),
        "stems": job.get("stems", []),
        "is_karaoke": job.get("is_karaoke", False)
    })

@app.route("/api/file/<job_id>")
def download_file(job_id):
    stem = request.args.get("stem")
    job_folder = os.path.join(DOWNLOAD_DIR, job_id)

    if stem:
        safe_stem = os.path.basename(stem)
        target_path = os.path.join(job_folder, safe_stem)
        if os.path.exists(target_path):
            stem_dl = safe_stem
            if not stem_dl.lower().startswith("quoctinmedia"):
                stem_dl = f"QuocTinMedia - {stem_dl}"
            return send_file(target_path, as_attachment=True, download_name=stem_dl)

    with JOBS_LOCK:
        job = JOBS.get(job_id)

    if not job or not job.get("filepath") or not os.path.exists(job["filepath"]):
        return jsonify({"error": "File không tồn tại hoặc đã bị xóa."}), 404

    dl_name = job.get("filename") or os.path.basename(job["filepath"])
    if not dl_name.lower().startswith("quoctinmedia"):
        dl_name = f"QuocTinMedia - {dl_name}"

    return send_file(
        job["filepath"],
        as_attachment=True,
        download_name=dl_name
    )

if __name__ == "__main__":
    import socket
    local_ip = "127.0.0.1"
    try:
        temp_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_s.connect(('8.8.8.8', 80))
        local_ip = temp_s.getsockname()[0]
        temp_s.close()
    except Exception:
        pass

    PORT = int(os.environ.get("PORT", 5500))
    print("=====================================================")
    print("  OmniMedia Pro - YouTube & Spotify Downloader")
    print(f"  PC Local:     http://localhost:{PORT}")
    print(f"  PC Local:     http://127.0.0.1:{PORT}")
    print(f"  Điện thoại:   http://{local_ip}:{PORT} (cùng mạng Wi-Fi)")
    print("  Audio: MP3 320kbps / FLAC / Opus Lossless")
    print("  Video: MP4 4K / 2K / 1080p Full HD")
    print("=====================================================")
    from werkzeug.serving import make_server
    try:
        # Dual-stack socket (binds both IPv4 and IPv6 on Windows)
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        s.bind(('::', PORT))
        s.listen(128)
        server = make_server('::', PORT, app, fd=s.fileno(), threaded=True)
        print(f"[*] Server running with Dual-Stack on port {PORT} (IPv4 + IPv6 localhost)")
        server.serve_forever()
    except Exception as e:
        print(f"[!] Dual-stack fallback: {e}")
        app.run(host="0.0.0.0", port=PORT, threaded=True)
