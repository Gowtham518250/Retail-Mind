from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from inventory import ProductCreate, ProductResponse, ProductUpdate
from invoices_billing import _calculate_sale_loss, _record_below_cost_sale_loss
from models import ShopExpense, UniversalTransaction


def test_below_cost_sale_loss_multiplies_unit_cost_by_sold_quantity():
    assert _calculate_sale_loss(
        purchase_price=50,
        quantity=2,
        net_sale_amount=90,
    ) == Decimal("10.00")


def test_line_discount_is_included_in_effective_sale_revenue():
    # Three items cost ₹20 each (₹60 total); sale after discount is ₹49.
    assert _calculate_sale_loss(
        purchase_price=20,
        quantity=3,
        net_sale_amount=49,
    ) == Decimal("11.00")


def test_sale_at_or_above_cost_does_not_create_loss():
    assert _calculate_sale_loss(
        purchase_price=50,
        quantity=2,
        net_sale_amount=100,
    ) == Decimal("0.00")
    assert _calculate_sale_loss(
        purchase_price=50,
        quantity=2,
        net_sale_amount=130,
    ) == Decimal("0.00")


def test_unknown_purchase_cost_never_invents_a_loss():
    assert _calculate_sale_loss(
        purchase_price=0,
        quantity=2,
        net_sale_amount=10,
    ) == Decimal("0.00")
    assert _calculate_sale_loss(
        purchase_price=None,
        quantity=2,
        net_sale_amount=10,
    ) == Decimal("0.00")


def test_below_cost_loss_is_written_to_expense_ledger_and_universal_pnl_journal():
    class FakeDb:
        def __init__(self):
            self.added = []

        def add(self, entity):
            self.added.append(entity)

    db = FakeDb()
    product = SimpleNamespace(
        id=42,
        product_name="Sona Masoori Rice",
        purchase_price=Decimal("50.00"),
    )
    result = _record_below_cost_sale_loss(
        db=db,
        shop_id=7,
        invoice_number="BILL-0042",
        sale_date=date(2026, 10, 12),
        product=product,
        quantity=2,
        net_sale_amount=90,
    )

    assert result == Decimal("10.00")
    assert len(db.added) == 2
    expense = next(entity for entity in db.added if isinstance(entity, ShopExpense))
    journal = next(entity for entity in db.added if isinstance(entity, UniversalTransaction))
    assert expense.shop_id == 7
    assert expense.category == "SALE_LOSS"
    assert Decimal(str(expense.amount)) == Decimal("10.00")
    assert expense.expense_date == date(2026, 10, 12)
    assert "BILL-0042" in expense.description
    assert journal.shop_id == 7
    assert journal.tx_type == "EXPENSE"
    assert journal.category == "SALE_LOSS"
    assert Decimal(str(journal.amount)) == Decimal("10.00")
    assert journal.reference_id == "BILL-0042"


def test_non_loss_line_does_not_create_expense_records():
    class FakeDb:
        def __init__(self):
            self.added = []

        def add(self, entity):
            self.added.append(entity)

    db = FakeDb()
    product = SimpleNamespace(id=42, product_name="Milk", purchase_price=40)
    result = _record_below_cost_sale_loss(
        db=db,
        shop_id=7,
        invoice_number="BILL-0043",
        sale_date=date(2026, 10, 12),
        product=product,
        quantity=1,
        net_sale_amount=45,
    )
    assert result == Decimal("0.00")
    assert db.added == []


def test_inventory_api_accepts_and_returns_purchase_price():
    created = ProductCreate(
        product_name="Milk",
        sku="MILK-1",
        unit_price=60,
        purchase_price=48,
    )
    updated = ProductUpdate(purchase_price=49)
    response = ProductResponse(
        id=1,
        product_name="Milk",
        sku="MILK-1",
        current_stock=2,
        min_stock=1,
        max_stock=10,
        unit_price=60,
        purchase_price=48,
        category="Dairy",
    )
    assert created.purchase_price == 48
    assert updated.purchase_price == 49
    assert response.purchase_price == 48
