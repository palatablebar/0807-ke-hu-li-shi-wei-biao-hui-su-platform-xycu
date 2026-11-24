from app.business import DomainIssue, by_kind, prepared, single


def prepare(rows):
    versions = sorted(by_kind(rows, "version"), key=lambda r: r["start_day"])
    target = single(rows, "expected")["cents"]
    if any(r["start_day"] >= r["end_day"] for r in versions):
        raise DomainIssue("INVALID_VERSION_RANGE")
    if any(a["end_day"] > b["start_day"] for a, b in zip(versions, versions[1:])):
        raise DomainIssue("VERSION_OVERLAP")
    tx = by_kind(rows, "transaction")
    matched = sum(
        any(v["start_day"] <= t["start_day"] < v["end_day"] for v in versions)
        for t in tx
    )
    return prepared(
        matched,
        {"versions": len(versions), "transactions": len(tx)},
        (versions, tx, target),
    )
