from flask import Flask, jsonify, make_response, request, render_template_string, send_from_directory
from flask_cors import CORS
import time
import secrets
import json
import os
from datetime import datetime

# ==========================================
# 📁 SERVE STATIC FILES (HTML/JS/CSS)
# ==========================================
# By telling Flask where the frontend files live, we can serve everything
# through a single port (8000) instead of needing VS Code Live Server on
# 5500 at the same time. One ngrok tunnel covers everything.
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'waitingroom.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)

# ==========================================
# 🗄️ IN-MEMORY SESSION STORAGE
# ==========================================
sessions = {}

# ==========================================
# 💾 PERSISTENT EVALUATION LOG
# ==========================================
# evaluation_logs used to be a plain in-memory list, which meant any server
# restart (manual, or Flask's own debug auto-reloader) silently wiped the
# whole history. It's now backed by a small JSON file next to this script,
# loaded on startup and re-saved after every evaluation, so the log survives
# restarts.
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evaluation_logs.json')

def load_logs():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load saved evaluation logs ({e}); starting fresh.")
    return []

def save_logs():
    try:
        with open(LOG_FILE, 'w') as f:
            json.dump(evaluation_logs, f)
    except Exception as e:
        print(f"⚠️  Could not save evaluation logs: {e}")

evaluation_logs = load_logs()  # Stores all evaluation results for monitoring

# ==========================================
# ⏱️ SYSTEM-SYNCHRONIZED MASTER CLOCK
# ==========================================
# How many seconds from Flask startup until the sale goes live.
# Change this one number to adjust the countdown for your demo.
SALE_COUNTDOWN_SECONDS = 120   # 2 minutes

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

# Original hand-picked seed patterns
SEED_PATTERNS = ["HADSQSC", "HADSSQC", "HADSSSQC", "HADSQQQC"]
for p in SEED_PATTERNS:
    bot_tree.insert(p)

# ==========================================
# 🧠 SELF-LEARNING PATTERN BLACKLIST
# ==========================================
# Whenever a session is confidently scored as Tier 3 (ghost ticket - the
# highest-confidence bot tier), its exact action-string pattern gets added
# here, persisted to disk, and inserted into the trie above. From then on,
# ANY future session producing that same pattern gets the trie's pattern-
# match bonus too, even if nobody hand-typed that pattern in advance.
PATTERNS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'learned_patterns.json')

def load_learned_patterns():
    if os.path.exists(PATTERNS_FILE):
        try:
            with open(PATTERNS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load learned patterns ({e}); starting fresh.")
    return []

def save_learned_patterns():
    try:
        with open(PATTERNS_FILE, 'w') as f:
            json.dump(learned_patterns, f)
    except Exception as e:
        print(f"⚠️  Could not save learned patterns: {e}")

learned_patterns = load_learned_patterns()
for p in learned_patterns:
    bot_tree.insert(p)

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
        .stat-value { 
            font-size: 2.5rem; 
            font-weight: bold; 
            color: #00d4ff; 
        }
        .stat-label { 
            color: #888; 
            font-size: 0.9rem; 
            margin-top: 5px; 
        }
        .stat-card.tier1 .stat-value { color: #ffc107; }
        .stat-card.tier2 .stat-value { color: #ff9800; }
        .stat-card.tier3 .stat-value { color: #f44336; }
        .stat-card.clean .stat-value { color: #4caf50; }
        
        .section-title {
            color: #00d4ff;
            margin: 30px 0 15px 0;
            padding-bottom: 10px;
            border-bottom: 1px solid #0f3460;
        }
        
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
        th { 
            background: #0f3460; 
            color: #00d4ff; 
            font-weight: 600;
        }
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
        
        .auto-refresh {
            color: #888;
            font-size: 0.85rem;
            margin-left: 15px;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
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
        }
        .session-item:last-child { border-bottom: none; }
        .session-id { 
            font-family: monospace; 
            color: #00d4ff; 
        }
        .session-actions {
            font-family: monospace;
            color: #ffc107;
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
    
    <h2 class="section-title">🔴 Active Sessions ({{ active_count }})</h2>
    <div class="active-sessions">
        {% if active_sessions %}
            {% for sid, session in active_sessions.items() %}
            <div class="session-item">
                <span class="session-id">{{ sid[:16] }}...</span>
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
    
    <h2 class="section-title">📋 Evaluation History</h2>
    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Session ID</th>
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
                    <td><span class="pattern-code">{{ log.pattern }}</span></td>
                    <td>{{ "%.1f" | format(log.duration / 1000) }}s</td>
                    <td>{{ log.quantity }}</td>
                    <td>{{ log.mouse_movements }}</td>
                    <td><strong>{{ log.score }}</strong></td>
                    <td><span class="tier-badge tier-{{ log.tier }}">Tier {{ log.tier }}</span></td>
                    <td>{{ log.reasons | join(', ') }}</td>
                </tr>
                {% endfor %}
            {% else %}
                <tr>
                    <td colspan="9" class="empty-state">No evaluations yet. Run a bot to see data.</td>
                </tr>
            {% endif %}
        </tbody>
    </table>
    
    <script>
        // Auto-refresh every 5 seconds
        setTimeout(() => location.reload(), 5000);
    </script>
</body>
</html>
"""

@app.route('/monitor')
def monitor_dashboard():
    """Visual dashboard to monitor all sessions and detections."""
    
    # Calculate statistics
    stats = {'clean': 0, 'tier1': 0, 'tier2': 0, 'tier3': 0}
    for log in evaluation_logs:
        if log['tier'] == 0:
            stats['clean'] += 1
        elif log['tier'] == 1:
            stats['tier1'] += 1
        elif log['tier'] == 2:
            stats['tier2'] += 1
        elif log['tier'] == 3:
            stats['tier3'] += 1
    
    # Prepare active sessions with age
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
        logs=list(reversed(evaluation_logs[-50:]))  # Last 50, newest first
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
    
    data = {
        "countdown": remaining_seconds,
        "isSaleLive": is_live
    }
    
    response = make_response(jsonify(data))
    response.headers["ngrok-skip-browser-warning"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "ngrok-skip-browser-warning, Content-Type"
    return response


@app.route('/api/init-session', methods=['POST'])
def init_session():
    """Create a new session when user enters the site."""
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
    
    print(f"\n[+] New session created: {session_id[:16]}...")
    
    response = make_response(jsonify({
        'session_id': session_id,
        'status': 'initialized'
    }))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


@app.route('/api/track-action', methods=['POST'])
def track_action():
    """Track each user action server-side."""
    data = request.get_json() or {}
    session_id = data.get('session_id')
    action = data.get('action', '')
    
    if not session_id or session_id not in sessions:
        response = make_response(jsonify({'error': 'Invalid session'}), 400)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response
    
    session = sessions[session_id]
    elapsed = time.time() - session['start_time']
    
    # Record the action
    if action:
        session['actions'].append(action)
        session['timestamps'].append(elapsed)
    
    # Update other tracked data
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
    """Log successful CAPTCHA verification."""
    data = request.get_json() or {}
    
    session_id = data.get('session_id', 'unknown')
    method = data.get('method', 'unknown')
    proof = data.get('proof', {})
    
    print("\n" + "=" * 50)
    print("✅ CAPTCHA VERIFICATION SUCCESS")
    print("=" * 50)
    print(f"   Session: {session_id[:16]}...")
    print(f"   Method:  {method}")
    
    if method == 'pow':
        print(f"   Nonce:   {proof.get('nonce', 'N/A')}")
        print(f"   Hash:    {proof.get('hash', 'N/A')[:20]}...")
        print(f"   Time:    {proof.get('time', 'N/A')}s")
    
    print("=" * 50 + "\n")
    
    response = make_response(jsonify({'status': 'verified'}))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


@app.route('/detect', methods=['POST'])
def detect_agent():
    """Legacy telemetry endpoint for backwards compatibility."""
    data = request.get_json() or {}
    print(f"\n[Telemetry] {data}")
    
    response = make_response(jsonify({"status": "captured"}))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


@app.route('/evaluate', methods=['POST'])
def evaluate_session():
    """Evaluate a session for bot-like behavior."""
    data = request.get_json() or {}
    session_id = data.get('session_id')
    force_tier = data.get('force_tier')
    
    # Fallback for old client-side approach (backwards compatibility)
    if not session_id or session_id not in sessions:
        # Use client-provided data as fallback
        pattern = data.get('pattern', '')
        duration = data.get('duration', 0)
        quantity = int(data.get('quantity', 1))
        qty_speed = data.get('qty_speed', 9999)
        mouse_movements = data.get('mouse_movements', 0)
        session_id = 'LEGACY-' + secrets.token_urlsafe(8)
    else:
        # Use server-side tracked data (trusted)
        session = sessions[session_id]
        pattern = ''.join(session['actions'])
        duration = (time.time() - session['start_time']) * 1000
        quantity = session['quantity']
        mouse_movements = session['mouse_movements']
        qty_speed = data.get('qty_speed', 9999)
    
    print("\n" + "=" * 60)
    print("📊 EVALUATION REQUEST")
    print("=" * 60)
    print(f"   Session ID    : {session_id[:20]}...")
    print(f"   Pattern       : {pattern}")
    print(f"   Duration      : {duration:.0f}ms")
    print(f"   Quantity      : {quantity}")
    print(f"   Mouse Moves   : {mouse_movements}")
    print(f"   Qty Speed     : {qty_speed}ms")
    print("=" * 60)
    
    # ==========================================
    # CLIENT-SIDE FAST-PATH SHORTCUT
    # ==========================================
    # confirm.html has its own instant "Tier 1" gate that fires before this
    # endpoint is even reached, purely so the user/bot isn't kept waiting.
    # It used to just alert() and return, which meant that detection never
    # got logged here at all. Now it pings this endpoint with force_tier
    # set, so the dashboard reflects it without re-running the full scorer
    # (which could disagree with the tier the alert already showed).
    if force_tier is not None:
        tier = int(force_tier)
        score = {1: 30, 2: 60, 3: 100}.get(tier, 0)
        reasons = ["Client-side fast-path: HADSQC pattern + low mouse activity under 15s"]

        print(f"⚡ CLIENT FAST-PATH: Tier {tier} (logged without server re-scoring)")
        print("=" * 60 + "\n")

        evaluation_logs.append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'session_id': session_id,
            'pattern': pattern or 'N/A',
            'duration': duration,
            'quantity': quantity,
            'mouse_movements': mouse_movements,
            'score': score,
            'tier': tier,
            'reasons': reasons
        })
        save_logs()

        if session_id in sessions:
            del sessions[session_id]

        response = make_response(jsonify({
            'score': score,
            'tier': tier,
            'reasons': reasons
        }))
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response
    
    score = 0
    reasons = []
    
    # ==========================================
    # TIER 1 DETECTION - SPEED
    # ==========================================
    if pattern == "HADSQC" and quantity == 1 and duration < 15000:
        score += 30
        reasons.append("Elevated interaction speed")
    
    # ==========================================
    # TIER 2 DETECTION - BULK PURCHASE
    # ==========================================
    # Only flag quantity = 5 (the absolute maximum per customer).
    # Buying 4 tickets is still within normal range for a group purchase
    # — flagging it with enough points to hit Tier 1 on its own was
    # causing false positives for legitimate human buyers.
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
    
    # ==========================================
    # TIER 3 DETECTION - PATTERN MATCHING
    # ==========================================
    if bot_tree.search(pattern):
        score += 40
        reasons.append(f"Known bot pattern: {pattern}")
    
    # ==========================================
    # MOUSE MOVEMENT ANALYSIS
    # ==========================================
    if mouse_movements == 0:
        score += 35
        reasons.append("Zero mouse movement detected")
    elif mouse_movements < 10:
        score += 15
        reasons.append(f"Minimal mouse activity ({mouse_movements})")
    
    # ==========================================
    # TIMING ANALYSIS
    # ==========================================
    # A motivated human can realistically complete checkout in 10-15s.
    # Only flag under 8s as impossible, and under 12s as abnormal.
    if duration < 8000:
        score += 20
        reasons.append(f"Impossible speed ({duration:.0f}ms)")
    elif duration < 12000:
        score += 15
        reasons.append(f"Abnormally fast ({duration:.0f}ms)")
    
    # ==========================================
    # HONEYPOT CHECK
    # ==========================================
    if "ghost_ticket" in pattern.lower():
        score += 100
        reasons.append("Honeypot triggered")
    
    # ==========================================
    # QUEUE BYPASS DETECTION
    # ==========================================
    # 'X' is stamped into the pattern by select.html when the sale_verified
    # session token is missing — meaning the user jumped straight to
    # select.html without clearing the waiting room or the salelive gate.
    # Bots that bypass the queue entirely always trigger this.
    if 'X' in pattern:
        score += 50
        reasons.append("Queue gate bypassed (skipped waiting room)")
    
    # ==========================================
    # DETERMINE RESPONSE TIER
    # ==========================================
    if score >= 100:
        tier = 3
        print("🚫 TIER 3: Redirecting to ghost ticket")

        if pattern and not bot_tree.search(pattern):
            bot_tree.insert(pattern)
            if pattern not in learned_patterns:
                learned_patterns.append(pattern)
                save_learned_patterns()
                print(f"🧠 LEARNED NEW PATTERN: '{pattern}' added to the bot-pattern blacklist")

    elif score >= 60:
        tier = 2
        print("🔒 TIER 2: CAPTCHA required")
    elif score >= 30:
        tier = 1
        print("⚠️  TIER 1: Applying 3-second delay")
        time.sleep(3)
    else:
        tier = 0
        reasons.append("No suspicious activity")
        print("✅ TIER 0: Clean session")
    
    print(f"\n   Final Score: {score}")
    print(f"   Tier: {tier}")
    print(f"   Reasons: {reasons}")
    print("=" * 60 + "\n")
    
    # Log this evaluation for monitoring
    evaluation_logs.append({
        'time': datetime.now().strftime('%H:%M:%S'),
        'session_id': session_id,
        'pattern': pattern or 'N/A',
        'duration': duration,
        'quantity': quantity,
        'mouse_movements': mouse_movements,
        'score': score,
        'tier': tier,
        'reasons': reasons
    })
    save_logs()
    
    # Clean up session after evaluation
    if session_id in sessions:
        del sessions[session_id]
    
    response = make_response(jsonify({
        'score': score,
        'tier': tier,
        'reasons': reasons
    }))
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


# ==========================================
# 🚀 SERVER START
# ==========================================
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🛡️  BOT DETECTION SERVER STARTING")
    print("=" * 60)
    print(f"   API Server    : [localhost](http://localhost:8000)")
    print(f"   Monitor       : [localhost](http://localhost:8000/monitor)")
    print(f"   Restored      : {len(evaluation_logs)} saved evaluation(s) from {LOG_FILE}")
    print(f"   Learned       : {len(learned_patterns)} self-learned pattern(s) from {PATTERNS_FILE}")
    print("=" * 60 + "\n")
    
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)