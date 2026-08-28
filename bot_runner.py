import sys
import multiprocessing
from bot_worker import run_single_bot, run_repeat_offender_test

# ==========================================================
# 🚀 BOT RUNNER
# Single-bot mode:  python3 bot_runner.py [1|2|3]
# All-at-once mode: python3 bot_runner.py all
#   -> launches bot1 (Tier 1), bot2 (Tier 2), bot3 (Tier 3)
#      simultaneously as separate processes (Selenium/Chrome
#      instances can't share one process), each tiled on
#      screen, each independently registering + logging its
#      own attempt to evaluation_logs.
# ==========================================================

TARGET_URL = "https://tickago.onrender.com/waitingroom.html"

BEHAVIOR_MAP = {
    "1": "tier1",   # rapid clicks, no mouse telemetry -> Tier 1 fast-path delay
    "2": "tier2",   # qty override + timing pattern -> Tier 2 CAPTCHA
    "3": "tier3",   # stacked scoring signals -> Tier 3 ghost ticket
}

WINDOW_W, WINDOW_H = 480, 800


def window_position(bot_id):
    # Tile side-by-side so all 3 browser windows are visible at once
    return ((bot_id - 1) * (WINDOW_W + 10) + 50, 50, WINDOW_W, WINDOW_H)


def run_all():
    print("=" * 57)
    print("  Running ALL 3 bots at once: bot1=Tier1, bot2=Tier2, bot3=Tier3")
    print("=" * 57)
    print()

    processes = []
    for bot_id_str, behavior in BEHAVIOR_MAP.items():
        bot_id = int(bot_id_str)
        p = multiprocessing.Process(
            target=run_single_bot,
            args=(TARGET_URL, window_position(bot_id), bot_id, behavior)
        )
        processes.append(p)

    for p in processes:
        p.start()

    for p in processes:
        p.join()

    print("\nAll 3 bots finished. Check /monitor or evaluation_logs for the results.")


if __name__ == "__main__":
    if len(sys.argv) < 2 or (sys.argv[1] not in BEHAVIOR_MAP and sys.argv[1] not in ("all", "repeat")):
        print("Usage: python3 bot_runner.py [1|2|3|all|repeat]")
        print("  1      -> Tier 1 trigger (fast, no mouse movement)")
        print("  2      -> Tier 2 trigger (bulk qty, instant selection)")
        print("  3      -> Tier 3 trigger (known-bad pattern + max qty + instant speed)")
        print("  all    -> run bot1/bot2/bot3 simultaneously, one per tier")
        print("  repeat -> same account attempts Tier 3 twice: expect ghost ticket,")
        print("            then a hard block on the 2nd attempt")
        sys.exit(1)

    if sys.argv[1] == "all":
        run_all()
    elif sys.argv[1] == "repeat":
        run_repeat_offender_test(TARGET_URL, window_position(1), bot_id=1)
    else:
        choice = sys.argv[1]
        behavior = BEHAVIOR_MAP[choice]
        run_single_bot(TARGET_URL, window_position(int(choice)), bot_id=int(choice), behavior=behavior)