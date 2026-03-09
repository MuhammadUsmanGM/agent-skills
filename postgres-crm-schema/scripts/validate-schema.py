#!/usr/bin/env python3
"""Validate a schema.sql file against the canonical CRM schema definitions.

Usage:
    python validate-schema.py --schema production/database/schema.sql

Checks:
- All 8 canonical tables exist
- Required columns present with correct types
- Required indexes exist
- Warns about extra tables or columns (possible schema drift)

Outputs a validation report to stdout.
"""

import argparse
import re
import sys

# --- Canonical Schema Definition ---

CANONICAL_TABLES = {
    "customers": {
        "columns": {
            "id": "UUID",
            "name": "VARCHAR",
            "email": "VARCHAR",
            "phone": "VARCHAR",
            "company": "VARCHAR",
            "metadata": "JSONB",
            "created_at": "TIMESTAMPTZ",
            "updated_at": "TIMESTAMPTZ",
        },
        "required_indexes": ["idx_customers_email", "idx_customers_phone"],
    },
    "customer_identifiers": {
        "columns": {
            "id": "UUID",
            "customer_id": "UUID",
            "identifier_type": "VARCHAR",
            "identifier_value": "VARCHAR",
            "verified": "BOOLEAN",
            "created_at": "TIMESTAMPTZ",
        },
        "required_indexes": ["idx_ci_lookup", "idx_ci_customer"],
    },
    "conversations": {
        "columns": {
            "id": "UUID",
            "customer_id": "UUID",
            "channel": "VARCHAR",
            "status": "VARCHAR",
            "sentiment_score": "FLOAT",
            "thread_id": "VARCHAR",
            "started_at": "TIMESTAMPTZ",
            "updated_at": "TIMESTAMPTZ",
        },
        "required_indexes": ["idx_conv_customer", "idx_conv_channel", "idx_conv_thread"],
    },
    "messages": {
        "columns": {
            "id": "UUID",
            "conversation_id": "UUID",
            "sender_type": "VARCHAR",
            "content": "TEXT",
            "channel": "VARCHAR",
            "delivery_status": "VARCHAR",
            "metadata": "JSONB",
            "created_at": "TIMESTAMPTZ",
        },
        "required_indexes": ["idx_msg_conversation", "idx_msg_created"],
    },
    "tickets": {
        "columns": {
            "id": "UUID",
            "conversation_id": "UUID",
            "customer_id": "UUID",
            "subject": "VARCHAR",
            "issue": "TEXT",
            "category": "VARCHAR",
            "priority": "VARCHAR",
            "status": "VARCHAR",
            "channel": "VARCHAR",
            "assigned_to": "VARCHAR",
            "resolved_at": "TIMESTAMPTZ",
            "created_at": "TIMESTAMPTZ",
            "updated_at": "TIMESTAMPTZ",
        },
        "required_indexes": ["idx_tickets_customer", "idx_tickets_status", "idx_tickets_channel"],
    },
    "knowledge_base": {
        "columns": {
            "id": "UUID",
            "title": "VARCHAR",
            "content": "TEXT",
            "category": "VARCHAR",
            "embedding": "VECTOR",
            "metadata": "JSONB",
            "created_at": "TIMESTAMPTZ",
            "updated_at": "TIMESTAMPTZ",
        },
        "required_indexes": ["idx_kb_category", "idx_kb_embedding"],
    },
    "channel_configs": {
        "columns": {
            "id": "UUID",
            "channel": "VARCHAR",
            "enabled": "BOOLEAN",
            "api_config": "JSONB",
            "response_template": "JSONB",
            "max_response_length": "INTEGER",
            "metadata": "JSONB",
            "created_at": "TIMESTAMPTZ",
            "updated_at": "TIMESTAMPTZ",
        },
        "required_indexes": [],
    },
    "agent_metrics": {
        "columns": {
            "id": "UUID",
            "channel": "VARCHAR",
            "metric_type": "VARCHAR",
            "metric_value": "FLOAT",
            "ticket_id": "UUID",
            "metadata": "JSONB",
            "recorded_at": "TIMESTAMPTZ",
        },
        "required_indexes": ["idx_metrics_channel", "idx_metrics_type", "idx_metrics_recorded"],
    },
}


def parse_schema(sql_content: str) -> dict:
    """Parse a schema.sql file to extract tables, columns, and indexes."""
    result = {"tables": {}, "indexes": set()}

    # Find CREATE TABLE statements
    table_pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\);",
        re.DOTALL | re.IGNORECASE,
    )

    for match in table_pattern.finditer(sql_content):
        table_name = match.group(1).lower()
        body = match.group(2)
        columns = {}

        # Parse column definitions (simplified)
        for line in body.split("\n"):
            line = line.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue

            # Skip constraints
            if re.match(r"^\s*(PRIMARY|FOREIGN|UNIQUE|CHECK|CONSTRAINT)", line, re.IGNORECASE):
                continue

            # Match: column_name TYPE ...
            col_match = re.match(r"(\w+)\s+(UUID|VARCHAR|TEXT|INTEGER|FLOAT|BOOLEAN|JSONB|JSON|TIMESTAMPTZ|TIMESTAMP|vector)\b", line, re.IGNORECASE)
            if col_match:
                col_name = col_match.group(1).lower()
                col_type = col_match.group(2).upper()
                # Normalize vector -> VECTOR
                if col_type == "VECTOR":
                    col_type = "VECTOR"
                columns[col_name] = col_type

        result["tables"][table_name] = columns

    # Find CREATE INDEX statements
    index_pattern = re.compile(
        r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
        re.IGNORECASE,
    )
    for match in index_pattern.finditer(sql_content):
        result["indexes"].add(match.group(1).lower())

    return result


def validate(schema_path: str) -> tuple[list, list, list]:
    """Validate schema file. Returns (errors, warnings, info)."""
    errors = []
    warnings = []
    info = []

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return [f"Schema file not found: {schema_path}"], [], []

    parsed = parse_schema(content)

    # Check all canonical tables exist
    for table_name, spec in CANONICAL_TABLES.items():
        if table_name not in parsed["tables"]:
            errors.append(f"MISSING TABLE: '{table_name}' not found in schema")
            continue

        actual_columns = parsed["tables"][table_name]

        # Check required columns
        for col_name, expected_type in spec["columns"].items():
            if col_name not in actual_columns:
                errors.append(f"MISSING COLUMN: '{table_name}.{col_name}' ({expected_type})")
            else:
                actual_type = actual_columns[col_name]
                if actual_type != expected_type:
                    # Check for common acceptable variants
                    if expected_type == "FLOAT" and actual_type in ("FLOAT", "DOUBLE PRECISION", "REAL"):
                        pass  # Acceptable
                    elif expected_type == "VECTOR" and actual_type.startswith("VECTOR"):
                        pass  # Acceptable
                    else:
                        errors.append(
                            f"TYPE MISMATCH: '{table_name}.{col_name}' expected {expected_type}, got {actual_type}"
                        )

        # Check for extra columns (schema drift warning)
        for col_name in actual_columns:
            if col_name not in spec["columns"]:
                warnings.append(f"EXTRA COLUMN: '{table_name}.{col_name}' — not in canonical schema")

        # Check required indexes
        for idx_name in spec["required_indexes"]:
            if idx_name.lower() not in parsed["indexes"]:
                errors.append(f"MISSING INDEX: '{idx_name}' for table '{table_name}'")

    # Check for extra tables
    canonical_names = set(CANONICAL_TABLES.keys())
    for table_name in parsed["tables"]:
        if table_name not in canonical_names:
            warnings.append(f"EXTRA TABLE: '{table_name}' — not in canonical schema")

    # Check for TIMESTAMP vs TIMESTAMPTZ issues
    if "TIMESTAMP" in content.upper():
        # Distinguish TIMESTAMP from TIMESTAMPTZ
        timestamp_only = re.findall(r"\bTIMESTAMP\b(?!TZ)", content, re.IGNORECASE)
        if timestamp_only:
            warnings.append("TIMESTAMP used instead of TIMESTAMPTZ — always use TIMESTAMPTZ")

    # Check for JSON vs JSONB
    json_only = re.findall(r"\bJSON\b(?!B)", content, re.IGNORECASE)
    if json_only:
        warnings.append("JSON used instead of JSONB — always use JSONB")

    # Check for SERIAL/BIGSERIAL (should use UUID)
    if re.search(r"\b(SERIAL|BIGSERIAL)\b", content, re.IGNORECASE):
        warnings.append("SERIAL/BIGSERIAL found — use UUID for all primary keys")

    info.append(f"Tables found: {len(parsed['tables'])}")
    info.append(f"Indexes found: {len(parsed['indexes'])}")
    info.append(f"Canonical tables expected: {len(CANONICAL_TABLES)}")

    return errors, warnings, info


def main():
    parser = argparse.ArgumentParser(description="Validate CRM schema against canonical definitions")
    parser.add_argument("--schema", required=True, help="Path to schema.sql file")
    args = parser.parse_args()

    errors, warnings, info = validate(args.schema)

    print("=" * 60)
    print("CRM Schema Validation Report")
    print("=" * 60)

    for line in info:
        print(f"  INFO: {line}")
    print()

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ❌ {e}")
        print()

    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠️  {w}")
        print()

    if not errors and not warnings:
        print("✅ Schema is valid — matches canonical definitions")
    elif not errors:
        print(f"✅ Schema is valid with {len(warnings)} warning(s)")
    else:
        print(f"❌ Schema validation FAILED — {len(errors)} error(s), {len(warnings)} warning(s)")

    print("=" * 60)

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
