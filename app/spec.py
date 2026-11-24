COLUMNS = ("start_day", "end_day", "segment", "cents")
KINDS = ("version", "transaction", "expected")
PROJECT = {
    "name": "客户历史维表回溯台",
    "actor": "数仓维度维护员",
    "stages": [
        ("intake", "样例采信"),
        ("prepare", "版本编排"),
        ("calculate", "时点关联"),
        ("policy", "补数判定"),
        ("balance", "运行对账"),
    ],
    "chart": "版本覆盖",
}
