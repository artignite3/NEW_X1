"""Publication, recovery, readiness and isolation gates; no cloud credentials."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from botocore.exceptions import ClientError
from model.model_fastapi import app
from pipeline.object_store import LocalStore, S3Store, PublicationConflict, configured_store, json_bytes
from pipeline.releases import REQUIRED, publish_release, restore_release, read_pointer, check_manifest, rollback
from pipeline.validate_release import validate_feature_frame
from pipeline.worker import run_worker
from pipeline.serving import STATE, SNAPSHOT_LOCK, refresh_once, prune_cache


def accept(root): return {"t20": {"latest_match": "2026-10-07"}}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "input"
        self.store = LocalStore(self.base / "store")
        for name in REQUIRED:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("original " + name).encode())

    def publish(self): return publish_release(self.root, self.store, validator=accept)

    def test_whole_release_round_trip_checks_every_file(self):
        manifest = self.publish()
        restored, actual, recovery = restore_release(self.store, self.base / "cache", validator=accept)
        self.assertEqual(actual["release_id"], manifest["release_id"])
        self.assertFalse(recovery["fallback_used"])
        for name in REQUIRED: self.assertEqual((restored/name).read_bytes(), (self.root/name).read_bytes())

    def test_failed_contract_or_missing_file_never_promotes(self):
        self.publish()
        pointer = self.store.read("current.json")
        with self.assertRaises(ValueError):
            publish_release(self.root, self.store, validator=lambda _: (_ for _ in ()).throw(ValueError()))
        (self.root / REQUIRED[0]).unlink()
        with self.assertRaises(ValueError): self.publish()
        self.assertEqual(self.store.read("current.json"), pointer)

    def test_stale_publisher_cannot_replace_newer_release(self):
        original, etag = read_pointer(self.store)
        first = self.publish()
        with self.assertRaises(PublicationConflict):
            publish_release(self.root, self.store, pointer=original, etag=etag, validator=accept)
        self.assertEqual(read_pointer(self.store)[0]["current"], "releases/"+first["release_id"]+".json")

    def test_corrupt_current_falls_back_to_complete_previous_release(self):
        first = self.publish()
        (self.root / REQUIRED[0]).write_bytes(b"new valid snapshot")
        second = self.publish()
        self.store.path("blobs/" + second["files"][REQUIRED[0]]["sha256"]).write_bytes(b"corrupt")
        root, manifest, recovery = restore_release(self.store, self.base / "cache", validator=accept)
        self.assertTrue(recovery["fallback_used"])
        self.assertEqual(manifest["release_id"], first["release_id"])
        self.assertEqual((root/REQUIRED[0]).read_bytes(), b"original " + REQUIRED[0].encode())

    def test_both_invalid_releases_are_refused(self):
        first=self.publish(); second=self.publish()
        for manifest in (first,second):
            self.store.path("releases/"+manifest["release_id"]+".json").write_bytes(b"invalid")
        with self.assertRaises(ValueError): restore_release(self.store,self.base/"cache",validator=accept)

    def test_manifest_path_schema_size_checksum_and_time_guards(self):
        original = self.publish()
        for field, value in (("schema", -1), ("cutoff", "future"), ("created_at", "2026-10-08")):
            invalid=deepcopy(original); invalid[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError): check_manifest(invalid)
        invalid=deepcopy(original); invalid["files"]["../../escape"]={"sha256":"a"*64,"bytes":1}
        with self.assertRaises(ValueError): check_manifest(invalid)
        for value in (0, True, -1, 3_000_000_000):
            invalid=deepcopy(original); invalid["files"][REQUIRED[0]]["bytes"]=value
            with self.assertRaises(ValueError): check_manifest(invalid)
        for key in ("../secret","/absolute","a/../../b","a\\b"):
            with self.assertRaises(ValueError): self.store.read(key)

    def test_verified_rollback_promotes_previous_without_changing_files(self):
        first=self.publish(); second=self.publish()
        rollback(self.store,validator=accept)
        pointer,_=read_pointer(self.store)
        self.assertEqual(pointer["current"],"releases/"+first["release_id"]+".json")
        self.assertEqual(pointer["previous"],"releases/"+second["release_id"]+".json")

    def test_validation_uses_frozen_snapshot_even_if_source_changes(self):
        def validator(frozen):
            (self.root/REQUIRED[0]).write_bytes(b"concurrent source edit")
            self.assertNotEqual(frozen,self.root)
            return accept(frozen)
        manifest=publish_release(self.root,self.store,validator=validator)
        restored,_,_=restore_release(self.store,self.base/"cache",validator=accept)
        self.assertNotEqual((restored/REQUIRED[0]).read_bytes(),(self.root/REQUIRED[0]).read_bytes())
        self.assertEqual(manifest["files"][REQUIRED[0]]["bytes"],len(b"original "+REQUIRED[0].encode()))

    def test_failed_worker_keeps_pointer_and_records_failure(self):
        self.publish(); pointer=self.store.read("current.json")
        with patch("pipeline.worker.restore_release", wraps=lambda store, cache: restore_release(store,cache,validator=accept)), \
             patch("pipeline.worker.run_sync",return_value={"status":"failed","stages":[]}):
            report=run_worker(self.store)
        self.assertEqual(report["status"],"failed")
        self.assertEqual(self.store.read("current.json"),pointer)
        self.assertEqual(json.loads(self.store.read("latest_run.json")[0])["status"],"failed")

    def test_immutable_blob_is_not_overwritten(self):
        path=self.root/REQUIRED[0]
        self.store.put_file("blobs/fixed",path)
        previous=self.store.read("blobs/fixed")[0]
        path.write_bytes(b"different")
        self.store.put_file("blobs/fixed",path)
        self.assertEqual(self.store.read("blobs/fixed")[0],previous)

    def test_production_cannot_fall_back_to_local_store(self):
        with patch.dict(os.environ,{"APP_ENV":"production","RELEASE_STORE_DIR":str(self.base)}):
            with self.assertRaises(ValueError): configured_store()

    def test_s3_pointer_uses_conditional_write_and_conflicts_are_controlled(self):
        store=S3Store.__new__(S3Store); store.bucket="test"; store.prefix="new-x1"; store.client=MagicMock()
        store.write("current.json",b"{}",conditional=True,expected='"prior-etag"')
        self.assertEqual(store.client.put_object.call_args.kwargs["IfMatch"],'"prior-etag"')
        store.write("current.json",b"{}",conditional=True)
        self.assertEqual(store.client.put_object.call_args.kwargs["IfNoneMatch"],"*")
        store.client.put_object.side_effect=ClientError({"Error":{"Code":"PreconditionFailed"}},"PutObject")
        with self.assertRaises(PublicationConflict): store.write("current.json",b"{}",conditional=True)


class ServingTests(unittest.TestCase):
    def setUp(self):
        self.previous=deepcopy(STATE)
        self.addCleanup(lambda: (STATE.clear(),STATE.update(self.previous)))
        STATE.update(release_id="a"*32,created_at=datetime.now(timezone.utc).isoformat(),fallback_used=False,refresh_error=None)

    def test_readiness_accepts_configured_contract_and_rejects_missing_and_stale(self):
        with patch.dict(os.environ,{"APP_ENV":"production","SUPABASE_URL":"https://test.supabase.co","SUPABASE_PUBLISHABLE_KEY":"public"}), TestClient(app) as client:
            self.assertEqual(client.get("/ready").status_code,200)
            with patch.dict(os.environ,{"SUPABASE_URL":"","SUPABASE_PUBLISHABLE_KEY":""}):
                self.assertEqual(client.get("/ready").status_code,503)
            STATE["created_at"]=(datetime.now(timezone.utc)-timedelta(hours=73)).isoformat()
            self.assertEqual(client.get("/ready").status_code,503)

    def test_busy_generation_is_bounded_but_liveness_remains_available(self):
        with TestClient(app) as client:
            SNAPSHOT_LOCK.acquire()
            try:
                self.assertEqual(client.get("/live").status_code,200)
                response=client.post("/generate_best_team",json={"match_id":"x"})
                self.assertEqual(response.status_code,503)
                self.assertEqual(response.headers["Retry-After"],"3")
            finally: SNAPSHOT_LOCK.release()

    def test_storage_outage_keeps_current_serving_release_and_reports_error(self):
        store=MagicMock(); store.read.side_effect=OSError("unavailable")
        refresh_once(store,"unused")
        self.assertEqual(STATE["release_id"],"a"*32)
        self.assertEqual(STATE["refresh_error"],"OSError")

    def test_release_cache_retains_only_current_previous_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as cache:
            for name in ("a"*32,"b"*32,"c"*32,"unrelated"):
                (Path(cache)/name).mkdir()
            prune_cache(cache,{"current":"releases/"+"a"*32+".json","previous":"releases/"+"b"*32+".json"},"a"*32)
            self.assertFalse((Path(cache)/('c'*32)).exists())
            self.assertTrue((Path(cache)/('a'*32)).exists())
            self.assertTrue((Path(cache)/('b'*32)).exists())
            self.assertTrue((Path(cache)/'unrelated').exists())


class FeatureContractTests(unittest.TestCase):
    def frame(self):
        from data_processing.feature_engineering import RAW_STATS
        return pd.DataFrame([{**{name:0. for name in RAW_STATS},"fixed_lag":np.nan,
            "player":"Known","match_key":"known-match","match_date":"2026-10-01",
            "available_date":"2026-10-02","feature_schema_version":2,"venue":"Ground",
            "opponent":"Other","total_points":10.}])

    def test_cold_start_missing_feature_is_supported_but_infinity_is_rejected(self):
        frame=self.frame()
        self.assertEqual(len(validate_feature_frame(frame,["fixed_lag"])),1)
        frame["fixed_lag"]=np.inf
        with self.assertRaises(ValueError): validate_feature_frame(frame,["fixed_lag"])

    def test_missing_raw_columns_and_invalid_availability_are_rejected(self):
        with self.assertRaises(ValueError): validate_feature_frame(self.frame().drop(columns=["wickets"]),["fixed_lag"])
        frame=self.frame(); frame["available_date"]="2026-09-30"
        with self.assertRaises(ValueError): validate_feature_frame(frame,["fixed_lag"])


if __name__ == "__main__": unittest.main()
