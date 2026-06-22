# ==========================================
# SEAT MANAGEMENT — paste this into app.py
# ==========================================
# Add these imports at the top of app.py:
# from datetime import datetime, timedelta
# import threading

import json
import threading
from datetime import datetime, timedelta

# ---- In-memory seat store (replace with DB for production) ----
# Status: "available" | "reserved" | "sold"
# reserved_at: timestamp when reserved (for expiry)

HOLD_MINUTES = 10  # seat hold duration before auto-release

def init_seats():
    seats = {}
    zones = {
        "rock":  {"rows": 5, "cols": 10, "price": 599},
        "cat1":  {"rows": 5, "cols": 10, "price": 488},
        "cat2":  {"rows": 5, "cols": 10, "price": 388},
        "cat3":  {"rows": 5, "cols": 10, "price": 288},
    }
    row_labels = ["A", "B", "C", "D", "E"]
    for zone, cfg in zones.items():
        seats[zone] = {}
        for r in range(cfg["rows"]):
            for c in range(1, cfg["cols"] + 1):
                seat_id = f"{row_labels[r]}{c}"
                seats[zone][seat_id] = {
                    "status": "available",
                    "reserved_at": None,
                    "session_id": None
                }
    return seats

seat_store = init_seats()
seat_lock = threading.Lock()


def release_expired_holds():
    """Background worker — releases seats held > HOLD_MINUTES."""
    while True:
        import time
        time.sleep(30)  # check every 30 seconds
        now = datetime.utcnow()
        with seat_lock:
            for zone in seat_store:
                for seat_id, seat in seat_store[zone].items():
                    if seat["status"] == "reserved" and seat["reserved_at"]:
                        held_since = datetime.fromisoformat(seat["reserved_at"])
                        if now - held_since > timedelta(minutes=HOLD_MINUTES):
                            seat["status"] = "available"
                            seat["reserved_at"] = None
                            seat["session_id"] = None
                            print(f"[Seat] Auto-released: {zone}/{seat_id}")

# Start background worker thread (add this near app.run at the bottom)
# worker = threading.Thread(target=release_expired_holds, daemon=True)
# worker.start()


# ---- Routes — paste these into your Flask app ----

@app.route("/seats/<zone>", methods=["GET"])
def get_seats(zone):
    """Return all seats for a zone with buyer-facing status."""
    with seat_lock:
        zone_data = seat_store.get(zone)
        if not zone_data:
            return jsonify({"error": "Zone not found"}), 404

        # Buyer view: merge reserved+sold → "unavailable"
        buyer_view = {}
        for seat_id, seat in zone_data.items():
            if seat["status"] == "available":
                buyer_view[seat_id] = "available"
            else:
                buyer_view[seat_id] = "unavailable"

    return jsonify({"zone": zone, "seats": buyer_view})


@app.route("/seats/<zone>/reserve", methods=["POST"])
def reserve_seat(zone):
    """Reserve a seat (on hold) for a session."""
    data = request.get_json()
    seat_id = data.get("seat_id")
    session_id = data.get("session_id")

    if not seat_id or not session_id:
        return jsonify({"error": "seat_id and session_id required"}), 400

    with seat_lock:
        zone_data = seat_store.get(zone)
        if not zone_data or seat_id not in zone_data:
            return jsonify({"error": "Seat not found"}), 404

        seat = zone_data[seat_id]
        if seat["status"] != "available":
            return jsonify({"success": False, "reason": "Seat already taken"}), 409

        seat["status"] = "reserved"
        seat["reserved_at"] = datetime.utcnow().isoformat()
        seat["session_id"] = session_id

    return jsonify({"success": True, "seat_id": seat_id, "zone": zone})


@app.route("/seats/<zone>/confirm", methods=["POST"])
def confirm_seat(zone):
    """Mark seat as sold after successful payment."""
    data = request.get_json()
    seat_id = data.get("seat_id")
    session_id = data.get("session_id")

    with seat_lock:
        zone_data = seat_store.get(zone)
        if not zone_data or seat_id not in zone_data:
            return jsonify({"error": "Seat not found"}), 404

        seat = zone_data[seat_id]
        if seat["session_id"] != session_id:
            return jsonify({"error": "Session mismatch"}), 403

        seat["status"] = "sold"
        seat["reserved_at"] = None

    return jsonify({"success": True, "seat_id": seat_id, "status": "sold"})


@app.route("/seats/<zone>/release", methods=["POST"])
def release_seat(zone):
    """Manually release a reserved seat (user abandoned cart)."""
    data = request.get_json()
    seat_id = data.get("seat_id")
    session_id = data.get("session_id")

    with seat_lock:
        zone_data = seat_store.get(zone)
        if not zone_data or seat_id not in zone_data:
            return jsonify({"error": "Seat not found"}), 404

        seat = zone_data[seat_id]
        if seat["session_id"] != session_id:
            return jsonify({"error": "Session mismatch"}), 403

        if seat["status"] == "reserved":
            seat["status"] = "available"
            seat["reserved_at"] = None
            seat["session_id"] = None

    return jsonify({"success": True, "seat_id": seat_id, "status": "available"})


@app.route("/seats/admin/<zone>", methods=["GET"])
def admin_seats(zone):
    """Admin/debug view — shows real status (available/reserved/sold)."""
    with seat_lock:
        zone_data = seat_store.get(zone)
        if not zone_data:
            return jsonify({"error": "Zone not found"}), 404
        return jsonify({"zone": zone, "seats": dict(zone_data)})