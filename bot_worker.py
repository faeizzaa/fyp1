import time
import os
import shutil
import traceback
import uuid

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================================
# 🤖 GENERIC STRESS-TEST BOT WORKER
# Parameterized version of bot1new.py / bot2.py so N of these
# can run at once (each process gets its own profile dir,
# remote-debugging port, and window position).
#
# behavior="tier1" -> rapid clicks, no mouse telemetry, single
#                      seat, meant to land on Tier 1 fast-path.
# behavior="tier2" -> injects qty override + timing pattern
#                      meant to land on Tier 2 (CAPTCHA).
# behavior="tier3" -> stacks three independent scoring signals
#                      (known bad pattern +40, qty=5 +40,
#                      qty_speed<500ms +40) so the sum clears the
#                      100-point Tier 3 cutoff in app.py regardless
#                      of duration/mouse noise -> ghost_ticket.html.
#
# NOTE: confirm.html and payment.html are now gated behind a login
# (see CHECKOUT_GATED_PAGES in app.py) - a session with no logged-in
# user gets redirected to /login before ever reaching those pages.
# Phase 3.5 below registers a disposable throwaway account so the
# bot can actually reach checkout instead of silently dead-ending on
# the login page.
# ==========================================================


def run_single_bot(target_url, screen_position, bot_id, behavior="tier1"):
    tag = f"[Bot-{bot_id}:{behavior}]"
    print(f"{tag} Window staging initialized...")

    chrome_options = Options()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, f"chrome_sandbox_profile_{bot_id}")

    # Comment this out on Windows/Mac if the binary path differs
    # chrome_options.binary_location = "/usr/bin/google-chrome"

    if os.path.exists(profile_dir):
        shutil.rmtree(profile_dir, ignore_errors=True)

    debug_port = 9300 + bot_id  # unique per process, avoids "port in use" crashes

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
        return

    x_pos, y_pos, width, height = screen_position
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(width, height)

    try:
        # PHASE 1 - WAITING ROOM ENTRY
        print(f"{tag} [Phase 1] Bypassing waiting room...")
        driver.get(target_url)

        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "enter-btn")))
        driver.execute_script("""
            sessionStorage.setItem('gate_token', Date.now().toString());
            if(!localStorage.getItem('start_time')){ localStorage.setItem('start_time', Date.now()); }
        """)
        time.sleep(1)
        driver.execute_script("document.getElementById('enter-btn').click();")
        print(f"{tag} [Phase 1] Queue gate bypassed — localStorage initialized.")

        # PHASE 2 - SALE LIVE GATE
        print(f"{tag} [Phase 2] Navigating to select page...")
        WebDriverWait(driver, 10).until(EC.url_contains("salelive.html"))
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "buy-btn")))
        driver.execute_script("enterSale();")

        WebDriverWait(driver, 10).until(EC.url_contains("select.html"))
        print(f"{tag} [Phase 2] On select page.")

        # PHASE 3 - SEAT SELECTION
        print(f"{tag} [Phase 3] Selecting date...")
        date_card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "date-card"))
        )
        driver.execute_script("arguments[0].click();", date_card)
        print(f"{tag} [Phase 3] Date clicked.")
        time.sleep(0.5)

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "btn-rock")))
        driver.execute_script("document.getElementById('btn-rock').click();")
        print(f"{tag} [Phase 3] Zone selected.")
        time.sleep(0.5)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".seat.available"))
        )
        driver.execute_script("""
            const seat = document.querySelector('.seat[data-sid="A1"]');
            if (seat && seat.classList.contains('available')) { seat.click(); }
        """)
        print(f"{tag} [Phase 3] Seat A1 selected.")

        if behavior == "tier2":
            # Human-mimic gap + forced qty/pattern override to push into
            # the Tier 2 evaluation boundary.
            time.sleep(1.8)
            driver.execute_script("""
                localStorage.setItem('selected_qty', '5');
                localStorage.setItem('qty_select_speed', '1600');
                let pattern = localStorage.getItem('fyp_pattern') || 'HAD';
                if(!pattern.includes('SSSQC')) {
                    localStorage.setItem('fyp_pattern', pattern + 'SSSQC');
                }
            """)
            time.sleep(0.5)
        elif behavior == "tier3":
            # Stack three independent +40 signals so the total score
            # clears the 100-point Tier 3 cutoff on its own:
            #   - pattern exactly matches a seeded bad pattern (+40)
            #   - max quantity, 5 tickets (+40)
            #   - instant quantity-select speed, <500ms (+40)
            # No sleep before this - the whole point is "impossibly fast".
            driver.execute_script("""
                localStorage.setItem('selected_qty', '5');
                localStorage.setItem('qty_select_speed', '150');
                localStorage.setItem('fyp_pattern', 'HADSSQC');
            """)
        else:
            time.sleep(0.5)

        driver.execute_script("goNext();")

        # PHASE 3.5 - AUTH
        # confirm.html / payment.html are gated behind a logged-in session
        # (see CHECKOUT_GATED_PAGES in app.py). Without this, goNext() above
        # gets redirected to /login and the bot dead-ends there - nothing
        # ever reaches /evaluate, so nothing ever reaches Supabase either.
        print(f"{tag} [Phase 3.5] Checking for login gate...")
        WebDriverWait(driver, 10).until(
            lambda d: "confirm.html" in d.current_url or "login" in d.current_url
        )

        if "login" in driver.current_url:
            bot_username = f"stressbot_{bot_id}_{uuid.uuid4().hex[:6]}"
            print(f"{tag} [Phase 3.5] Gated — registering throwaway account: {bot_username}")
            driver.execute_script(f"""
                fetch('/register', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        username: '{bot_username}',
                        password: 'StressTest123',
                        next: 'confirm.html'
                    }})
                }})
                .then(res => res.json())
                .then(data => {{ window.location.href = data.redirect || 'confirm.html'; }});
            """)
            WebDriverWait(driver, 10).until(EC.url_contains("confirm.html"))
            print(f"{tag} [Phase 3.5] Account ready, reached confirm.html.")
        else:
            print(f"{tag} [Phase 3.5] Already authenticated, no gate hit.")

        # PHASE 4 - CONFIRMATION
        print(f"{tag} [Phase 4] Filling checkout form...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "fullname")))
        driver.execute_script(f"""
            document.getElementById('fullname').value = 'StressBot {bot_id}';
            document.getElementById('email').value = 'bot{bot_id}@stress.test';
        """)
        driver.execute_script("validateAndCheckout();")
        print(f"{tag} [Phase 4] Checkout submitted.")

        # SECURITY INTERCEPT HANDLER
        try:
            WebDriverWait(driver, 8).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"🚨 {tag} INTERCEPTED: {alert_text}")
            alert.accept()
            # Handle a possible second stacked alert
            try:
                WebDriverWait(driver, 2).until(EC.alert_is_present())
                second = driver.switch_to.alert
                print(f"⚠️  {tag} second alert: {second.text}")
                second.accept()
            except TimeoutException:
                pass
        except TimeoutException:
            print(f"{tag} No blocking dialog intercepted.")

        # PHASE 5 - FINAL ROUTE, with a short poll instead of a blind sleep
        print(f"{tag} [Phase 5] Waiting for final route...")
        landing = driver.current_url
        for _ in range(15):
            landing = driver.current_url
            if any(p in landing for p in ("ghost_ticket.html", "captcha.html", "payment.html", "success.html")):
                break
            time.sleep(1)

        print(f"📊 {tag} [Phase 5] FINAL ROUTE -> {landing}")
        if "ghost_ticket.html" in landing:
            print(f"{tag} RESULT: TIER 3 (Ghost Ticket)")
        elif "captcha.html" in landing:
            print(f"{tag} RESULT: TIER 2 (CAPTCHA)")
            # Bots can't solve the CAPTCHA — that's the point. Just record
            # that it landed there and stop; don't sit here for 5 minutes.
        elif "payment.html" in landing:
            print(f"{tag} RESULT: TIER 1 / PASS")
        elif "success.html" in landing:
            print(f"{tag} RESULT: UNRESTRICTED SUCCESS")
        else:
            print(f"{tag} RESULT: UNKNOWN -> {landing}")

    except Exception:
        print(f"❌ {tag} CRITICAL FAULT:")
        traceback.print_exc()
    finally:
        print(f"{tag} Pipeline complete, closing driver.")
        time.sleep(2)
        driver.quit()