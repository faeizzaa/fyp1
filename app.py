from flask import Flask, jsonify, make_response, request, render_template_string, send_from_directory
from flask_cors import CORS
import time
import secrets
import json
import os
from supabase import create_client
import threading
from datetime import datetime, timedelta

# ==========================================
# 📁 SERVE STATIC FILES (HTML/JS/CSS)
# ==========================================
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'home.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)

# ==========================================
# 🗄️ SUPABASE DATABASE
# ==========================================
# ✅ CORRECT — Remove os.environ.get() entirely
SUPABASE_URL = "https://bpvjejwusdjqrotdoehi.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwdmpland1c2RqcXJvdGRvZWhpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MjIzNDY2OCwiZXhwIjoyMDk3ODEwNjY4fQ.eS0Vchi8-EX5-4v6_ybg1XUYH1kt_9Ld4Hpunmj6vd0"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def init_supabase():
    global supabase_client
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            from supabase import create_client
            supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("[DB] Supabase connected successfully.")
        except Exception as e:
            print(f"[DB] Supabase connection failed: {e}")
    else:
        print("[DB] Supabase credentials not found — using in-memory fallback.")

def save_evaluation_to_db(log):
    if not supabase_client:
        return
    try:
        supabase_client.table("evaluation_logs").insert({
            "session_id":      log["session_id"],
            "pattern":         log["pattern"],
            "duration_ms":     int(log["duration"]),
            "quantity":        log["quantity"],
            "mouse_movements": log["mouse_movements"],
            "score":           log["score"],
            "tier":            log["tier"],
            "reasons":         ", ".join(log["reasons"]) if isinstance(log["reasons"], list) else log["reasons"],
            "ip_address":      log.get("ip", "unknown")
        }).execute()
        print(f"[DB] Evaluation log saved to Supabase.")
    except Exception as e:
        print(f"[DB] Failed to save evaluation: {e}")

def save_session_to_db(session_id, session):
    if not supabase_client:
        return
    try:
        supabase_client.table("sessions").upsert({
            "session_id":     session_id,
            "ip_address":     session.get("ip", "unknown"),
            "user_agent":     session.get("user_agent", ""),
            "pattern":        "".join(session.get("actions", [])),
            "mouse_movements": session.get("mouse_movements", 0),
            "quantity":       session.get("quantity", 1),
            "pages_visited":  ", ".join(session.get("pages_visited", [])),
            "start_time":     session.get("start_time", time.time())
        }).execute()
    except Exception as e:
        print(f"[DB] Failed to save session: {e}")

def save_seat_to_db(zone, seat_id, status, reserved_at=None, session_id=None):
    if not supabase_client:
        return
    try:
        supabase_client.table("seat_store").upsert({
            "zone":        zone,
            "seat_id":     seat_id,
            "status":      status,
            "reserved_at": reserved_at,
            "session_id":  session_id
        }).execute()
    except Exception as e:
        print(f"[DB] Failed to save seat: {e}")

def load_logs_from_db():
    if not supabase_client:
        return []
    try:
        result = supabase_client.table("evaluation_logs")\
            .select("*")\
            .order("created_at", desc=True)\
            .limit(100)\
            .execute()
        logs = []
        for row in result.data:
            logs.append({
                "time":            row.get("created_at", "")[:19].replace("T", " "),
                "session_id":      row.get("session_id", "unknown"),
                "pattern":         row.get("pattern", "N/A"),
                "duration":        row.get("duration_ms", 0),
                "quantity":        row.get("quantity", 1),
                "mouse_movements": row.get("mouse_movements", 0),
                "score":           row.get("score", 0),
                "tier":            row.get("tier", 0),
                "reasons":         row.get("reasons", "").split(", ") if row.get("reasons") else [],
                "ip":              row.get("ip_address", "unknown")
            })
        return logs
    except Exception as e:
        print(f"[DB] Failed to load logs: {e}")
        return []

# ==========================================
# 🗄️ IN-MEMORY SESSION STORAGE
# ==========================================
sessions = {}

# ==========================================
# 💾 FALLBACK — JSON FILE LOG
# ==========================================
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evaluation_logs.json')

def load_logs():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Log] Could not load JSON logs: {e}")
    return []

def save_logs():
    try:
        with open(LOG_FILE, 'w') as f:
            json.dump(evaluation_logs[-200:], f)
    except Exception as e:
        print(f"[Log] Could not save JSON logs: {e}")

evaluation_logs = load_logs()

# ==========================================
# ⏱️ SALE COUNTDOWN
# ==========================================
SALE_COUNTDOWN_SECONDS = 120
TARGET_DROP_TIME = time.time() + SALE_COUNTDOWN_SECONDS

# ==========================================
# 🌲 BEHAVIORAL PATTERN MATCHING (TRIE)
# ==========================================
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_bad_pattern = False

class PrefixTree:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, pattern):
        node = self.root
        for char in pattern:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_bad_pattern = True

    def search(self, pattern):
        node = self.root
        for char in pattern:
            if char not in node.children:
                return False
            node = node.children[char]
        return node.is_bad_pattern

bot_tree = PrefixTree()

SEED_PATTERNS = ["HADSQSC", "HADSSQC", "HADSSSQC", "HADSQQQC"]
for p in SEED_PATTERNS:
    bot_tree.insert(p)

# ==========================================
# 🧠 SELF-LEARNING PATTERN BLACKLIST
# ==========================================
PATTERNS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'learned_patterns.json')

def load_learned_patterns():
    if os.path.exists(PATTERNS_FILE):
        try:
            with open(PATTERNS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Patterns] Could not load: {e}")
    return []

def save_learned_patterns():
    try:
        with open(PATTERNS_FILE, 'w') as f:
            json.dump(learned_patterns, f)
    except Exception as e:
        print(f"[Patterns] Could not save: {e}")

learned_patterns = load_learned_patterns()
for p in learned_patterns:
    bot_tree.insert(p)

# ==========================================
# 🪑 SEAT MANAGEMENT
# ==========================================
HOLD_MINUTES = 10

def init_seats():
    seats = {}
    zones = {
        "rock": {"rows": 5, "cols": 10, "price": 599},
        "cat1": {"rows": 5, "cols": 10, "price": 488},
        "cat2": {"rows": 5, "cols": 10, "price": 388},
        "cat3": {"rows": 5, "cols": 10, "price": 288},
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
    while True:
        time.sleep(30)
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
                            save_seat_to_db(zone, seat_id, "available")
                            print(f"[Seat] Auto-released: {zone}/{seat_id}")

worker = threading.Thread(target=release_expired_holds, daemon=True)
worker.start()

@app.route('/seats/<zone>', methods=['GET'])
def get_seats(zone):
    with seat_lock:
        zone_data = seat_store.get(zone)
        if not zone_data:
            return jsonify({"error": "Zone not found"}), 404
        buyer_view = {}
        for seat_id, seat in zone_data.items():
            buyer_view[seat_id] = "available" if seat["status"] == "available" else "unavailable"
    response = make_response(jsonify({"zone": zone, "seats": buyer_view}))
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route('/seats/<zone>/reserve', methods=['POST', 'OPTIONS'])
def reserve_seat(zone):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return response

    data = request.get_json() or {}
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

    save_seat_to_db(zone, seat_id, "reserved", seat["reserved_at"], session_id)
    print(f"[Seat] Reserved: {zone}/{seat_id} by session {session_id[:12]}")
    response = make_response(jsonify({"success": True, "seat_id": seat_id, "zone": zone}))
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route('/seats/<zone>/confirm', methods=['POST', 'OPTIONS'])
def confirm_seat(zone):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return response

    data = request.get_json() or {}
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

    save_seat_to_db(zone, seat_id, "sold")
    print(f"[Seat] Sold: {zone}/{seat_id}")
    response = make_response(jsonify({"success": True, "seat_id": seat_id, "status": "sold"}))
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route('/seats/<zone>/release', methods=['POST', 'OPTIONS'])
def release_seat(zone):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return response

    data = request.get_json() or {}
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

    save_seat_to_db(zone, seat_id, "available")
    print(f"[Seat] Released: {zone}/{seat_id}")
    response = make_response(jsonify({"success": True, "seat_id": seat_id, "status": "available"}))
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route('/seats/admin/<zone>', methods=['GET'])
def admin_seats(zone):
    with seat_lock:
        zone_data = seat_store.get(zone)
        if not zone_data:
            return jsonify({"error": "Zone not found"}), 404
        return jsonify({"zone": zone, "seats": dict(zone_data)})

# ==========================================
# 📊 MONITORING DASHBOARD
# ==========================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Bot Detection Monitor</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
        }
        h1 { color: #00d4ff; margin-bottom: 10px; }
        .subtitle { color: #888; margin-bottom: 30px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #16213e;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 1px solid #0f3460;
        }
        .stat-value { font-size: 2.5rem; font-weight: bold; color: #00d4ff; }
        .stat-label { color: #888; font-size: 0.9rem; margin-top: 5px; }
        .stat-card.tier1 .stat-value { color: #ffc107; }
        .stat-card.tier2 .stat-value { color: #ff9800; }
        .stat-card.tier3 .stat-value { color: #f44336; }
        .stat-card.clean .stat-value { color: #4caf50; }
        .section-title {
            color: #00d4ff;
            margin: 30px 0 15px 0;
            padding-bottom: 10px;
            border-bottom: 1px solid #0f3460;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .db-badge {
            font-size: 12px;
            background: #27ae60;
            color: white;
            padding: 3px 10px;
            border-radius: 20px;
        }
        .db-badge.offline { background: #e74c3c; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: #16213e;
            border-radius: 12px;
            overflow: hidden;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #0f3460;
        }
        th { background: #0f3460; color: #00d4ff; font-weight: 600; }
        tr:hover { background: #1f2b4d; }
        .tier-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.85rem;
        }
        .tier-0 { background: #4caf50; color: white; }
        .tier-1 { background: #ffc107; color: black; }
        .tier-2 { background: #ff9800; color: white; }
        .tier-3 { background: #f44336; color: white; }
        .pattern-code {
            font-family: 'Courier New', monospace;
            background: #0f3460;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9rem;
        }
        .refresh-btn {
            background: #00d4ff;
            color: #1a1a2e;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            margin-bottom: 20px;
        }
        .refresh-btn:hover { background: #00b8e6; }
        .auto-refresh { color: #888; font-size: 0.85rem; margin-left: 15px; }
        .empty-state { text-align: center; padding: 40px; color: #666; }
        .active-sessions {
            background: #16213e;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .session-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid #0f3460;
            flex-wrap: wrap;
            gap: 8px;
        }
        .session-item:last-child { border-bottom: none; }
        .session-id { font-family: monospace; color: #00d4ff; }
        .session-actions { font-family: monospace; color: #ffc107; }
        .ip-badge {
            background: #0f3460;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-family: monospace;
            color: #aaa;
        }
    </style>
</head>
<body>
    <h1>🛡️ Bot Detection Monitor</h1>
    <p class="subtitle">Real-time session tracking and threat analysis</p>

    <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
    <span class="auto-refresh">Auto-refreshes every 5 seconds</span>

    <div class="stats-grid">
        <div class="stat-card clean">
            <div class="stat-value">{{ stats.clean }}</div>
            <div class="stat-label">✅ Clean Sessions</div>
        </div>
        <div class="stat-card tier1">
            <div class="stat-value">{{ stats.tier1 }}</div>
            <div class="stat-label">⚠️ Tier 1 (Delay)</div>
        </div>
        <div class="stat-card tier2">
            <div class="stat-value">{{ stats.tier2 }}</div>
            <div class="stat-label">🔒 Tier 2 (CAPTCHA)</div>
        </div>
        <div class="stat-card tier3">
            <div class="stat-value">{{ stats.tier3 }}</div>
            <div class="stat-label">🚫 Tier 3 (Blocked)</div>
        </div>
    </div>

    <h2 class="section-title">
        🔴 Active Sessions ({{ active_count }})
        <span class="db-badge {{ 'online' if db_online else 'offline' }}">
            {{ '🟢 Supabase Connected' if db_online else '🔴 DB Offline (in-memory)' }}
        </span>
    </h2>
    <div class="active-sessions">
        {% if active_sessions %}
            {% for sid, session in active_sessions.items() %}
            <div class="session-item">
                <span class="session-id">{{ sid[:16] }}...</span>
                <span class="ip-badge">{{ session.get('ip', 'unknown') }}</span>
                <span>Pages: {{ session.pages_visited | join(', ') or 'None' }}</span>
                <span class="session-actions">Pattern: {{ session.actions | join('') or 'N/A' }}</span>
                <span>Mouse: {{ session.mouse_movements }}</span>
                <span>{{ "%.1f" | format(session.age) }}s ago</span>
            </div>
            {% endfor %}
        {% else %}
            <div class="empty-state">No active sessions</div>
        {% endif %}
    </div>

    <h2 class="section-title">📋 Evaluation History ({{ logs | length }} records)</h2>
    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Session ID</th>
                <th>IP</th>
                <th>Pattern</th>
                <th>Duration</th>
                <th>Qty</th>
                <th>Mouse</th>
                <th>Score</th>
                <th>Tier</th>
                <th>Reasons</th>
            </tr>
        </thead>
        <tbody>
            {% if logs %}
                {% for log in logs %}
                <tr>
                    <td>{{ log.time }}</td>
                    <td><code>{{ log.session_id[:12] }}...</code></td>
                    <td><span style="font-size:12px;color:#aaa">{{ log.get('ip', 'unknown') }}</span></td>
                    <td><span class="pattern-code">{{ log.pattern }}</span></td>
                    <td>{{ "%.1f" | format(log.duration / 1000) }}s</td>
                    <td>{{ log.quantity }}</td>
                    <td>{{ log.mouse_movements }}</td>
                    <td><strong>{{ log.score }}</strong></td>
                    <td><span class="tier-badge tier-{{ log.tier }}">Tier {{ log.tier }}</span></td>
                    <td style="font-size:12px">{{ log.reasons | join(', ') if log.reasons is iterable and log.reasons is not string else log.reasons }}</td>
                </tr>
                {% endfor %}
            {% else %}
                <tr>
                    <td colspan="10" class="empty-state">No evaluations yet. Run a bot to see data.</td>
                </tr>
            {% endif %}
        </tbody>
    </table>

    <script>
        setTimeout(() => location.reload(), 5000);
    </script>
</body>
</html>
"""

@app.route('/monitor')
def monitor_dashboard():
    # Try to load from Supabase, fallback to in-memory
    if supabase_client:
        logs = load_logs_from_db()
        db_online = True
    else:
        logs = list(reversed(evaluation_logs[-50:]))
        db_online = False

    stats = {'clean': 0, 'tier1': 0, 'tier2': 0, 'tier3': 0}
    for log in logs:
        t = log['tier']
        if t == 0:   stats['clean'] += 1
        elif t == 1: stats['tier1'] += 1
        elif t == 2: stats['tier2'] += 1
        elif t == 3: stats['tier3'] += 1

    active_sessions = {}
    current_time = time.time()
    for sid, session in sessions.items():
        active_sessions[sid] = {
            **session,
            'age': current_time - session['start_time']
        }

    return render_template_string(
        DASHBOARD_HTML,
        stats=stats,
        active_sessions=active_sessions,
        active_count=len(sessions),
        logs=logs,
        db_online=db_online
    )


# ==========================================
# 🔌 API ENDPOINTS
# ==========================================

@app.route('/api/sale-status', methods=['GET'])
def sale_status():
    current_system_time = time.time()
    remaining_seconds = int(TARGET_DROP_TIME - current_system_time)
    if remaining_seconds < 0:
        remaining_seconds = 0
    is_live = (remaining_seconds <= 0)
    data = {"countdown": remaining_seconds, "isSaleLive": is_live}
    response = make_response(jsonify(data))
    response.headers["ngrok-skip-browser-warning"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "ngrok-skip-browser-warning, Content-Type"
    return response


@app.route('/api/init-session', methods=['POST'])
def init_session():
    session_id = secrets.token_urlsafe(24)
    sessions[session_id] = {
        'start_time': time.time(),
        'actions': [],
        'timestamps': [],
        'mouse_movements': 0,
        'ip': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', ''),
        'quantity': 1,
        'pages_visited': []
    }
    save_session_to_db(session_id, sessions[session_id])
    print(f"\n[+] New session: {session_id[:16]}... from {request.remote_addr}")
    response = make_response(jsonify({'session_id': session_id, 'status': 'initialized'}))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


@app.route('/api/track-action', methods=['POST'])
def track_action():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    action = data.get('action', '')

    if not session_id or session_id not in sessions:
        response = make_response(jsonify({'error': 'Invalid session'}), 400)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

    session = sessions[session_id]
    elapsed = time.time() - session['start_time']

    if action:
        session['actions'].append(action)
        session['timestamps'].append(elapsed)
    if 'mouse_movements' in data:
        session['mouse_movements'] = data['mouse_movements']
    if 'quantity' in data:
        session['quantity'] = int(data['quantity'])
    if 'page' in data:
        page = data['page']
        if page and page not in session['pages_visited']:
            session['pages_visited'].append(page)

    print(f"[Session {session_id[:12]}] Action: {action:12} | Pattern: {''.join(session['actions']):20} | Mouse: {session['mouse_movements']}")

    response = make_response(jsonify({'status': 'tracked'}))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


@app.route('/api/captcha-verified', methods=['POST'])
def captcha_verified():
    data = request.get_json() or {}
    session_id = data.get('session_id', 'unknown')
    method = data.get('method', 'unknown')

    print("\n" + "=" * 50)
    print("CAPTCHA VERIFICATION SUCCESS")
    print(f"   Session: {session_id[:16]}...")
    print(f"   Method:  {method}")
    print("=" * 50 + "\n")

    response = make_response(jsonify({'status': 'verified'}))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


@app.route('/detect', methods=['POST'])
def detect_agent():
    data = request.get_json() or {}
    print(f"\n[Telemetry] {data}")
    response = make_response(jsonify({"status": "captured"}))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


@app.route('/evaluate', methods=['POST'])
def evaluate_session():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    force_tier = data.get('force_tier')
    ip_address = request.remote_addr


    if not session_id or session_id not in sessions:
        pattern        = data.get('pattern', '')
        duration       = data.get('duration', 0)
        quantity       = int(data.get('quantity', 1))
        qty_speed      = data.get('qty_speed', 9999)
        mouse_movements = data.get('mouse_movements', 0)
        session_id     = 'LEGACY-' + secrets.token_urlsafe(8)
    else:
        session        = sessions[session_id]
        pattern        = ''.join(session['actions'])
        duration       = (time.time() - session['start_time']) * 1000
        quantity       = session['quantity']
        mouse_movements = session['mouse_movements']
        qty_speed      = data.get('qty_speed', 9999)

    print("\n" + "=" * 60)
    print("EVALUATION REQUEST")
    print("=" * 60)
    print(f"   Session ID    : {session_id[:20]}...")
    print(f"   IP Address    : {ip_address}")
    print(f"   Pattern       : {pattern}")
    print(f"   Duration      : {duration:.0f}ms")
    print(f"   Quantity      : {quantity}")
    print(f"   Mouse Moves   : {mouse_movements}")
    print(f"   Qty Speed     : {qty_speed}ms")
    print("=" * 60)

    if force_tier is not None:
        tier    = int(force_tier)
        score   = {1: 30, 2: 60, 3: 100}.get(tier, 0)
        reasons = ["Client-side fast-path: HADSQC pattern + low mouse activity under 15s"]

        print(f"CLIENT FAST-PATH: Tier {tier}")
        print("=" * 60 + "\n")

        log_entry = {
            'time':            datetime.now().strftime('%H:%M:%S'),
            'session_id':      session_id,
            'pattern':         pattern or 'N/A',
            'duration':        duration,
            'quantity':        quantity,
            'mouse_movements': mouse_movements,
            'score':           score,
            'tier':            tier,
            'reasons':         reasons,
            'ip':              ip_address
        }
        evaluation_logs.append(log_entry)
        save_logs()
        save_evaluation_to_db(log_entry)

        if tier == 3 and session_id in sessions:
            del sessions[session_id]

        response = make_response(jsonify({'score': score, 'tier': tier, 'reasons': reasons}))
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

    score   = 0
    reasons = []

    if pattern == "HADSQC" and quantity == 1 and duration < 15000:
        score += 30
        reasons.append("Elevated interaction speed")

    if quantity == 5:
        score += 40
        reasons.append(f"Max quantity purchase: {quantity} tickets")
    elif quantity >= 4:
        score += 15
        reasons.append(f"High quantity purchase: {quantity} tickets")

    if qty_speed < 500:
        score += 40
        reasons.append(f"Instant quantity selection ({qty_speed}ms)")
    elif qty_speed < 1500:
        score += 20
        reasons.append(f"Fast quantity selection ({qty_speed}ms)")

    if bot_tree.search(pattern):
        score += 40
        reasons.append(f"Known bot pattern: {pattern}")

    if mouse_movements == 0:
        score += 35
        reasons.append("Zero mouse movement detected")
    elif mouse_movements < 10:
        score += 15
        reasons.append(f"Minimal mouse activity ({mouse_movements})")

    if duration < 8000:
        score += 20
        reasons.append(f"Impossible speed ({duration:.0f}ms)")
    elif duration < 12000:
        score += 15
        reasons.append(f"Abnormally fast ({duration:.0f}ms)")

    if "ghost_ticket" in pattern.lower():
        score += 100
        reasons.append("Honeypot triggered")

    if 'X' in pattern:
        score += 50
        reasons.append("Queue gate bypassed (skipped waiting room)")

    # Retrieve previous cumulative score from session or request
    cumulative_score = int(data.get('cumulative_score', 0))
    total_score = score + cumulative_score
    
    # Determine tier based on TOTAL score
    if total_score >= 100:
        tier = 3
    elif total_score >= 60:
        tier = 2
    elif total_score >= 30:
        tier = 1
    else:
        tier = 0
        reasons.append("No suspicious activity")
    # For Tier 1, add penalty points for next evaluation
    carry_forward = 0
    if tier == 1:
        carry_forward = 15  # Added to next evaluation
        reasons.append("Session flagged for monitoring (+15 carry)")
    print(f"\n   Base Score      : {score}")
    print(f"   Cumulative      : {cumulative_score}")
    print(f"   Total Score     : {total_score}")
    print(f"   Tier            : {tier}")
    print(f"   Carry Forward   : {carry_forward}")

    if score >= 100:
        tier = 3
        print("TIER 3: Redirecting to ghost ticket")
        if pattern and not bot_tree.search(pattern):
            bot_tree.insert(pattern)
            if pattern not in learned_patterns:
                learned_patterns.append(pattern)
                save_learned_patterns()
                print(f"LEARNED NEW PATTERN: '{pattern}'")
    elif score >= 60:
        tier = 2
        print("TIER 2: CAPTCHA required")
    elif score >= 30:
        tier = 1
        print("TIER 1: Applying 3-second delay")
        time.sleep(3)
    else:
        tier = 0
        reasons.append("No suspicious activity")
        print("TIER 0: Clean session")

    print(f"\n   Final Score : {score}")
    print(f"   Tier        : {tier}")
    print(f"   Reasons     : {reasons}")
    print("=" * 60 + "\n")

    log_entry = {
        'time':            datetime.now().strftime('%H:%M:%S'),
        'session_id':      session_id,
        'pattern':         pattern or 'N/A',
        'duration':        duration,
        'quantity':        quantity,
        'mouse_movements': mouse_movements,
        'score':           score,
        'tier':            tier,
        'reasons':         reasons,
        'ip':              ip_address
    }
    evaluation_logs.append(log_entry)
    save_logs()
    save_evaluation_to_db(log_entry)

    if session_id in sessions:
        del sessions[session_id]

    response = make_response(jsonify({
        'score': score,
        'total_score': total_score,
        'tier': tier,
        'reasons': reasons,
        'carry_forward': carry_forward
    }))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


# ==========================================
# 🚀 SERVER START
# ==========================================
if __name__ == '__main__':
    init_supabase()

    print("\n" + "=" * 60)
    print("BOT DETECTION SERVER STARTING")
    print("=" * 60)
    print(f"   API Server    : http://localhost:8000")
    print(f"   Monitor       : http://localhost:8000/monitor")
    print(f"   Supabase      : {'Connected' if supabase_client else 'Not configured'}")
    print(f"   Restored      : {len(evaluation_logs)} saved evaluation(s)")
    print(f"   Learned       : {len(learned_patterns)} self-learned pattern(s)")
    print("=" * 60 + "\n")

    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)

# Init Supabase on module load (for Render/Gunicorn)
init_supabase()