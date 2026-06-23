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
# CONFIGURATION — edit these
# ==========================================

TARGET_SITE = "https://fyp1-gnoo.onrender.com"

# Which scenario to run:
# 1 = Tier 1 (fast single seat, no mouse)
# 2 = Tier 2 (bulk qty override, no mouse)
# 3 = Tier 3 (repeated seat clicks + bulk qty)
SCENARIO = 1  # ← CHANGE THIS (1, 2, or 3)

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
        "name": "Bot 1 — Tier 1 Trigger",
        "desc": "Fast single seat, no mouse moves",
        "expected": "Tier 1 (Artificial Delay)",
        "qty": 1,
        "repeat_seat": 1,
        "port": 9221,
        "profile": "profile_bot1"
    },
    2: {
        "name": "Bot 2 — Tier 2 Trigger",
        "desc": "Single seat + qty override to 5",
        "expected": "Tier 2 (CAPTCHA)",
        "qty": 5,
        "repeat_seat": 1,
        "port": 9222,
        "profile": "profile_bot2"
    },
    3: {
        "name": "Bot 3 — Tier 3 Trigger",
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
        driver.get(f"{TARGET_SITE}/waitingroom.html")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        driver.get(f"{TARGET_SITE}/home.html")
        driver.execute_script("localStorage.setItem('selected_date', '22 Nov 2026 (Day 1 - Saturday)');")
        print("[Phase 1] Queue gate bypassed.")

        # =========================
        # PHASE 2 - HOME PAGE
        # =========================
        print("[Phase 2] Selecting event...")
        time.sleep(2)
        driver.execute_script("selectEvent('Stray Kids World Tour KARMA');")
        WebDriverWait(driver, 10).until(EC.url_contains("select.html"))
        print("[Phase 2] Event selected.")

        # =========================
        # PHASE 3 - ZONE + SEAT SELECTION
        # =========================
        print("[Phase 3] Selecting zone and seat...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "btn-rock"))
        )
        driver.execute_script("document.getElementById('btn-rock').click();")
        time.sleep(1.5)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".seat.available"))
        )

        # Repeat seat clicks based on scenario
        for i in range(cfg["repeat_seat"]):
            driver.execute_script("""
                const seat = document.querySelector('.seat[data-sid="A1"]');
                if (seat) seat.click();
            """)
            time.sleep(0.2)
            print(f"[Phase 3] Seat click {i+1}/{cfg['repeat_seat']}")

        # Try A2 as well for scenario 3 (scanning behaviour)
        if scenario_num == 3:
            driver.execute_script("""
                const seat = document.querySelector('.seat[data-sid="A2"]');
                if (seat && seat.classList.contains('available')) seat.click();
            """)
            time.sleep(0.2)

        time.sleep(1.8)

        # Qty override
        if cfg["qty"] > 1:
            driver.execute_script(f"localStorage.setItem('selected_qty', '{cfg['qty']}');")
            print(f"[Phase 3] Quantity override: {cfg['qty']} tickets")
        else:
            print(f"[Phase 3] Keeping default qty: 1 ticket")

        time.sleep(1)
        driver.execute_script("goNext();")

        WebDriverWait(driver, 10).until(EC.url_contains("confirm.html"))
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

        pattern = driver.execute_script("return localStorage.getItem('fyp_pattern');")
        mouse  = driver.execute_script("return localStorage.getItem('fyp_mouse_moves') || '0';")
        print(f"[Phase 4] Pattern: {pattern}")
        print(f"[Phase 4] Mouse Moves: {mouse}")

        # Click proceed button
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            if "Proceed to Payment" in btn.text:
                driver.execute_script("arguments[0].click();", btn)
                break

        time.sleep(3)

        # =========================
        # DECISION ENGINE CHECK
        # =========================
        print("[Decision] Checking server response...")

        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"[Decision] Alert: {alert_text}")

            if "Tier 3" in alert_text:
                print("\n" + "=" * 55)
                print("  TIER 3 DETECTED")
                print(f"  Pattern: {pattern}")
                print(f"  Response: Ghost Ticket")
                print("=" * 55)
                time.sleep(2)
                try: alert.accept()
                except Exception: pass
                time.sleep(1)
                driver.get(f"{TARGET_SITE}/ghost_ticket.html")
                print("[Result] Ghost Ticket page loaded.")
                time.sleep(4)
                return

            elif "Tier 2" in alert_text:
                print("\n" + "=" * 55)
                print("  TIER 2 DETECTED")
                print(f"  Pattern: {pattern}")
                print(f"  Response: CAPTCHA Challenge")
                print("=" * 55)
                time.sleep(2)
                try: alert.accept()
                except Exception: pass
                time.sleep(1)
                driver.get(f"{TARGET_SITE}/captcha.html")
                print("[Result] CAPTCHA page loaded.")

                # Attempt to fail CAPTCHA (bot cannot solve it)
                print("[CAPTCHA] Bot attempting to solve — will fail...")
                time.sleep(2)
                for attempt in range(3):
                    try:
                        inp = driver.find_element(By.CSS_SELECTOR, ".captcha-input")
                        inp.clear()
                        inp.send_keys("XXXXXX")
                        verify_btn = driver.find_element(By.CSS_SELECTOR, ".btn-verify")
                        verify_btn.click()
                        print(f"[CAPTCHA] Wrong attempt {attempt+1}/3")
                        time.sleep(2)
                    except Exception as ce:
                        print(f"[CAPTCHA] Could not interact: {ce}")
                        break

                time.sleep(3)
                landing = driver.current_url
                if "ghost_ticket.html" in landing:
                    print("[Result] CAPTCHA failed → Ghost Ticket confirmed.")
                else:
                    print(f"[Result] Landing: {landing}")
                return

            elif "Tier 1" in alert_text:
                print("\n" + "=" * 55)
                print("  TIER 1 DETECTED")
                print(f"  Pattern: {pattern}")
                print(f"  Response: Artificial Delay (60s)")
                print("=" * 55)

                if IS_WINDOWS:
                    input("\nPress ENTER to continue...")
                try: alert.accept()
                except Exception: pass
                return

            else:
                try: alert.accept()
                except Exception: pass

        except TimeoutException:
            print("[Decision] No alert — checking URL...")

        current_url = driver.current_url
        if "captcha.html" in current_url:
            print("[Result] Tier 2 — CAPTCHA page")
            return
        if "ghost_ticket.html" in current_url:
            print("[Result] Tier 3 — Ghost Ticket page")
            return

        # =========================
        # PHASE 5 - PAYMENT (Tier 0/1)
        # =========================
        print("[Phase 5] Reaching payment page...")
        WebDriverWait(driver, 10).until(EC.url_contains("payment.html"))

        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "card-number"))
        )
        driver.find_element(By.ID, "card-number").send_keys("4111222233334444")
        driver.find_element(By.ID, "card-expiry").send_keys("1229")
        driver.find_element(By.ID, "card-cvv").send_keys("123")

        print("[Phase 5] Submitting payment...")
        driver.execute_script("executeFinalTransaction();")
        time.sleep(5)

        landing = driver.current_url
        print("\n" + "=" * 55)
        print("  FINAL RESULT")
        if "ghost_ticket.html" in landing:   print("  Tier 3 — Ghost Ticket")
        elif "captcha.html" in landing:      print("  Tier 2 — CAPTCHA")
        elif "success.html" in landing:      print("  Tier 0 — Success (bot passed!)")
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

    # Allow passing scenario via command line:
    # python3 bot_runner.py 2
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