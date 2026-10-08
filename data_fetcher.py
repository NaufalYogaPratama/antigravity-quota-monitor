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

def extract_email(identity_key):
    if not identity_key:
        return ""
    if identity_key.startswith("email:"):
        part = identity_key[6:]
        return part.split("|")[0].strip()
    return identity_key.split("|")[0].strip()

def fetch_usage(db_path=DEFAULT_DB_PATH):
    empty_result = {
        "status": "empty",
        "message": "Database not found or empty",
        "providers": {
            "antigravity": {"name": "Google Antigravity", "accounts": []},
            "codex": {"name": "OpenAI Codex", "accounts": []}
        },
        "accounts": []
    }

    if not os.path.exists(db_path):
        return empty_result

    uri = f"file:{os.path.abspath(db_path)}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=1.0)
        cur = conn.cursor()

        # Query active accounts for both providers
        cur.execute("""
            SELECT provider, identity_key
            FROM auth_credentials 
            WHERE provider IN ('google-antigravity', 'openai-codex')
              AND disabled_cause IS NULL
        """)
        auth_rows = cur.fetchall()

        ag_emails = set()
        codex_emails = set()

        for prov, id_key in auth_rows:
            em = extract_email(id_key)
            if em:
                if prov == "google-antigravity":
                    ag_emails.add(em)
                elif prov == "openai-codex":
                    codex_emails.add(em)

        query = """
        WITH latest AS (
            SELECT email, provider, label, window_label, used_fraction, status, resets_at, recorded_at,
                   ROW_NUMBER() OVER (PARTITION BY email, provider, label, window_label ORDER BY recorded_at DESC) as rn
            FROM usage_history
            WHERE provider IN ('google-antigravity', 'openai-codex')
        )
        SELECT email, provider, label, window_label, used_fraction, status, resets_at, recorded_at
        FROM latest
        WHERE rn = 1
        ORDER BY recorded_at DESC
        """
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()

        now_ms = int(time.time() * 1000)
        max_synced_at = 0

        # Build Antigravity Accounts
        ag_accounts_map = {}
        for email in sorted(ag_emails):
            username = email.split("@")[0]
            ag_accounts_map[email] = {
                "email": email,
                "display_name": username,
                "is_active_session": False,
                "metrics_dict": {}
            }

        # Build Codex Accounts
        codex_accounts_map = {}
        for email in sorted(codex_emails):
            username = email.split("@")[0]
            codex_accounts_map[email] = {
                "email": email,
                "display_name": username,
                "is_active_session": False,
                "metrics_dict": {}
            }

        for r in rows:
            email, provider, label, window, used_frac, status, resets_at, recorded_at = r
            max_synced_at = max(max_synced_at, recorded_at or 0)
            rem_pct = round(max(0.0, min(100.0, (1.0 - (used_frac or 0.0)) * 100.0)), 1)
            resets_in = format_countdown(resets_at, now_ms)
            metric_status = status if status else ("exhausted" if rem_pct == 0 else "ok")

            if provider == "google-antigravity" and email in ag_accounts_map:
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

                if tier_key not in ag_accounts_map[email]["metrics_dict"]:
                    ag_accounts_map[email]["metrics_dict"][tier_key] = {
                        "tier_key": tier_key,
                        "label": display_label,
                        "remaining_pct": rem_pct,
                        "status": metric_status,
                        "resets_in": resets_in
                    }

            elif provider == "openai-codex" and email in codex_accounts_map:
                if "7" in str(label) or "week" in str(label).lower() or "7" in str(window):
                    tier_key = "codex_7d"
                    display_label = "Codex (7d)"
                else:
                    tier_key = "codex_standard"
                    display_label = label or "Codex"

                if tier_key not in codex_accounts_map[email]["metrics_dict"]:
                    codex_accounts_map[email]["metrics_dict"][tier_key] = {
                        "tier_key": tier_key,
                        "label": display_label,
                        "remaining_pct": rem_pct,
                        "status": metric_status,
                        "resets_in": resets_in
                    }

        # Format Antigravity List
        ag_list = []
        ag_tier_order = ["gemini_5h", "gemini_weekly", "claude_gpt_weekly"]
        for email, acc in ag_accounts_map.items():
            metrics = []
            for t_key in ag_tier_order:
                if t_key in acc["metrics_dict"]:
                    metrics.append(acc["metrics_dict"][t_key])
                else:
                    metrics.append({
                        "tier_key": t_key,
                        "label": "Gemini (5h)" if t_key == "gemini_5h" else ("Gemini (7d)" if t_key == "gemini_weekly" else "Claude & GPT"),
                        "remaining_pct": 100.0,
                        "status": "ok",
                        "resets_in": "-"
                    })
            ag_list.append({
                "email": acc["email"],
                "display_name": acc["display_name"],
                "is_active_session": False,
                "metrics": metrics
            })

        # Format Codex List
        codex_list = []
        for email, acc in codex_accounts_map.items():
            metrics = list(acc["metrics_dict"].values())
            if not metrics:
                metrics.append({
                    "tier_key": "codex_7d",
                    "label": "Codex (7d)",
                    "remaining_pct": 100.0,
                    "status": "ok",
                    "resets_in": "-"
                })
            codex_list.append({
                "email": acc["email"],
                "display_name": acc["display_name"],
                "is_active_session": False,
                "metrics": metrics
            })

        return {
            "status": "ok",
            "synced_at": max_synced_at or now_ms,
            "providers": {
                "antigravity": {
                    "name": "Google Antigravity",
                    "accounts": ag_list
                },
                "codex": {
                    "name": "OpenAI Codex",
                    "accounts": codex_list
                }
            },
            "accounts": ag_list
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "providers": {
                "antigravity": {"name": "Google Antigravity", "accounts": []},
                "codex": {"name": "OpenAI Codex", "accounts": []}
            },
            "accounts": []
        }

if __name__ == "__main__":
    result = fetch_usage()
    print(json.dumps(result))
