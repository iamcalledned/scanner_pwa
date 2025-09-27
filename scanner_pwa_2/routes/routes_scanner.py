from flask import Blueprint, render_template, send_from_directory, request, jsonify, redirect
from pathlib import Path
import datetime
import json
from collections import defaultdict
from werkzeug.utils import secure_filename
import shutil
import os
import time
import threading
import uuid
import requests

scanner_bp = Blueprint("scanner", __name__)
LOGIN_PROCESS_URL = os.environ.get('LOGIN_PROCESS_URL', 'http://127.0.0.1:8010/api/login')
LOGIN_API_URL = os.environ.get('LOGIN_API_URL', 'http://127.0.0.1:8010')
ARCHIVE_DIR = "/home/ned/scanner_archive/clean"
PD_DIR = Path("/home/ned/scanner_archive/clean/pd")
REVIEW_DIR = Path("/home/ned/scanner_archive/review")
SEGMENT_DIR = Path("/home/ned/scanner_archive/segmentation/processed")
CALLS_PER_PAGE = 10

# Simple in-memory active user registry. Key: client_id -> {last_seen, ip, ua, page}
ACTIVE_USERS = {}
ACTIVE_LOCK = threading.Lock()
ACTIVE_TIMEOUT = 120  # seconds considered "active"



def load_calls(directory, feed="pd", filter_today=False):
    calls = []
    today = datetime.date.today()

    for wav in sorted(Path(directory).glob("*.wav"), reverse=True):
        base = wav.stem
        txt = wav.with_suffix(".txt")
        json_path = wav.with_suffix(".json")

        try:
            date_str = base.split("_")[1]
            call_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            call_date = None

        if filter_today and call_date != today:
            continue

        timestamp = base.replace("rec_", "").replace("_", " ")
        try:
            dt = datetime.datetime.strptime(base.replace("rec_", ""), "%Y-%m-%d_%H-%M-%S")
            timestamp_human = dt.strftime("%b %d, %I:%M %p")
        except Exception:
            timestamp_human = timestamp

        transcript = "(no transcript)"
        edit_pending = False
        edited_transcript = ""

        if json_path.exists():
            try:
                with open(json_path) as f:
                    data = json.load(f)

                if data.get("edited") and data.get("edited_transcript"):
                    transcript = data["edited_transcript"]
                    edit_pending = False
                elif "edited_transcript" in data:
                    transcript = data["edited_transcript"]
                    edit_pending = True
                else:
                    transcript = data.get("transcript", transcript)

                calls.append({
                    "file": wav.name,
                    "path": f"/scanner/audio/{wav.name}",
                    "transcript": data.get("transcript", transcript),
                    "edited_transcript": data.get("edited_transcript", ""),
                    "enhanced_transcript": data.get("enhanced_transcript", ""),
                    "edit_pending": edit_pending,
                    "timestamp": timestamp,
                    "timestamp_human": timestamp_human,
                    "feed": feed,
                    "metadata": data
                })
            except Exception as e:
                print(f"[!] Failed to load JSON for {base}: {e}")

    return calls


def load_archive(directory):
    archive = {}
    for wav in sorted(Path(directory).glob("*.wav"), reverse=True):
        base = wav.stem
        txt = wav.with_suffix(".txt")
        try:
            date_str = base.split("_")[1]
            call_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            day_key = call_date.strftime("%Y-%m-%d")
        except Exception:
            day_key = "unknown"

        timestamp = base.replace("rec_", "").replace("_", " ")
        try:
            dt = datetime.datetime.strptime(base.replace("rec_", ""), "%Y-%m-%d_%H-%M-%S")
            timestamp_human = dt.strftime("%b %d, %I:%M %p")
        except Exception:
            timestamp_human = timestamp

        data = {
            "file": wav.name,
            "path": f"/scanner/audio/{wav.name}",
            "transcript": txt.read_text() if txt.exists() else "(no transcript)",
            "timestamp": timestamp,
            "timestamp_human": timestamp_human
        }
        archive.setdefault(day_key, []).append(data)
    return dict(sorted(archive.items(), reverse=True))


@scanner_bp.route("/scanner/segments")
def scanner_segments():
    calls = []
    for wav in sorted(SEGMENT_DIR.glob("*.wav"), reverse=True):
        base = wav.stem
        json_path = wav.with_suffix(".json")
        transcript = "(no transcript)"
        speaker = ""
        timestamp_human = wav.stem.replace("_", " ")

        if json_path.exists():
            try:
                with open(json_path) as f:
                    data = json.load(f)
                transcript = data.get("transcript", transcript)
                speaker = data.get("speaker", "")
                timestamp_human = datetime.datetime.fromisoformat(data.get("timestamp")).strftime("%b %d, %I:%M %p")
            except Exception:
                pass

        calls.append({
            "file": wav.name,
            "path": f"/scanner/audio/{wav.name}",
            "transcript": transcript,
            "timestamp_human": timestamp_human,
            "speaker": speaker
        })

    return render_template("scanner_segments.html", calls=calls)

@scanner_bp.route("/scanner_pd")
def scanner_pd():
    calls = load_calls(f"{ARCHIVE_DIR}/pd", filter_today=True)
    page = int(request.args.get("page", 1))
    start = (page - 1) * CALLS_PER_PAGE
    end = start + CALLS_PER_PAGE
    if request.headers.get("Accept") == "application/json":
        return jsonify({"calls": calls[start:end]})
    return render_template("scanner_pd.html", calls=calls[:CALLS_PER_PAGE])


@scanner_bp.route("/scanner_fire")
def scanner_fire():
    calls = load_calls(f"{ARCHIVE_DIR}/fd", feed="fd", filter_today=True)
    page = int(request.args.get("page", 1))
    start = (page - 1) * CALLS_PER_PAGE
    end = start + CALLS_PER_PAGE
    if request.headers.get("Accept") == "application/json":
        return jsonify({"calls": calls[start:end]})
    return render_template("scanner_fire.html", calls=calls[:CALLS_PER_PAGE])


# Backwards-compatible aliases: some links use /scanner_fd — keep working
@scanner_bp.route("/scanner_fd")
def scanner_fd():
    # Delegate to the existing scanner_fire handler
    return scanner_fire()


@scanner_bp.route("/scanner")
def scanner_list():
    calls = load_calls(f"{ARCHIVE_DIR}/pd", filter_today=True)
    page = int(request.args.get("page", 1))
    start = (page - 1) * CALLS_PER_PAGE
    end = start + CALLS_PER_PAGE
    if request.headers.get("Accept") == "application/json" or request.args.get("json") == "1":
        return jsonify({"calls": calls[start:end]})
    return render_template("scanner.html", calls=calls[:CALLS_PER_PAGE])


# Accept trailing slash as well so `/scanner/` doesn't 404.
@scanner_bp.route("/scanner/")
def scanner_list_slash():
    return scanner_list()


@scanner_bp.route("/scanner/archive")
def scanner_archive():
    sorted_archive = load_archive(f"{ARCHIVE_DIR}/pd")
    if request.headers.get("Accept") == "application/json" or request.args.get("json") == "1":
        day = request.args.get("day")
        page = int(request.args.get("page", 1))
        if day and day in sorted_archive:
            calls = sorted_archive[day]
            start = (page - 1) * CALLS_PER_PAGE
            end = start + CALLS_PER_PAGE
            return jsonify({"calls": calls[start:end], "total": len(calls)})
        return jsonify({"error": "Invalid day"}), 400

    archive_render = {}
    call_totals = {}
    for day, call_list in sorted_archive.items():
        call_totals[day] = len(call_list)
        archive_render[day] = call_list[:CALLS_PER_PAGE]

    return render_template(
        "scanner_archive.html",
        archive=archive_render,
        calls_per_page=CALLS_PER_PAGE,
        call_totals=call_totals
    )


@scanner_bp.route("/scanner_fire/archive")
def scanner_fire_archive():
    sorted_archive = load_archive(f"{ARCHIVE_DIR}/fd")
    if request.headers.get("Accept") == "application/json" or request.args.get("json") == "1":
        day = request.args.get("day")
        page = int(request.args.get("page", 1))
        if day and day in sorted_archive:
            calls = sorted_archive[day]
            start = (page - 1) * CALLS_PER_PAGE
            end = start + CALLS_PER_PAGE
            return jsonify({"calls": calls[start:end], "total": len(calls)})
        return jsonify({"error": "Invalid day"}), 400

    archive_render = {}
    call_totals = {}
    for day, call_list in sorted_archive.items():
        call_totals[day] = len(call_list)
        archive_render[day] = call_list[:CALLS_PER_PAGE]

    return render_template(
        "scanner_archive.html",
        archive=archive_render,
        calls_per_page=CALLS_PER_PAGE,
        call_totals=call_totals
    )


@scanner_bp.route("/scanner/audio/<filename>")
def scanner_audio(filename):
    search_paths = [
        Path("/home/ned/scanner_archive/clean/pd"),
        Path("/home/ned/scanner_archive/clean/fd"),
        Path("/home/ned/scanner_archive/segmentation/processed")
    ]

    for path in search_paths:
        file_path = path / filename
        if file_path.exists():
            return send_from_directory(path, filename)

    return "File not found", 404


@scanner_bp.route("/scanner/submit_edit", methods=["POST"])
def submit_edit():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    raw_filename = data.get("filename")
    if not raw_filename:
        return jsonify({"success": False, "error": "Filename required"}), 400

    filename = secure_filename(raw_filename)
    if not filename.endswith(".wav"):
        return jsonify({"success": False, "error": "Invalid file type"}), 400

    new_transcript = data.get("transcript", "").strip()
    feed = data.get("feed", "pd")

    src_dir = Path(f"/home/ned/scanner_archive/clean/{feed}")
    src_wav = src_dir / filename
    src_json = src_wav.with_suffix(".json")

    if not src_wav.exists() or not src_json.exists():
        return jsonify({"success": False, "error": "Source file missing"}), 404

    try:
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        dst_wav = REVIEW_DIR / src_wav.name
        shutil.copy2(src_wav, dst_wav)
        with open(src_json) as f:
            meta = json.load(f)
        meta["edited_transcript"] = new_transcript
        dst_json = REVIEW_DIR / src_json.name
        with open(dst_json, "w") as f:
            json.dump(meta, f, indent=2)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@scanner_bp.route('/scanner/_heartbeat', methods=['POST'])
def scanner_heartbeat():
    """Receive periodic heartbeats from clients to mark them active."""
    data = request.get_json(silent=True) or {}
    client_id = data.get('client_id') or str(uuid.uuid4())
    page = data.get('page', '')
    ua = request.headers.get('User-Agent', '')
    now = time.time()
    with ACTIVE_LOCK:
        ACTIVE_USERS[client_id] = {
            'last_seen': now,
            'ip': request.remote_addr,
            'ua': ua,
            'page': page,
        }
    return jsonify({'success': True, 'client_id': client_id})



@scanner_bp.route('/scanner/login')
def scanner_login():
    """Redirect to the external login process (FastAPI Cognito flow).

    The external login process should handle the auth code flow and redirect
    back to your app's redirect URI. The default `LOGIN_PROCESS_URL` points to
    the FastAPI login endpoint in your other project. Configure via
    environment variable `LOGIN_PROCESS_URL`.
    """
    return redirect(LOGIN_PROCESS_URL)


@scanner_bp.route('/scanner/admin/active')
def scanner_active():
    """Return currently active clients seen within ACTIVE_TIMEOUT seconds."""
    cutoff = time.time() - ACTIVE_TIMEOUT
    with ACTIVE_LOCK:
        # remove stale entries to keep memory small
        stale = [k for k, v in ACTIVE_USERS.items() if v['last_seen'] < cutoff]
        for k in stale:
            del ACTIVE_USERS[k]
        active = [
            {
                'client_id': k,
                'ip': v['ip'],
                'ua': v['ua'],
                'page': v.get('page', ''),
                'last_seen': v['last_seen']
            }
            for k, v in ACTIVE_USERS.items()
        ]
    return jsonify({'active_count': len(active), 'active': active})


@scanner_bp.route("/api/pd_heatmap")
def pd_heatmap():
    now = datetime.datetime.now()
    start = now - datetime.timedelta(days=6)
    heatmap = defaultdict(lambda: [0] * 24)

    for file in PD_DIR.glob("*.json"):
        try:
            with open(file) as f:
                meta = json.load(f)
            ts = meta.get("timestamp")
            if not ts:
                continue
            dt = datetime.datetime.fromisoformat(ts)
            if dt < start:
                continue
            date_key = dt.strftime("%Y-%m-%d")
            heatmap[date_key][dt.hour] += 1
        except Exception:
            continue

    sorted_days = sorted(heatmap.keys())
    matrix = [heatmap[day] for day in sorted_days]

    return jsonify({"days": sorted_days, "data": matrix})

@scanner_bp.route("/scanner/submit_segment_label", methods=["POST"])
def submit_segment_label():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    filename = data.get("filename")
    speaker = data.get("speaker")
    label = data.get("label", "").strip()

    if not filename or not speaker:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    json_path = SEGMENT_DIR / filename
    if json_path.suffix != ".wav":
        return jsonify({"success": False, "error": "Invalid file type"}), 400

    json_file = json_path.with_suffix(".json")
    if not json_file.exists():
        return jsonify({"success": False, "error": "Metadata JSON not found"}), 404

    try:
        with open(json_file) as f:
            meta = json.load(f)

        meta["speaker_role"] = speaker  # e.g., "dispatcher" or "officer"
        if label:
            meta["speaker_label"] = label  # e.g., "303", "Control", etc.

        with open(json_file, "w") as f:
            json.dump(meta, f, indent=2)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@scanner_bp.route('/scanner/callback')
def scanner_callback():
    """Accept the session_id from the login process, save to localStorage, and redirect."""
    session_id = request.args.get('session_id')
    return_to = request.args.get('return_to', '/scanner')
    if not session_id:
        return "Error: session_id missing", 400

    return render_template("callback.html", session_id=session_id, return_to=return_to)


@scanner_bp.route('/scanner/me')
def scanner_me():
    """Check the validity of a session_id and return user info."""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({"error": "Authorization header missing"}), 401

    # The frontend sends "Authorization: <session_id>"
    session_id = auth_header

    try:
        # Call the login service to get session data
        response = requests.get(f"{LOGIN_API_URL}/get_session_data", params={"session_id": session_id})
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        if data and data.get("userInfo"):
            return jsonify({"userInfo": data["userInfo"]})
        else:
            return jsonify({"error": "Invalid session"}), 401
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Could not contact login service: {e}")
        return jsonify({"error": "Could not validate session"}), 502


@scanner_bp.route('/scanner/logout', methods=['POST'])
def scanner_logout():
    """Logout by calling the login service's logout endpoint."""
    data = request.get_json()
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({"error": "session_id missing"}), 400

    try:
        response = requests.post(f"{LOGIN_API_URL}/api/logout", json={"session_id": session_id})
        response.raise_for_status()
        return jsonify({"message": "Logout successful"})
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Could not contact login service for logout: {e}")
        return jsonify({"error": "Logout failed"}), 502

