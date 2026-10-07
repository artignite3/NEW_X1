"""User-owned JSON state: Supabase RLS in deployment, SQLite in local development."""
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

import requests
from fastapi import HTTPException
from model.auth import auth_config


class UserStore:
    def __init__(self, principal):
        self.principal = principal
        self.config = auth_config()
        if self.config["required"] and not principal.access_token:
            raise HTTPException(401, "User session required")

    def remote(self, method, table, **kwargs):
        try:
            response = requests.request(method, f"{self.config['url']}/rest/v1/{table}",
                headers={"apikey": self.config["key"],
                         "Authorization": f"Bearer {self.principal.access_token}",
                         "Prefer": "return=representation"}, timeout=10, **kwargs)
            if response.status_code in {401, 403}:
                raise HTTPException(response.status_code, "Session or data access denied")
            response.raise_for_status()
            return response.json() if response.content else None
        except (requests.RequestException, ValueError):
            raise HTTPException(503, "Account storage temporarily unavailable")

    @contextmanager
    def connect(self):
        # This local adapter is unreachable whenever authentication is configured.
        path = Path(os.getenv("APP_STATE_PATH", str(Path(__file__).resolve().parents[1] / "outputs/app_state.sqlite")))
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, user_id TEXT, payload TEXT, created_at TEXT, expires_at TEXT, PRIMARY KEY(kind,id))")
        connection.execute("CREATE TABLE IF NOT EXISTS usage (user_id TEXT, day TEXT, count INTEGER, PRIMARY KEY(user_id,day))")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def consume_quota(self):
        if self.config["required"]:
            if self.remote("POST", "rpc/consume_generation_quota", json={}) is not True:
                raise HTTPException(429, "Daily generation limit reached", headers={"Retry-After": "3600"})
        # Local development does not consume production quotas.

    def put(self, kind, identity, payload, expires_at=None):
        created = datetime.now(timezone.utc).isoformat()
        row = {"id": identity, "user_id": self.principal.user_id,
               "payload": payload, "created_at": created}
        if kind == "explanations":
            row["expires_at"] = expires_at
        if self.config["required"]:
            self.remote("POST", kind, json=row)
        else:
            with self.connect() as connection:
                connection.execute("INSERT INTO records VALUES (?,?,?,?,?,?)",
                    (kind, identity, self.principal.user_id, json.dumps(payload, allow_nan=False), created, expires_at))
                connection.execute("DELETE FROM records WHERE kind='explanations' AND expires_at < ?", (created,))
        return {"id": identity, "created_at": created, "payload": payload}

    def get(self, kind, identity):
        now = datetime.now(timezone.utc).isoformat()
        if self.config["required"]:
            params = {"id": f"eq.{identity}", "user_id": f"eq.{self.principal.user_id}", "select": "id,payload,created_at"}
            if kind == "explanations":
                params["expires_at"] = f"gt.{now}"
            rows = self.remote("GET", kind, params=params)
            return rows[0] if rows else None
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM records WHERE kind=? AND id=? AND user_id=? AND (expires_at IS NULL OR expires_at>?)",
                (kind, identity, self.principal.user_id, now)).fetchone()
            return {"id": row["id"], "payload": json.loads(row["payload"]), "created_at": row["created_at"]} if row else None

    def list_analyses(self):
        if self.config["required"]:
            return self.remote("GET", "saved_analyses", params={"user_id": f"eq.{self.principal.user_id}",
                "select": "id,payload,created_at", "order": "created_at.desc", "limit": "100"})
        with self.connect() as connection:
            rows = connection.execute("SELECT id,payload,created_at FROM records WHERE kind='saved_analyses' AND user_id=? ORDER BY created_at DESC LIMIT 100",
                                      (self.principal.user_id,)).fetchall()
            return [{"id": r["id"], "payload": json.loads(r["payload"]), "created_at": r["created_at"]} for r in rows]

    def delete_analysis(self, identity):
        if self.config["required"]:
            return bool(self.remote("DELETE", "saved_analyses", params={"id": f"eq.{identity}", "user_id": f"eq.{self.principal.user_id}"}))
        with self.connect() as connection:
            return connection.execute("DELETE FROM records WHERE kind='saved_analyses' AND id=? AND user_id=?",
                                      (identity, self.principal.user_id)).rowcount > 0

    def save_explanation(self, identity, snapshot, result):
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        return self.put("explanations", identity, {"snapshot": snapshot, "result": result}, expires)

    def save_analysis(self, token, title):
        explanation = self.get("explanations", token)
        if not explanation:
            raise HTTPException(404, "Analysis unavailable or expired; generate it again")
        return self.put("saved_analyses", uuid4().hex,
                        {"title": title, "result": explanation["payload"]["result"]})
