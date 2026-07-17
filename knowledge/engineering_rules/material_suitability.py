"""Engineering rules for validation."""

MATERIAL_SUITABILITY: list[dict] = [
    {
        "materials": ["carbon fiber", "carbon fibre", "cfrp"],
        "unsuitable_contexts": ["cylinder", "combustion", "bore", "block", "chamber"],
        "severity": "critical",
        "message": "{material} cannot withstand combustion temperatures in {function}",
    },
    {
        "materials": ["wood", "timber"],
        "unsuitable_contexts": ["engine", "cylinder", "crankshaft", "combustion", "bearing"],
        "severity": "critical",
        "message": "{material} lacks structural integrity for {function}",
    },
    {
        "materials": ["glass"],
        "unsuitable_contexts": ["crankshaft", "block", "bearing", "connecting rod"],
        "severity": "critical",
        "message": "{material} is brittle and unsuitable for {function}",
    },
    {
        "materials": ["plastic", "polymer", "abs"],
        "unsuitable_contexts": ["cylinder", "combustion", "crankshaft", "block"],
        "severity": "critical",
        "message": "{material} cannot survive operating conditions of {function}",
    },
]
