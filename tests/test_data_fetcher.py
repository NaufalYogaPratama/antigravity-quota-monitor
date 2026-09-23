import json
import os
import sqlite3
import tempfile
import time
import unittest
import sys

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import data_fetcher

class TestDataFetcher(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE auth_credentials (
                id INTEGER PRIMARY KEY,
                provider TEXT,
                identity_key TEXT,
                disabled_cause TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE usage_history (
                id INTEGER PRIMARY KEY,
                recorded_at INTEGER,
                provider TEXT,
                account_key TEXT,
                email TEXT,
                account_id TEXT,
                limit_id TEXT,
                label TEXT,
                window_label TEXT,
                used_fraction REAL,
                status TEXT,
                resets_at INTEGER
            )
        """)
        # Insert active account and deleted account
        cur.execute("INSERT INTO auth_credentials VALUES (1, 'google-antigravity', 'email:testuser@gmail.com', NULL)")
        cur.execute("INSERT INTO auth_credentials VALUES (2, 'google-antigravity', 'email:deleted@gmail.com', 'deleted by user')")

        # Insert metrics for testuser
        now_ms = int(time.time() * 1000)
        cur.execute("""
            INSERT INTO usage_history VALUES 
            (1, ?, 'google-antigravity', 'k1', 'testuser@gmail.com', NULL, 'l1', 'Gemini', '5 Hour', 0.45, 'ok', ?),
            (2, ?, 'google-antigravity', 'k1', 'testuser@gmail.com', NULL, 'l2', 'Gemini', 'Weekly', 0.80, 'ok', ?),
            (3, ?, 'google-antigravity', 'k1', 'testuser@gmail.com', NULL, 'l3', 'Claude & GPT (shared)', 'Weekly', 1.0, 'exhausted', ?)
        """, (
            now_ms, now_ms + (45 * 60 * 1000),      # resets in 45m
            now_ms, now_ms + (28 * 3600 * 1000),    # resets in 1d 4h
            now_ms, now_ms + (60 * 3600 * 1000),    # resets in 2d 12h
        ))
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_fetch_antigravity_usage(self):
        result = data_fetcher.fetch_usage(self.db_path)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["accounts"]), 1)

        acc = result["accounts"][0]
        self.assertEqual(acc["email"], "testuser@gmail.com")
        self.assertEqual(acc["display_name"], "testuser")
        self.assertEqual(len(acc["metrics"]), 3)

        m5h = next(m for m in acc["metrics"] if m["tier_key"] == "gemini_5h")
        self.assertEqual(m5h["remaining_pct"], 55.0)
        self.assertEqual(m5h["status"], "ok")
        self.assertIn("m", m5h["resets_in"])

        cgpt = next(m for m in acc["metrics"] if m["tier_key"] == "claude_gpt_weekly")
        self.assertEqual(cgpt["remaining_pct"], 0.0)
        self.assertEqual(cgpt["status"], "exhausted")

    def test_missing_database(self):
        result = data_fetcher.fetch_usage("/non/existent/path.db")
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["accounts"], [])

if __name__ == "__main__":
    unittest.main()
