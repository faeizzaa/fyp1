import time
import os
import shutil
import platform
import random
import string
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BEHAVIOR_INFO = {
    "tier1": {
        "title": "Tier 1 Trigger",
        "desc": "Fast single seat, no mouse moves",
        "expected": "Tier 1 (Artificial Delay)",
    },
    "tier2": {
        "title": "Tier 2 Trigger",
        "desc": "Bulk quantity (5), instant selection speed",
        "expected": "Tier 2 (CAPTCHA Challenge)",
    },
    "tier3": {
        "title": "Tier 3 Trigger",
        "desc": "Known-bad pattern + max qty + instant speed",
        "expected": "Tier 3 (Ghost Ticket)",
    },
}

def print_header(bot_id, behavior, target_url):
    info = BEHAVIOR_INFO.get(behavior, {"title": behavior, "desc": "-", "expected": "-"})
    line = "=" * 57
    print(line)
    print(f"  Bot {bot_id} - {info['title']}")
    print(f"  {info['desc']}")
    print(f"  Expected: {info['expected']}")
    print(f"  Target:   {target_url}")
    print(f"  OS:       {platform.system()}")
    print(line)
    print()

def register_throwaway_account(driver, bot_id, fixed_credentials=None):
    """Registers a new account by default. If fixed_credentials=(username,
    password) is passed, tries /login with those creds instead - used by
    run_repeat_offender_test() so the SAME account can attempt Tier 3
    twice, to verify the 2nd attempt gets hard-blocked instead of
    ghost-ticketed again."""
    if fixed_credentials:
        username, password = fixed_credentials
        print(f"[Phase 0] Logging in as existing account '{username}'...")
        login_script = """
            const callback = arguments[arguments.length - 1];
            fetch('/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({username: arguments[0], password: arguments[1]})
            })
            .then(res => res.json().then(data => ({ok: res.ok, status: res.status, data})))
            .then(result => callback(result))
            .catch(err => callback({ok: false, data: {error: String(err)}}));
        """
        result = driver.execute_async_script(login_script, username, password)

        if not result.get('ok'):
            print(f"[Phase 0] Login failed ({result.get('status')}): {result.get('data')}")
            return False

        print(f"[Phase 0] Logged in as '{username}'.")
        return True

    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    username = f"bot{bot_id}_{suffix}"
    password = "BotPass123!"

    print(f"[Phase 0] Registering throwaway account '{username}'...")

    register_script = """
        const callback = arguments[arguments.length - 1];
        fetch('/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({username: arguments[0], password: arguments[1]})
        })
        .then(res => res.json().then(data => ({ok: res.ok, data})))
        .then(result => callback(result))
        .catch(err => callback({ok: false, data: {error: String(err)}}));
    """
    result = driver.execute_async_script(register_script, username, password)

    if not result.get('ok'):
        print(f"[Phase 0] Registration failed: {result.get('data')}")
        return False

    print(f"[Phase 0] Registered and logged in as '{username}'.")
    return (username, password)


def select_seats(driver, count, delay_between=0.3):
    """Clicks `count` DISTINCT available seats through the real
    pickSeat() UI handler - not a hardcoded seat ID, and not a
    localStorage override. Each click triggers a real async
    /seats/<zone>/reserve call, so the server actually reserves that
    many real seats, and selected_qty in localStorage ends up reflecting
    genuine clicks via updateSummary() rather than a spoofed number.
    Querying fresh each time (instead of hardcoding e.g. "A1") also
    avoids two bots running concurrently (see bot_runner.py's `all`
    mode) from colliding on the same seat."""
    clicked_sids = []
    for _ in range(count):
        def get_next_available(d):
            script = """
                const clicked = arguments[0];
                const seats = document.querySelectorAll('.seat.available');
                for (const s of seats) {
                    if (!clicked.includes(s.dataset.sid)) return s.dataset.sid;
                }
                return null;
            """
            return d.execute_script(script, clicked_sids)

        sid = WebDriverWait(driver, 5).until(lambda d: get_next_available(d))
        driver.execute_script("""
            const sid = arguments[0];
            const seat = document.querySelector('.seat[data-sid="' + sid + '"]');
            if (seat) seat.click();
        """, sid)
        clicked_sids.append(sid)
        time.sleep(delay_between)
    return clicked_sids

def run_single_bot(target_url, screen_position, bot_id, behavior="tier1", fixed_credentials=None):
    tag = f"[Bot-{bot_id}:{behavior}]"
    print_header(bot_id, behavior, target_url)

    chrome_options = Options()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, f"chrome_sandbox_profile_{bot_id}")

    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception:
            pass

    debug_port = 9300 + bot_id

    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f"--remote-debugging-port={debug_port}")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-features=CalculateNativeWinOcclusion")

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options,
        )
    except Exception as init_err:
        print(f"❌ {tag} Driver Crash: {init_err}")
        return None

    x_pos, y_pos, width, height = screen_position
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(width, height)

    account_used = fixed_credentials
    landing = None

    try:
        # PHASE 1 - WAITING ROOM ENTRY
        print(f"[Phase 1] Bypassing waiting room...")
        driver.get(target_url)

        driver.execute_script("localStorage.clear(); sessionStorage.clear();")

        auth_result = register_throwaway_account(driver, bot_id, fixed_credentials=fixed_credentials)
        if not fixed_credentials and isinstance(auth_result, tuple):
            account_used = auth_result

        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "enter-btn")))
        driver.execute_script("""
            sessionStorage.setItem('gate_token', Date.now().toString());
            if(!localStorage.getItem('start_time')){ localStorage.setItem('start_time', Date.now()); }
        """)
        print(f"[Phase 1] Queue gate bypassed - localStorage initialized.")
        time.sleep(1)
        driver.execute_script("document.getElementById('enter-btn').click();")

        # PHASE 2 - SALE LIVE GATE
        print(f"[Phase 2] Navigating to select page...")
        WebDriverWait(driver, 10).until(EC.url_contains("salelive.html"))
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "buy-btn")))
        driver.execute_script("enterSale();")
        WebDriverWait(driver, 10).until(EC.url_contains("select.html"))
        print(f"[Phase 2] On select page.")

        # PHASE 3 - SEAT SELECTION
        print(f"[Phase 3] Selecting date...")
        date_card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "date-card"))
        )
        driver.execute_script("arguments[0].click();", date_card)
        print(f"[Phase 3] Date clicked.")
        time.sleep(0.5)

        print(f"[Phase 3] Opening seat map...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "btn-rock")))
        driver.execute_script("document.getElementById('btn-rock').click();")
        print(f"[Phase 3] Seat map opened.")
        time.sleep(0.5)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".seat.available"))
        )

        if behavior == "tier3":
            # Genuinely select the max 5 seats through the real UI
            # (rather than clicking 1 seat and faking selected_qty),
            # clicked back-to-back with minimal delay - the actual max
            # ticket purchase, done as fast as a bot plausibly could.
            print(f"[Phase 3] Selecting 5 seats (max purchase) as fast as possible...")
            sids = select_seats(driver, 5, delay_between=0.1)
            print(f"[Phase 3] Seats selected: {', '.join(sids)}")
        else:
            print(f"[Phase 3] Selecting seat...")
            sids = select_seats(driver, 1, delay_between=0.1)
            print(f"[Phase 3] Seat selected: {sids[0] if sids else 'none'}")

        if behavior == "tier2":
            print(f"[Phase 3] Injecting Tier 2 behavior...")
            time.sleep(1.8)
            driver.execute_script("""
                localStorage.setItem('selected_qty', '5');
                localStorage.setItem('qty_select_speed', '1600');
                let pattern = localStorage.getItem('fyp_pattern') || 'HAD';
                if(!pattern.includes('SSSQC')) {
                    localStorage.setItem('fyp_pattern', pattern + 'SSSQC');
                }
            """)
            print(f"[Phase 3] Behavior parameters injected.")
            time.sleep(0.5)
        elif behavior == "tier3":
            # selected_qty is now genuinely 5 from real clicks above - only
            # the pattern needs an explicit nudge, since the site's own
            # tracking caps accumulated 'S' letters at 3 regardless of how
            # many seats are actually clicked, so 5 real clicks wouldn't
            # naturally reach the exact seeded bad-pattern match on its own.
            print(f"[Phase 3] Injecting Tier 3 pattern signature...")
            driver.execute_script("""
                localStorage.setItem('fyp_pattern', 'HADSSQC');
            """)
            print(f"[Phase 3] Pattern injected.")
        else:
            time.sleep(0.5)

        print(f"[Phase 3] Proceeding to confirmation...")
        driver.execute_script("goNext();")

        # PHASE 4 - CONFIRMATION / SECURITY ROUTING
        # goNext() triggers an async navigation (window.location.href),
        # so the browser may still be on select.html for a moment after
        # this call returns. Without waiting here, validateAndCheckout()
        # doesn't exist yet on whatever page is still loaded, the next
        # execute_script silently does nothing, and /evaluate never
        # fires - this was why bots intermittently never showed up in
        # evaluation_logs even though registration (a separate, earlier
        # request) had already succeeded.
        WebDriverWait(driver, 10).until(EC.url_contains("confirm.html"))
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return typeof validateAndCheckout === 'function';")
        )
        print(f"[Phase 4] Confirm page loaded. Submitting checkout action...")

        if behavior == "tier3":
            print(f"[Phase 4] Tier 3 expected block - checking response...")
            driver.execute_script("validateAndCheckout();")
            time.sleep(2)
        else:
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "fullname")))
                driver.execute_script(f"""
                    document.getElementById('fullname').value = 'StressBot {bot_id}';
                    document.getElementById('email').value = 'bot{bot_id}@stress.test';
                """)
                driver.execute_script("validateAndCheckout();")
            except TimeoutException:
                print(f"[Phase 4] Form elements not found, checking direct redirect...")

        # PHASE 5 - FINAL ROUTE & LOGGING
        print(f"[Phase 5] Awaiting final routing decision...")
        landing = driver.current_url
        for _ in range(10):
            landing = driver.current_url
            if any(p in landing for p in ("ghost_ticket.html", "captcha.html", "payment.html", "success.html")):
                break
            time.sleep(1)

        print(f"[Phase 5] Final route -> {landing}")
        if "ghost_ticket.html" in landing:
            print(f"{tag} RESULT: TIER 3 (Ghost Ticket triggered successfully!)")
        elif "error.html" in landing:
            print(f"{tag} RESULT: TIER 3 (Hard Blocked — repeat offender!)")
        elif "captcha.html" in landing:
            print(f"{tag} RESULT: TIER 2 (CAPTCHA triggered)")
        elif "payment.html" in landing:
            print(f"{tag} RESULT: TIER 1 / PASS")
        else:
            print(f"{tag} RESULT: Routed to -> {landing}")

    except Exception:
        print(f"{tag} CRITICAL FAULT:")
        traceback.print_exc()
    finally:
        print(f"{tag} Pipeline complete, closing driver.")
        time.sleep(2)
        driver.quit()

    return {"landing": landing, "account": account_used}


def run_repeat_offender_test(target_url, screen_position, bot_id):
    """Runs Tier 3 behavior twice with the SAME account to verify the
    escalation logic: 1st attempt should land on ghost_ticket.html,
    2nd attempt (same account) should land on error.html (hard block)."""
    tag = f"[Bot-{bot_id}:repeat-offender]"

    print(f"{tag} === ATTEMPT 1 (expect: ghost ticket) ===")
    result1 = run_single_bot(target_url, screen_position, bot_id, behavior="tier3")

    if not result1 or not result1.get("account"):
        print(f"{tag} Attempt 1 failed before an account was established - aborting test.")
        return

    username, password = result1["account"]
    print(f"{tag} Attempt 1 landed on: {result1['landing']}")
    print(f"{tag} Using account '{username}' again for attempt 2...")

    print(f"{tag} Waiting before second attempt...")
    time.sleep(3)

    print(f"{tag} === ATTEMPT 2, SAME ACCOUNT (expect: hard block) ===")
    result2 = run_single_bot(
        target_url, screen_position, bot_id, behavior="tier3",
        fixed_credentials=(username, password)
    )

    print(f"\n{tag} " + "=" * 50)
    print(f"{tag} REPEAT-OFFENDER TEST SUMMARY")
    print(f"{tag}   Attempt 1 -> {result1['landing']}")
    print(f"{tag}   Attempt 2 -> {result2['landing'] if result2 else 'FAILED'}")
    if result2 and "error.html" in result2["landing"]:
        print(f"{tag}   RESULT: PASS - escalation correctly hard-blocked the repeat offender.")
    else:
        print(f"{tag}   RESULT: FAIL - 2nd attempt did not get hard-blocked as expected.")
    print(f"{tag} " + "=" * 50)