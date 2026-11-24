import json


def artifact(run):
    packet = {
        "schema": "review-evidence/1",
        "manifest": run["report"]["manifest"],
        "balance": run["report"]["balance"],
        "cases": run["report"]["cases"],
        "intake": run["report"]["intake"],
        "review": {key: run[key] for key in ("status", "revision", "note", "reviewed")},
    }
    return (
        json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def release_artifact(release):
    packet = {
        "schema": "release-evidence/1",
        "release": {key: release[key] for key in ("seq", "status", "parent", "created")},
        "manifest": release["report"]["manifest"],
        "summary": release["report"]["summary"],
        "cases": release["report"]["cases"],
        "intake": release["report"]["intake"],
        "conflicts": release["report"]["conflicts"],
        "records": release["report"]["records"],
    }
    return (
        json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
