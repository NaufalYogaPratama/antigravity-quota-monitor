#!/usr/bin/env python3
import json
import os
import sqlite3
import sys
import time

DEFAULT_DB_PATH = os.path.expanduser("~/.omp/agent/agent.db")

def format_countdown(resets_at_ms, now_ms):
    if not resets_at_ms or resets_at_ms <= now_ms:
        return "0m"
    diff_min = max(0, int((resets_at_ms - now_ms) / (1000 * 60)))
    hours, mins = divmod(diff_min, 60)
    days, hours = divmod(hours, 24)
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"

def fetch_usage(db_path=DEFAULT_DB_PATH):
    if not os.path.exists(db_path):
        return {
            "status": "empty",
            "message": "OMP database not found",
            "accounts": []
        }

    uri = f"file:{os.path.abspath(db_path)}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=1.0)
        cur = conn.cursor()

        # Query active accounts
        cur.execute("""
            SELECT SUBSTR(identity_key, 7)
            FROM auth_credentials 
            WHERE provider = 'google-antigravity' 
              AND disabled_cause IS NULL
        """)
        active_emails = {row[0] for row in cur.fetchall()}

        if not active_emails:
            conn.close()
            return {
                "status": "empty",
                "message": "No active Antigravity accounts",
                "accounts": []
            }

        query = """
        WITH latest AS (
            SELECT email, label, window_label, used_fraction, status, resets_at, recorded_at,
                   ROW_NUMBER() OVER (PARTITION BY email, label, window_label ORDER BY recorded_at DESC) as rn
            FROM usage_history
            WHERE provider = 'google-antigravity'
        )
        SELECT email, label, window_label, used_fraction, status, resets_at, recorded_at
        FROM latest
        WHERE rn = 1
        ORDER BY recorded_at DESC
        """
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()

        now_ms = int(time.time() * 1000)
        accounts_map = {}

        # Initialize accounts
        for email in sorted(active_emails):
            username = email.split("@")[0]
            accounts_map[email] = {
                "email": email,
                "display_name": username,
                "is_active_session": False,
                "metrics_dict": {}
            }

        max_synced_at = 0

        for r in rows:
            email, label, window, used_frac, status, resets_at, recorded_at = r
            if email not in accounts_map:
                continue

            max_synced_at = max(max_synced_at, recorded_at or 0)
            rem_pct = round(max(0.0, min(100.0, (1.0 - (used_frac or 0.0)) * 100.0)), 1)
            resets_in = format_countdown(resets_at, now_ms)

            # Classify into 3 standard tiers
            if label == "Gemini" and window == "5 Hour":
                tier_key = "gemini_5h"
                display_label = "Gemini (5h)"
            elif label == "Gemini" and window == "Weekly":
                tier_key = "gemini_weekly"
                display_label = "Gemini (7d)"
            elif "Claude" in label or "GPT" in label:
                tier_key = "claude_gpt_weekly"
                display_label = "Claude & GPT"
            else:
                continue

            if tier_key not in accounts_map[email]["metrics_dict"]:
                accounts_map[email]["metrics_dict"][tier_key] = {
                    "tier_key": tier_key,
                    "label": display_label,
                    "remaining_pct": rem_pct,
                    "status": status if status else ("exhausted" if rem_pct == 0 else "ok"),
                    "resets_in": resets_in
                }

        account_list = []
        tier_order = ["gemini_5h", "gemini_weekly", "claude_gpt_weekly"]

        for email, acc in accounts_map.items():
            metrics = []
            for t_key in tier_order:
                if t_key in acc["metrics_dict"]:
                    metrics.append(acc["metrics_dict"][t_key])
                else:
                    # Default placeholder if specific tier not recorded yet
                    metrics.append({
                        "tier_key": t_key,
                        "label": "Gemini (5h)" if t_key == "gemini_5h" else ("Gemini (7d)" if t_key == "gemini_weekly" else "Claude & GPT"),
                        "remaining_pct": 100.0,
                        "status": "ok",
                        "resets_in": "-"
                    })
            account_list.append({
                "email": acc["email"],
                "display_name": acc["display_name"],
                "is_active_session": False,
                "metrics": metrics
            })

        return {
            "status": "ok",
            "synced_at": max_synced_at or now_ms,
            "accounts": account_list
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "accounts": []
        }

if __name__ == "__main__":
    result = fetch_usage()
    print(json.dumps(result))
