//telemetry

// telemetry.js - Captures page actions and sends them to your Flask backend
(function() {
    const pageLoadTime = Date.now();
    let clickCount = 0;

    // ==========================================
    // 🆔 SERVER SESSION BOOTSTRAP (NEW)
    // ==========================================
    // Separate from the 'session_id' key used for seat reservation/hold
    // tracking (do not touch that one). This is purely so the backend's
    // `sessions` dict + Supabase `sessions` table get populated for real,
    // as originally designed. It does NOT feed /evaluate's scoring - that
    // still reads pattern/quantity/mouse straight from localStorage like
    // before, so bot1/bot2/stress_test bots keep working unchanged.
    const FYP_SESSION_KEY = 'fyp_session_id';

    function bootstrapSession() {
        const existing = localStorage.getItem(FYP_SESSION_KEY);
        if (existing) return; // already have one for this journey (home.html clears it on a fresh visit)
        if (typeof API_URL === 'undefined') return;

        fetch(`${API_URL}/api/init-session`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.session_id) {
                    localStorage.setItem(FYP_SESSION_KEY, data.session_id);
                }
            })
            .catch(err => console.warn('init-session failed:', err));
    }

    bootstrapSession();

    // Exposed so each page's existing pattern-building code (home.html,
    // select.html, confirm.html, payment.html) can report the same action
    // letter to the server alongside its localStorage update. Fire-and-
    // forget - this is logging only, never blocks navigation/checkout.
    window.trackAction = function(action) {
        if (typeof API_URL === 'undefined') return;
        const sessionId = localStorage.getItem(FYP_SESSION_KEY);
        if (!sessionId) return;

        fetch(`${API_URL}/api/track-action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                action: action,
                page: window.location.pathname.split('/').pop() || 'home.html',
                quantity: parseInt(localStorage.getItem('selected_qty') || '1'),
                mouse_movements: typeof window.getMouseMoveCount === 'function'
                    ? window.getMouseMoveCount()
                    : parseInt(localStorage.getItem('fyp_mouse_moves') || '0')
            })
        }).catch(err => console.warn('track-action failed:', err));
    };

    // ==========================================
    // 🖱️ MOUSE MOVEMENT TRACKING (NEW)
    // ==========================================
    // Persists a cumulative mouse-movement count across the whole journey
    // (home -> select -> confirm -> payment) via localStorage, the same way
    // fyp_pattern already does. Real humans generate lots of these events;
    // Selenium bots calling functions via execute_script() never do, since
    // they don't dispatch real mousemove input events.
    let _mouseMoveBuffer = 0;

    document.addEventListener('mousemove', () => {
        _mouseMoveBuffer++;
    });

    function flushMouseMoves() {
        if (_mouseMoveBuffer > 0) {
            const current = parseInt(localStorage.getItem('fyp_mouse_moves') || '0');
            localStorage.setItem('fyp_mouse_moves', current + _mouseMoveBuffer);
            _mouseMoveBuffer = 0;
        }
    }

    // Flush the buffer to localStorage periodically instead of on every
    // single pixel of movement, to avoid hammering localStorage.
    setInterval(flushMouseMoves, 500);

    // Exposed so other pages can grab an up-to-the-moment count (forces a
    // flush first so nothing in the buffer gets missed right before checkout).
    window.getMouseMoveCount = function() {
        flushMouseMoves();
        return parseInt(localStorage.getItem('fyp_mouse_moves') || '0');
    };

    // Track every click automatically on the current page
    document.addEventListener('click', (event) => {
        clickCount++;
        
        const payload = {
            page: window.location.pathname.split('/').pop() || 'home.html',
            timeSinceLoad: (Date.now() - pageLoadTime) / 1000, // seconds
            totalClicksOnPage: clickCount,
            elementClicked: event.target.tagName + (event.target.className ? `.${event.target.className.replace(/\s+/g, '.')}` : '')
        };

        console.log("Telemetry Event Captured:", payload);

        // Send to Flask backend via the ngrok tunnel address from config.js
        if (typeof API_URL !== 'undefined') {
            fetch(`${API_URL}/detect`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            })
            .then(res => console.log("Data sent successfully over tunnel!"))
            .catch(err => console.error("Tunnel transmission failed:", err));
        }
    });
})();