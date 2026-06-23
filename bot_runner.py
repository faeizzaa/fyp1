import time
import os
import shutil
import traceback
import sys
import platform

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ==========================================
# CONFIGURATION
# ==========================================

TARGET_SITE = "https://fyp1-gnoo.onrender.com"

# 1 = Tier 1 (fast single seat, no mouse)
# 2 = Tier 2 (bulk qty override, no mouse)
# 3 = Tier 3 (repeated seat clicks + bulk qty)
SCENARIO = 1  # <- CHANGE THIS (1, 2, or 3)

# ==========================================
# AUTO DETECT OS
# ==========================================
IS_LINUX   = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"

# ==========================================
# SCENARIO DEFINITIONS
# ==========================================
SCENARIOS = {
    1: {
        "name": "Bot 1 - Tier 1 Trigger",
        "desc": "Fast single seat, no mouse moves",
        "expected": "Tier 1 (Artificial Delay)",
        "qty": 1,
        "repeat_seat": 1,
        "port": 9221,
        "profile": "profile_bot1"
    },
    2: {
        "name": "Bot 2 - Tier 2 Trigger",
        "desc": "Single seat + qty override to 5",
        "expected": "Tier 2 (CAPTCHA)",
        "qty": 5,
        "repeat_seat": 1,
        "port": 9222,
        "profile": "profile_bot2"
    },
    3: {
        "name": "Bot 3 - Tier 3 Trigger",
        "desc": "Repeated seat clicks + qty override to 5",
        "expected": "Tier 3 (Ghost Ticket)",
        "qty": 5,
        "repeat_seat": 3,
        "port": 9223,
        "profile": "profile_bot3"
    }
}

# ==========================================
# CHROME SETUP
# ==========================================
def build_driver(scenario_cfg):
    chrome_options = Options()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, scenario_cfg["profile"])

    if IS_WINDOWS:
        chrome_options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    else:
        chrome_options.binary_location = "/usr/bin/google-chrome"
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1280,800")

    if os.path.exists(profile_dir):
        shutil.rmtree(profile_dir, ignore_errors=True)

    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-features=CalculateNativeWinOcclusion")
    chrome_options.add_argument(f"--remote-debugging-port={scenario_cfg['port']}")

    if IS_WINDOWS:
        driver = webdriver.Chrome(options=chrome_options)
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

    return driver

# ==========================================
# BOT RUNNER
# ==========================================
def run_bot(scenario_num):
    cfg = SCENARIOS[scenario_num]

    print("\n" + "=" * 55)
    print(f"  {cfg['name']}")
    print(f"  {cfg['desc']}")
    print(f"  Expected: {cfg['expected']}")
    print(f"  Target:   {TARGET_SITE}")
    print(f"  OS:       {platform.system()}")
    print("=" * 55)

    try:
        driver = build_driver(cfg)
    except Exception as e:
        print(f"Driver Crash: {e}")
        return

    if IS_WINDOWS:
        driver.set_window_position(10, 10)
        driver.set_window_size(500, 800)

    try:
        # =========================
        # PHASE 1 - WAITING ROOM BYPASS
        # =========================
        print("\n[Phase 1] Bypassing waiting room...")
        driver.get(f"{TARGET_SITE}/home.html")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Set all required localStorage before navigating
        driver.execute_script("""
            localStorage.clear();
            localStorage.setItem('selected_event', 'Stray Kids World Tour KARMA');
            localStorage.setItem('selected_date', '22 Nov 2026 (Day 1 - Saturday)');
            localStorage.setItem('fyp_pattern', 'HA');
            localStorage.setItem('session_start', Date.now().toString());
            localStorage.setItem('fyp_mouse_moves', '0');
            localStorage.setItem('session_id', 'bot-' + Math.random().toString(36).substr(2,9));
            localStorage.setItem('qty_speed_start', Date.now().toString());
        """)
        print("[Phase 1] Queue gate bypassed — localStorage initialized.")

        # =========================
        # PHASE 2 - GO DIRECTLY TO SELECT PAGE
        # =========================
        print("[Phase 2] Navigating to select page...")
        driver.get(f"{TARGET_SITE}/select.html")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)
        print("[Phase 2] On select page.")

        # =========================
        # PHASE 3 - DATE + ZONE + SEAT
        # =========================
        print("[Phase 3] Selecting date...")
        try:
            WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.ID, "date1-card"))
            )
            driver.execute_script("document.getElementById('date1-card').click();")
            print("[Phase 3] Date 1 clicked.")
            time.sleep(1)
        except TimeoutException:
            driver.execute_script("localStorage.setItem('selected_date', '22 Nov 2026 (Day 1 - Saturday)');")
            print("[Phase 3] Date set via localStorage fallback.")

        print("[Phase 3] Selecting Rock Zone...")
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "btn-rock"))
        )
        driver.execute_script("document.getElementById('btn-rock').click();")
        time.sleep(2)

        # Wait for seats to load from API
        print("[Phase 3] Waiting for seats to load from API...")
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".seat.available"))
            )
            print("[Phase 3] Seats loaded — bot scanning for clickable seats...")
        except TimeoutException:
            print("[Phase 3] Seat API slow — continuing with localStorage injection.")

        # Bot clicks available seats
        for i in range(cfg["repeat_seat"]):
            driver.execute_script("""
                const seat = document.querySelector('.seat[data-sid="A1"]');
                if (seat && !seat.disabled) seat.click();
            """)
            time.sleep(0.3)
            print(f"[Phase 3] Bot clicked seat A1 ({i+1}/{cfg['repeat_seat']})")

        # Scenario 3 — scan extra seat (bot scanning behaviour)
        if scenario_num == 3:
            time.sleep(0.2)
            driver.execute_script("""
                const seat = document.querySelector('.seat[data-sid="A2"]');
                if (seat && !seat.disabled) seat.click();
            """)
            print("[Phase 3] Bot scanned extra seat A2.")

        time.sleep(1.8)

        # Force inject all seat data into localStorage
        # Guarantees confirm page has correct data even if API was slow
        zone_label = "Rock Zone (Standing)"
        zone_key   = "rock"
        seat_id    = "A1"
        price      = 599
        qty        = cfg["qty"]

        driver.execute_script(f"""
            localStorage.setItem('selected_seat_id', '{seat_id}');
            localStorage.setItem('selected_zone',    '{zone_key}');
            localStorage.setItem('selected_seat',    '{zone_label} - RM {price}');
            localStorage.setItem('selected_qty',     '{qty}');
            localStorage.setItem('qty_select_speed', '300');
        """)
        print(f"[Phase 3] Seat data injected: {zone_label} Seat {seat_id} x{qty}")

        # Build correct pattern based on scenario
        repeat = cfg["repeat_seat"]
        driver.execute_script(f"""
            let p = localStorage.getItem('fyp_pattern') || 'HA';
            if (!p.includes('D')) p += 'D';
            for (let i = 0; i < {repeat}; i++) {{
                let sc = (p.match(/S/g) || []).length;
                if (sc < 3) p += 'S';
            }}
            localStorage.setItem('fyp_pattern', p);
        """)

        pattern_now = driver.execute_script("return localStorage.getItem('fyp_pattern');")
        print(f"[Phase 3] Pattern so far: {pattern_now}")

        time.sleep(1)

        # Navigate to confirm — use goNext() if available, else direct nav
        go_next_exists = driver.execute_script("return typeof goNext === 'function';")
        if go_next_exists:
            driver.execute_script("""
                let p = localStorage.getItem('fyp_pattern') || 'HADS';
                if (!p.includes('Q')) p += 'Q';
                localStorage.setItem('fyp_pattern', p);
                goNext();
            """)
        else:
            driver.execute_script("""
                let p = localStorage.getItem('fyp_pattern') || 'HADS';
                if (!p.includes('Q')) p += 'Q';
                localStorage.setItem('fyp_pattern', p);
            """)
            driver.get(f"{TARGET_SITE}/confirm.html")

        WebDriverWait(driver, 15).until(EC.url_contains("confirm.html"))
        print("[Phase 3] Proceeded to confirmation.")

        # =========================
        # PHASE 4 - CONFIRM PAGE
        # =========================
        print("[Phase 4] Filling confirmation details...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "fullname"))
        )

        driver.execute_script("""
            document.getElementById('fullname').value = 'bot_user';
            document.getElementById('email').value = 'bot@attack.com';
        """)

        # Wait for confirm page onload to append C to pattern
        time.sleep(1.5)

        pattern = driver.execute_script("return localStorage.getItem('fyp_pattern');")
        mouse   = driver.execute_script("return localStorage.getItem('fyp_mouse_moves') || '0';")
        qty_val = driver.execute_script("return localStorage.getItem('selected_qty') || '1';")

        print(f"[Phase 4] Pattern     : {pattern}")
        print(f"[Phase 4] Mouse Moves : {mouse}")
        print(f"[Phase 4] Quantity    : {qty_val}")

        # Click Proceed to Payment
        buttons = driver.find_elements(By.TAG_NAME, "button")
        clicked = False
        for btn in buttons:
            if "Proceed to Payment" in btn.text:
                driver.execute_script("arguments[0].click();", btn)
                clicked = True
                print("[Phase 4] Proceed to Payment clicked.")
                break

        if not clicked:
            print("[Phase 4] Button not found — calling validateAndCheckout() directly.")
            driver.execute_script("validateAndCheckout();")

        time.sleep(3)

        # =========================
        # DECISION ENGINE CHECK
        # =========================
        print("[Decision] Waiting for server tier response...")

        try:
            WebDriverWait(driver, 8).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"[Decision] Alert received: {alert_text}")

            score = driver.execute_script("return localStorage.getItem('last_score');") or "?"
            tier  =  driver.execute_script("return localStorage.getItem('last_tier');") or "?"
            print("\n" + "=" * 55)
            print("  EVALUATION RESULT")
            print(f"  Pattern      : {pattern}")
            print(f"  Mouse Moves  : {mouse}")
            print(f"  Quantity     : {qty_val}")
            print(f"  Score        : {score}")
            print(f"  Detected Tier: {alert_text}")
            print("=" * 55)

            if "Tier 3" in alert_text:
                print("\n" + "=" * 55)
                print("  TIER 3 DETECTED")
                print(f"  Pattern : {pattern}")
                print(f"  Qty     : {qty_val}")
                print(f"  Mouse   : {mouse}")
                print(f"  Response: Ghost Ticket")
                print("=" * 55)
                time.sleep(2)
                try: alert.accept()
                except Exception: pass
                time.sleep(1)
                driver.get(f"{TARGET_SITE}/ghost_ticket.html")
                print("[Result] Ghost Ticket page loaded — interception confirmed.")
                time.sleep(4)
                return

            elif "Tier 2" in alert_text:
                print("\n" + "=" * 55)
                print("  TIER 2 DETECTED")
                print(f"  Pattern : {pattern}")
                print(f"  Qty     : {qty_val}")
                print(f"  Mouse   : {mouse}")
                print(f"  Response: CAPTCHA Challenge")
                print("=" * 55)
                time.sleep(2)
                try: alert.accept()
                except Exception: pass
                time.sleep(1)
                driver.get(f"{TARGET_SITE}/captcha.html")
                print("[Result] CAPTCHA page loaded.")

                # Bot tries to solve CAPTCHA but will fail
                print("[CAPTCHA] Bot scanning for input fields...")
                time.sleep(2)
                for attempt in range(3):
                    try:
                        inp = driver.find_element(By.CSS_SELECTOR, ".captcha-input")
                        inp.clear()
                        inp.send_keys("XXXXXX")
                        verify_btn = driver.find_element(By.CSS_SELECTOR, ".btn-verify")
                        driver.execute_script("arguments[0].click();", verify_btn)
                        print(f"[CAPTCHA] Wrong answer submitted — attempt {attempt+1}/3")
                        time.sleep(2)
                    except Exception as ce:
                        print(f"[CAPTCHA] Could not find input: {ce}")
                        break

                time.sleep(3)
                landing = driver.current_url
                if "ghost_ticket.html" in landing:
                    print("[Result] CAPTCHA failed 3x — redirected to Ghost Ticket.")
                    print("[Result] Full detection chain confirmed: Tier 2 -> CAPTCHA -> Ghost Ticket")
                else:
                    print(f"[Result] Current page: {landing}")
                return

            elif "Tier 1" in alert_text:
                print("\n" + "=" * 55)
                print("  TIER 1 DETECTED")
                print(f"  Pattern : {pattern}")
                print(f"  Qty     : {qty_val}")
                print(f"  Mouse   : {mouse}")
                print(f"  Response: Artificial Delay applied")
                print("=" * 55)
                if IS_WINDOWS:
                    input("\nPress ENTER to continue...")
                try: alert.accept()
                except Exception: pass
                return

            else:
                print(f"[Decision] Unrecognized alert: {alert_text}")
                try: alert.accept()
                except Exception: pass

        except TimeoutException:
            print("[Decision] No alert — checking current URL...")

        current_url = driver.current_url
        if "captcha.html" in current_url:
            print("[Result] Tier 2 — CAPTCHA page reached")
            return
        if "ghost_ticket.html" in current_url:
            print("[Result] Tier 3 — Ghost Ticket page reached")
            return

        # =========================
        # PHASE 5 - PAYMENT (Tier 0/1 fallthrough)
        # =========================
        print("[Phase 5] Reaching payment page...")
        try:
            WebDriverWait(driver, 10).until(EC.url_contains("payment.html"))
        except TimeoutException:
            print(f"[Phase 5] Timeout — current URL: {driver.current_url}")
            return

        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "card-number"))
        )
        driver.find_element(By.ID, "card-number").send_keys("4111222233334444")
        driver.find_element(By.ID, "card-expiry").send_keys("1229")
        driver.find_element(By.ID, "card-cvv").send_keys("123")

        print("[Phase 5] Submitting payment details...")
        driver.execute_script("executeFinalTransaction();")
        time.sleep(5)

        landing = driver.current_url
        print("\n" + "=" * 55)
        print("  FINAL RESULT")
        if "ghost_ticket.html" in landing:   print("  Tier 3 — Ghost Ticket")
        elif "captcha.html" in landing:      print("  Tier 2 — CAPTCHA")
        elif "success.html" in landing:      print("  Tier 0 — Bot passed through!")
        else:                                print(f"  Landing: {landing}")
        print("=" * 55)

    except Exception:
        print("FULL ERROR:")
        traceback.print_exc()

    finally:
        print("\n[Bot] Execution complete.")
        if IS_WINDOWS:
            input("Press ENTER to close browser...")
        else:
            time.sleep(5)
        try:
            driver.quit()
        except Exception:
            pass


# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":

    if len(sys.argv) > 1:
        try:
            SCENARIO = int(sys.argv[1])
        except ValueError:
            pass

    if SCENARIO not in SCENARIOS:
        print("Invalid scenario. Choose 1, 2, or 3.")
        print("  1 = Tier 1 (fast single seat)")
        print("  2 = Tier 2 (bulk qty override)")
        print("  3 = Tier 3 (repeated seat + bulk)")
        sys.exit(1)

    run_bot(SCENARIO)