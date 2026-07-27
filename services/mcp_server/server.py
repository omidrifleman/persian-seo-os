"""MCP server — تنها سطح تماس ایجنت‌ها با محصول.

هر tool مخرب باید approval_id بگیرد. این را در schema اجبار کن، نه در مستندات.
"""
from __future__ import annotations

TOOLS = [
    # domain.verb, readOnly, destructive, needs_approval
    ("keywords.normalize", True, False, False),
    ("keywords.cluster", True, False, False),
    ("keywords.volume_lookup", True, False, False),
    ("audit.run", True, False, False),
    ("audit.persian_checks", True, False, False),
    ("content.brief", True, False, False),
    ("content.draft", False, False, False),
    ("content.quality_gate", True, False, False),
    ("approvals.submit", False, False, False),
    ("publish.dry_run", True, False, False),
    ("publish.apply", False, True, True),
    ("publish.rollback", False, True, True),
    ("geo.brand_visibility", True, False, False),
]


def describe() -> list[dict]:
    return [
        {
            "name": name,
            "annotations": {
                "readOnlyHint": read_only,
                "destructiveHint": destructive,
                "idempotent": True,
            },
            "requires_approval_id": needs_approval,
        }
        for name, read_only, destructive, needs_approval in TOOLS
    ]


if __name__ == "__main__":
    import json

    print(json.dumps(describe(), ensure_ascii=False, indent=2))
