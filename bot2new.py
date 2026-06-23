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

# Bot 2 — Tier 2 trigger
# Behaviour: Picks seat then overrides qty to 5, no mouse moves
# Expected pattern: HADSQC → Tier 2 (CAPTCHA)

def run_single_bot(target_url, screen_position):
    print(f"[Bot2] Window staging initialized...")

    chrome_options = Options()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, "chrome_sandbox_profile_bot2")

    chrome_options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    if os.path.exists(profile_dir):
        shutil.rmtree(profile_dir, ignore_errors=True)

    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-features=CalculateNativeWinOcclusion")

    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"[Bot2] Driver Crash: {e}")
        return

    x_pos, y_pos, width, height = screen_position
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(width, height)

    try:
        # =========================
        # PHASE 1 - WAITING ROOM
        # =========================
        driver.get(target_url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("[Bot2] Waiting room bypass active.")
        driver.get("https://tickago.onrender.com/home.html")
        driver.execute_script("localStorage.setItem('selected_date', '22 Nov 2026 (Saturday)');")
        print("[Bot2] Queue gate bypassed.")

        # =========================
        # PHASE 2 - HOME PAGE
        # =========================
        time.sleep(2)
        driver.execute_script("selectEvent('Stray Kids World Tour KARMA');")
        WebDriverWait(driver, 10).until(EC.url_contains("select.html"))
        print("[Bot2] Event selected.")

        # =========================
        # PHASE 3 - ZONE + SEAT SELECTION
        # =========================
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "btn-rock")))
        driver.execute_script("document.getElementById('btn-rock').click();")
        time.sleep(1.5)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".seat.available"))
        )

        print("[Bot2] Picking seat A1...")
        driver.execute_script("""
            const seat = document.querySelector('.seat[data-sid="A1"]');
            if (seat && seat.classList.contains('available')) seat.click();
        """)

        time.sleep(1.8)  # deliberate pause so qty_speed > 1500ms

        # Override qty to 5 (bulk purchase signal)
        driver.execute_script("localStorage.setItem('selected_qty', '5');")
        print("[Bot2] Quantity override injected (5 tickets).")

        time.sleep(1)
        driver.execute_script("goNext();")

        WebDriverWait(driver, 10).until(EC.url_contains("confirm.html"))
        print("[Bot2] Proceeded to confirmation.")

        # =========================
        # PHASE 4 - CONFIRM PAGE
        # =========================
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "fullname")))

        driver.execute_script("""
            document.getElementById('fullname').value = 'asdfghjk';
            document.getElementById('email').value = 'asdfghjk@botnet.com';
        """)

        pattern = driver.execute_script("return localStorage.getItem('fyp_pattern');")
        print(f"[Bot2] Pattern: {pattern}")
        print("[Bot2] Mouse Moves:", driver.execute_script("return localStorage.getItem('fyp_mouse_moves') || '0';"))

        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            if "Proceed to Payment" in btn.text:
                driver.execute_script("arguments[0].click();", btn)
                break

        time.sleep(3)

        # =========================
        # DECISION ENGINE CHECK
        # =========================
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"Security Alert: {alert_text}")

            if "Tier 3" in alert_text:
                print("\n==================================================")
                print("TIER 3 DETECTION SUCCESS")
                print(f"Action String: {pattern}")
                print("Response: Ghost Ticket")
                print("==================================================")
                time.sleep(2)
                try: alert.accept()
                except Exception: pass
                time.sleep(1)
                driver.get("https://tickago.onrender.com/ghost_ticket.html")
                print("[Bot2] Navigated to Ghost Ticket page.")
                time.sleep(4)
                return

            if "Tier 2" in alert_text:
                print("\n==================================================")
                print("TIER 2 DETECTION SUCCESS")
                print(f"Action String: {pattern}")
                print("Response: CAPTCHA Challenge")
                print("==================================================")
                time.sleep(2)
                try: alert.accept()
                except Exception: pass
                time.sleep(1)
                driver.get("https://tickago.onrender.com/captcha.html")
                print("[Bot2] Navigated to CAPTCHA page.")
                time.sleep(4)
                return

            try: alert.accept()
            except Exception: pass
            return

        except TimeoutException:
            pass
        except Exception as e:
            print(f"Alert handling error: {e}")

        current_url = driver.current_url
        if "captcha.html" in current_url:
            print("Tier 2 triggered (CAPTCHA)")
            return
        if "ghost_ticket.html" in current_url:
            print("Tier 3 triggered (Ghost Ticket)")
            return

        # =========================
        # PHASE 5 - PAYMENT
        # =========================
        WebDriverWait(driver, 10).until(EC.url_contains("payment.html"))
        print("[Bot2] Payment page reached.")

        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "card-number")))
        driver.find_element(By.ID, "card-number").send_keys("4111222233334444")
        driver.find_element(By.ID, "card-expiry").send_keys("1229")
        driver.find_element(By.ID, "card-cvv").send_keys("123")

        print("[Bot2] Submitting payment...")
        driver.execute_script("executeFinalTransaction();")
        time.sleep(5)

        landing = driver.current_url
        print("\n==================================================")
        print("BOT2 INTERCEPTION ANALYSIS")
        if "ghost_ticket.html" in landing:   print("• TIER 3 (Ghost Ticket)")
        elif "captcha.html" in landing:      print("• TIER 2 (CAPTCHA)")
        elif "success.html" in landing:      print("• BOT REACHED SUCCESS PAGE")
        else:                                print(f"• FINAL LANDING: {landing}")
        print("==================================================")

    except Exception:
        print("FULL ERROR:")
        traceback.print_exc()
    finally:
        print("[Bot2] Execution complete.")
        input("Press ENTER to close browser...")
        driver.quit()


if __name__ == "__main__":
    target = "https://tickago.onrender.com/waitingroom.html"
    print("\n==================================================")
    print("BOT 2 — TIER 2 TRIGGER (Bulk qty override)")
    print("==================================================")
    run_single_bot(target, (520, 10, 500, 800))