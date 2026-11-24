EXPECTED = {
    "0001": (2, 130, "READY"),
    "0002": (1, 25, "READY"),
    "0003": (0, None, "VERSION_OVERLAP"),
    "0004": (1, 60, "DIMENSION_GAP"),
}
EVIDENCE = {
    "0001": {"segments": {"1": 29, "2": 101}, "gaps": []},
    "0004": {"segments": {"1": 60}, "gaps": ["000403"]},
}
