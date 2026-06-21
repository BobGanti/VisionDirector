from pathlib import Path

path = Path("src/smx_visiondirector/admin_dashboard.py")
text = path.read_text(encoding="utf-8")

needle = '''    status_value = "Ready" if available_count else "Needs Setup"

    cards = [
'''

replacement = '''    status_value = "Ready" if available_count else "Needs Setup"
    total_events = len(events)
    successful_events = total_events - len(failed_events)
    success_rate = (
        f"{round((successful_events / total_events) * 100)}%"
        if total_events
        else "No Events"
    )

    cards = [
'''

if needle not in text:
    raise SystemExit("Could not find status_value/cards anchor.")

text = text.replace(needle, replacement, 1)

needle = '''        (
            "Token Volume",
            _num(total_tokens),
            "Provider-reported token usage counts only; monetary estimates are not shown.",
        ),
'''

replacement = '''        (
            "Success Rate",
            success_rate,
            "Share of recent token events that completed successfully.",
        ),
        (
            "Token Volume",
            _num(total_tokens),
            "Provider-reported token usage counts only; monetary estimates are not shown.",
        ),
'''

if needle not in text:
    raise SystemExit("Could not find Token Volume card anchor.")

text = text.replace(needle, replacement, 1)
path.write_text(text, encoding="utf-8")
print("Restored Success Rate executive analytics card.")
