"""Fail-closed SQL validation for AI-generated read queries.

This module intentionally rejects unfamiliar tables and indirect joins that cannot
be proven tenant-scoped. It favours a clarification response over a plausible
answer that could leak another shop's data or report the wrong metric.
"""
from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp


# Direct ownership columns are derived from the repository's business table catalog.
# Do not add a table here until its tenant key is verified against its model/schema.
_DIRECT_TENANT_COLUMNS: dict[str, str] = {
    "attendance": "employee_id",
    "bank_reconciliations": "shop_id",
    "billing_counters": "user_id",
    "daily_reports": "user_id",
    "flash_sales": "user_id",
    "gift_cards": "shop_id",
    "invoices": "user_id",
    "khata_balances": "shop_id",
    "loyalty_tiers": "user_id",
    "online_orders": "shop_id",
    "products": "user_id",
    "purchase_orders": "shop_id",
    "sales": "shopkeeper_id",
    "shop_expenses": "shop_id",
    "shop_profiles": "shop_id",
    "universal_transactions": "shop_id",
    "whatsapp_orders": "shop_id",
    "workers": "shopkeeper_id",
    "customers": "user_id",
}

# Tables without a direct tenant key must be joined to one of these verified,
# tenant-scoped parent relations. Each tuple is (parent, child FK, parent PK).
_INDIRECT_TENANT_RELATIONS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "customer_credit_scores": (("customers", "customer_id", "id"),),
    "customer_loyalty": (("customers", "customer_id", "id"),),
    "customer_occasions": (("customers", "customer_id", "id"),),
    "delivery_tracking": (("deliveries", "delivery_id", "id"),),
    "deliveries": (("shop_profiles", "shop_id", "id"),),
    "invoice_line_items": (("invoices", "invoice_id", "id"),),
    "khata_history": (("khata_balances", "khata_id", "id"),),
    "loyalty_transactions": (("customer_loyalty", "customer_loyalty_id", "id"),),
    "payments": (("invoices", "invoice_id", "id"),),
    "product_batches": (("products", "product_id", "id"),),
    "sales_by_counter": (
        ("invoices", "invoice_id", "id"),
        ("billing_counters", "counter_id", "id"),
        ("shop_profiles", "shop_id", "id"),
    ),
    "shop_settings": (("shop_profiles", "shop_id", "id"),),
    "stock_movements": (("products", "product_id", "id"),),
    "upi_ledger": (
        ("invoices", "invoice_id", "id"),
        ("shop_profiles", "shop_id", "id"),
    ),
}

# This is the only currently documented global read-only business calendar table.
_GLOBAL_TABLES = {"festival_events"}
_EXTRA_CATALOG_TABLES = {"products", "product_batches", "stock_movements"}


def _column_is_tenant_parameter(
    node: Any,
    *,
    table_alias: str,
    table_name: str,
    column_name: str,
    allow_unqualified: bool,
) -> bool:
    if not isinstance(node, exp.Column) or node.name.casefold() != column_name.casefold():
        return False
    qualifier = (node.table or "").casefold()
    if qualifier:
        return qualifier in {table_alias.casefold(), table_name.casefold()}
    return allow_unqualified


def _is_user_id_parameter(node: Any) -> bool:
    if not isinstance(node, exp.Placeholder):
        return False
    try:
        rendered = node.sql(dialect="postgres").strip().casefold()
    except Exception:
        rendered = str(node.this or "").strip().casefold()
    return rendered in {":user_id", "user_id"}


def _condition_guarantees_tenant_scope(
    node: Any,
    *,
    table_alias: str,
    table_name: str,
    column_name: str,
    allow_unqualified: bool,
) -> bool:
    """True only if every logical path through a WHERE expression binds tenant scope."""
    if node is None:
        return False
    if isinstance(node, exp.Paren):
        return _condition_guarantees_tenant_scope(
            node.this,
            table_alias=table_alias,
            table_name=table_name,
            column_name=column_name,
            allow_unqualified=allow_unqualified,
        )
    if isinstance(node, exp.And):
        # One conjunct that guarantees the tenant is sufficient for an AND.
        return (
            _condition_guarantees_tenant_scope(
                node.this, table_alias=table_alias, table_name=table_name,
                column_name=column_name, allow_unqualified=allow_unqualified,
            )
            or _condition_guarantees_tenant_scope(
                node.expression, table_alias=table_alias, table_name=table_name,
                column_name=column_name, allow_unqualified=allow_unqualified,
            )
        )
    if isinstance(node, exp.Or):
        # Both branches must preserve tenant scope; otherwise an OR can bypass it.
        return (
            _condition_guarantees_tenant_scope(
                node.this, table_alias=table_alias, table_name=table_name,
                column_name=column_name, allow_unqualified=allow_unqualified,
            )
            and _condition_guarantees_tenant_scope(
                node.expression, table_alias=table_alias, table_name=table_name,
                column_name=column_name, allow_unqualified=allow_unqualified,
            )
        )
    if not isinstance(node, exp.EQ):
        return False

    left, right = node.this, node.expression
    return (
        _column_is_tenant_parameter(
            left, table_alias=table_alias, table_name=table_name,
            column_name=column_name, allow_unqualified=allow_unqualified,
        )
        and _is_user_id_parameter(right)
    ) or (
        _column_is_tenant_parameter(
            right, table_alias=table_alias, table_name=table_name,
            column_name=column_name, allow_unqualified=allow_unqualified,
        )
        and _is_user_id_parameter(left)
    )


def _catalog_table_names(catalog: dict[str, Any] | None) -> set[str]:
    names = set(_EXTRA_CATALOG_TABLES)
    if not isinstance(catalog, dict):
        return names
    for key, entry in catalog.items():
        table_key = str(key or "").strip().casefold()
        content = entry.get("content", "") if isinstance(entry, dict) else str(entry or "")
        # "inventory" is a documentation grouping, not a physical table. Only
        # catalog headings and explicitly defined extras are accepted as tables.
        if table_key != "inventory" and re.search(
            rf"(?im)^\s*TABLE:\s*{re.escape(table_key)}\s*$", str(content or "")
        ):
            names.add(table_key)
        for name in re.findall(r"(?im)^\s*TABLE:\s*([A-Za-z_][A-Za-z0-9_]*)\s*$", str(content or "")):
            if name.casefold() != "inventory":
                names.add(name.casefold())
    return names


def _nearest_select(node: exp.Expression) -> exp.Select | None:
    parent = node.parent
    while parent is not None:
        if isinstance(parent, exp.Select):
            return parent
        parent = parent.parent
    return None


def _same_select_tables(select: exp.Select) -> list[exp.Table]:
    return [
        table
        for table in select.find_all(exp.Table)
        if _nearest_select(table) is select
    ]


def _has_join_relationship(
    select: exp.Select,
    child: exp.Table,
    parent_name: str,
    child_fk: str,
    parent_pk: str,
) -> bool:
    local_tables = _same_select_tables(select)
    child_alias = (child.alias_or_name or child.name).casefold()
    parent_tables = [t for t in local_tables if t.name.casefold() == parent_name.casefold()]
    if not parent_tables:
        return False
    parent_aliases = {(t.alias_or_name or t.name).casefold() for t in parent_tables}
    child_qualifiers = {child_alias, child.name.casefold()}

    for join in select.args.get("joins") or []:
        on = join.args.get("on")
        if on is None:
            continue
        for equality in on.find_all(exp.EQ):
            left, right = equality.this, equality.expression
            if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
                continue
            left_table, right_table = (left.table or "").casefold(), (right.table or "").casefold()
            if (
                left.name.casefold() == child_fk.casefold()
                and left_table in child_qualifiers
                and right.name.casefold() == parent_pk.casefold()
                and right_table in parent_aliases
            ) or (
                right.name.casefold() == child_fk.casefold()
                and right_table in child_qualifiers
                and left.name.casefold() == parent_pk.casefold()
                and left_table in parent_aliases
            ):
                return True
    return False


def validate_read_only_tenant_sql(
    sql: str,
    catalog: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Validate one PostgreSQL SELECT and prove a scope path for every physical table."""
    candidate = str(sql or "").strip().rstrip(";").strip()
    if not candidate:
        return False, "empty_sql"
    if ";" in candidate or "--" in candidate or "/*" in candidate or "*/" in candidate:
        return False, "multiple_statements_or_comments"
    if re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|CALL|DO|EXECUTE|MERGE|VACUUM|ANALYZE)\b",
        candidate, re.IGNORECASE,
    ):
        return False, "write_or_admin_keyword"
    if re.search(
        r"\b(pg_sleep|pg_terminate_backend|pg_cancel_backend|dblink|lo_import|lo_export|pg_read_file|pg_write_file|nextval|setval|pg_advisory_lock)\s*\(",
        candidate, re.IGNORECASE,
    ):
        return False, "unsafe_function"
    if re.search(r"\bFOR\s+(?:UPDATE|SHARE)\b", candidate, re.IGNORECASE):
        return False, "locking_select"

    try:
        statements = sqlglot.parse(candidate, read="postgres")
    except Exception:
        return False, "sql_parse_error"
    if len(statements) != 1 or statements[0] is None:
        return False, "not_one_statement"

    root = statements[0]
    if root.key not in {"select", "union", "intersect", "except"}:
        return False, "not_read_only_select"
    selects = list(root.find_all(exp.Select))
    if not selects:
        return False, "missing_select"

    allowed_tables = _catalog_table_names(catalog)
    cte_names = {
        str(cte.alias_or_name or "").casefold()
        for cte in root.find_all(exp.CTE)
        if str(cte.alias_or_name or "").strip()
    }

    for table in root.find_all(exp.Table):
        name = str(table.name or "").casefold()
        if not name or name in cte_names:
            continue
        if str(table.db or "").casefold() not in {"", "public"}:
            return False, "non_public_schema"
        if name not in allowed_tables:
            return False, "unknown_or_disallowed_table"

        select = _nearest_select(table)
        if select is None:
            return False, "table_without_select"
        local_tables = _same_select_tables(select)

        if name in _DIRECT_TENANT_COLUMNS:
            column_name = _DIRECT_TENANT_COLUMNS[name]
            table_alias = (table.alias_or_name or table.name).casefold()
            same_column_candidates = [
                item for item in local_tables
                if _DIRECT_TENANT_COLUMNS.get(item.name.casefold(), "").casefold() == column_name.casefold()
            ]
            allow_unqualified = len(same_column_candidates) == 1
            where = select.args.get("where")
            if where is None or not _condition_guarantees_tenant_scope(
                where.this,
                table_alias=table_alias,
                table_name=name,
                column_name=column_name,
                allow_unqualified=allow_unqualified,
            ):
                return False, "tenant_scope_missing_or_bypassable"
        elif name in _INDIRECT_TENANT_RELATIONS:
            linked_to_scoped_parent = any(
                _has_join_relationship(select, table, parent_name, child_fk, parent_pk)
                for parent_name, child_fk, parent_pk in _INDIRECT_TENANT_RELATIONS[name]
            )
            if not linked_to_scoped_parent:
                return False, "indirect_relation_without_scoped_parent_join"
        elif name not in _GLOBAL_TABLES:
            return False, "table_has_no_verified_tenant_scope"

    return True, "ok"
