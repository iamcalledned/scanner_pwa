from flask import Blueprint, jsonify, send_from_directory, abort
from pathlib import Path
import json

api_scanner_bp = Blueprint("api_scanner", __name__)
ARCHIVE_DIR = "/home/ned/scanner_archive/clean"

@api_scanner_bp.route("/api/calls")
def list_calls():
    calls = []
    for wav in sorted(Path(ARCHIVE_DIR).glob("*.wav"), reverse=True):
        base = wav.stem
        json_path = wav.with_suffix(".json")
        call_id = base.replace("rec_", "")
        entry = {
            "id": call_id,
            "audio": f"/api/audio/{wav.name}",
            "transcript": f"/api/call/{call_id}",
            "filename": wav.name,
        }
        if json_path.exists():
            try:
                with open(json_path) as f:
                    meta = json.load(f)
                    entry.update(meta)
            except:
                pass
        calls.append(entry)
    return jsonify(calls)

@api_scanner_bp.route("/api/call/<call_id>")
def get_call_details(call_id):
    base = f"rec_{call_id}"
    wav = Path(ARCHIVE_DIR) / f"{base}.wav"
    txt = Path(ARCHIVE_DIR) / f"{base}.txt"
    json_path = Path(ARCHIVE_DIR) / f"{base}.json"

    if not wav.exists():
        return abort(404, description="Call not found")

    data = {
        "id": call_id,
        "audio": f"/api/audio/{wav.name}",
        "filename": wav.name,
        "transcript": "",
        "metadata": {}
    }

    if txt.exists():
        data["transcript"] = txt.read_text()
    if json_path.exists():
        try:
            data["metadata"] = json.loads(json_path.read_text())
        except:
            pass

    return jsonify(data)

@api_scanner_bp.route("/api/audio/<filename>")
def get_audio(filename):
    file_path = Path(ARCHIVE_DIR) / filename
    if not file_path.exists():
        abort(404)
    return send_from_directory(ARCHIVE_DIR, filename)
