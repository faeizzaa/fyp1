import time
import threading
import os
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

global_checkout_counter = 0
counter_lock = threading.Lock()

def run_bot_instance(bot_id, target_url, screen_position):
    global global_checkout_counter
    print(f"[Bot Thread #{bot_id}] Window staging initialized...")
    
    chrome_options = Options()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, f"chrome_sandbox_profile_{bot_id}")
    
    # 🌟 FIX: Force Selenium to target standard Google Chrome installation binary paths
    # This prevents your script from launching Edge accidentally!
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
    chrome_options.add_argument(f"--remote-debugging-port={9220 + bot_id}")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-features=CalculateNativeWinOcclusion")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as init_err:
        print(f"❌ [Bot Thread #{bot_id}] Driver Crash: {init_err}")
        return
    
    x_pos, y_pos, width, height = screen_position
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(width, height)
    
    try:
        # --- STAGE 0: LANDING DIRECTLY IN WAITING ROOM ---
        driver.get(target_url)
        print(f"[Bot Thread #{bot_id}] Target Hit: Synchronizing with active live drop pool timer...")
        
        # --- PHASE 1: ACTIVE COUNTDOWN SYNCHRONIZATION ---
        print(f"[Bot Thread #{bot_id}] Waiting in queue room loop...")
        bypass_trigger = WebDriverWait(driver, 45).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#enter-btn.active"))
        )
        bypass_trigger.click()
        print(f"[Bot Thread #{bot_id}] ⚡ Countdown hit 00:00! Forcing navigation jump to home.html...")
        
        # --- PHASE 2: HOME PAGE ROUTING WITH HARD RE-NAVIGATE ---
        # Instead of relying entirely on the browser's redirect processing speed, 
        # force the bot to fetch home.html explicitly.
        time.sleep(0.5) 
        driver.get("http://127.0.0.1:5500/home.html") 

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
            (By.XPATH, "//*[contains(@onclick, 'selectEvent')]")
            )
        )
        
        print(f"[Bot Thread #{bot_id}] Arrived at home.html. Scanning DOM for concert card...")
        
        # Robust element locator combination: wait for presence, scroll, then click via execution engine
        concert_card = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(@onclick, 'selectEvent')]"))
        )
        
        driver.execute_script("arguments[0].scrollIntoView(true);", concert_card)
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(@onclick, 'selectEvent')]")))
        driver.execute_script("arguments[0].click();", concert_card)
        
        print(f"[Bot Thread #{bot_id}] Event picked successfully. Navigating to seating panel...")

        # --- PHASE 3: SEATING & QUANTITY SELECTION ---
        date_card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "date1-card"))
        )
        date_card.click()
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "seat-section")))
        
        # Select target tier
        seat_card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "tier1-card"))
        )
        seat_card.click()
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "next-btn")))

        # Inject excessive ticket request to challenge behavioral rules
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "select-qty-1")))
        driver.execute_script("""
            let qtySelect = document.getElementById('select-qty-1');
            if (qtySelect) {
                qtySelect.value = '5';
                qtySelect.dispatchEvent(new Event('change'));
                localStorage.setItem('selected_qty', '5');
            }
        """)
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "next-btn")))

        driver.find_element(By.ID, "next-btn").click()
        print(f"[Bot Thread #{bot_id}] Quantity validation locked. Navigating to checkout details...")

        # --- PHASE 4: REVIEWS & PROFILE FORM INJECTION ---
        fullname_field = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "fullname")))
        fullname_field.clear()
        fullname_field.send_keys(f"Bot-Agent-{bot_id}")
        
        email_field = driver.find_element(By.ID, "email")
        email_field.clear()
        email_field.send_keys(f"automated_swarm_{bot_id}@botnet.com")
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[contains(text(), 'Proceed') or @id='proceed-btn']"
            )
            )
        ).click()
        # --- PHASE 5: SECURE PAYMENT CHECKOUT ---
        print("[Bot] Arrived at secure payment terminal...")
        card_field = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "card-number"))
        )
        card_field.send_keys("4111222233334444")
        driver.find_element(By.ID, "card-expiry").send_keys("1229")
        driver.find_element(By.ID, "card-cvv").send_keys("123")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "card-cvv")))

        print("[Bot] Submitting final checkout payment payload...")
        
        # 🌟 FIX: Target the button using its text value instead of a non-existent ID
        pay_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Submit Secure Payment')]"))
        )
        pay_button.click()
        
        # Handle the confirmation browser alert prompt box automatically
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            print(f"[Bot] Browser Alert Intercepted: {alert.text}")
            alert.accept()
            print("[Bot] Alert confirmed.")
        except Exception:
            print("[Bot] No intermediate alert pop-up encountered.")

        # Wait to analyze redirection zone routing behavior
        WebDriverWait(driver, 10).until(
            lambda d:
                "success.html" in d.current_url
                or "captcha.html" in d.current_url
                or "ghost_ticket.html" in d.current_url
        )

        landing_zone = driver.current_url
        
        print(f"\n==================================================\n🤖 BOT DEMO INTERCEPTION ANALYSIS")
        print(f"• Target Node: Browser Instance #{bot_id}")
        if "ghost_ticket.html" in landing_zone:
            print(f"• MITIGATION TIER STRATEGY: SUCCESS 🛡️ (Trapped in Honeypot)")
        elif "captcha.html" in landing_zone:
            print(f"• MITIGATION TIER STRATEGY: SUCCESS ⚠️ (Blocked by CAPTCHA)")
        else:
            print(f"• MITIGATION TIER STRATEGY: FAILED ❌ (Reached Destination: {landing_zone})")
        print(f"==================================================")
            
    except Exception as e:
        print(f"❌ [Bot Thread #{bot_id}] Automation sequence execution error: {e}")
    finally:
        input(f"[Bot Thread #{bot_id}] Press ENTER to close...")
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    # TARGET ALTERED: Direct connection deployment right into the waiting room page layout
    target = "http://127.0.0.1:5500/waitingroom.html" 
    
    print("\n==================================================")
    print("LAUNCHING STAGED APERIODIC MULTI-WINDOW BOT SWARM")
    print("DIRECT WAITING ROOM TARGETING ACTIVE")
    print("==================================================")
    
    window_width = 440 
    window_height = 750
    positions = [(0, 0, window_width, window_height), (450, 0, window_width, window_height), (900, 0, window_width, window_height)]
    
    bot_threads = []
    for i in range(1, 4):
        thread = threading.Thread(target=run_bot_instance, args=(i, target, positions[i-1]))
        bot_threads.append(thread)
        
    for thread in bot_threads:
        thread.start()
        time.sleep(0.5)
        
    for thread in bot_threads:
        thread.join()