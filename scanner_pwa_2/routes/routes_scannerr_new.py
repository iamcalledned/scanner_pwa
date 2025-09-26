from flask import Blueprint, render_template, send_from_directory, request, jsonify
from pathlib import Path
import datetime

scanner_bp = Blueprint("scanner", __name__)
ARCHIVE_DIR = "/home/ned/scanner_archive/clean"
CALLS_PER_PAGE = 10

def load_calls(directory, filter_today=False):
    calls = []
    today = datetime.date.today()
    for wav in sorted(Path(directory).glob("*.wav"), reverse=True):
        base = wav.stem
        txt = wav.with_suffix(".txt")
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

        calls.append({
            "file": wav.name,
            "path": f"/scanner/audio/{wav.name}",
            "transcript": txt.read_text() if txt.exists() else "(no transcript)",
            "timestamp": timestamp,
            "timestamp_human": timestamp_human
        })
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
    calls = load_calls(f"{ARCHIVE_DIR}/fire", filter_today=True)
    page = int(request.args.get("page", 1))
    start = (page - 1) * CALLS_PER_PAGE
    end = start + CALLS_PER_PAGE
    if request.headers.get("Accept") == "application/json":
        return jsonify({"calls": calls[start:end]})
    return render_template("scanner_fire.html", calls=calls[:CALLS_PER_PAGE])

@scanner_bp.route("/scanner")
def scanner_list():
    calls = load_calls(f"{ARCHIVE_DIR}/pd", filter_today=True)  # legacy default to PD
    page = int(request.args.get("page", 1))
    start = (page - 1) * CALLS_PER_PAGE
    end = start + CALLS_PER_PAGE
    if request.headers.get("Accept") == "application/json" or request.args.get("json") == "1":
        return jsonify({"calls": calls[start:end]})
    return render_template("scanner.html", calls=calls[:CALLS_PER_PAGE])

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
    sorted_archive = load_archive(f"{ARCHIVE_DIR}/fire")
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
    for sub in ["pd", "fire"]:
        file_path = Path(f"{ARCHIVE_DIR}/{sub}/{filename}")
        if file_path.exists():
            return send_from_directory(file_path.parent, file_path.name)
    return "File not found", 404
