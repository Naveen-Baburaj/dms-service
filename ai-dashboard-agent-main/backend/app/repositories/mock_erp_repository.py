SALES_RECORDS = [
    {"tenant_id": "toyota", "month": "2026-01", "sales": 1200000, "service_count": 82},
    {"tenant_id": "toyota", "month": "2026-02", "sales": 1450000, "service_count": 91},
    {"tenant_id": "toyota", "month": "2026-03", "sales": 1320000, "service_count": 86},
    {"tenant_id": "toyota", "month": "2026-04", "sales": 1600000, "service_count": 99},
    {"tenant_id": "toyota", "month": "2026-05", "sales": 1750000, "service_count": 105},

    {"tenant_id": "suzuki", "month": "2026-01", "sales": 820000, "service_count": 61},
    {"tenant_id": "suzuki", "month": "2026-02", "sales": 910000, "service_count": 68},
    {"tenant_id": "suzuki", "month": "2026-03", "sales": 990000, "service_count": 73},
    {"tenant_id": "suzuki", "month": "2026-04", "sales": 1040000, "service_count": 79},
    {"tenant_id": "suzuki", "month": "2026-05", "sales": 1160000, "service_count": 84},

    {"tenant_id": "hyundai", "month": "2026-01", "sales": 1100000, "service_count": 74},
    {"tenant_id": "hyundai", "month": "2026-02", "sales": 1180000, "service_count": 80},
    {"tenant_id": "hyundai", "month": "2026-03", "sales": 1210000, "service_count": 83},
    {"tenant_id": "hyundai", "month": "2026-04", "sales": 1290000, "service_count": 89},
    {"tenant_id": "hyundai", "month": "2026-05", "sales": 1370000, "service_count": 93},
]


INVENTORY_RECORDS = [
    {"tenant_id": "toyota", "category": "engine_oil", "stock": 420},
    {"tenant_id": "toyota", "category": "brake_pad", "stock": 155},

    {"tenant_id": "suzuki", "category": "engine_oil", "stock": 260},
    {"tenant_id": "suzuki", "category": "brake_pad", "stock": 92},

    {"tenant_id": "hyundai", "category": "engine_oil", "stock": 310},
    {"tenant_id": "hyundai", "category": "brake_pad", "stock": 120},
]


def list_sales_records(
    tenant_id: str | None = None,
    month_limit: int | None = None,
) -> list[dict]:
    records = SALES_RECORDS

    if tenant_id:
        records = [
            record for record in records
            if record["tenant_id"] == tenant_id
        ]

    if month_limit:
        records = records[-month_limit:]

    return records


def list_inventory_records(
    tenant_id: str | None = None,
) -> list[dict]:
    records = INVENTORY_RECORDS

    if tenant_id:
        records = [
            record for record in records
            if record["tenant_id"] == tenant_id
        ]

    return records
