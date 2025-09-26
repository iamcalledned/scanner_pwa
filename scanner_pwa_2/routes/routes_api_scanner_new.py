from flask import Blueprint, jsonify, send_from_directory, abort
from pathlib import Path
import json

api_scanner_bp = Blueprint("api_scanner", __name__)
ARCHIVE_BASE = Path("/home/ned/scanner_archive/clean")

def find_file(filename):
    for sub in ["pd", "fire"]:
        f = ARCHIVE_BASE / sub / filename
        if f.exists():
            return f
    return None

@api_scanner_bp.route("/api/calls")
def list_calls():
    calls = []
    for sub in ["pd", "fire"]:
        for wav in sorted((ARCHIVE_BASE / sub).glob("*.wav"), reverse=True):
            base = wav.stem
            json_path = wav.with_suffix(".json")
            call_id = base.replace("rec_", "")
            entry = {
                "id": call_id,
                "feed": sub,
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
    wav = find_file(f"{base}.wav")
    if not wav:
        return abort(404, description="Call not found")
    txt = wav.with_suffix(".txt")
    json_path = wav.with_suffix(".json")

    data = {
        "id": call_id,
        "audio": f"/api/audio/{wav.name}",
        "filename": wav.name,
        "transcript": txt.read_text() if txt.exists() else "",
        "metadata": {}
    }

    if json_path.exists():
        try:
            data["metadata"] = json.loads(json_path.read_text())
        except:
            pass

    return jsonify(data)

@api_scanner_bp.route("/api/audio/<filename>")
def get_audio(filename):
    f = find_file(filename)
    if not f:
        return abort(404)
    return send_from_directory(f.parent, f.name)
