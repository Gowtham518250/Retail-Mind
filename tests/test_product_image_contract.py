def test_product_image_field_is_optional_and_accepts_safe_image_sources():
    from inventory import ProductCreate, ProductUpdate, ProductResponse

    photo = "https://images.example.test/milk-carton.webp"
    inline = "data:image/jpeg;base64,/9j/AA=="

    created = ProductCreate(product_name="Milk", sku="milk-1", unit_price=50, image_url=photo)
    assert created.image_url == photo
    assert ProductCreate(product_name="Milk", sku="milk-2", unit_price=50).image_url is None

    changed = ProductUpdate(image_url=inline)
    assert changed.image_url == inline

    response_fields = getattr(ProductResponse, "model_fields", getattr(ProductResponse, "__fields__", {}))
    assert "image_url" in response_fields


def test_product_image_validation_rejects_unsafe_and_oversized_values():
    import pytest
    from pydantic import ValidationError
    from inventory import ProductCreate

    with pytest.raises(ValidationError):
        ProductCreate(product_name="Milk", sku="milk-1", unit_price=50, image_url="javascript:alert(1)")
    with pytest.raises(ValidationError):
        ProductCreate(product_name="Milk", sku="milk-2", unit_price=50, image_url="data:text/html;base64,PGh0bWw+")
    with pytest.raises(ValidationError):
        ProductCreate(product_name="Milk", sku="milk-3", unit_price=50, image_url="https://example.test/" + "a" * 120001)


def test_product_image_suggestion_endpoint_is_owner_authenticated():
    from inventory import router

    route = next(
        route for route in router.routes
        if route.path == "/api/inventory/product-image-suggestions"
    )
    assert "GET" in route.methods
    assert route.dependant.dependencies
