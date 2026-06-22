// session.js - Server-side session tracking

let SESSION_ID = null;
let mouseMovementCount = 0;

// Track mouse movements
document.addEventListener('mousemove', () => {
    mouseMovementCount++;
});

// Initialize session
async function initSession() {
    SESSION_ID = sessionStorage.getItem('server_session_id');
    
    if (!SESSION_ID) {
        try {
            const response = await fetch(`${NGROK_URL}/api/init-session`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'ngrok-skip-browser-warning': 'true'
                }
            });
            const data = await response.json();
            SESSION_ID = data.session_id;
            sessionStorage.setItem('server_session_id', SESSION_ID);
            console.log('✅ Session initialized:', SESSION_ID.substring(0, 16));
        } catch (err) {
            console.error('❌ Session init failed:', err);
        }
    }
}

// Track an action
async function trackAction(actionCode, extraData = {}) {
    if (!SESSION_ID) {
        console.warn('No session - tracking skipped');
        return;
    }
    
    const payload = {
        session_id: SESSION_ID,
        action: actionCode,
        mouse_movements: mouseMovementCount,
        page: window.location.pathname.split('/').pop(),
        ...extraData
    };
    
    try {
        await fetch(`${NGROK_URL}/api/track-action`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify(payload)
        });
    } catch (err) {
        console.error('Track failed:', err);
    }
}

// Evaluate at checkout
async function evaluateSession(extraData = {}) {
    const payload = {
        session_id: SESSION_ID,
        mouse_movements: mouseMovementCount,
        ...extraData
    };
    
    try {
        const response = await fetch(`${NGROK_URL}/evaluate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify(payload)
        });
        return await response.json();
    } catch (err) {
        console.error('Evaluation failed:', err);
        return { tier: 0, score: 0, reasons: [] };
    }
}

// Auto-initialize
document.addEventListener('DOMContentLoaded', initSession);
