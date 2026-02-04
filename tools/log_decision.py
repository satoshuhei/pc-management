import sys
from datetime import datetime, timezone, timedelta

LOG_PATH = "docs/decision_log.md"
JST = timezone(timedelta(hours=9))

def get_now_jst():
    return datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S")

def prepend_log(summary: str, instruction: str, response: str):
    now = get_now_jst()
    entry = f"[{now}]\n概要: {summary}\n指示全文: {instruction}\n対応内容: {response}\n\n"
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            old = f.read()
    except FileNotFoundError:
        old = ""
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(entry + old)

def main():
    if len(sys.argv) < 3:
        print("usage: python -m tools.log_decision '概要' '指示全文' ['対応内容']")
        sys.exit(1)
    summary = sys.argv[1]
    instruction = sys.argv[2]
    response = sys.argv[3] if len(sys.argv) > 3 else "(未記入)"
    prepend_log(summary, instruction, response)
    print("decision_log.mdに追記しました")

if __name__ == "__main__":
    main()
