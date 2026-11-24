from app.business import decision


def policy(result):
    return decision(result, "DIMENSION_GAP" if result["flag"] else None)
