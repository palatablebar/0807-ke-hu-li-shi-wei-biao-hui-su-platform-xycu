"""按交易时点重算单条客户时间线,并检出断档、重叠与未关联交易。"""

from app.business import by_kind, intervals, subtract


def covered(spans, day):
    return any(start <= day < end for start, end in spans)


def merged(spans):
    return [list(span) for span in intervals(spans)]


def ordering(version):
    return (version["start_day"], version["end_day"], version["record"])


def case_timeline(base_rows, rows):
    """对照基线与合并结果,产出覆盖变化、逐交易时点状态和时间线问题记录键。"""
    versions = sorted(by_kind(rows, "version"), key=ordering)
    valid = [v for v in versions if v["start_day"] < v["end_day"]]
    before = merged(
        (v["start_day"], v["end_day"])
        for v in by_kind(base_rows, "version")
        if v["start_day"] < v["end_day"]
    )
    after = merged((v["start_day"], v["end_day"]) for v in valid)
    issues = {"overlap": set(), "gap": set(), "unlinked": set()}
    # 无效区间无法提供覆盖,与重叠同属版本编排冲突
    issues["overlap"].update(
        v["record"] for v in versions if v["start_day"] >= v["end_day"]
    )
    max_end, max_record = None, None
    for v in valid:
        if max_end is not None and v["start_day"] < max_end:
            issues["overlap"].update((max_record, v["record"]))
        if max_end is None or v["end_day"] > max_end:
            max_end, max_record = v["end_day"], v["record"]
    for left, right in zip(after, after[1:]):
        if left[1] < right[0]:
            issues["gap"].update(
                v["record"]
                for v in valid
                if v["end_day"] == left[1] or v["start_day"] == right[0]
            )
    base_keys = {row["record"] for row in base_rows}
    points = []
    for tx in sorted(by_kind(rows, "transaction"), key=lambda r: (r["start_day"], r["record"])):
        point = {
            "record": tx["record"],
            "day": tx["start_day"],
            "origin": "baseline" if tx["record"] in base_keys else "supplement",
            "before": covered(before, tx["start_day"]),
            "after": covered(after, tx["start_day"]),
        }
        if not point["after"]:
            issues["unlinked"].add(tx["record"])
        points.append(point)
    return {
        "coverage": {
            "before": before,
            "after": after,
            "added": [list(span) for span in subtract(after, before)],
        },
        "points": points,
        "issues": {key: sorted(keys) for key, keys in issues.items()},
    }
