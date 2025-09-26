from flask import Blueprint, render_template, send_from_directory, request, jsonify
from pathlib import Path
import datetime

scanner_bp = Blueprint("scanner", __name__)
ARCHIVE_DIR = "/home/ned/scanner_archive/clean"
CALLS_PER_PAGE = 10

@scanner_bp.route("/scanner")
def scanner_list():
    today = datetime.date.today()
    calls = []
    for wav in sorted(Path(ARCHIVE_DIR).glob("*.wav"), reverse=True):
        base = wav.stem
        txt = wav.with_suffix(".txt")
        # Extract date from filename: expects format rec_YYYY-MM-DD_HH-MM-SS
        try:
            date_str = base.split("_")[1]
            call_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            call_date = None
        if call_date == today:
            timestamp = base.replace("rec_", "").replace("_", " ")
            data = {
                "file": wav.name,
                "path": f"/scanner/audio/{wav.name}",
                "transcript": txt.read_text() if txt.exists() else "(no transcript)",
                "timestamp": timestamp,
                "timestamp_human": None
            }
            # Try to parse timestamp for human readable
            try:
                # expects rec_YYYY-MM-DD_HH-MM-SS
                dt_str = base.replace("rec_", "")
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d_%H-%M-%S")
                data["timestamp_human"] = dt.strftime("%b %d, %I:%M %p")
            except Exception:
                data["timestamp_human"] = timestamp
            calls.append(data)
    # Pagination
    page = int(request.args.get("page", 1))
    start = (page - 1) * CALLS_PER_PAGE
    end = start + CALLS_PER_PAGE
    if request.headers.get("Accept") == "application/json" or request.args.get("json") == "1":
        return jsonify({"calls": calls[start:end]})
    return render_template("scanner.html", calls=calls[:CALLS_PER_PAGE])

@scanner_bp.route("/scanner/archive")
def scanner_archive():
    archive = {}
    for wav in sorted(Path(ARCHIVE_DIR).glob("*.wav"), reverse=True):
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
            dt_str = base.replace("rec_", "")
            dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d_%H-%M-%S")
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

    # Sort days descending
    sorted_archive = dict(sorted(archive.items(), reverse=True))

    # Return JSON for pagination (load more)
    if request.headers.get("Accept") == "application/json" or request.args.get("json") == "1":
        day = request.args.get("day")
        page = int(request.args.get("page", 1))
        if day and day in sorted_archive:
            calls = sorted_archive[day]
            start = (page - 1) * CALLS_PER_PAGE
            end = start + CALLS_PER_PAGE
            return jsonify({
                "calls": calls[start:end],
                "total": len(calls)
            })
        return jsonify({"error": "Invalid day"}), 400

    # For initial HTML render: show total count, but limit output to 10 calls per day
    archive_render = {}
    call_totals = {}
    for day, call_list in sorted_archive.items():
        call_totals[day] = len(call_list)                 # Full count
        archive_render[day] = call_list[:CALLS_PER_PAGE]  # First 10 only

    return render_template(
        "scanner_archive.html",
        archive=archive_render,
        calls_per_page=CALLS_PER_PAGE,
        call_totals=call_totals
    )


@scanner_bp.route("/scanner/audio/<filename>")
def scanner_audio(filename):
    return send_from_directory(ARCHIVE_DIR, filename)
