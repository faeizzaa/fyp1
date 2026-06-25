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

def dismiss_stacked_alert(driver, label=""):
    """Check for a SECOND alert stacking up right behind the one we just
    dismissed. If /evaluate is ever firing twice for one click, this is
    what would silently block the redirect - this surfaces it instead."""
    try:
        WebDriverWait(driver, 2).until(EC.alert_is_present())
        second_alert = driver.switch_to.alert
        print(f"⚠️  A SECOND alert appeared{(' ' + label) if label else ''}: {second_alert.text}")
        second_alert.accept()
        return True
    except TimeoutException:
        return False
    except Exception as e:
        print(f"⚠️  Error checking for a stacked alert: {e}")
        return False


def run_single_bot(target_url, screen_position):
    print(f"[Bot2] Window staging initialized...")
    
    chrome_options = Options()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, "chrome_sandbox_profile_bot2")
    
    # Targets the standard Google Chrome installation path
    chrome_options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception:
            pass
            
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
    except Exception as init_err:
        print(f"❌ [Bot2] Driver Crash: {init_err}")
        return
    
    x_pos, y_pos, width, height = screen_position
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(width, height)
    
    try:
        # ==========================================
        # PHASE 1 - WAITING ROOM ENTRY
        # ==========================================
        print(f"[Bot2] Target entry initiated: {target_url}")
        driver.get(target_url)
        
        enter_btn = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "enter-btn"))
        )
        print("[Bot2] Waiting room loaded. Instantiating valid queue gate context...")
        
        driver.execute_script("""
            sessionStorage.setItem('gate_token', Date.now().toString());
            if(!localStorage.getItem('start_time')){ localStorage.setItem('start_time', Date.now()); }
        """)
        time.sleep(1)
        driver.execute_script("document.getElementById('enter-btn').click();")

        # ==========================================
        # PHASE 2 - SALE LIVE GATE TRAVERSAL
        # ==========================================
        WebDriverWait(driver, 10).until(EC.url_contains("salelive.html"))
        print("[Bot2] Passing live sale gate room...")
        
        buy_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "buy-btn"))
        )
        driver.execute_script("enterSale();")

        # ==========================================
        # PHASE 3 - SEAT SELECTION & PARAMETER INJECTION
        # ==========================================
        WebDriverWait(driver, 10).until(EC.url_contains("select.html"))
        print("[Bot2] Entering selection matrix...")

        # Pick Event Date Card
        date_card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "date-card"))
        )
        driver.execute_script("arguments[0].click();", date_card)
        time.sleep(0.5)

        # Open Layout Window
        rock_zone = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "btn-rock"))
        )
        driver.execute_script("document.getElementById('btn-rock').click();")
        time.sleep(0.5)

        # Select a standard map coordinate node
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".seat.available"))
        )
        driver.execute_script("""
            const seat = document.querySelector('.seat[data-sid="A1"]');
            if (seat && seat.classList.contains('available')) {
                seat.click();
            }
        """)
        
        # Human mimic delay gap targeting Tier 2 evaluation constraints
        time.sleep(1.8)

        print("[Bot2] Injecting ticket volume overrides to force Tier 2 detection boundary...")
        driver.execute_script("""
            localStorage.setItem('selected_qty', '5'); 
            localStorage.setItem('qty_select_speed', '1600');
            let pattern = localStorage.getItem('fyp_pattern') || 'HAD';
            if(!pattern.includes('SSSQC')) {
                localStorage.setItem('fyp_pattern', pattern + 'SSSQC');
            }
        """)
        time.sleep(0.5)
        driver.execute_script("goNext();")

        # ==========================================
        # PHASE 4 - CHECKOUT VALIDATION & ALERT CAPTURE
        # ==========================================
        WebDriverWait(driver, 10).until(EC.url_contains("confirm.html"))
        print("[Bot2] Confirmation terminal reached. Submitting verification payload...")
        
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "fullname")))
        driver.execute_script("""
            document.getElementById('fullname').value = 'Automated Agent';
            document.getElementById('email').value = 'bot2@telemetry.io';
        """)
        
        driver.execute_script("validateAndCheckout();")
        
        # Intercept and process browser notification mechanics
        try:
            WebDriverWait(driver, 8).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"\n==================================================")
            print(f"🚨 INTERCEPTED ALERT: {alert_text}")
            print(f"==================================================")
            alert.accept()
            dismiss_stacked_alert(driver, "after Tier 2 mitigation")
        except TimeoutException:
            print("[Bot2] Transitioning boundary without alert interruptions.")

        # ==========================================
        # PHASE 5 - CAPTCHA RETENTION LOOP
        # ==========================================
        WebDriverWait(driver, 12).until(EC.url_contains("captcha.html"))
        print("\n==================================================")
        print("🔥 MITIGATION TARGET VERIFIED: INTENT ROUTED TO CAPTCHA TIER")
        print("• Status: Session isolated. Waiting for human interaction verification.")
        print("==================================================")

        # Track if manual validation succeeds and transfers downstream
        WebDriverWait(driver, 300).until(EC.url_contains("payment.html"))
        print(f"\n[Bot2] ✓ CAPTCHA cleared successfully. Finalizing landing channel: {driver.current_url}")

    except Exception:
        print("❌ CRITICAL EXCEPTION INSIDE BOT RUNTIME EXECUTION:")
        traceback.print_exc()
    finally:
        print("[Bot2] Automation cycle terminated.")
        input("Press ENTER to destroy sandboxed worker shell...")
        driver.quit()


if __name__ == "__main__":
    target = "https://tickago.onrender.com/waitingroom.html"
    window_width = 500 
    window_height = 800
    single_position = (550, 10, window_width, window_height)
    
    run_single_bot(target, single_position)