import io
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.business import DomainIssue
from app.release.service import publish, trial
from conftest import csv_data


def version(record, case, start, end, segment="1"):
    return [record, case, "version", str(start), str(end), segment, "0", "版本"]


def transaction(record, case, day, cents="10"):
    return [record, case, "transaction", str(day), "0", "0", str(cents), "交易"]


def expected(record, case, cents="10"):
    return [record, case, "expected", "0", "0", "0", str(cents), "对账"]


def base_rows():
    return [
        version("v1", "9001", 0, 10),
        version("v2", "9001", 10, 20, "2"),
        transaction("t1", "9001", 3, "40"),
        transaction("t2", "9001", 12, "60"),
        expected("e1", "9001", "100"),
    ]


def test_trial_and_publish_share_one_source(store):
    data = csv_data(base_rows())
    outcome = trial(store, data)
    release = publish(store, data)
    assert release["id"] == outcome["manifest"]["release_id"]
    assert release["report"]["cases"] == outcome["cases"]
    assert release["report"]["summary"]["publishable"] is True


def test_identical_content_never_adds_version(store):
    data = csv_data(base_rows())
    first = publish(store, data)
    second = publish(store, data)
    assert first == second and len(store.list_releases()) == 1


def test_replay_of_merged_content_returns_existing_version(store):
    publish(store, csv_data(base_rows()))
    grown = publish(store, csv_data(base_rows() + [version("v3", "9002", 0, 5)]))
    again = publish(store, csv_data(base_rows()))
    assert again["id"] == grown["id"] and len(store.list_releases()) == 2


def test_gap_keeps_pending_and_lists_record_keys(store):
    data = csv_data([version("v1", "9001", 0, 5), version("v2", "9001", 8, 12)])
    release = publish(store, data)
    assert release["status"] == "PENDING"
    assert release["report"]["cases"][0]["issues"]["gap"] == ["v1", "v2"]
    assert store.current_release() is None


def test_overlap_keeps_pending_and_lists_record_keys(store):
    data = csv_data([version("v1", "9001", 0, 8), version("v2", "9001", 7, 15)])
    release = publish(store, data)
    assert release["status"] == "PENDING"
    assert release["report"]["cases"][0]["issues"]["overlap"] == ["v1", "v2"]


def test_unlinked_transaction_keeps_pending_and_lists_record_keys(store):
    data = csv_data([version("v1", "9001", 0, 8), transaction("t9", "9001", 9)])
    release = publish(store, data)
    assert release["status"] == "PENDING"
    assert release["report"]["cases"][0]["issues"]["unlinked"] == ["t9"]


def test_failed_publish_preserves_previous_release_and_evidence(store):
    good = publish(store, csv_data(base_rows()))
    broken = csv_data(base_rows() + [transaction("t9", "9002", 9)])
    failed = publish(store, broken)
    assert failed["status"] == "PENDING"
    current = store.current_release()
    assert (current["id"], current["seq"]) == (good["id"], 1)
    assert current["report"] == good["report"]  # 旧版按原时点复现
    assert [item["status"] for item in store.list_releases()] == ["PENDING", "PUBLISHED"]


def test_trial_shows_coverage_change_and_unresolved(store):
    publish(store, csv_data(base_rows()))
    supplement = csv_data(
        [
            version("v3", "9001", 20, 30, "3"),
            transaction("t3", "9001", 25, "30"),
            transaction("t4", "9001", 35, "5"),
        ]
    )
    outcome = trial(store, supplement)
    case = next(c for c in outcome["cases"] if c["case"] == "9001")
    assert case["coverage"]["before"] == [[0, 20]]
    assert case["coverage"]["after"] == [[0, 30]]
    assert case["coverage"]["added"] == [[20, 30]]
    points = {p["record"]: p for p in case["points"]}
    assert (points["t3"]["before"], points["t3"]["after"]) == (False, True)
    assert (points["t4"]["before"], points["t4"]["after"]) == (False, False)
    assert case["issues"]["unlinked"] == ["t4"]
    assert outcome["summary"]["unresolved"] == 1


def test_baseline_conflict_is_isolated_not_merged(store):
    publish(store, csv_data(base_rows()))
    tampered = csv_data([version("v1", "9001", 0, 99), version("v3", "9002", 0, 5)])
    outcome = trial(store, tampered)
    assert outcome["conflicts"] == [
        {"record": "v1", "case": "9001", "reason": "BASELINE_CONFLICT"}
    ]
    case = next(c for c in outcome["cases"] if c["case"] == "9001")
    assert case["coverage"]["after"] == [[0, 20]]


def test_empty_release_is_rejected(store):
    data = csv_data([["bad", "9001", "version", "-", "0", "0", "0", "缺测"]])
    with pytest.raises(DomainIssue, match="RELEASE_EMPTY"):
        publish(store, data)


def test_publish_requires_current_trial_snapshot(store):
    first, second = csv_data(base_rows()), csv_data([version("w1", "9009", 0, 4)])
    stale = trial(store, second)["manifest"]["release_id"]
    publish(store, first)
    with pytest.raises(DomainIssue, match="TRIAL_STALE"):
        publish(store, second, expected=stale)
    assert publish(store, second)["seq"] == 2


def test_parallel_identical_publish_commits_single_version(store):
    data = csv_data(base_rows())
    start = Barrier(4)
    with ThreadPoolExecutor(max_workers=4) as threads:
        results = list(threads.map(lambda _: (start.wait(3), publish(store, data))[1], range(4)))
    assert all(result == results[0] for result in results)
    assert len(store.list_releases()) == 1


def test_parallel_distinct_publish_keeps_seq_unique(store):
    other = csv_data([version("w1", "9009", 0, 4)])
    start = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as threads:
        results = list(
            threads.map(lambda d: (start.wait(3), publish(store, d))[1], [csv_data(base_rows()), other])
        )
    assert sorted(r["seq"] for r in results) == [1, 2]


def test_release_evidence_roundtrip(store, client):
    release = publish(store, csv_data(base_rows()))
    response = client.get(f"/api/releases/{release['id']}/evidence")
    assert response.status_code == 200
    packet = json.loads(response.data)
    assert packet["schema"] == "release-evidence/1"
    assert packet["release"]["seq"] == 1
    assert packet["records"] == release["report"]["records"]


def test_release_http_flow(client):
    assert client.get("/api/releases").json == {"items": []}
    preview = client.post("/api/releases/trial", data={"sample": "supplement"})
    assert preview.status_code == 200 and "records" not in preview.json
    assert client.get("/api/releases").json == {"items": []}  # 试算不入库
    release_id = preview.json["manifest"]["release_id"]
    made = client.post(
        "/api/releases",
        data={"sample": "supplement", "expected": release_id},
    )
    assert made.status_code == 200 and made.json["status"] == "PENDING"
    assert made.json["report"]["cases"][1]["issues"]["unlinked"] == ["100202"]
    replay = client.post("/api/releases", data={"sample": "supplement"})
    assert replay.json["id"] == made.json["id"]
    assert len(client.get("/api/releases").json["items"]) == 1
    fixed = client.post("/api/releases", data={"sample": "supplement_fix"})
    assert fixed.json["status"] == "PUBLISHED" and fixed.json["seq"] == 2
    grown = client.post("/api/releases", data={"sample": "supplement_more"})
    assert grown.json["status"] == "PUBLISHED" and grown.json["seq"] == 3
    again = client.post("/api/releases", data={"sample": "supplement_more"})
    assert again.json["id"] == grown.json["id"]
    assert len(client.get("/api/releases").json["items"]) == 3


def test_release_http_errors(client):
    assert client.get("/api/releases/unknown").status_code == 404
    assert client.get("/api/releases/unknown/evidence").status_code == 404
    bad = client.post("/api/releases/trial", data={"file": (io.BytesIO(b"x,y\n"), "b.csv")})
    assert bad.status_code == 422
    stale = client.post("/api/releases", data={"sample": "supplement", "expected": "0" * 64})
    assert stale.status_code == 409 and stale.json["code"] == "TRIAL_STALE"
