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

# ==========================================================
# 🤖 BOT 1 — TIER 1 TRIGGER AGENT (REVISED VERSION)
# Behaviour: Rapid sequential automated clicks, zero mouse telemetry.
# Expected Response: Tier 1 Identification -> Artificial Delay
# ==========================================================

def run_single_bot(target_url, screen_position):
    print(f"[Bot1] Window staging initialized...")

    chrome_options = Options()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, "chrome_sandbox_profile_bot1")

    # If running on Windows/Mac, comment out this binary location line if necessary
    # chrome_options.binary_location = "/usr/bin/google-chrome"
    
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

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
    except Exception as init_err:
        print(f"❌ [Bot1] Driver Crash: {init_err}")
        return

    x_pos, y_pos, width, height = screen_position
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(width, height)

    try:
        # ==========================================================
        # PHASE 1 - WAITING ROOM ENTRY
        # ==========================================================
        print(f"[Bot1] Target entry initiated: {target_url}")
        driver.get(target_url)
        
        enter_btn = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "enter-btn"))
        )
        print("[Bot1] Waiting room loaded. Injecting verification token variables safely...")
        
        # Inject validation markers to simulate a valid queue pass context
        driver.execute_script("""
            sessionStorage.setItem('gate_token', Date.now().toString());
            if(!localStorage.getItem('start_time')){ localStorage.setItem('start_time', Date.now()); }
        """)
        time.sleep(1)
        driver.execute_script("document.getElementById('enter-btn').click();")

        # ==========================================================
        # PHASE 2 - SALE LIVE GATE TRAVERSAL
        # ==========================================================
        WebDriverWait(driver, 10).until(EC.url_contains("salelive.html"))
        print("[Bot1] Landing on live sale room gate. Progressing transaction pipeline...")
        
        buy_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "buy-btn"))
        )
        driver.execute_script("enterSale();")

        # ==========================================================
        # PHASE 3 - SEAT SELECTION
        # ==========================================================
        WebDriverWait(driver, 10).until(EC.url_contains("select.html"))
        print("[Bot1] Scanning interactive target elements...")

        # Select the Event Date Card organically
        date_card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "date-card"))
        )
        driver.execute_script("arguments[0].click();", date_card)
        time.sleep(0.5)

        # Expand Rock Zone
        rock_zone = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "btn-rock"))
        )
        driver.execute_script("document.getElementById('btn-rock').click();")
        time.sleep(0.5)

        # Select active coordinate node (Seat A1)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".seat.available"))
        )
        print("[Bot1] Locking seat coordinates...")
        driver.execute_script("""
            const seat = document.querySelector('.seat[data-sid="A1"]');
            if (seat && seat.classList.contains('available')) {
                seat.click();
            }
        """)
        time.sleep(0.5)

        # Forward execution to calculation/confirmation deck
        driver.execute_script("goNext();")

        # ==========================================================
        # PHASE 4 - CONFIRMATION ASSESSMENT
        # ==========================================================
        WebDriverWait(driver, 10).until(EC.url_contains("confirm.html"))
        print("[Bot1] Form calculation complete. Analyzing threat pattern array parameters...")

        pattern = driver.execute_script("return localStorage.getItem('fyp_pattern');")
        duration = driver.execute_script("return Date.now() - parseInt(localStorage.getItem('start_time'));")
        mouse_moves = driver.execute_script("return localStorage.getItem('fyp_mouse_moves') || '0';")
        
        print(f"[Bot1] Pattern signature generated: {pattern}")
        print(f"[Bot1] Session delta time: {duration}ms")
        print(f"[Bot1] Total mouse positions logged: {mouse_moves}")

        print("[Bot1] Deploying payload check call -> validateAndCheckout()")
        driver.execute_script("validateAndCheckout();")
        
        # ==========================================================
        # SECURITY INTERCEPT HANDLER
        # ==========================================================
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"\n==================================================")
            print(f"🚨 INTERCEPTED SECURITY NOTICE: {alert_text}")
            print(f"==================================================")

            if "Tier 1" in alert_text:
                print("[Bot1] Target Verified: Tier 1 Mitigation applied (Artificial Delay).")
            
            alert.accept()
            print("[Bot1] Security alert dismissed. Proceeding along verification channel...")
        except TimeoutException:
            print("[Bot1] No blocking dialog window was intercepted directly.")

        # ==========================================================
        # PHASE 5 - FINAL ROUTING VERIFICATION
        # ==========================================================
        print("[Bot1] Tracking post-evaluation route routing context...")
        time.sleep(4)  # Let any artificial window delays complete execution
        
        landing = driver.current_url
        print("\n==================================================")
        print("📊 FINAL TRANSACTION ROUTE RESOLUTION")
        if "ghost_ticket.html" in landing:   print("• ROUTE RESULT: TIER 3 (Ghost Ticket Isolation)")
        elif "captcha.html" in landing:      print("• ROUTE RESULT: TIER 2 (CAPTCHA Validation Core)")
        elif "payment.html" in landing:      print("• ROUTE RESULT: TIER 1 / PASS (Forwarded to payment screen)")
        elif "success.html" in landing:      print("• ROUTE RESULT: UNRESTRICTED ORDER PLACEMENT SUCCESS")
        else:                                print(f"• ROUTE RESULT: UNKNOWN REDIRECT PATH -> {landing}")
        print("==================================================")

    except Exception:
        print("❌ CRITICAL SCRIPT EXECUTION FAULT:")
        traceback.print_exc()
    finally:
        print("[Bot1] Pipeline lifecycle complete.")
        input("Press ENTER to destroy isolated test driver process...")
        driver.quit()

if __name__ == "__main__":
    target = "https://tickago.onrender.com/waitingroom.html"
    print("\n==================================================")
    print("🚀 RUNNING BOT 1 PIPELINE — TARGET TIER 1")
    print("==================================================")
    run_single_bot(target, (10, 10, 500, 800))