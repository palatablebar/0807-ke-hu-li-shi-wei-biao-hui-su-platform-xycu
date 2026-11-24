from app.business import measured


def compute(data):
    from bisect import bisect_right

    versions, tx, target = data
    starts = [r["start_day"] for r in versions]
    totals = {}
    gaps = []
    for row in tx:
        i = bisect_right(starts, row["start_day"]) - 1
        if i < 0 or row["start_day"] >= versions[i]["end_day"]:
            gaps.append(row["record"])
            continue
        key = str(versions[i]["segment"])
        totals[key] = totals.get(key, 0) + row["cents"]
    return measured(
        sum(totals.values()),
        target,
        "分",
        {"segments": totals, "gaps": gaps},
        bool(gaps),
    )
