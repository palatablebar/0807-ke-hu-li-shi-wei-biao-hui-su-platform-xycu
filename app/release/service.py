"""补录试算与发布:试算与发布共用同一计算,版本按合并内容寻址。"""

import json
from hashlib import sha256

from app.business import DomainIssue
from app.config import RULE_VERSION
from app.intake.service import inspect
from app.modules.grouping import case_groups
from app.release.timeline import case_timeline
from app.review.service import now


def canonical(rows):
    return json.dumps(
        sorted(rows, key=lambda row: row["record"]), ensure_ascii=False, sort_keys=True
    )


def content_id(rows):
    digest = sha256(canonical(rows).encode()).hexdigest()
    return sha256(f"release:{RULE_VERSION}:{digest}".encode()).hexdigest(), digest


def merge(baseline_rows, supplement_rows):
    """已发布基线优先;同键同内容按回放忽略,异内容把补录行隔离。"""
    merged = list(baseline_rows)
    known = {row["record"]: row for row in baseline_rows}
    replays, conflicts = 0, []
    for row in supplement_rows:
        prior = known.get(row["record"])
        if prior is None:
            known[row["record"]] = row
            merged.append(row)
        elif prior == row:
            replays += 1
        else:
            conflicts.append(
                {"record": row["record"], "case": row["case"], "reason": "BASELINE_CONFLICT"}
            )
    return merged, replays, conflicts


def trial(store, data):
    """补录试算。发布复用同一函数,保证同源。只读,不入库。"""
    intake = inspect(data)
    baseline = store.current_release()
    base_rows = baseline["report"]["records"] if baseline else []
    merged, replays, conflicts = merge(base_rows, intake["rows"])
    base_grouped = dict(case_groups(base_rows))
    cases = []
    for case, rows in case_groups(merged):
        entry = {"case": case, "records": [row["record"] for row in rows]}
        entry.update(case_timeline(base_grouped.get(case, []), rows))
        entry["status"] = "READY" if not any(entry["issues"].values()) else "PENDING"
        cases.append(entry)
    release_id, digest = content_id(merged)
    return {
        "manifest": {
            "release_id": release_id,
            "content": digest,
            "parent": baseline["id"] if baseline else None,
            "parent_seq": baseline["seq"] if baseline else None,
            "version": RULE_VERSION,
            "sha256": sha256(data).hexdigest(),
            "bytes": len(data),
        },
        "baseline": (
            {key: baseline[key] for key in ("id", "seq", "created")} if baseline else None
        ),
        "intake": {key: value for key, value in intake.items() if key != "rows"},
        "conflicts": conflicts,
        "cases": cases,
        "summary": {
            "cases": len(cases),
            "unresolved": sum(len(c["issues"]["unlinked"]) for c in cases),
            "gaps": sum(len(c["issues"]["gap"]) for c in cases),
            "overlaps": sum(len(c["issues"]["overlap"]) for c in cases),
            "conflicts": len(conflicts),
            "replays": replays,
            "publishable": bool(cases)
            and all(c["status"] == "READY" for c in cases),
        },
        "records": merged,
        "existing": store.find_release(release_id),
    }


def publish(store, data, expected=None):
    """发布补录版本。内容相同返回既有版本;时间线异常保持待复核并列出记录键。"""
    outcome = trial(store, data)
    release_id = outcome["manifest"]["release_id"]
    if expected is not None and expected != release_id:
        raise DomainIssue("TRIAL_STALE")
    if not outcome["records"]:
        raise DomainIssue("RELEASE_EMPTY")
    outcome.pop("existing")
    outcome["manifest"]["created"] = now()
    status = "PUBLISHED" if outcome["summary"]["publishable"] else "PENDING"
    return store.register_release(
        release_id, outcome["manifest"]["parent"], status, outcome
    )
