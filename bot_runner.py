import sys
from bot_worker import run_single_bot

# ==========================================================
# 🚀 SINGLE-BOT CLI RUNNER
# Thin wrapper around bot_worker.py's run_single_bot() so you get the
# same "python3 bot_runner.py [1|2|3]" convenience botnew.py had, but
# driving the ACTUAL Tickago site (correct URL, correct element IDs/
# structure) instead of the old fyp1-gnoo one. Because this drives real
# pages, telemetry.js + confirm.html/payment.html's own JS fire exactly
# as they would for a real visitor - /evaluate gets called normally, and
# every attempt shows up in evaluation_logs / the /monitor dashboard
# with no extra plumbing needed.
# ==========================================================

TARGET_URL = "https://tickago.onrender.com/waitingroom.html"
WINDOW_POSITION = (100, 100, 480, 800)  # x, y, width, height

BEHAVIOR_MAP = {
    "1": "tier1",   # rapid clicks, no mouse telemetry -> Tier 1 fast-path delay
    "2": "tier2",   # qty override + timing pattern -> Tier 2 CAPTCHA
    "3": "tier3",   # stacked scoring signals -> Tier 3 ghost ticket
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in BEHAVIOR_MAP:
        print("Usage: python3 bot_runner.py [1|2|3]")
        print("  1 -> Tier 1 trigger (fast, no mouse movement)")
        print("  2 -> Tier 2 trigger (bulk qty, instant selection)")
        print("  3 -> Tier 3 trigger (known-bad pattern + max qty + instant speed)")
        sys.exit(1)

    choice = sys.argv[1]
    behavior = BEHAVIOR_MAP[choice]
    print("=" * 55)
    print(f"Bot Runner - Tier {choice} Trigger ({behavior}) Initiated")
    print(f"Target: {TARGET_URL}")
    print("=" * 55)

    run_single_bot(TARGET_URL, WINDOW_POSITION, bot_id=int(choice), behavior=behavior)