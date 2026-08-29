from bot_worker import run_single_bot

TARGET_URL = "https://tickago.onrender.com/waitingroom.html"
WINDOW_POSITION = (50, 50, 480, 800)

USERNAME = "tier3_bot"
PASSWORD = "TestPass123!"

if __name__ == "__main__":
    run_single_bot(
        TARGET_URL, WINDOW_POSITION, bot_id=3, behavior="tier3",
        fixed_credentials=(USERNAME, PASSWORD)
    )