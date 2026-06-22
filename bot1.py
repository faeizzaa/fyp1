import time
import os
import shutil
import  traceback

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def run_single_bot(target_url, screen_position):
    print(f"[Bot] Window staging initialized...")
    
    chrome_options = Options()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, "chrome_sandbox_profile_single")
    
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
    chrome_options.add_argument("--remote-debugging-port=9221")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-features=CalculateNativeWinOcclusion")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as init_err:
        print(f"❌ [Bot] Driver Crash: {init_err}")
        return
    
    x_pos, y_pos, width, height = screen_position
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(width, height)
    
    try:
        # =========================
        # PHASE 1 - WAITING ROOM
        # =========================

        driver.get(target_url)

        print("[Bot] Target Hit: Synchronizing with active live drop pool timer...")

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        print("[Bot] Waiting for sale to become live...")

        print("[Bot] Waiting room bypass active.")

        driver.get("http://127.0.0.1:5500/home.html")

        print("[Bot] Queue gate bypassed successfully.")

        # =========================
        # PHASE 2 - HOME PAGE
        # =========================

        print("[Bot] Arrived at home page...")
        print("Current URL:", driver.current_url)
        print("Page title:", driver.title)  

        time.sleep(2)

        driver.execute_script("""
        document.getElementById('stray-kids-card').click();
        """)

        WebDriverWait(driver, 10).until(
            EC.url_contains("select.html")
        )

        print("[Bot] Event selected.")

        # =========================
        # PHASE 3 - SEAT SELECTION
        # =========================

        print("[Bot] Processing seating assignment map...")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "date1-card"))
        )

        driver.execute_script("""
        chooseDate(
            '12 Dec 2026 (Day 1 - Saturday)',
            'date1'
            );
        """)

        time.sleep(2)

        driver.execute_script("""
            chooseSeat(
                'Rock Zone (Standing) - RM 599',
                'tier1-card'
            );
        """)

        time.sleep(2)

        print("[Bot] Keep default quantity (1 ticket).")


        driver.execute_script("""
            updateQuantity('1');
        """)

        time.sleep(1)

        driver.execute_script("""
            goNext();
        """)
        
        time.sleep(2)

        print("Current URL:", driver.current_url)

        print(
    "selected_qty =",
    driver.execute_script(
        "return localStorage.getItem('selected_qty');"
    )
)

        WebDriverWait(driver, 10).until(
            EC.url_contains("confirm.html")
        )

        print("[Bot] Proceeded to confirmation.")

        print(
            "Pattern:",
            driver.execute_script(
                "return localStorage.getItem('fyp_pattern');"
            )
        )

        print(
            "Duration:",
            driver.execute_script(
                """
                return Date.now() -
                parseInt(localStorage.getItem('session_start'));
                """
            )
        )


        # =========================
        # PHASE 4 - CONFIRM PAGE
        # =========================

        time.sleep(2)
        
      

        print(
            driver.execute_script(
                "return document.getElementById('fullname').value;"
            )
        )

        print(
            driver.execute_script(
                "return document.getElementById('email').value;"
            )
        )


        print("Current URL before validation:", driver.current_url)

        print(
            "Pattern:",
            driver.execute_script(
            "return localStorage.getItem('fyp_pattern');"
            )
        )

        print(
            "Mouse Moves:",
            driver.execute_script(
                "return localStorage.getItem('fyp_mouse_moves') || '0';"
            )
        )

        print("[Bot] Triggering checkout...")

        driver.execute_script("""
        validateAndCheckout();
        """)

        time.sleep(3)

        # =========================
        # DECISION ENGINE CHECK
        # =========================

        try:

            WebDriverWait(driver, 3).until(
                EC.alert_is_present()
            )

            alert = driver.switch_to.alert

            alert_text = alert.text

            print("🚨 Security Alert:", alert_text)

            if "Tier 1" in alert_text:

                print("\n==================================================")
                print("TIER 1 DETECTION")
                print("Action String: HADSQC")
                print("Behaviour: Elevated Interaction Speed")
                print("Response: Artificial Delay")
                print("==================================================")

                input("\nPress ENTER to continue...")

                try:
                    alert.accept()
                except Exception as accept_err:
                    print(f"⚠️  Could not dismiss alert (likely already closed): {accept_err}")

                return
            
            if "Tier 2" in alert_text:

                print("Tier 2 triggered successfully.")

                input("Press ENTER to continue...")

                try:
                    alert.accept()
                except Exception as accept_err:
                    print(f"⚠️  Could not dismiss alert (likely already closed): {accept_err}")

                time.sleep(99999)

            alert.accept()

        except TimeoutException:
            # No alert appeared at all - normal for a clean (Tier 0) run
            pass
        except Exception as alert_err:
            print(f"⚠️  Alert handling error: {alert_err}")

        #current_url = driver.current_url

        #if "captcha.html" in current_url:
            #print("⚠️ Tier 2 triggered (CAPTCHA)")
            #return

        #if "ghost_ticket.html" in current_url:
            #print("🛡️ Tier 3 triggered (Ghost Ticket)")
            #return

        #WebDriverWait(driver, 10).until(
            #EC.url_contains("payment.html")
        #)

        #print("[Bot] Payment page reached.")

        # =========================
        # PHASE 5 - PAYMENT
        # =========================

        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "card-number"))
        )

        driver.find_element(
            By.ID,
            "card-number"
        ).send_keys("4111222233334444")

        driver.find_element(
            By.ID,
            "card-expiry"
        ).send_keys("1229")

        driver.find_element(
            By.ID,
            "card-cvv"
        ).send_keys("123")

        print("[Bot] Submitting payment payload...")

        driver.execute_script("""
            executeFinalTransaction();
        """)

        time.sleep(5)

        landing_zone = driver.current_url

        print("\n==================================================")
        print("🤖 BOT DEMO INTERCEPTION ANALYSIS")

        if "ghost_ticket.html" in landing_zone:
            print("• TIER 3 SUCCESS (Ghost Ticket Trap)")
        elif "captcha.html" in landing_zone:
            print("• TIER 2 SUCCESS (CAPTCHA Triggered)")
        elif "success.html" in landing_zone:
            print("• BOT REACHED SUCCESS PAGE")
        else:
            print(f"• FINAL LANDING: {landing_zone}")

        print("==================================================")

    except Exception as e:
        print(f"FULL ERROR:")
        traceback.print_exc()

    finally:
        print("[Bot] Execution complete.")
        input("Press ENTER to close browser...")
        driver.quit()

if __name__ == "__main__":
    target = "http://127.0.0.1:5500/waitingroom.html" 
    
    print("\n==================================================")
    print("LAUNCHING SINGLE ISOLATED AUTOMATION AGENT")
    print("🔥 DIRECT WAITING ROOM TARGETING ACTIVE")
    print("==================================================")
    
    window_width = 500 
    window_height = 800
    single_position = (10, 10, window_width, window_height)
    
    run_single_bot(target, single_position)