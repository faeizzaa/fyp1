from bot_worker import run_single_bot

TARGET_URL = "https://tickago.onrender.com/waitingroom.html"
WINDOW_POSITION = (560, 50, 480, 800)

USERNAME = "def"
PASSWORD = "TestPass123!"

if __name__ == "__main__":
    run_single_bot(
        TARGET_URL, WINDOW_POSITION, bot_id=2, behavior="tier2",
        fixed_credentials=(USERNAME, PASSWORD)
    )