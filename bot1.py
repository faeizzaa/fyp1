import time
import os
import shutil
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Bot 1 — Tier 1 trigger
# Behaviour: Fast single-seat purchase, no mouse moves
# Expected pattern: HADSQC → Tier 1 (artificial delay)

def run_single_bot(target_url, screen_position):
    print(f"[Bot1] Window staging initialized...")

    chrome_options = Options()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, "chrome_sandbox_profile_bot1")

    chrome_options.binary_location = "/usr/bin/google-chrome"
    if os.path.exists(profile_dir):
        shutil.rmtree(profile_dir, ignore_errors=True)

    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9221")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-features=CalculateNativeWinOcclusion")
    
driver = webdriver.Chrome(
    service=Service(
        ChromeDriverManager().install()
    ),
    options=chrome_options
)

    x_pos, y_pos, width, height = screen_position
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(width, height)

    try:
        # =========================
        # PHASE 1 - WAITING ROOM
        # =========================
        driver.get(target_url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("[Bot1] Waiting room bypass active.")
        driver.get("https://tickago.onrender.com/home.html")
        driver.execute_script("localStorage.setItem('selected_date', '22 Nov 2026 (Saturday)');")
        print("[Bot1] Queue gate bypassed.")

        # =========================
        # PHASE 2 - HOME PAGE
        # =========================
        time.sleep(2)
        driver.execute_script("selectEvent('Stray Kids World Tour KARMA');")
        WebDriverWait(driver, 10).until(EC.url_contains("select.html"))
        print("[Bot1] Event selected.")

        # =========================
        # PHASE 3 - ZONE + SEAT SELECTION
        # =========================
        print("[Bot1] Selecting zone via JS...")

        # Click the Rock Zone button
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "btn-rock"))
        )
        driver.execute_script("document.getElementById('btn-rock').click();")
        time.sleep(1.5)

        # Wait for seats to load then pick seat A1
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".seat.available"))
        )

        print("[Bot1] Picking seat A1...")
        driver.execute_script("""
            const seat = document.querySelector('.seat[data-sid="A1"]');
            if (seat && seat.classList.contains('available')) seat.click();
        """)

        time.sleep(1.5)

        print("[Bot1] Keep default quantity (1 ticket).")
        localStorage_qty = driver.execute_script("return localStorage.getItem('selected_qty');")
        print(f"[Bot1] selected_qty = {localStorage_qty}")

        driver.execute_script("goNext();")

        WebDriverWait(driver, 10).until(EC.url_contains("confirm.html"))
        print("[Bot1] Proceeded to confirmation.")

        pattern = driver.execute_script("return localStorage.getItem('fyp_pattern');")
        duration = driver.execute_script("return Date.now() - parseInt(localStorage.getItem('session_start'));")
        print(f"[Bot1] Pattern: {pattern}")
        print(f"[Bot1] Duration: {duration}ms")

        # =========================
        # PHASE 4 - CONFIRM PAGE
        # =========================
        time.sleep(2)

        print("Current URL before validation:", driver.current_url)

        pattern = driver.execute_script("return localStorage.getItem('fyp_pattern');")
        print(f"[Bot1] Pattern: {pattern}")
        print("[Bot1] Mouse Moves:", driver.execute_script("return localStorage.getItem('fyp_mouse_moves') || '0';"))

        print("[Bot1] Triggering checkout...")
        driver.execute_script("validateAndCheckout();")
        time.sleep(3)

        # =========================
        # DECISION ENGINE CHECK
        # =========================
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"Security Alert: {alert_text}")

            if "Tier 1" in alert_text:
                print("\n==================================================")
                print("TIER 1 DETECTION")
                print(f"Action String: {pattern}")
                print("Behaviour: Elevated Interaction Speed")
                print("Response: Artificial Delay")
                print("==================================================")
                input("\nPress ENTER to continue...")
                try:
                    alert.accept()
                except Exception:
                    pass
                return

            alert.accept()

        except TimeoutException:
            pass
        except Exception as e:
            print(f"Alert handling error: {e}")

        # =========================
        # PHASE 5 - PAYMENT
        # =========================
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "card-number")))
        driver.find_element(By.ID, "card-number").send_keys("4111222233334444")
        driver.find_element(By.ID, "card-expiry").send_keys("1229")
        driver.find_element(By.ID, "card-cvv").send_keys("123")

        print("[Bot1] Submitting payment...")
        driver.execute_script("executeFinalTransaction();")
        time.sleep(5)

        landing = driver.current_url
        print("\n==================================================")
        print("BOT1 INTERCEPTION ANALYSIS")
        if "ghost_ticket.html" in landing:   print("• TIER 3 (Ghost Ticket)")
        elif "captcha.html" in landing:      print("• TIER 2 (CAPTCHA)")
        elif "success.html" in landing:      print("• BOT REACHED SUCCESS PAGE")
        else:                                print(f"• FINAL LANDING: {landing}")
        print("==================================================")

    except Exception:
        print("FULL ERROR:")
        traceback.print_exc()
    finally:
        print("[Bot1] Execution complete.")
        input("Press ENTER to close browser...")
        driver.quit()


if __name__ == "__main__":
    target = "https://tickago.onrender.com/waitingroom.html"
    print("\n==================================================")
    print("BOT 1 — TIER 1 TRIGGER (Fast single seat)")
    print("==================================================")
    run_single_bot(target, (10, 10, 500, 800))
