import asyncio
import io
import json
from types import SimpleNamespace

from fastapi import UploadFile
from PIL import Image
from starlette.datastructures import Headers

import inventory as inventory_module


def test_inventory_upload_preview_and_confirm_routes_are_registered():
    paths = {
        (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
        for route in inventory_module.router.routes
    }
    assert ("/api/inventory/upload/preview", frozenset({"POST"})) in paths
    assert ("/api/inventory/upload/confirm", frozenset({"POST"})) in paths


def test_groq_column_mapping_only_accepts_headers_that_exist():
    columns = ["Item description", "Qty available", "Selling rate"]
    mapping = inventory_module._inventory_import_select_mapping(
        {
            "product_name": "Item description",
            "current_stock": "Qty available",
            "unit_price": "Invented price header",
            "sku": "Not in file",
        },
        columns,
    )
    assert mapping["product_name"] == "Item description"
    assert mapping["current_stock"] == "Qty available"
    assert mapping["unit_price"] is None
    assert mapping["sku"] is None


def test_header_fallback_supports_common_inventory_spreadsheet_names():
    columns = ["Product", "Qty", "Rate", "Barcode", "Product Category"]
    mapping = inventory_module._inventory_import_fallback_mapping(columns)
    assert mapping["product_name"] == "Product"
    assert mapping["current_stock"] == "Qty"
    assert mapping["unit_price"] == "Rate"
    assert mapping["sku"] == "Barcode"
    assert mapping["category"] == "Product Category"


def test_preview_reorders_values_to_canonical_inventory_fields_without_changing_them():
    columns = ["Selling rate", "Qty available", "Item description", "Barcode"]
    row = {
        "Selling rate": "₹125.50",
        "Qty available": "17",
        "Item description": "Filter Coffee",
        "Barcode": "8901234567890",
    }
    mapping = inventory_module._inventory_import_select_mapping(
        {
            "product_name": "Item description",
            "sku": "Barcode",
            "current_stock": "Qty available",
            "unit_price": "Selling rate",
        },
        columns,
    )
    preview = inventory_module._inventory_import_build_preview_rows(columns, [row], mapping)
    assert preview[0]["product_name"] == "Filter Coffee"
    assert preview[0]["sku"] == "8901234567890"
    assert preview[0]["current_stock"] == 17
    assert preview[0]["unit_price"] == 125.5
    assert preview[0]["issues"] == []


def test_missing_sku_is_stable_and_missing_price_blocks_upload():
    columns = ["Product"]
    mapping = inventory_module._inventory_import_select_mapping({}, columns)
    first = inventory_module._inventory_import_build_preview_rows(
        columns, [{"Product": "Ghee"}], mapping
    )[0]
    second = inventory_module._inventory_import_build_preview_rows(
        columns, [{"Product": "Ghee"}], mapping
    )[0]
    assert first["sku"] == second["sku"]
    assert first["sku"].startswith("AUTO-")
    assert any("price" in issue.lower() for issue in first["issues"])


def test_csv_reader_preserves_original_headers_and_values():
    columns, rows, truncated = inventory_module._inventory_import_parse_structured(
        b"Description,Count,Rate\nMilk 500ml,12,32.5\n",
        ".csv",
    )
    assert columns == ["Description", "Count", "Rate"]
    assert rows == [{"Description": "Milk 500ml", "Count": "12", "Rate": "32.5"}]
    assert truncated is False


def test_image_preview_uses_groq_extraction_and_returns_review_rows(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "unit-test-key")
    captured = {}

    async def fake_groq_json(api_key, model, messages, *, max_tokens=6000):
        captured["api_key"] = api_key
        captured["model"] = model
        captured["messages"] = messages
        return {
            "source_columns": ["Item", "Qty", "Rate"],
            "mapping": {
                "product_name": "Item",
                "current_stock": "Qty",
                "unit_price": "Rate",
            },
            "rows": [{"Item": "Ghee 1L", "Qty": "6", "Rate": "540"}],
            "notes": [],
        }

    monkeypatch.setattr(inventory_module, "_inventory_import_groq_json", fake_groq_json)
    image_buffer = io.BytesIO()
    Image.new("RGB", (90, 50), "white").save(image_buffer, format="PNG")
    upload = UploadFile(
        filename="stock-photo.png",
        file=io.BytesIO(image_buffer.getvalue()),
        headers=Headers({"content-type": "image/png"}),
    )

    result = asyncio.run(
        inventory_module.preview_inventory_upload(file=upload, user_id=9)
    )

    assert captured["api_key"] == "unit-test-key"
    assert captured["model"] == "qwen/qwen3.8-27b"
    assert result["provider"] == "Groq"
    assert result["row_count"] == 1
    assert result["rows"][0]["product_name"] == "Ghee 1L"
    assert result["rows"][0]["current_stock"] == 6
    assert result["rows"][0]["unit_price"] == 540.0
    assert result["rows"][0]["issues"] == []
    image_content = captured["messages"][0]["content"][1]["image_url"]["url"]
    assert image_content.startswith("data:image/jpeg;base64,")


def test_structured_preview_asks_groq_to_map_columns(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "unit-test-key")
    captured = {}

    async def fake_groq_json(api_key, model, messages, *, max_tokens=6000):
        captured["prompt"] = messages[0]["content"]
        return {
            "mapping": {
                "product_name": "Item",
                "current_stock": "Quantity",
                "unit_price": "Rate",
            }
        }

    monkeypatch.setattr(inventory_module, "_inventory_import_groq_json", fake_groq_json)
    upload = UploadFile(
        filename="inventory.csv",
        file=io.BytesIO(b"Rate,Quantity,Item\n45,4,Tea powder\n"),
        headers=Headers({"content-type": "text/csv"}),
    )

    result = asyncio.run(
        inventory_module.preview_inventory_upload(file=upload, user_id=9)
    )

    assert "source_columns" in captured["prompt"]
    assert result["mapping"]["product_name"] == "Item"
    assert result["mapping"]["unit_price"] == "Rate"
    assert result["rows"][0]["product_name"] == "Tea powder"
    assert result["rows"][0]["current_stock"] == 4
    assert result["rows"][0]["unit_price"] == 45.0
