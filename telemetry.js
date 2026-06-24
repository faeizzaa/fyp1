//telemetry

// telemetry.js - Captures page actions and sends them to your Flask backend
(function() {
    const pageLoadTime = Date.now();
    let clickCount = 0;

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