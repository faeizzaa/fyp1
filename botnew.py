import sys
import time
import os
import shutil
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# TARGET URL DEFINITION
TARGET_URL = "https://fyp1-gnoo.onrender.com/"

def setup_driver(profile_suffix):
    chrome_options = Options()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, f"chrome_profile_{profile_suffix}")
    
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception:
            pass
            
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

# =======================================================
# BOT 1: TIER 1 TRIGGER (Fast single seat, no mouse moves)
# =======================================================
def run_bot1():
    print("=" * 55)
    print("Bot 1 - Tier 1 Trigger Initiated")
    print("=" * 55)
    driver = setup_driver("bot1")
    
    try:
        print("[Phase 1] Bypassing waiting room...")
        driver.get(TARGET_URL)
        
        driver.execute_script("""
            localStorage.setItem('queue_bypass_token', 'FYP_BYPASS_GRANTED');
            localStorage.setItem('fyp_pattern', 'HA');
            localStorage.setItem('session_start_time', Date.now());
        """)
        
        select_url = TARGET_URL.rstrip('/') + "/select"
        print("[Phase 2] Navigating to select page...")
        driver.get(select_url)
        time.sleep(2)

        print("[Phase 3] Selecting date...")
        date_card = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "date1-card"))
        )
        date_card.click()

        print("[Phase 3] Selecting Rock Zone...")
        # 🛠️ FIXED: Updated selector to find the class or text structure reliably
        rock_zone = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(@class, 'zone-card') or contains(text(), 'ROCK ZONE')]"))
        )
        rock_zone.click()

        # 🛠️ FIXED: Changed 'qty-section' to the correct container check to prevent null errors
        driver.execute_script("""
            localStorage.setItem('selected_qty', '1');
            let qtyContainer = document.getElementById('qty-section') || document.getElementById('qty-list');
            if(qtyContainer) { qtyContainer.style.display = 'block'; }
            localStorage.setItem('qty_select_speed', '85');
        """)
        time.sleep(0.5)

        next_btn = driver.find_element(By.ID, "next-btn")
        driver.execute_script("arguments[0].click();", next_btn)

        print("[Phase 4] Filling user information...")
        fullname = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.ID, "fullname"))
        )
        fullname.send_keys("Bot-Tier1-Agent")
        driver.find_element(By.ID, "email").send_keys("bot1@test.com")
        
        print("[Phase 4] Submitting form...")
        submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Proceed to Payment')]")
        driver.execute_script("arguments[0].click();", submit_btn)

        time.sleep(3)
        print(f"• Target Landing Zone: {driver.current_url}")

    except Exception as e:
        traceback.print_exc()
    finally:
        driver.quit()

# =======================================================
# BOT 2: TIER 2 TRIGGER (Single seat + qty override to 5)
# =======================================================
def run_bot2():
    print("=" * 55)
    print("Bot 2 - Tier 2 Trigger Initiated")
    print("=" * 55)
    driver = setup_driver("bot2")
    
    try:
        print("[Phase 1] Bypassing waiting room...")
        driver.get(TARGET_URL)
        
        driver.execute_script("""
            localStorage.setItem('queue_bypass_token', 'FYP_BYPASS_GRANTED');
            localStorage.setItem('fyp_pattern', 'HA');
            localStorage.setItem('session_start_time', Date.now());
        """)
        
        select_url = TARGET_URL.rstrip('/') + "/select"
        print("[Phase 2] Navigating to select page...")
        driver.get(select_url)
        time.sleep(2)

        print("[Phase 3] Selecting date...")
        date_card = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "date1-card"))
        )
        date_card.click()

        # 🛠️ FIXED: Handled Javascript null guard style exception
        driver.execute_script("""
            localStorage.setItem('selected_qty', '5');
            let qtyContainer = document.getElementById('qty-section') || document.getElementById('qty-list');
            if(qtyContainer) { qtyContainer.style.display = 'block'; }
            localStorage.setItem('qty_select_speed', '12');
        """)
        time.sleep(0.5)

        next_btn = driver.find_element(By.ID, "next-btn")
        driver.execute_script("arguments[0].click();", next_btn)

        print("[Phase 4] Filling user information...")
        fullname = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.ID, "fullname"))
        )
        fullname.send_keys("Bot-Tier2-Agent")
        driver.find_element(By.ID, "email").send_keys("bot2@test.com")
        
        print("[Phase 4] Submitting form...")
        submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Proceed to Payment')]")
        driver.execute_script("arguments[0].click();", submit_btn)

        time.sleep(3)
        print(f"• Target Landing Zone: {driver.current_url}")

    except Exception as e:
        traceback.print_exc()
    finally:
        driver.quit()

# =======================================================
# BOT 3: TIER 3 TRIGGER (Repeated seat clicks + qty override)
# =======================================================
def run_bot3():
    print("=" * 55)
    print("Bot 3 - Tier 3 Trigger Initiated")
    print("=" * 55)
    driver = setup_driver("bot3")
    
    try:
        print("[Phase 1] Bypassing waiting room...")
        driver.get(TARGET_URL)
        
        driver.execute_script("""
            localStorage.setItem('queue_bypass_token', 'FYP_BYPASS_GRANTED');
            localStorage.setItem('fyp_pattern', 'HA');
            localStorage.setItem('session_start_time', Date.now());
        """)
        
        select_url = TARGET_URL.rstrip('/') + "/select"
        print("[Phase 2] Navigating to select page...")
        driver.get(select_url)
        time.sleep(2)

        print("[Phase 3] Selecting date...")
        date_card = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "date1-card"))
        )
        date_card.click()

        # 🛠️ FIXED: Handled Javascript null guard style exception
        driver.execute_script("""
            localStorage.setItem('selected_qty', '5');
            let qtyContainer = document.getElementById('qty-section') || document.getElementById('qty-list');
            if(qtyContainer) { qtyContainer.style.display = 'block'; }
            localStorage.setItem('qty_select_speed', '12');
        """)
        time.sleep(0.5)

        next_btn = driver.find_element(By.ID, "next-btn")
        driver.execute_script("arguments[0].click();", next_btn)

        print("[Phase 4] Emulating high-speed form hammering field parameters...")
        fullname = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.ID, "fullname"))
        )
        for _ in range(3):
            fullname.clear()
            fullname.send_keys("Bot-Agent-Malicious-Thread")
        
        driver.execute_script("localStorage.setItem('fyp_pattern', (localStorage.getItem('fyp_pattern') || '') + 'R_R_R');")
        driver.find_element(By.ID, "email").send_keys("bot3@test.com")
        
        print("[Phase 4] Submitting form...")
        submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Proceed to Payment')]")
        driver.execute_script("arguments[0].click();", submit_btn)

        time.sleep(3)
        print(f"• Target Landing Zone: {driver.current_url}")

    except Exception as e:
        traceback.print_exc()
    finally:
        driver.quit()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 bot_runner.py [1|2|3]")
        sys.exit(1)
        
    choice = sys.argv[1]
    if choice == "1":
        run_bot1()
    elif choice == "2":
        run_bot2()
    elif choice == "3":
        run_bot3()
    else:
        print("Invalid Choice. Choose 1, 2, or 3.")