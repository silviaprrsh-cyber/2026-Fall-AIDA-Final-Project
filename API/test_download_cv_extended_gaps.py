"""Offline tests only. No real client, credentials, authentication or HTTP."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from API import download_cv_extended_gaps as d

import numpy as np
from pyproj import Transformer
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import LineString, box, mapping


def usage(remaining=20000, overage=0):
    return {"processingUnitsMonthly": {"configuration": "30000", "consumed": str(30000 - remaining), "remaining": str(remaining)},
            "processingUnitsOverage": {"configuration": str(overage), "consumed": "0", "remaining": "0"},
            "requestsMonthly": {"configuration": "30000", "consumed": "0", "remaining": "30000"},
            "requestsOverage": {"configuration": "0", "consumed": "0", "remaining": "0"}}


class Response:
    def __init__(self, content, receipt="0.01", status=200):
        self.content, self.status_code = content, status
        self.headers = {} if receipt is None else {"x-processingunits-spent": receipt}


class FakeClient:
    def __init__(self, responses, quota=None):
        self.responses = list(responses)
        self.quota = quota or usage()
        self.process_calls, self.usage_calls, self.payloads = 0, 0, []

    def usage(self):
        self.usage_calls += 1
        return copy.deepcopy(self.quota)

    def process(self, payload):
        self.payloads.append(payload)
        self.process_calls += 1
        result = self.responses.pop(0)
        if isinstance(result, BaseException): raise result
        return result


def make_tar(job, empty_tiles=False, no_data=False, shifted_y=0, wrong_product=False, scl=10):
    a = np.zeros((6, job["height"], job["width"]), dtype="uint16")
    if not no_data:
        a[:4] = 1000
        a[4] = scl
        a[5] = 1
    with MemoryFile() as mem:
        with mem.open(driver="GTiff", count=6, width=job["width"], height=job["height"], dtype="uint16", crs="EPSG:32612",
                      transform=from_origin(job["bounds"][0], job["bounds"][3] + shifted_y, 10, 10)) as ds: ds.write(a)
        image = mem.read()
    tiles = [] if empty_tiles else [{"sentinel2ProductId": "WRONG" if wrong_product else job["product_id"], "date": job["scene_time"]}]
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        for name, data in [("image.tif", image), ("userdata.json", json.dumps({"tiles": tiles}).encode())]:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return payload.getvalue()


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parents[1]
        self.temp = tempfile.TemporaryDirectory(prefix="cv_extended_offline_tests_", dir=self.repo)
        self.root = Path(self.temp.name).resolve()
        if not self.root.is_relative_to(self.repo.resolve()): raise RuntimeError("Unsafe test cleanup path")
        self.addCleanup(self.temp.cleanup)
        self.case = 0

    def paths(self, output=True):
        self.case += 1
        paths = d.Paths(self.root / str(self.case))
        paths.river.parent.mkdir(parents=True)
        reverse = Transformer.from_crs(32612, 4326, always_xy=True).transform
        line = LineString([reverse(500000, 5800100), reverse(501000, 5800100)])
        paths.river.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": mapping(line)}]}))
        paths.source.mkdir(parents=True)
        paths.raw.mkdir(parents=True)
        if output: paths.output.mkdir(parents=True)
        return paths

    def fixture(self, count=1, duplicate=False):
        paths = self.paths()
        jobs, geometries, states = [], {}, []
        for i in range(count):
            x = 500000 + (0 if duplicate else 1000 * i)
            gid = f"g{i}"
            geometry = mapping(box(x, 5800000, x + 200, 5800200))
            geometries[gid] = geometry
            job = {"id": f"job{i}", "geometry_id": gid, "stage": 1, "product_id": "S2A_MSIL2A_20200101T000000_N0500_R070_T11UQU_20230101T000000",
                   "scene_time": "2020-01-01T00:00:00Z", "bounds": [x, 5800000, x + 200, 5800200], "width": 20, "height": 20,
                   "bands": d.BANDS, "pixel_size_m": 10, "crs": "EPSG:32612", "expected_pu": .01, "guarded_pu": .04}
            jobs.append(job)
            states.append({"id": job["id"], "status": "pending", "pixel_visibility": "unknown_not_downloaded", "independent_labels": False})
        plan = {"jobs": jobs, "source_hashes": {}, "source_archives": []}
        manifest = {"jobs": states, "pu_spent_total": 0.0}
        d.write_new(paths.output / "plan.json", plan)
        d.write_new(paths.output / "geometries.json", geometries)
        manifest.update(plan_sha256=d.sha_file(paths.output / "plan.json"), geometries_sha256=d.sha_file(paths.output / "geometries.json"))
        d.write_new(paths.output / "manifest.json", manifest)
        return paths, plan, geometries, manifest

    def run_batch(self, fixture, client, **kwargs):
        return d.run_batch(*fixture, client, sleep_fn=lambda _: None, **kwargs)

    def test_budget_boundaries_and_zero_overage(self):
        self.assertEqual(d.budget_stop(1999, 2, 2000, 20000, 1000), "cumulative_actual_cap_precheck")
        self.assertIsNone(d.budget_stop(1990, 10, 2000, 20000, 1000))
        self.assertEqual(d.budget_stop(0, 4, 2000, 5253, 1000), "account_reserve_precheck")
        self.assertEqual(d.budget_stop(0, 4, 2000, 20000, 99), "request_reserve_precheck")
        for number in [float("nan"), float("inf"), -1]:
            with self.assertRaises(d.GuardError): d.finite_nonnegative(number)
        with self.assertRaises(d.GuardError): d.validate_usage(usage(overage=1))
        with self.assertRaises(d.GuardError): d.budget_stop(0, 1, 2001, 20000, 1000)

    def test_default_main_never_constructs_official_client(self):
        fixture = self.fixture()
        with patch.object(d, "Paths", return_value=fixture[0]), patch.object(d, "original_gate", return_value={}), patch.object(d, "OfficialClient") as official:
            d.main([])
            official.assert_not_called()
        self.assertFalse(fixture[3].get("network_processing_started", False))

    def test_unknown_exception_blocks_all_future_attempts(self):
        fixture = self.fixture()
        client = FakeClient([TimeoutError("simulated interrupted response")])
        with self.assertRaises(d.GuardError): self.run_batch(fixture, client)
        persisted = d.read(fixture[0].output / "manifest.json")
        self.assertEqual(persisted["jobs"][0]["status"], "needs_review")
        self.assertTrue(persisted["jobs"][0]["billed_pu_unknown"])
        second = FakeClient([])
        with self.assertRaises(d.GuardError): self.run_batch((*fixture[:3], persisted), second)
        self.assertEqual(client.process_calls, 1)
        self.assertEqual(second.process_calls, 0)
        self.assertEqual(second.usage_calls, 0)

    def test_missing_invalid_and_negative_receipts_never_retry(self):
        for receipt in [None, "nan", "inf", "-1", "not-a-number"]:
            with self.subTest(receipt=receipt):
                fixture = self.fixture()
                client = FakeClient([Response(make_tar(fixture[1]["jobs"][0]), receipt=receipt)])
                with self.assertRaises(d.GuardError): self.run_batch(fixture, client)
                self.assertTrue((fixture[0].output / "job0/response.tar").is_file())
                self.assertEqual(fixture[3]["jobs"][0]["status"], "needs_review")
                self.assertTrue(fixture[3]["jobs"][0]["billed_pu_unknown"])
                with self.assertRaises(d.GuardError): self.run_batch(fixture, client)
                self.assertEqual(client.process_calls, 1)

    def test_http_error_is_preserved_and_not_retried(self):
        fixture = self.fixture()
        client = FakeClient([Response(b"mock error", receipt="0", status=429)])
        self.run_batch(fixture, client)
        self.assertEqual(fixture[3]["jobs"][0]["status"], "stopped_http")
        self.assertEqual((fixture[0].output / "job0/http_response.bin").read_bytes(), b"mock error")
        with self.assertRaises(d.GuardError): self.run_batch(fixture, client)
        self.assertEqual(client.process_calls, 1)

    def test_unrecorded_response_blocks_before_network(self):
        fixture = self.fixture()
        folder = fixture[0].output / "job0"
        folder.mkdir()
        (folder / "response.tar").write_bytes(b"unknown")
        client = FakeClient([])
        with self.assertRaises(d.GuardError): self.run_batch(fixture, client)
        self.assertEqual(client.usage_calls + client.process_calls, 0)

    def test_same_pass_duplicate_is_skipped_without_second_request(self):
        fixture = self.fixture(count=2, duplicate=True)
        fixture[1]["jobs"][1]["product_id"] = fixture[1]["jobs"][1]["product_id"].replace("T11UQU", "T12UUD")
        client = FakeClient([Response(make_tar(fixture[1]["jobs"][0]))])
        self.assertEqual(self.run_batch(fixture, client), 1)
        self.assertEqual(fixture[3]["jobs"][1]["status"], "skipped_covered")
        self.assertEqual(client.process_calls, 1)

    def test_completed_work_is_not_downloaded_again(self):
        fixture = self.fixture()
        client = FakeClient([Response(make_tar(fixture[1]["jobs"][0]))])
        self.run_batch(fixture, client)
        quota_calls = client.usage_calls
        self.assertEqual(self.run_batch(fixture, client), 0)
        self.assertEqual(client.process_calls, 1)
        self.assertEqual(client.usage_calls, quota_calls)

    def test_cumulative_cap_persists_across_batches(self):
        fixture = self.fixture(count=2)
        fixture[1]["jobs"][0]["guarded_pu"] = 1999
        fixture[1]["jobs"][1]["guarded_pu"] = 4
        client = FakeClient([Response(make_tar(fixture[1]["jobs"][0]), receipt="1998")])
        self.run_batch(fixture, client, max_requests=1)
        self.assertEqual(fixture[3]["pu_spent_total"], 1998)
        self.assertEqual(self.run_batch(fixture, client), 0)
        self.assertEqual(fixture[3]["stop_reason"], "cumulative_actual_cap_precheck")
        self.assertEqual(client.process_calls, 1)

    def test_reserve_and_overage_block_processing(self):
        for quota in [usage(remaining=5250), usage(overage=1)]:
            fixture = self.fixture()
            client = FakeClient([], quota)
            if quota["processingUnitsOverage"]["configuration"] == "1":
                with self.assertRaises(d.GuardError): self.run_batch(fixture, client)
            else:
                self.assertEqual(self.run_batch(fixture, client), 0)
                self.assertEqual(fixture[3]["stop_reason"], "account_reserve_precheck")
            self.assertEqual(client.process_calls, 0)

    def test_quota_refresh_after_each_five_attempts(self):
        fixture = self.fixture(count=6)
        client = FakeClient([Response(make_tar(j)) for j in fixture[1]["jobs"]])
        self.assertEqual(self.run_batch(fixture, client), 6)
        self.assertEqual(client.usage_calls, 3)  # initial, before request 6, final

    def test_thin_cloud_retained_and_cloud_ceiling_100(self):
        fixture = self.fixture()
        client = FakeClient([Response(make_tar(fixture[1]["jobs"][0], scl=10))])
        self.run_batch(fixture, client)
        state = fixture[3]["jobs"][0]
        self.assertEqual(state["status"], "downloaded")
        self.assertEqual(state["quality"]["clear_proxy_fraction"], 0)
        self.assertEqual(state["pixel_visibility"], "unknown_review_needed")
        self.assertFalse(state["independent_labels"])
        self.assertEqual(client.payloads[0]["input"]["data"][0]["dataFilter"]["maxCloudCoverage"], 100)
        self.assertIn(fixture[1]["jobs"][0]["product_id"], client.payloads[0]["evalscript"])

    def test_no_data_response_is_preserved_and_not_retried(self):
        fixture = self.fixture()
        client = FakeClient([Response(make_tar(fixture[1]["jobs"][0], no_data=True, empty_tiles=True))])
        self.run_batch(fixture, client)
        self.assertEqual(fixture[3]["jobs"][0]["status"], "no_data")
        self.assertEqual(self.run_batch(fixture, client), 0)
        self.assertEqual(client.process_calls, 1)

    def test_response_grid_and_product_provenance_are_strict(self):
        fixture = self.fixture()
        job = fixture[1]["jobs"][0]
        geo = fixture[2][job["geometry_id"]]
        for options in [{"shifted_y": 40}, {"empty_tiles": True}, {"wrong_product": True}]:
            with self.subTest(options=options), self.assertRaises(d.GuardError):
                d.inspect_response(make_tar(job, **options), job, geo, box(*job["bounds"]))

    def test_estimate_overrun_persistently_requires_review(self):
        fixture = self.fixture()
        client = FakeClient([Response(make_tar(fixture[1]["jobs"][0]), receipt="1")])
        self.run_batch(fixture, client)
        persisted = d.read(fixture[0].output / "manifest.json")
        self.assertTrue(persisted["budget_review_required"])
        self.assertEqual(persisted["pu_spent_total"], 1)
        with self.assertRaises(d.GuardError): self.run_batch((*fixture[:3], persisted), client)
        self.assertEqual(client.process_calls, 1)

    def test_no_automatic_stage_advance_and_review_gate(self):
        fixture = self.fixture(count=2)
        fixture[1]["jobs"][1]["stage"] = 2
        client = FakeClient([Response(make_tar(j)) for j in fixture[1]["jobs"]])
        with self.assertRaises(d.GuardError): self.run_batch(fixture, client, stage=2)
        with self.assertRaises(d.GuardError): self.run_batch(fixture, client, stage=2, previous_stage_reviewed=True)
        self.run_batch(fixture, client, stage=1)
        self.assertEqual(client.process_calls, 1)
        self.assertEqual(fixture[3]["jobs"][1]["status"], "pending")
        self.run_batch(fixture, client, stage=2, previous_stage_reviewed=True)
        self.assertEqual(client.process_calls, 2)

    def test_geometry_dedup_full_partial_and_small(self):
        g = box(0, 0, 1000, 1000)
        rivers = LineString([(0, 500), (1000, 500)])
        self.assertEqual(d.clip_candidate({}, g, g, rivers)[0], "skipped_covered")
        status, missing = d.clip_candidate({}, g, box(0, 0, 500, 1000), rivers)
        self.assertEqual(status, "pending")
        self.assertAlmostEqual(missing.area, 500000)
        self.assertEqual(d.clip_candidate({}, g, box(0, 0, 999, 1000), rivers)[0], "skipped_small_fragment")

    def test_frozen_geometry_hash_and_execution_lock(self):
        fixture = self.fixture()
        with d.execution_lock(fixture[0].output):
            with self.assertRaises(d.GuardError):
                with d.execution_lock(fixture[0].output): pass
        self.assertFalse((fixture[0].output / "execution.lock").exists())
        (fixture[0].output / "geometries.json").write_bytes(b"{}")
        with self.assertRaises(d.GuardError): d.load_frozen(fixture[0])

    def original_fixture(self):
        paths = self.paths()
        paths.original.mkdir(parents=True)
        geometry = mapping(box(500000, 5800000, 501000, 5801000))
        identity = {"observation_key": "S2A_20200101T000000_R070_T11UQU", "product_id": "S2A_MSIL2A_20200101T000000_N0500_R070_T11UQU_20230101T000000",
                    "geometry": geometry, "bounds": [500000, 5800000, 501000, 5801000], "bands": d.BANDS, "pixel_size_m": 10, "crs": "EPSG:32612", "scene_time": "2020-01-01T00:00:00Z"}
        jid = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
        job = {k: v for k, v in identity.items() if k != "geometry"}
        job.update(id=jid, status="downloaded", received_at="2026-11-11T10:00:00Z")
        d.write_new(paths.original / "planned_geometries.json", {jid: geometry})
        geometry_hash = d.sha_file(paths.original / "planned_geometries.json")
        manifest = {"jobs": [job], "river_sha256": d.sha_file(paths.river), "geometry_index": "planned_geometries.json", "geometry_index_sha256": geometry_hash,
                    "last_stopped_at": "2026-11-11T10:00:01Z", "stop_reason": "bounded_batch_finished"}
        d.write_new(paths.original / "manifest.json", manifest)
        d.write_new(paths.original / "quota_after.json", {"checked_at": "2026-11-11T10:00:02Z", "quota": usage()})
        d.write_new(paths.source / "summary.json", {"source_hashes": {str((paths.original / "planned_geometries.json").relative_to(paths.repo)): geometry_hash}})
        return paths, manifest

    def test_original_completion_and_immutable_identity_gate(self):
        paths, manifest = self.original_fixture()
        d.original_gate(paths, expected_jobs=1)
        manifest["jobs"][0]["status"] = "pending"
        d.save(paths.original / "manifest.json", manifest)
        with self.assertRaises(d.GuardError): d.original_gate(paths, expected_jobs=1)
        manifest["jobs"][0]["status"] = "downloaded"
        manifest["jobs"][0]["product_id"] = manifest["jobs"][0]["product_id"].replace("T11UQU", "T12UUD")
        d.save(paths.original / "manifest.json", manifest)
        with self.assertRaises(d.GuardError): d.original_gate(paths, expected_jobs=1)

    def test_original_geometry_cannot_be_replaced_with_new_self_consistent_hash(self):
        paths, manifest = self.original_fixture()
        d.save(paths.original / "planned_geometries.json", {manifest["jobs"][0]["id"]: mapping(box(0, 0, 1, 1))})
        manifest["geometry_index_sha256"] = d.sha_file(paths.original / "planned_geometries.json")
        d.save(paths.original / "manifest.json", manifest)
        with self.assertRaises(d.GuardError): d.original_gate(paths, expected_jobs=1)

    def test_original_final_accounting_checkpoint_required(self):
        paths, manifest = self.original_fixture()
        d.save(paths.original / "quota_after.json", {"checked_at": "2026-11-11T09:00:00Z", "quota": usage()})
        with self.assertRaises(d.GuardError): d.original_gate(paths, expected_jobs=1)

    def test_freeze_reconciles_duplicate_candidates_offline(self):
        paths = self.paths(output=False)
        geometry = mapping(box(500000, 5800000, 501000, 5801000))
        jobs = []
        for i in range(2):
            jobs.append({"id": f"source{i}", "product_id": f"S2A_MSIL2A_20200101T000000_N0500_R070_{'T11UQU' if i == 0 else 'T12UUD'}_20230101T000000",
                         "geometry_id": "g", "bands": d.BANDS, "pixel_size_m": 10, "crs": "EPSG:32612", "bounds": [500000, 5800000, 501000, 5801000],
                         "width": 100, "height": 100, "scene_time": "2020-01-01T00:00:00Z"})
        summary = {"river_sha256": d.sha_file(paths.river), "proposed_stages": [{"name": name, "job_ids": [j["id"] for j in jobs] if number == 1 else [], "guarded_cap_pu": 2000} for number, name in d.STAGES.items()]}
        for name, value in [("summary.json", summary), ("candidate_jobs.json", {"jobs": jobs}), ("geometry_index.json", {"g": geometry})]: d.write_new(paths.source / name, value)
        d.write_new(paths.source / "validation.json", {"artifact_sha256": {name: d.sha_file(paths.source / name) for name in ["summary.json", "candidate_jobs.json", "geometry_index.json"]}})
        with patch.object(d, "source_coverage", return_value=({}, {}, [])):
            plan, _, manifest = d.freeze(paths, {"jobs": []})
        self.assertEqual([s["status"] for s in manifest["jobs"]], ["pending", "skipped_covered"])
        self.assertFalse(manifest["network_processing_started"])
        self.assertEqual(manifest["pu_spent_total"], 0)
        self.assertEqual(len({j["id"] for j in plan["jobs"]}), 2)

    def quarantine_fixture(self):
        """Synthetic signed fixtures; patch only the reviewed test fingerprints."""
        paths, manifest = self.original_fixture()
        job = manifest["jobs"][0]
        qid = job["id"]
        geometry = d.read(paths.original / "planned_geometries.json")[qid]
        other = copy.deepcopy(job)
        other["scene_time"] = "2020-01-02T00:00:00Z"
        other["observation_key"] = other["observation_key"].replace("20200101", "20200102")
        other["product_id"] = other["product_id"].replace("20200101", "20200102")
        identity = {k: other[k] for k in ["observation_key", "product_id", "bounds", "bands", "pixel_size_m", "crs", "scene_time"]}
        identity["geometry"] = geometry
        other["id"] = d.digest(json.dumps(identity, sort_keys=True).encode())[:24]
        job.update(status="needs_review", error_type="ConnectionError", estimated_pu=5.096435546875, width=100, height=100)
        job.pop("received_at")
        manifest["jobs"].append(other)
        d.save(paths.original / "planned_geometries.json", {qid: geometry, other["id"]: geometry})
        manifest["geometry_index_sha256"] = d.sha_file(paths.original / "planned_geometries.json")
        d.save(paths.original / "manifest.json", manifest)
        d.save(paths.source / "summary.json", {"source_hashes": {str((paths.original / "planned_geometries.json").relative_to(paths.repo)): manifest["geometry_index_sha256"]}})
        folder = paths.original / qid
        folder.mkdir()
        d.write_new(folder / "request.json", d.payload_for(job, geometry))
        spec = dict(d.QUARANTINE_SPEC, job_id=qid, geometry_index_sha256=manifest["geometry_index_sha256"])
        snapshot_path = paths.original / spec["snapshot_name"]
        d.write_new(snapshot_path, manifest)
        spec["snapshot_sha256"] = d.sha_file(snapshot_path)
        spec["request_sha256"] = d.sha_file(folder / "request.json")
        evidence = {"manifest_sha256": spec["snapshot_sha256"], "job": job, "request_sha256": spec["request_sha256"]}
        evidence_path = paths.original / spec["evidence_name"]
        d.write_new(evidence_path, evidence)
        spec["evidence_sha256"] = d.sha_file(evidence_path)
        return paths, manifest, spec

    def test_quarantine_requires_exact_explicit_option_and_preserves_original(self):
        paths, manifest, spec = self.quarantine_fixture()
        before = (paths.original / "manifest.json").read_bytes()
        with patch.object(d, "QUARANTINE_SPEC", spec):
            with self.assertRaises(d.GuardError): d.original_gate(paths, expected_jobs=2)
            with self.assertRaises(d.GuardError): d.original_gate(paths, expected_jobs=2, allow_original_quarantine="another-id")
            d.original_gate(paths, expected_jobs=2, allow_original_quarantine=spec["job_id"])
            record = d.validate_original_quarantine(paths, manifest, spec["job_id"], expected_jobs=2)
            self.assertEqual(record["outcome"], "unknown_not_retried")
            self.assertIsNone(record["actual_processing_units"])
            self.assertEqual((paths.original / "manifest.json").read_bytes(), before)
            self.assertEqual({p.name for p in (paths.original / spec["job_id"]).iterdir()}, {"request.json"})

    def test_quarantine_rejects_changed_evidence_and_request(self):
        for kind in ["evidence_name", "snapshot_name", "request"]:
            with self.subTest(kind=kind):
                paths, _, spec = self.quarantine_fixture()
                target = paths.original / spec[kind] if kind != "request" else paths.original / spec["job_id"] / "request.json"
                target.write_bytes(target.read_bytes() + b" ")
                with patch.object(d, "QUARANTINE_SPEC", spec), self.assertRaises(d.GuardError):
                    d.original_gate(paths, expected_jobs=2, allow_original_quarantine=spec["job_id"])

    def test_quarantine_rejects_second_unknown_and_unfinished_work(self):
        for status in ["pending", "in_progress", "needs_review"]:
            with self.subTest(status=status):
                paths, manifest, spec = self.quarantine_fixture()
                manifest["jobs"][1]["status"] = status
                d.save(paths.original / "manifest.json", manifest)
                with patch.object(d, "QUARANTINE_SPEC", spec), self.assertRaises(d.GuardError):
                    d.original_gate(paths, expected_jobs=2, allow_original_quarantine=spec["job_id"])

    def test_quarantine_rejects_status_relabel_and_new_response(self):
        for kind in ["relabel", "response"]:
            with self.subTest(kind=kind):
                paths, manifest, spec = self.quarantine_fixture()
                if kind == "relabel":
                    manifest["jobs"][0]["status"] = "downloaded"
                    manifest["jobs"][0]["received_at"] = "2026-11-11T10:00:00Z"
                    d.save(paths.original / "manifest.json", manifest)
                else:
                    (paths.original / spec["job_id"] / "response.tar").write_bytes(b"new evidence")
                with patch.object(d, "QUARANTINE_SPEC", spec), self.assertRaises(d.GuardError):
                    d.original_gate(paths, expected_jobs=2, allow_original_quarantine=spec["job_id"])

    def test_quarantine_overlap_and_altered_geometry_are_rejected(self):
        paths, manifest, spec = self.quarantine_fixture()
        with patch.object(d, "QUARANTINE_SPEC", spec):
            record = d.validate_original_quarantine(paths, manifest, spec["job_id"], expected_jobs=2)
        job = {"id": "new", "product_id": record["original_job"]["product_id"].replace("T11UQU", "T12UUD"), "geometry_id": "g", "status": "pending"}
        plan = {"jobs": [job], "quarantined_original_requests": [record]}
        with self.assertRaises(d.GuardError): d.verify_quarantine_exclusions(plan, {"g": record["geometry"]})
        # A genuinely different date is permitted at the same location.
        job["product_id"] = job["product_id"].replace("20200101", "20200201")
        d.verify_quarantine_exclusions(plan, {"g": record["geometry"]})
        record["geometry"] = mapping(box(0, 0, 1, 1))
        with self.assertRaises(d.GuardError): d.verify_quarantine_exclusions(plan, {"g": record["geometry"]})

    def test_quarantine_hold_is_separate_and_requires_option_every_time(self):
        paths, manifest, spec = self.quarantine_fixture()
        with patch.object(d, "QUARANTINE_SPEC", spec):
            record = d.validate_original_quarantine(paths, manifest, spec["job_id"], expected_jobs=2)
            plan = {"jobs": [], "quarantined_original_requests": [record]}
            with self.assertRaises(d.GuardError): d.quarantine_holds(plan, None)
            pu, requests = d.quarantine_holds(plan, spec["job_id"])
            self.assertEqual((pu, requests), (5.096435546875, 1))
            self.assertEqual(d.budget_stop(0, 1, 2000, 5255, 101, pu, requests), "account_reserve_precheck")
            self.assertEqual(d.budget_stop(0, 1, 2000, 20000, 100, pu, requests), "request_reserve_precheck")
            self.assertIsNone(d.budget_stop(0, 1, 2000, 20000, 101, pu, requests))
            self.assertIsNone(record["actual_processing_units"])

    def test_quarantine_new_evidence_or_final_manifest_change_blocks_resume(self):
        paths, manifest, spec = self.quarantine_fixture()
        with patch.object(d, "QUARANTINE_SPEC", spec): record = d.validate_original_quarantine(paths, manifest, spec["job_id"], expected_jobs=2)
        plan = {"jobs": [], "quarantined_original_requests": [record]}
        d.verify_quarantine_artifacts(paths, plan)
        manifest["jobs"][1]["status"] = "needs_review"
        d.save(paths.original / "manifest.json", manifest)
        with self.assertRaises(d.GuardError): d.verify_quarantine_artifacts(paths, plan)

    def test_original_quarantine_does_not_allow_extension_unknown(self):
        paths, original, spec = self.quarantine_fixture()
        with patch.object(d, "QUARANTINE_SPEC", spec):
            record = d.validate_original_quarantine(paths, original, spec["job_id"], expected_jobs=2)
            job = {"id": "extension-unknown", "stage": 1, "geometry_id": "g", "product_id": record["original_job"]["product_id"].replace("20200101", "20200201")}
            plan = {"jobs": [job], "quarantined_original_requests": [record]}
            manifest = {"jobs": [{"id": job["id"], "status": "needs_review", "billed_pu_unknown": True}], "pu_spent_total": 0}
            client = FakeClient([])
            with self.assertRaises(d.GuardError):
                d.run_batch(paths, plan, {"g": record["geometry"]}, manifest, client, allow_original_quarantine=spec["job_id"])
            self.assertEqual(client.usage_calls + client.process_calls, 0)


if __name__ == "__main__": unittest.main()
