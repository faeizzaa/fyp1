from flask import Flask, jsonify, make_response, request, render_template_string, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
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

app = Flask(__name__, static_folder=None)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Session cookie signing key. MUST be set via env var on Render - if this
# falls back to a fresh random value every process start, every logged-in
# user gets silently logged out on every restart (same class of problem
# we hit with the in-memory sessions dict earlier). Set FLASK_SECRET_KEY
# in Render's Environment tab to a long random string.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# ==========================================
# 👤 USER ACCOUNTS (login/register gate before checkout)
# ==========================================
def get_current_user():
    """Returns {'id':..,'username':..,'created_at':..} for the logged-in
    user, or None. created_at is used for the 'new account, instant
    purchase' detection signal in evaluate_session()."""
    user_id = session.get('user_id')
    if not user_id or not supabase:
        return None
    try:
        result = supabase.table("users").select("*").eq("id", user_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[Auth] Failed to load current user: {e}")
        return None

def login_required_page(f):
    """For HTML page routes - redirects to /login?next=<page> instead of
    a bare 401, since a human needs somewhere to actually go."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(f"/login?next={request.path}")
        return f(*args, **kwargs)
    return decorated

def login_required_api(f):
    """For JSON/API routes - returns a 401 the frontend JS can check for,
    rather than an HTML redirect a fetch() call can't follow usefully."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            response = make_response(jsonify({'error': 'not_authenticated', 'redirect': '/login'}), 401)
            return response
        return f(*args, **kwargs)
    return decorated

# ==========================================
# 🔒 ADMIN-ONLY ROUTES (HTTP Basic Auth)
# ==========================================
# Credentials come from environment variables, not hardcoded, so they
# never sit in GitHub. Set ADMIN_USERNAME / ADMIN_PASSWORD in Render's
# Environment tab. The 'admin' / 'changeme123' fallbacks below only
# exist so local testing doesn't crash if the env vars aren't set - do
# not deploy to Render without overriding both.
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme123')

def requires_admin_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ADMIN_USERNAME or auth.password != ADMIN_PASSWORD:
            return make_response(
                'Authentication required.', 401,
                {'WWW-Authenticate': 'Basic realm="Admin Dashboard"'}
            )
        return f(*args, **kwargs)
    return decorated

# Render sits the app behind more than one internal proxy hop (confirmed
# by seeing an internal-looking 10.x.x.x address show up instead of a
# real public IP), so rather than guess the exact hop count with
# ProxyFix's x_for=N, read X-Forwarded-For directly and take the FIRST
# entry - by HTTP convention that's always the original client, no
# matter how many internal hops were appended after it.
def get_client_ip():
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'home.html')

# Pages that require a logged-in account to view at all - browsing
# (home/waitingroom/select) stays open to everyone, the gate kicks in
# right where checkout actually starts.
CHECKOUT_GATED_PAGES = {'confirm.html', 'payment.html'}

@app.route('/<path:filename>')
def serve_static(filename):
    if filename in CHECKOUT_GATED_PAGES and not session.get('user_id'):
        return redirect(f"/login?next={filename}")
    return send_from_directory(FRONTEND_DIR, filename)

# ==========================================
# SUPABASE DATABASE
# ==========================================

SUPABASE_URL = "https://bpvjejwusdjqrotdoehi.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwdmpland1c2RqcXJvdGRvZWhpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MjIzNDY2OCwiZXhwIjoyMDk3ODEwNjY4fQ.eS0Vchi8-EX5-4v6_ybg1XUYH1kt_9Ld4Hpunmj6vd0"

supabase = None

MYT_OFFSET = timedelta(hours=8)  # Malaysia Time = UTC+8, no DST, safe as a fixed offset

def now_myt_iso():
    """Current time in Malaysia local time, as an ISO string, for explicit
    created_at writes. Supabase's Table Editor always displays the raw
    stored value with no timezone conversion, so to have times 'tally'
    there too (not just on /monitor), we write MYT directly instead of
    relying on the column's `default now()` (which is UTC)."""
    return (datetime.utcnow() + MYT_OFFSET).isoformat()

def init_supabase():
    global supabase
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY) 
            print("[DB] Supabase connected successfully.")
        except Exception as e:
            print(f"[DB] Supabase connection failed: {e}")

init_supabase()

# ==========================================
# 👤 AUTH ROUTES
# ==========================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return send_from_directory(FRONTEND_DIR, 'register.html')

    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    next_page = data.get('next') or 'confirm.html'

    if len(username) < 3 or len(password) < 6:
        return jsonify({'error': 'Username must be 3+ chars, password 6+ chars'}), 400
    if not supabase:
        return jsonify({'error': 'Server database unavailable'}), 503

    try:
        existing = supabase.table("users").select("id").eq("username", username).limit(1).execute()
        if existing.data:
            return jsonify({'error': 'Username already taken'}), 409

        password_hash = generate_password_hash(password)
        result = supabase.table("users").insert({
            "username": username,
            "password_hash": password_hash
        }).execute()

        new_user = result.data[0]
        session['user_id'] = new_user['id']
        session['username'] = new_user['username']
        print(f"[Auth] New account registered: {username} (id={new_user['id']})")

        response = make_response(jsonify({'status': 'registered', 'redirect': f'/{next_page}'}))
        return response
    except Exception as e:
        print(f"[Auth] Registration failed: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return send_from_directory(FRONTEND_DIR, 'login.html')

    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    next_page = data.get('next') or 'confirm.html'

    if not supabase:
        return jsonify({'error': 'Server database unavailable'}), 503

    try:
        result = supabase.table("users").select("*").eq("username", username).limit(1).execute()
        if not result.data or not check_password_hash(result.data[0]['password_hash'], password):
            return jsonify({'error': 'Invalid username or password'}), 401

        user = result.data[0]

        if user.get('is_blocked'):
            print(f"[Auth] Login rejected - blocked account: {username} (id={user['id']})")
            return jsonify({'error': 'This account has been suspended.'}), 403

        session['user_id'] = user['id']
        session['username'] = user['username']
        print(f"[Auth] Login: {username} (id={user['id']})")

        response = make_response(jsonify({'status': 'logged_in', 'redirect': f'/{next_page}'}))
        return response
    except Exception as e:
        print(f"[Auth] Login failed: {e}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'logged_out'})

@app.route('/api/whoami', methods=['GET'])
def whoami():
    """Lets pages check login state without a full page reload."""
    if session.get('user_id'):
        return jsonify({'logged_in': True, 'username': session.get('username')})
    return jsonify({'logged_in': False})

def save_evaluation_to_db(log):
    if not supabase:
        return
    try:
        supabase.table("evaluation_logs").insert({
            "created_at":      now_myt_iso(),
            "session_id":      log["session_id"],
            "pattern":         log["pattern"],
            "duration_ms":     int(log["duration"]),
            "quantity":        log["quantity"],
            "mouse_movements": log["mouse_movements"],
            "score":           log["score"],
            "tier":            log["tier"],
            "reasons":         ", ".join(log["reasons"]) if isinstance(log["reasons"], list) else log["reasons"],
            "ip_address":      log.get("ip", "unknown"),
            "action":          log.get("action", "none"),
            "user_id":         log.get("user_id")
        }).execute()
        print(f"[DB] Evaluation log saved to Supabase.")
    except Exception as e:
        print(f"[DB] Failed to save evaluation: {e}")

def save_session_to_db(session_id, session):
    if not supabase:
        return
    try:
        supabase.table("sessions").upsert({
            "created_at":      now_myt_iso(),
            "session_id":      session_id,
            "ip_address":      session.get("ip", "unknown"),
            "user_agent":      session.get("user_agent", ""),
            "pattern":         "".join(session.get("actions", [])),
            "mouse_movements": session.get("mouse_movements", 0),
            "quantity":        session.get("quantity", 1),
            "pages_visited":   ", ".join(session.get("pages_visited", [])),
            "start_time":      session.get("start_time", time.time())
        }, on_conflict="session_id").execute()
    except Exception as e:
        print(f"[DB] Failed to save session: {e}")

def save_seat_to_db(zone, seat_id, status, reserved_at=None, session_id=None, ip_address=None, user_id=None):
    if not supabase:
        return
    try:
        payload = {
            "created_at":  now_myt_iso(),
            "zone":        zone,
            "seat_id":     seat_id,
            "status":      status,
            "reserved_at": reserved_at,
            "session_id":  session_id
        }
        if ip_address is not None:
            payload["ip_address"] = ip_address
        if user_id is not None:
            payload["user_id"] = user_id
        supabase.table("seat_store").upsert(payload, on_conflict="zone,seat_id").execute()
    except Exception as e:
        print(f"[DB] Failed to save seat: {e}")

def count_tickets_sold_to_ip(ip_address):
    """Lifetime count of tickets this IP has already had confirmed as
    'sold' - used to enforce the per-IP purchase cap. Requires the
    seat_store table to have an ip_address column (see migration note
    near confirm_seat() below)."""
    if not supabase or not ip_address or ip_address == 'unknown':
        return 0
    try:
        result = supabase.table("seat_store") \
            .select("id", count="exact") \
            .eq("status", "sold") \
            .eq("ip_address", ip_address) \
            .execute()
        return result.count or 0
    except Exception as e:
        print(f"[DB] Failed to count tickets for IP: {e}")
        return 0

def count_tickets_sold_to_user(user_id):
    """Lifetime count of tickets this ACCOUNT has already had confirmed
    as 'sold' - the per-account equivalent of count_tickets_sold_to_ip,
    and a more reliable signal since accounts (unlike IPs) aren't shared
    by multiple unrelated people on the same network."""
    if not supabase or not user_id:
        return 0
    try:
        result = supabase.table("seat_store") \
            .select("id", count="exact") \
            .eq("status", "sold") \
            .eq("user_id", user_id) \
            .execute()
        return result.count or 0
    except Exception as e:
        print(f"[DB] Failed to count tickets for user: {e}")
        return 0

def get_blocked_accounts():
    """All currently-blocked accounts for the dashboard's Blocked
    Accounts panel, each enriched with their most recent known IP
    (looked up via evaluation_logs.user_id, the newest evaluate call
    that account made - best-effort, since older log rows predating
    the user_id column won't have one to match against)."""
    if not supabase:
        return []
    try:
        result = supabase.table("users").select("*").eq("is_blocked", True).execute()
        blocked = result.data or []

        for user in blocked:
            try:
                ip_result = supabase.table("evaluation_logs") \
                    .select("ip_address") \
                    .eq("user_id", user["id"]) \
                    .order("created_at", desc=True) \
                    .limit(1) \
                    .execute()
                user["last_known_ip"] = ip_result.data[0]["ip_address"] if ip_result.data else "unknown"
            except Exception as e:
                print(f"[DB] Failed to look up last IP for user {user.get('id')}: {e}")
                user["last_known_ip"] = "unknown"

        # Most recently blocked first
        blocked.sort(key=lambda u: u.get("blocked_at") or "", reverse=True)
        return blocked
    except Exception as e:
        print(f"[DB] Failed to load blocked accounts: {e}")
        return []

def unblock_account(user_id):
    if not supabase:
        return False
    try:
        supabase.table("users").update({"is_blocked": False}).eq("id", user_id).execute()
        print(f"[Auth] Admin unblocked user_id={user_id}")
        return True
    except Exception as e:
        print(f"[DB] Failed to unblock account: {e}")
        return False

def get_username_map():
    """Returns {user_id: username} for every account. evaluation_logs
    only stores user_id (no FK/JOIN available since the schema doesn't
    declare a real foreign key - see ERD notes), so the dashboard
    resolves usernames itself with one bulk query instead of one query
    per log row."""
    if not supabase:
        return {}
    try:
        result = supabase.table("users").select("id, username").execute()
        return {u["id"]: u["username"] for u in (result.data or [])}
    except Exception as e:
        print(f"[DB] Failed to load username map: {e}")
        return {}

def count_tier3_hits_by_ip(ip_address):
    """Lifetime count of Tier-3 (ghost ticket) evaluations logged against
    this IP. Used alongside the per-account ghost_ticket_count so a bot
    that registers a fresh throwaway account each run (see
    register_throwaway_account in bot_worker.py) still gets caught
    reusing the same machine/script, not just the same account."""
    if not supabase or not ip_address or ip_address == 'unknown':
        return 0
    try:
        result = supabase.table("evaluation_logs") \
            .select("id", count="exact") \
            .eq("ip_address", ip_address) \
            .eq("tier", 3) \
            .execute()
        return result.count or 0
    except Exception as e:
        print(f"[DB] Failed to count Tier-3 hits for IP: {e}")
        return 0

def load_session_from_db(session_id):
    """The in-memory `sessions` dict can be wiped by a process restart
    (Render's free tier can recycle the instance without it always
    showing as a distinct Event) - if that happens mid-checkout, rebuild
    the session from Supabase instead of losing continuity entirely."""
    if not supabase or not session_id:
        return None
    try:
        result = supabase.table("sessions").select("*").eq("session_id", session_id).limit(1).execute()
        if not result.data:
            return None
        row = result.data[0]
        pattern = row.get("pattern") or ""
        return {
            'start_time':      row.get("start_time") or time.time(),
            'actions':         list(pattern),
            'timestamps':      [0] * len(pattern),
            'mouse_movements': row.get("mouse_movements", 0),
            'ip':              row.get("ip_address", "unknown"),
            'user_agent':      row.get("user_agent", ""),
            'quantity':        row.get("quantity", 1),
            'pages_visited':   row.get("pages_visited", "").split(", ") if row.get("pages_visited") else []
        }
    except Exception as e:
        print(f"[DB] Failed to rehydrate session: {e}")
        return None

def format_myt(created_at_str):
    """created_at is now written as MYT directly at insert time (see
    now_myt_iso() above), so this just formats it - no offset needed
    anymore. Kept as a function in case the source ever changes back."""
    if not created_at_str:
        return ""
    try:
        raw = created_at_str[:26]  # trim to handle variable microsecond precision
        dt = datetime.fromisoformat(raw)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return created_at_str[:19].replace("T", " ")

def load_logs_from_db():
    if not supabase:
        return []
    try:
        result = supabase.table("evaluation_logs")\
            .select("*")\
            .order("created_at", desc=True)\
            .limit(100)\
            .execute()
        logs = []
        for row in result.data:
            logs.append({
                "time":            format_myt(row.get("created_at", "")),
                "session_id":      row.get("session_id", "unknown"),
                "pattern":         row.get("pattern", "N/A"),
                "duration":        row.get("duration_ms", 0),
                "quantity":        row.get("quantity", 1),
                "mouse_movements": row.get("mouse_movements", 0),
                "score":           row.get("score", 0),
                "tier":            row.get("tier", 0),
                "reasons":         row.get("reasons", "").split(", ") if row.get("reasons") else [],
                "ip":              row.get("ip_address", "unknown"),
                "action":          row.get("action"),
                "user_id":         row.get("user_id")
            })
        return logs
    except Exception as e:
        print(f"[DB] Failed to load logs: {e}")
        return []

# ==========================================
# 🗄️ IN-MEMORY SESSION STORAGE
# ==========================================
sessions = {}

# Timestamps of recent /evaluate calls, for the dashboard's traffic-spike
# alert. A deque with maxlen auto-discards old entries so this never
# grows unbounded - it only ever needs to cover the last few minutes.
from collections import deque
evaluate_call_times = deque(maxlen=1000)

def detect_traffic_spike(window_seconds=60, spike_threshold=8):
    """Flags a spike if more than `spike_threshold` /evaluate calls
    happened in the last `window_seconds`. A single real visitor
    generates very few /evaluate calls (2 - one at confirm, one at
    payment); a burst like this is characteristic of multiple bots
    firing at once (e.g. stress_test.py), not organic traffic."""
    now = time.time()
    recent = [t for t in evaluate_call_times if now - t <= window_seconds]
    return {
        'is_spike':      len(recent) >= spike_threshold,
        'count':         len(recent),
        'window_seconds': window_seconds,
        'threshold':     spike_threshold
    }

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

    # Backstop in case something reaches this endpoint without ever going
    # through the confirm.html/payment.html page gate (e.g. a bot hitting
    # the API directly).
    if not session.get('user_id'):
        return jsonify({"error": "not_authenticated", "redirect": "/login"}), 401

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

    save_seat_to_db(zone, seat_id, "sold", ip_address=get_client_ip(), user_id=session.get('user_id'))
    print(f"[Seat] Sold: {zone}/{seat_id} to user_id={session.get('user_id')}")
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
@requires_admin_auth
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
    <meta charset="UTF-8">
    <title>Tickago Admin — Monitor</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, 'Segoe UI', Roboto, Tahoma, Geneva, Verdana, sans-serif;
            background: #0a1826;
            color: #eef2f7;
            min-height: 100vh;
        }

        a { text-decoration: none; color: inherit; }

        /* ===== SIDEBAR ===== */
        .sidebar {
            position: fixed;
            top: 0; left: 0; bottom: 0;
            width: 232px;
            background: #0d1f33;
            border-right: 1px solid rgba(255,255,255,0.06);
            padding: 22px 16px;
            display: flex;
            flex-direction: column;
        }
        .sidebar-brand {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 0 8px 20px;
            margin-bottom: 8px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .sidebar-brand .logo-sq {
            width: 30px; height: 30px;
            background: #4fc3f7;
            border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            color: #06131f; font-weight: 800; font-size: 14px;
            flex-shrink: 0;
        }
        .sidebar-brand .brand-text { font-weight: 700; font-size: 0.95rem; color: #eef2f7; }
        .sidebar-brand .brand-text span { display: block; font-size: 0.66rem; font-weight: 600; color: #5f7690; letter-spacing: 0.5px; }

        .nav-group { margin-top: 18px; }
        .nav-label {
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.6px;
            color: #46617e;
            padding: 0 10px;
            margin-bottom: 6px;
            text-transform: uppercase;
        }
        .nav-link {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 10px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            color: #a8bcd4;
            margin-bottom: 2px;
        }
        .nav-link:hover { background: rgba(255,255,255,0.05); color: #eef2f7; }
        .nav-link .nav-icon { font-size: 0.95rem; width: 18px; text-align: center; }

        .sidebar-footer {
            margin-top: auto;
            padding-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.06);
        }
        .live-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.3px;
            color: #34d399;
            background: rgba(52,211,153,0.12);
            padding: 4px 10px;
            border-radius: 20px;
        }
        .live-dot {
            width: 6px; height: 6px; border-radius: 50%;
            background: #34d399;
            animation: pulse 1.6s infinite;
        }
        @keyframes pulse {
            0%   { box-shadow: 0 0 0 0 rgba(52,211,153,0.45); }
            70%  { box-shadow: 0 0 0 6px rgba(52,211,153,0); }
            100% { box-shadow: 0 0 0 0 rgba(52,211,153,0); }
        }
        .sidebar-footer .auto-refresh { display: block; font-size: 0.72rem; color: #46617e; margin-top: 8px; }

        /* ===== MAIN ===== */
        .main {
            margin-left: 232px;
            padding: 32px 40px 60px;
        }

        .topbar {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            margin-bottom: 6px;
        }
        h1 { font-size: 2.1rem; font-weight: 800; letter-spacing: -0.4px; color: #ffffff; }
        .subtitle { color: #7d93ad; margin-bottom: 28px; font-size: 0.92rem; }

        .refresh-btn {
            background: rgba(255,255,255,0.05);
            color: #cdd6e4;
            border: 1px solid rgba(255,255,255,0.14);
            padding: 8px 18px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.82rem;
            font-family: inherit;
        }
        .refresh-btn:hover { background: rgba(255,255,255,0.1); }
        .auto-refresh { color: #5f7690; font-size: 0.78rem; margin-left: 10px; }

        .spike-alert {
            background: rgba(229,72,77,0.12);
            border: 1px solid rgba(229,72,77,0.35);
            border-left: 3px solid #f04f56;
            border-radius: 10px;
            padding: 14px 20px;
            margin: 18px 0;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .spike-alert-icon { font-size: 1.2rem; }
        .spike-alert-text strong { color: #ff8a80; font-size: 0.9rem; display: block; margin-bottom: 2px; }
        .spike-alert-text span { color: #d99a97; font-size: 0.8rem; }

        .spike-baseline {
            color: #5f7690;
            font-size: 0.82rem;
            margin: 16px 0 20px;
        }

        /* ===== KPI PILLS ===== */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 22px;
            margin-bottom: 32px;
            margin-top: 10px;
        }
        .stat-pill {
            position: relative;
            border-radius: 46px;
            padding: 16px 22px 16px 60px;
            min-height: 64px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            box-shadow: 0 8px 20px rgba(0,0,0,0.25);
        }
        .stat-pill .icon-badge {
            position: absolute;
            left: -6px;
            top: 50%;
            transform: translateY(-50%);
            width: 50px; height: 50px;
            border-radius: 50%;
            background: #0a1826;
            border: 3px solid rgba(255,255,255,0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.15rem;
        }
        .stat-value { font-size: 1.55rem; font-weight: 800; color: #ffffff; line-height: 1.1; }
        .stat-label {
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.4px;
            text-transform: uppercase;
            margin-top: 3px;
        }

        .stat-pill.clean { background: linear-gradient(135deg, #0e9f6e, #0a7a55); }
        .stat-pill.clean .icon-badge { color: #0e9f6e; }
        .stat-pill.clean .stat-label { color: #c7f5e3; }

        .stat-pill.tier1 { background: linear-gradient(135deg, #d69e2e, #a97b1c); }
        .stat-pill.tier1 .icon-badge { color: #d69e2e; }
        .stat-pill.tier1 .stat-label { color: #ffecc2; }

        .stat-pill.tier2 { background: linear-gradient(135deg, #dd6b20, #b1530f); }
        .stat-pill.tier2 .icon-badge { color: #dd6b20; }
        .stat-pill.tier2 .stat-label { color: #ffdcc2; }

        .stat-pill.tier3 { background: linear-gradient(135deg, #e53e4d, #b32333); }
        .stat-pill.tier3 .icon-badge { color: #e53e4d; }
        .stat-pill.tier3 .stat-label { color: #ffd0d4; }

        /* ===== SECTION PANELS ===== */
        .panel {
            background: #102338;
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px;
            margin-bottom: 26px;
            overflow: hidden;
        }
        .panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 16px 22px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .panel-header .panel-title { font-size: 0.98rem; font-weight: 700; color: #ffffff; }
        .panel-header .panel-count { color: #5f7690; font-weight: 500; }
        .panel-body { padding: 20px 22px; }

        .db-badge {
            font-size: 10.5px;
            font-weight: 700;
            background: rgba(52,211,153,0.12);
            color: #34d399;
            border: 1px solid rgba(52,211,153,0.3);
            padding: 4px 11px;
            border-radius: 20px;
        }
        .db-badge.offline { background: rgba(240,79,86,0.12); color: #f87171; border-color: rgba(240,79,86,0.3); }

        /* ===== SESSION / BLOCKED CARD GRIDS ===== */
        .sessions-grid, .blocked-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 12px;
        }
        .session-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 10px;
            padding: 14px 16px;
        }
        .session-id {
            font-family: 'SF Mono', 'Courier New', monospace;
            font-size: 0.82rem;
            color: #eef2f7;
            font-weight: 600;
        }
        .session-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; font-size: 0.76rem; color: #8ea3bf; }
        .session-meta .ip-badge {
            background: rgba(255,255,255,0.06);
            padding: 2px 8px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            color: #a8bcd4;
        }
        .session-meta .pattern-mini { color: #ffcb6b; font-family: 'Courier New', monospace; font-weight: 600; }

        .blocked-card {
            background: rgba(229,72,77,0.08);
            border: 1px solid rgba(229,72,77,0.25);
            border-left: 3px solid #f04f56;
            border-radius: 10px;
            padding: 15px 17px;
        }
        .blocked-card .blocked-username {
            font-family: 'Courier New', monospace;
            color: #ff8a80;
            font-weight: 700;
            font-size: 0.9rem;
        }
        .blocked-card .blocked-meta {
            margin-top: 10px;
            font-size: 0.76rem;
            color: #b6c3d4;
            display: flex;
            flex-direction: column;
            gap: 3px;
        }
        .blocked-card .blocked-meta strong { color: #eef2f7; }
        .unblock-btn {
            margin-top: 12px;
            width: 100%;
            background: rgba(52,211,153,0.1);
            color: #34d399;
            border: 1px solid rgba(52,211,153,0.3);
            padding: 7px;
            border-radius: 7px;
            cursor: pointer;
            font-size: 0.75rem;
            font-weight: 700;
            font-family: inherit;
        }
        .unblock-btn:hover { background: rgba(52,211,153,0.2); }
        .unblock-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .empty-state {
            text-align: center;
            padding: 36px;
            color: #46617e;
            background: rgba(255,255,255,0.02);
            border: 1px dashed rgba(255,255,255,0.1);
            border-radius: 10px;
            font-size: 0.86rem;
        }

        /* ===== TABLE ===== */
        .table-wrap {
            overflow-x: auto;
            overflow-y: hidden;
            -webkit-overflow-scrolling: touch;
            border-top: 1px solid rgba(255,255,255,0.06);
        }
        .table-wrap::-webkit-scrollbar { height: 10px; }
        .table-wrap::-webkit-scrollbar-track { background: #0d1f33; }
        .table-wrap::-webkit-scrollbar-thumb { background: #2c4258; border-radius: 5px; }
        .table-wrap::-webkit-scrollbar-thumb:hover { background: #3a5771; }
        table { width: 100%; min-width: 1150px; border-collapse: collapse; }
        th, td { padding: 12px 16px; text-align: left; white-space: nowrap; }
        td.reasons-cell { white-space: normal; min-width: 220px; }
        th {
            background: rgba(255,255,255,0.03);
            color: #5f7690;
            font-weight: 700;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            position: sticky;
            top: 0;
        }
        td { border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 0.84rem; color: #eef2f7; }
        tbody tr:last-child td { border-bottom: none; }
        tbody tr:hover { background: rgba(255,255,255,0.025); }

        .pattern-code {
            font-family: 'Courier New', monospace;
            background: rgba(255,255,255,0.06);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.78rem;
            color: #a8bcd4;
        }

        .tier-badge {
            display: inline-block;
            padding: 4px 11px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.7rem;
        }
        .tier-0 { background: rgba(14,159,110,0.15); color: #34d399; }
        .tier-1 { background: rgba(214,158,46,0.15); color: #ffcb6b; }
        .tier-2 { background: rgba(221,107,32,0.15); color: #ffa261; }
        .tier-3 { background: rgba(229,62,77,0.15); color: #ff8a80; }

        .ip-cell { font-family: 'Courier New', monospace; font-size: 0.78rem; color: #7d93ad; }
        .username-cell { font-weight: 700; color: #ffffff; font-size: 0.84rem; }
        .action-cell { font-size: 0.78rem; color: #82b1ff; font-weight: 600; }
        .reasons-cell { font-size: 0.78rem; color: #7d93ad; max-width: 260px; }

        /* ===== MODAL (dark) ===== */
        .modal-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(3, 8, 15, 0.72);
            z-index: 999;
            align-items: center;
            justify-content: center;
        }
        .modal-overlay.open { display: flex; }
        .modal-box {
            background: #102338;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 14px;
            padding: 26px 28px;
            width: 100%;
            max-width: 340px;
            box-shadow: 0 24px 60px rgba(0,0,0,0.5);
        }
        .modal-box h3 { margin: 0 0 4px; font-size: 1rem; color: #ffffff; }
        .modal-box p { margin: 0 0 16px; font-size: 0.8rem; color: #8ea3bf; }
        .modal-box label {
            display: block;
            font-size: 0.75rem;
            font-weight: 600;
            color: #a8bcd4;
            margin-bottom: 4px;
            margin-top: 12px;
        }
        .modal-box input {
            width: 100%;
            background: #0a1826;
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 7px;
            padding: 9px 11px;
            color: #eef2f7;
            font-size: 0.85rem;
            box-sizing: border-box;
        }
        .modal-box input:focus { outline: none; border-color: #4fc3f7; }
        .modal-error {
            display: none;
            margin-top: 10px;
            background: rgba(229,72,77,0.12);
            border: 1px solid rgba(229,72,77,0.35);
            color: #ff8a80;
            font-size: 0.78rem;
            padding: 9px 11px;
            border-radius: 7px;
        }
        .modal-actions { display: flex; gap: 10px; margin-top: 18px; }
        .modal-actions button {
            flex: 1;
            padding: 10px;
            border-radius: 7px;
            border: none;
            font-weight: 700;
            font-size: 0.82rem;
            cursor: pointer;
            font-family: inherit;
        }
        .modal-btn-cancel { background: rgba(255,255,255,0.08); color: #cdd6e4; }
        .modal-btn-cancel:hover { background: rgba(255,255,255,0.14); }
        .modal-btn-confirm { background: #0e9f6e; color: #ffffff; }
        .modal-btn-confirm:hover { background: #0c8a5f; }
        .modal-btn-confirm:disabled { opacity: 0.5; cursor: not-allowed; }

        .two-col {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 22px;
        }

        @media (max-width: 1100px) {
            .two-col { grid-template-columns: 1fr; }
        }
        @media (max-width: 900px) {
            .sidebar { display: none; }
            .main { margin-left: 0; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-brand">
            <div class="logo-sq">T</div>
            <div class="brand-text">Tickago<span>ADMIN CONSOLE</span></div>
        </div>
        <div class="nav-group">
            <div class="nav-label">Monitor</div>
            <a class="nav-link" href="#overview"><span class="nav-icon">◆</span>Overview</a>
            <a class="nav-link" href="#sessions"><span class="nav-icon">◇</span>Active Sessions</a>
            <a class="nav-link" href="#blocked"><span class="nav-icon">⛔</span>Blocked Accounts</a>
            <a class="nav-link" href="#history"><span class="nav-icon">▤</span>Evaluation History</a>
        </div>
        <div class="sidebar-footer">
            <span class="live-badge"><span class="live-dot"></span>LIVE</span>
            <span class="auto-refresh">Auto-refreshes every 5s</span>
        </div>
    </div>

    <div class="main">
        <div id="overview"></div>
        <div class="topbar">
            <div>
                <h1>Bot Detection Monitor</h1>
                <p class="subtitle">Real-time session tracking &amp; account moderation for Tickago</p>
            </div>
            <div>
                <button class="refresh-btn" onclick="location.reload()">Refresh</button>
                <span class="auto-refresh">auto-refresh every 5s</span>
            </div>
        </div>

        {% if spike.is_spike %}
        <div class="spike-alert">
            <div class="spike-alert-icon">⚠</div>
            <div class="spike-alert-text">
                <strong>Traffic spike detected</strong>
                <span>{{ spike.count }} evaluation requests in the last {{ spike.window_seconds }}s (baseline is well under {{ spike.threshold }}) — possible coordinated bot attack.</span>
            </div>
        </div>
        {% else %}
        <div class="spike-baseline">
            Recent traffic: {{ spike.count }} request{{ '' if spike.count == 1 else 's' }} / {{ spike.window_seconds }}s &nbsp;(spike threshold: {{ spike.threshold }}+)
        </div>
        {% endif %}

        <div class="stats-grid">
            <div class="stat-pill clean">
                <div class="icon-badge">✓</div>
                <div class="stat-value">{{ stats.clean }}</div>
                <div class="stat-label">Clean Sessions</div>
            </div>
            <div class="stat-pill tier1">
                <div class="icon-badge">⏱</div>
                <div class="stat-value">{{ stats.tier1 }}</div>
                <div class="stat-label">Tier 1 — Delay</div>
            </div>
            <div class="stat-pill tier2">
                <div class="icon-badge">◈</div>
                <div class="stat-value">{{ stats.tier2 }}</div>
                <div class="stat-label">Tier 2 — CAPTCHA</div>
            </div>
            <div class="stat-pill tier3">
                <div class="icon-badge">⛔</div>
                <div class="stat-value">{{ stats.tier3 }}</div>
                <div class="stat-label">Tier 3 — Blocked</div>
            </div>
        </div>

        <div id="sessions"></div>
        <div class="two-col">
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Active Sessions <span class="panel-count">({{ active_count }})</span></span>
                    <span class="db-badge {{ '' if db_online else 'offline' }}">
                        {{ 'SUPABASE CONNECTED' if db_online else 'DB OFFLINE' }}
                    </span>
                </div>
                <div class="panel-body">
                    {% if active_sessions %}
                    <div class="sessions-grid">
                        {% for sid, session in active_sessions.items() %}
                        <div class="session-card">
                            <div class="session-id">{{ sid[:16] }}...</div>
                            <div class="session-meta">
                                <span class="ip-badge">{{ session.get('ip', 'unknown') }}</span>
                                <span>{{ "%.1f" | format(session.age) }}s ago</span>
                            </div>
                            <div class="session-meta">
                                <span>mouse: {{ session.mouse_movements }}</span>
                                <span class="pattern-mini">{{ session.actions | join('') or 'N/A' }}</span>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <div class="empty-state">No active sessions</div>
                    {% endif %}
                </div>
            </div>

            <div id="blocked"></div>
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Blocked Accounts <span class="panel-count">({{ blocked_accounts | length }})</span></span>
                </div>
                <div class="panel-body">
                    {% if blocked_accounts %}
                    <div class="blocked-grid">
                        {% for user in blocked_accounts %}
                        <div class="blocked-card" id="blocked-card-{{ user.id }}">
                            <div class="blocked-username">{{ user.username }}</div>
                            <div class="blocked-meta">
                                <span><strong>Blocked:</strong> {{ user.blocked_at or 'unknown' }}</span>
                                <span><strong>Ghost tickets:</strong> {{ user.ghost_ticket_count or 0 }}</span>
                                <span><strong>Last IP:</strong> {{ user.last_known_ip }}</span>
                            </div>
                            <button class="unblock-btn" onclick="openUnblockModal({{ user.id }}, '{{ user.username|e }}')" id="unblock-btn-{{ user.id }}">
                                Unblock account
                            </button>
                        </div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <div class="empty-state">No blocked accounts</div>
                    {% endif %}
                </div>
            </div>
        </div>

        <!-- Re-authentication modal: unblocking an account is a sensitive
             action, so the admin must type credentials again here even
             though the browser already has a cached Basic Auth session
             for /monitor itself. -->
        <div class="modal-overlay" id="unblock-modal">
            <div class="modal-box">
                <h3>Confirm account unblock</h3>
                <p id="unblock-modal-target">Re-enter admin credentials to unblock this account.</p>

                <label for="unblock-admin-user">Admin username</label>
                <input type="text" id="unblock-admin-user" autocomplete="username">

                <label for="unblock-admin-pass">Admin password</label>
                <input type="password" id="unblock-admin-pass" autocomplete="current-password">

                <div class="modal-error" id="unblock-modal-error">Invalid admin username or password.</div>

                <div class="modal-actions">
                    <button class="modal-btn-cancel" onclick="closeUnblockModal()">Cancel</button>
                    <button class="modal-btn-confirm" id="unblock-modal-confirm" onclick="submitUnblock()">Confirm unblock</button>
                </div>
            </div>
        </div>

        <div id="history"></div>
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">Evaluation History <span class="panel-count">({{ logs | length }} records)</span></span>
            </div>
            <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Session</th>
                        <th>Username</th>
                        <th>IP</th>
                        <th>Pattern</th>
                        <th>Duration</th>
                        <th>Qty</th>
                        <th>Mouse</th>
                        <th>Score</th>
                        <th>Tier</th>
                        <th>Action</th>
                        <th>Reasons</th>
                    </tr>
                </thead>
                <tbody>
                    {% if logs %}
                        {% for log in logs %}
                        <tr>
                            <td style="font-family:'Courier New',monospace;font-size:0.78rem;color:#5f7690">{{ log.time }}</td>
                            <td><code class="pattern-code">{{ log.session_id[:12] }}...</code></td>
                            <td class="username-cell">{{ log.username }}</td>
                            <td class="ip-cell">{{ log.get('ip', 'unknown') }}</td>
                            <td><span class="pattern-code">{{ log.pattern }}</span></td>
                            <td>{{ "%.1f" | format(log.duration / 1000) }}s</td>
                            <td>{{ log.quantity }}</td>
                            <td>{{ log.mouse_movements }}</td>
                            <td><strong>{{ log.score }}</strong></td>
                            <td><span class="tier-badge tier-{{ log.tier }}">TIER {{ log.tier }}</span></td>
                            <td class="action-cell">{{ log.action }}</td>
                            <td class="reasons-cell">{{ log.reasons | join(', ') if log.reasons is iterable and log.reasons is not string else log.reasons }}</td>
                        </tr>
                        {% endfor %}
                    {% else %}
                        <tr>
                            <td colspan="12" class="empty-state">No evaluations yet. Run a bot to see data.</td>
                        </tr>
                    {% endif %}
                </tbody>
            </table>
            </div>
        </div>
    </div>

    <script>
        let pendingUnblockUserId = null;
        let autoRefreshTimer = setTimeout(() => location.reload(), 5000);

        function openUnblockModal(userId, username) {
            clearTimeout(autoRefreshTimer);
            pendingUnblockUserId = userId;
            document.getElementById('unblock-modal-target').textContent =
                `Re-enter admin credentials to unblock "${username}".`;
            document.getElementById('unblock-admin-user').value = '';
            document.getElementById('unblock-admin-pass').value = '';
            document.getElementById('unblock-modal-error').style.display = 'none';
            document.getElementById('unblock-modal').classList.add('open');
            document.getElementById('unblock-admin-user').focus();
        }

        function closeUnblockModal() {
            pendingUnblockUserId = null;
            document.getElementById('unblock-modal').classList.remove('open');
            autoRefreshTimer = setTimeout(() => location.reload(), 5000);
        }

        function submitUnblock() {
            const userId = pendingUnblockUserId;
            if (!userId) return;

            const adminUser = document.getElementById('unblock-admin-user').value.trim();
            const adminPass = document.getElementById('unblock-admin-pass').value;
            const errorBox  = document.getElementById('unblock-modal-error');
            const confirmBtn = document.getElementById('unblock-modal-confirm');

            if (!adminUser || !adminPass) {
                errorBox.textContent = 'Please enter both admin username and password.';
                errorBox.style.display = 'block';
                return;
            }

            confirmBtn.disabled = true;
            confirmBtn.textContent = 'Verifying...';
            errorBox.style.display = 'none';

            const encoded = btoa(`${adminUser}:${adminPass}`);

            fetch(`/api/admin/unblock/${userId}`, {
                method: 'POST',
                headers: { 'Authorization': `Basic ${encoded}` }
            })
                .then(res => {
                    if (res.status === 401) {
                        throw new Error('unauthorized');
                    }
                    return res.json();
                })
                .then(data => {
                    if (data.status === 'unblocked') {
                        location.reload();
                    } else {
                        errorBox.textContent = 'Failed to unblock: ' + (data.error || 'unknown error');
                        errorBox.style.display = 'block';
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = 'Confirm unblock';
                    }
                })
                .catch(err => {
                    errorBox.textContent = (err.message === 'unauthorized')
                        ? 'Invalid admin username or password.'
                        : 'Network error: ' + err.message;
                    errorBox.style.display = 'block';
                    confirmBtn.disabled = false;
                    confirmBtn.textContent = 'Confirm unblock';
                });
        }

        document.getElementById('unblock-modal').addEventListener('click', (e) => {
            if (e.target.id === 'unblock-modal') closeUnblockModal();
        });
    </script>
</body>
</html>
"""

def derive_action_label(log):
    """What the system actually DID for this row, based on real routing
    logic (see confirm.html/payment.html/captcha.html) - not a guess.
    Distinguishes CAPTCHA-attempt rows (pattern starts with 'CAPTCHA-L')
    from normal full-checkout /evaluate rows, since a Tier 3 result means
    something different depending on which one produced it."""
    pattern = log.get('pattern') or ''
    tier = log.get('tier', 0)

    if pattern.startswith('CAPTCHA-L'):
        # Format: CAPTCHA-L{level}-{type}-{PASS|FAIL}
        parts = pattern.split('-')
        level = parts[1].replace('L', '') if len(parts) > 1 else '?'
        passed = pattern.endswith('PASS')
        if passed:
            return f"CAPTCHA passed (Level {level}), sent to payment"
        elif tier >= 3:
            return "Blocked, failed all 3 CAPTCHA levels"
        else:
            return f"CAPTCHA failed (Level {level}), escalated to Level {int(level) + 1}"

    reasons = log.get('reasons') or []
    if isinstance(reasons, str):
        reasons = [reasons]
    hit_purchase_cap = any('Per-account ticket limit' in r for r in reasons)

    if tier == 0:
        return "Clean"
    elif tier == 1:
        return "3s delay applied"
    elif tier == 2:
        if hit_purchase_cap:
            return "CAPTCHA triggered, account ticket limit reached"
        return "CAPTCHA triggered, suspicious behaviour"
    elif tier == 3:
        action = log.get('action')
        if action == 'blocked':
            return "Blocked, repeat offender"
        elif action == 'ghost':
            return "Ghost ticket issued"
        else:
            # Older rows saved before the 'action' column existed - fall
            # back to the previous (always-correct-for-first-offense)
            # assumption rather than showing a blank/unknown label.
            return "Ghost ticket issued"
    return "-"

def dedupe_logs_by_session(logs):
    """/evaluate fires at two checkpoints per completed purchase - once
    from confirm.html and again from payment.html - so a single
    transaction attempt can produce 2+ rows in evaluation_logs. This
    collapses that down to one row per session_id for dashboard display.
    Assumes `logs` is already ordered most-recent-first, so the first
    row seen per session_id is the furthest-progressed checkpoint for
    that attempt (e.g. the payment-stage entry over the confirm-only
    one, if both exist)."""
    seen = set()
    deduped = []
    for log in logs:
        sid = log.get('session_id')
        if sid in seen:
            continue
        seen.add(sid)
        deduped.append(log)
    return deduped

@app.route('/api/admin/unblock/<int:user_id>', methods=['POST'])
@requires_admin_auth
def admin_unblock(user_id):
    success = unblock_account(user_id)
    if success:
        return jsonify({'status': 'unblocked', 'user_id': user_id})
    return jsonify({'error': 'Failed to unblock account'}), 500

@app.route('/monitor')
@requires_admin_auth
def monitor_dashboard():
    # Try to load from Supabase, fallback to in-memory
    if supabase:
        logs = load_logs_from_db()
        db_online = True
    else:
        logs = list(reversed(evaluation_logs[-50:]))
        db_online = False

    logs = dedupe_logs_by_session(logs)
    username_map = get_username_map()
    for log in logs:
        log['action'] = derive_action_label(log)
        log['username'] = username_map.get(log.get('user_id')) or ('Guest' if log.get('user_id') is None else f"#{log.get('user_id')}")

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

    spike = detect_traffic_spike()
    blocked_accounts = get_blocked_accounts()

    return render_template_string(
        DASHBOARD_HTML,
        stats=stats,
        active_sessions=active_sessions,
        active_count=len(sessions),
        logs=logs,
        db_online=db_online,
        spike=spike,
        blocked_accounts=blocked_accounts
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
        'ip': get_client_ip(),
        'user_agent': request.headers.get('User-Agent', ''),
        'quantity': 1,
        'pages_visited': []
    }
    save_session_to_db(session_id, sessions[session_id])
    print(f"\n[+] New session: {session_id[:16]}... from {get_client_ip()}")
    response = make_response(jsonify({'session_id': session_id, 'status': 'initialized'}))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


@app.route('/api/track-action', methods=['POST'])
def track_action():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    action = data.get('action', '')

    # FIX: Ensure missing sessions safely attempt rehydration instead of crashing/blocking
    if session_id and session_id not in sessions:
        rehydrated = load_session_from_db(session_id)
        if rehydrated:
            sessions[session_id] = rehydrated

    if not session_id or session_id not in sessions:
        # Create an emergency fallback entry if completely absent
        sessions[session_id] = {
            'start_time': time.time(),
            'actions': [],
            'timestamps': [],
            'mouse_movements': 0,
            'ip': get_client_ip(),
            'user_agent': request.headers.get('User-Agent', ''),
            'quantity': 1,
            'pages_visited': []
        }

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

    # Keep Supabase in sync with every update, not just at creation -
    # otherwise rehydration above would only ever recover an empty
    # pattern (the DB copy was stuck at whatever it looked like when
    # /api/init-session first ran).
    save_session_to_db(session_id, session)

    response = make_response(jsonify({'status': 'tracked'}))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


@app.route('/api/captcha-attempt', methods=['POST'])
def captcha_attempt():
    data = request.get_json() or {}
    session_id = data.get('session_id') or 'unknown'
    level = int(data.get('level', 1))
    challenge_type = data.get('type', 'unknown')
    success = bool(data.get('success'))
    ip_address = get_client_ip()

    if success:
        tier    = 0
        score   = 0
        reasons = [f"Passed CAPTCHA level {level} ({challenge_type})"]
    elif level >= 3:
        # Failed the last, hardest level - this is the block/kick case.
        tier    = 3
        score   = 100
        reasons = ["Blocked: failed all 3 CAPTCHA levels"]
    else:
        # Escalating but not yet blocked - still worth a mid-tier flag.
        tier    = 2
        score   = 30 * level
        reasons = [f"Failed CAPTCHA level {level} ({challenge_type}) - escalating"]

    print("\n" + "=" * 50)
    print(f"CAPTCHA ATTEMPT: level {level} ({challenge_type}) - {'PASS' if success else 'FAIL'}")
    print(f"   Session: {session_id[:16]}...")
    print("=" * 50 + "\n")

    log_entry = {
        'time':            datetime.now().strftime('%H:%M:%S'),
        'session_id':      session_id,
        'pattern':         f"CAPTCHA-L{level}-{challenge_type}-{'PASS' if success else 'FAIL'}",
        'duration':        0,
        'quantity':        0,
        'mouse_movements': 0,
        'score':           score,
        'tier':            tier,
        'reasons':         reasons,
        'ip':              ip_address,
        'user_id':         session.get('user_id')
    }
    evaluation_logs.append(log_entry)
    save_logs()
    save_evaluation_to_db(log_entry)

    response = make_response(jsonify({'status': 'logged', 'tier': tier}))
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
    evaluate_call_times.append(time.time())

    # Backstop matching confirm_seat() - confirm.html/payment.html are
    # already gated at the page level, so a real visitor always has a
    # session by the time this fires. This catches anything hitting the
    # endpoint directly.
    if not session.get('user_id'):
        return jsonify({"error": "not_authenticated", "redirect": "/login"}), 401

    data = request.get_json() or {}
    session_id = data.get('session_id')
    force_tier = data.get('force_tier')
    ip_address = get_client_ip()

    # Unconditional block check - MUST run before any scoring, not
    # nested inside the Tier 3 escalation logic further down. That
    # placement meant a blocked account behaving completely normally on
    # a later attempt (not independently scoring as suspicious THIS
    # time) sailed straight through undetected, since the is_blocked
    # check never even ran unless the current request also happened to
    # score as Tier 3 on its own. Being blocked means blocked, full
    # stop - not "blocked again only if you also act suspiciously again."
    blocked_user = get_current_user()
    if blocked_user and blocked_user.get('is_blocked'):
        print(f"\n[BLOCKED ACCOUNT] user_id={blocked_user['id']} ({blocked_user.get('username')}) attempted /evaluate - hard blocking regardless of current behavior")
        log_entry = {
            'time':            datetime.now().strftime('%H:%M:%S'),
            'session_id':      session_id or 'unknown',
            'pattern':         data.get('pattern', 'N/A'),
            'duration':        data.get('duration', 0),
            'quantity':        data.get('quantity', 1),
            'mouse_movements': data.get('mouse_movements', 0),
            'score':           100,
            'tier':            3,
            'reasons':         ["Blocked account attempted checkout"],
            'ip':              ip_address,
            'action':          'blocked',
            'user_id':         blocked_user['id']
        }
        evaluation_logs.append(log_entry)
        save_logs()
        save_evaluation_to_db(log_entry)

        response = make_response(jsonify({
            'score': 100,
            'tier': 3,
            'reasons': ["Blocked account attempted checkout"],
            'redirect': 'error.html'
        }))
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

    # Detection scoring always trusts the client-supplied telemetry below -
    # this is a deliberate choice, not an oversight (see FYP write-up:
    # server-authoritative tracking was considered but would require every
    # page's business-logic function, not just click handlers, to report
    # actions, and would need bot1/bot2/stress_test rebuilt + revalidated
    # against it). Whether session_id matches a real tracked session only
    # changes what gets *logged* below, never what gets *scored*.
    pattern         = data.get('pattern', '')
    duration        = data.get('duration', 0)
    quantity        = int(data.get('quantity', 1))
    qty_speed       = data.get('qty_speed', 9999)
    mouse_movements = data.get('mouse_movements', 0)

    if session_id and session_id not in sessions:
        rehydrated = load_session_from_db(session_id)
        if rehydrated:
            sessions[session_id] = rehydrated
            print(f"[Session] Rehydrated {session_id[:12]}... from Supabase (in-memory copy was missing)")

    if not session_id or session_id not in sessions:
        # No real tracked session (e.g. init-session never fired, or this
        # request came from a script hitting /evaluate directly) - fall
        # back to a throwaway id just so every row still has one.
        session_id = 'LEGACY-' + secrets.token_urlsafe(8)

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
            'ip':              ip_address,
            'action':          'ghost' if tier == 3 else 'none',
            'user_id':         session.get('user_id')
        }
        evaluation_logs.append(log_entry)
        save_logs()
        save_evaluation_to_db(log_entry)

        if tier == 3 and session_id in sessions:
            del sessions[session_id]

        response = make_response(jsonify({
            'score': score,
            'tier': tier,
            'reasons': reasons,
            'action': 'ghost' if tier == 3 else 'none',
            'redirect': 'ghost_ticket.html' if tier == 3 else None
        }))
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

    # New-account signal: weighted, not a hard override. A brand new
    # account buying immediately isn't inherently suspicious - most real
    # buyers for a hot on-sale event register minutes (or seconds)
    # before purchasing. This only matters when COMBINED with other
    # bot-like behavior above (no mouse movement, instant qty, known-bad
    # pattern) - those already push the score up on their own, this just
    # adds a bit more weight when a fresh account is also part of the
    # picture, the same way every other signal here works.
    current_user = get_current_user()
    if current_user:
        try:
            account_created = datetime.fromisoformat(current_user['created_at'][:26])
            account_age_seconds = (datetime.utcnow() - account_created).total_seconds()
        except Exception:
            account_age_seconds = None

        if account_age_seconds is not None and account_age_seconds < 30:
            score += 20
            reasons.append(f"New account (created {int(account_age_seconds)}s ago)")

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
        print("TIER 3: Evaluating ghost-ticket vs hard-block escalation")
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

    # Per-account lifetime ticket cap: this one stays a hard rule (not a
    # weighted score) since exceeding your own stated purchase limit is
    # an unambiguous policy violation, unlike account age which is only
    # weak circumstantial evidence.
    if current_user:
        already_sold = count_tickets_sold_to_user(current_user['id'])
        if already_sold + quantity > 5:
            if tier < 2:
                tier = 2
            reasons.append(
                f"Per-account ticket limit: {already_sold} already purchased + {quantity} requested exceeds 5-ticket cap"
            )
            print(f"PURCHASE LIMIT: {already_sold} already sold to user_id={current_user['id']}, +{quantity} requested -> Tier {tier}")

    print(f"\n   Final Score : {score}")
    print(f"   Tier        : {tier}")
    print(f"   Reasons     : {reasons}")
    print("=" * 60 + "\n")

    # ------------------------------------------------------------
    # TIER 3 ESCALATION: first offense stays deceptive (ghost ticket),
    # a REPEAT offense - by the same account OR the same IP - gets
    # hard-blocked instead. This is deliberately keyed off two
    # independent signals rather than just one:
    #   - account (ghost_ticket_count / is_blocked): strongest signal
    #     now that checkout requires login, but a bot that registers a
    #     fresh throwaway account each run would otherwise look like a
    #     first-time offender every single time.
    #   - IP (count_tier3_hits_by_ip): catches that "fresh account
    #     every run" case, since the underlying script/machine is
    #     still the same even when the account isn't.
    # A single IP match isn't enough to block on its own (shared NAT /
    # mobile carriers mean multiple real people can share an IP), so it
    # requires >=2 prior IP hits, while a single prior account offense
    # is enough (an account, unlike an IP, isn't shared by strangers).
    # ------------------------------------------------------------
    action = "none"
    redirect_page = None

    resolved_user_id = session.get('user_id')

    if tier == 3:
        current_user = current_user or get_current_user()
        prior_ghosts = 0
        already_blocked = False

        if current_user:
            prior_ghosts = current_user.get('ghost_ticket_count') or 0
            already_blocked = bool(current_user.get('is_blocked'))

        ip_tier3_hits = count_tier3_hits_by_ip(ip_address)

        is_repeat_offender = already_blocked or prior_ghosts >= 1 or ip_tier3_hits >= 2

        if is_repeat_offender:
            action = "blocked"
            redirect_page = "error.html"
            reasons.append("Repeat offender - account or IP previously triggered Tier 3")
            print(f"TIER 3 ESCALATION: BLOCKING (prior_ghosts={prior_ghosts}, ip_hits={ip_tier3_hits}, already_blocked={already_blocked})")

            if supabase and current_user:
                try:
                    resolved_user_id = current_user['id']  # pin it down before clear()
                    supabase.table("users").update({"is_blocked": True, "blocked_at": now_myt_iso()}).eq("id", current_user['id']).execute()
                except Exception as e:
                    print(f"[DB] Failed to flag account as blocked: {e}")

            session.clear()  # force re-login (or rather, re-registration, since this account is now dead)
        else:
            action = "ghost"
            redirect_page = "ghost_ticket.html"
            print(f"TIER 3 ESCALATION: GHOST TICKET (first offense - prior_ghosts={prior_ghosts}, ip_hits={ip_tier3_hits})")

            if supabase and current_user:
                try:
                    supabase.table("users").update({
                        "ghost_ticket_count": prior_ghosts + 1,
                        "last_ghost_ticket_at": now_myt_iso()
                    }).eq("id", current_user['id']).execute()
                except Exception as e:
                    print(f"[DB] Failed to update ghost_ticket_count: {e}")

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
        'ip':              ip_address,
        'action':          action,
        'user_id':         resolved_user_id
    }
    evaluation_logs.append(log_entry)
    save_logs()
    save_evaluation_to_db(log_entry)

    if tier == 3 and session_id in sessions:
        del sessions[session_id]

    response = make_response(jsonify({
        'score': score,
        'total_score': total_score,
        'tier': tier,
        'reasons': reasons,
        'carry_forward': carry_forward,
        'action': action,
        'redirect': redirect_page
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
    print(f"   Supabase      : {'Connected' if supabase else 'Not configured'}")
    print(f"   Restored      : {len(evaluation_logs)} saved evaluation(s)")
    print(f"   Learned       : {len(learned_patterns)} self-learned pattern(s)")
    print("=" * 60 + "\n")

    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)

# Init Supabase on module load (for Render/Gunicorn)
init_supabase()