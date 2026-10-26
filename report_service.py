"""
Daily Report Service (Feature 16)
Generate daily WhatsApp reports with revenue, expenses, profit, top product
"""

from sqlalchemy.orm import Session
from models import DailyReport, Invoice, Payment, Product, ProductBatch, StockMovement, ShopExpense, InvoiceLineItem, OnlineOrderReturn, UniversalTransaction
from sqlalchemy import func
from datetime import date, datetime, timedelta, timezone, time
from decimal import Decimal
from fastapi import HTTPException
from sales_recognition import recognized_invoice_filters


from zoneinfo import ZoneInfo

_REPORT_TZ = ZoneInfo("Asia/Kolkata")


def _local_business_date() -> date:
    """India business date, not the server's (likely UTC on Render) date.
    Using date.today() directly here caused the exact class of timezone
    bug already fixed elsewhere in this codebase (attendance.py) - a sale
    made late evening IST could get filed under the wrong calendar day
    once the server's own UTC clock had already rolled over, silently
    splitting one day's real business across two different reports."""
    return datetime.now(_REPORT_TZ).date()


class ReportService:
    
    @staticmethod
    def _calculate_business_day_summary(db: Session, user_id: int, report_date: date) -> dict:
        """Calculate a live, traceable daily business summary from source records.

        Sales use the shared invoice-recognition rule; collections use payment
        timestamps; expenses come from entered expense records. Unknown costs
        stay unknown instead of being guessed as a fixed percentage of sales.
        """
        start_local = datetime.combine(report_date, time.min, tzinfo=_REPORT_TZ)
        end_local = start_local + timedelta(days=1)
        # DateTime columns in this application are stored as naive UTC.
        start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)

        recognized_filters = recognized_invoice_filters()
        day_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.user_id == user_id,
                Invoice.invoice_date == report_date,
                *recognized_filters,
            )
            .order_by(Invoice.id)
            .all()
        )
        invoice_ids = [int(row.id) for row in day_invoices]
        gross_sales = sum(
            (Decimal(str(row.total_amount or 0)) for row in day_invoices),
            Decimal("0"),
        )
        bill_count = len(day_invoices)

        # Actual cash received today, including a payment still requiring a
        # refund after an order was cancelled. We scope through the invoice's
        # owner, but deliberately do not suppress real receipts for voided bills.
        payment_rows = (
            db.query(Payment, Invoice)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .filter(
                Invoice.user_id == user_id,
                Payment.payment_date >= start_utc,
                Payment.payment_date < end_utc,
            )
            .order_by(Payment.id)
            .all()
        )
        cash_collected = Decimal("0")
        upi_collected = Decimal("0")
        card_collected = Decimal("0")
        other_collected = Decimal("0")
        payment_total = Decimal("0")
        payment_ids = []
        for payment, invoice in payment_rows:
            amount = Decimal(str(payment.amount or 0))
            method = getattr(payment.payment_method, "value", payment.payment_method)
            method = str(method or "").upper()
            payment_total += amount
            payment_ids.append(int(payment.id))
            if method == "CASH":
                cash_collected += amount
            elif method in {"ONLINE", "TRANSFER", "UPI"}:
                upi_collected += amount
            elif method == "CARD":
                card_collected += amount
            else:
                other_collected += amount

        expense_rows = (
            db.query(ShopExpense)
            .filter(
                ShopExpense.shop_id == user_id,
                ShopExpense.expense_date == report_date,
            )
            .order_by(ShopExpense.id)
            .all()
        )
        total_expenses = sum(
            (Decimal(str(expense.amount or 0)) for expense in expense_rows),
            Decimal("0"),
        )
        expense_ids = [int(row.id) for row in expense_rows]

        # Returns enter the operational summary only after the owner approves
        # them. processed_at is preserved as the initial decision timestamp.
        return_rows = (
            db.query(OnlineOrderReturn)
            .filter(
                OnlineOrderReturn.shop_id == user_id,
                OnlineOrderReturn.status.in_(["REFUND_PENDING", "REFUNDED"]),
                OnlineOrderReturn.processed_at >= start_utc,
                OnlineOrderReturn.processed_at < end_utc,
            )
            .order_by(OnlineOrderReturn.id)
            .all()
        )
        returns_total = sum(
            (Decimal(str(row.refund_amount or 0)) for row in return_rows),
            Decimal("0"),
        )
        return_ids = [int(row.id) for row in return_rows]
        net_sales = gross_sales - returns_total

        line_rows = (
            db.query(InvoiceLineItem, Product)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .outerjoin(Product, InvoiceLineItem.product_id == Product.id)
            .filter(
                Invoice.user_id == user_id,
                Invoice.invoice_date == report_date,
                *recognized_filters,
            )
            .order_by(InvoiceLineItem.id)
            .all()
        )
        cogs = Decimal("0")
        line_count = len(line_rows)
        cost_known_lines = 0
        product_quantities = {}
        for line, product in line_rows:
            name = (
                (product.product_name if product else None)
                or (line.description or "").strip()
                or "Unlinked product"
            )
            quantity = Decimal(str(line.quantity or 0))
            product_quantities[name] = product_quantities.get(name, Decimal("0")) + quantity
            purchase_price = Decimal(str(getattr(product, "purchase_price", 0) or 0))
            if product is not None and purchase_price > 0 and quantity >= 0:
                cogs += purchase_price * quantity
                cost_known_lines += 1

        # A total cost estimate is only defensible when every billed line has
        # a usable recorded purchase cost. For returns the returned item costs
        # are not reliably linked to the return record, so report profit as
        # unavailable instead of pretending the margin is exact.
        has_sales_without_lines = bool(day_invoices) and not line_rows
        costs_complete = (
            not has_sales_without_lines
            and (line_count == 0 or cost_known_lines == line_count)
        )
        profit_available = costs_complete and returns_total == 0
        estimated_gross_profit = (gross_sales - cogs) if profit_available else None
        estimated_net_profit = (
            estimated_gross_profit - total_expenses
            if estimated_gross_profit is not None
            else None
        )
        cost_coverage_pct = (
            round((cost_known_lines / line_count) * 100, 2)
            if line_count else (100.0 if not day_invoices else 0.0)
        )

        top_product_name = "N/A"
        top_product_qty = Decimal("0")
        if product_quantities:
            top_product_name, top_product_qty = max(
                product_quantities.items(), key=lambda entry: (entry[1], entry[0])
            )

        outstanding_rows = (
            db.query(Invoice)
            .filter(
                Invoice.user_id == user_id,
                *recognized_invoice_filters(),
            )
            .order_by(Invoice.id)
            .all()
        )
        outstanding_by_invoice = []
        credit_outstanding = Decimal("0")
        for invoice in outstanding_rows:
            balance = max(
                Decimal("0"),
                Decimal(str(invoice.total_amount or 0))
                - Decimal(str(invoice.paid_amount or 0)),
            )
            if balance > 0:
                credit_outstanding += balance
                outstanding_by_invoice.append({
                    "invoice_id": int(invoice.id),
                    "invoice_number": str(invoice.invoice_number or ""),
                    "outstanding_amount": float(balance),
                })

        low_stock_rows = (
            db.query(Product)
            .filter(
                Product.user_id == user_id,
                Product.is_active.is_(True),
                Product.current_stock <= Product.min_stock,
            )
            .order_by(Product.product_name)
            .limit(100)
            .all()
        )
        low_stock = [{
            "product_id": int(product.id),
            "product_name": product.product_name,
            "current_stock": float(product.current_stock or 0),
            "minimum_stock": float(product.min_stock or 0),
        } for product in low_stock_rows]

        # Expiry alerts are scoped through the owning product/shop.
        expiry_cutoff = report_date + timedelta(days=30)
        expiry_rows = (
            db.query(ProductBatch, Product)
            .join(Product, Product.id == ProductBatch.product_id)
            .filter(
                Product.user_id == user_id,
                Product.is_active.is_(True),
                ProductBatch.quantity > 0,
                ProductBatch.expiry_date.isnot(None),
                ProductBatch.expiry_date <= expiry_cutoff,
            )
            .order_by(ProductBatch.expiry_date.asc(), Product.product_name.asc())
            .limit(100)
            .all()
        )
        expiry_alerts = []
        expired_stock_units = Decimal("0")
        expiring_stock_units = Decimal("0")
        for batch, product in expiry_rows:
            expiry_date = batch.expiry_date
            if expiry_date is None:
                continue
            quantity = Decimal(str(batch.quantity or 0))
            days_until_expiry = (expiry_date - report_date).days
            expired = days_until_expiry < 0
            if expired:
                expired_stock_units += quantity
            else:
                expiring_stock_units += quantity
            expiry_alerts.append({
                "batch_id": int(batch.id),
                "product_id": int(product.id),
                "product_name": product.product_name,
                "batch_number": batch.batch_number,
                "expiry_date": expiry_date.isoformat(),
                "days_until_expiry": days_until_expiry,
                "quantity": float(quantity),
                "expired": expired,
            })

        # Keep refund-payable receipts distinct from sales and ordinary expenses.
        refund_required_rows = (
            db.query(UniversalTransaction)
            .filter(
                UniversalTransaction.shop_id == user_id,
                UniversalTransaction.category == "REFUND_REQUIRED",
                UniversalTransaction.tx_date >= start_utc,
                UniversalTransaction.tx_date < end_utc,
            )
            .order_by(UniversalTransaction.id)
            .all()
        )
        refund_required_total = sum(
            (Decimal(str(row.amount or 0)) for row in refund_required_rows),
            Decimal("0"),
        )

        return {
            "report_date": report_date.isoformat(),
            "gross_sales": float(gross_sales),
            "returns": float(returns_total),
            "net_sales": float(net_sales),
            "total_revenue": float(net_sales),  # legacy API key
            "payment_collections": {
                "total": float(payment_total),
                "cash": float(cash_collected),
                "upi": float(upi_collected),
                "card": float(card_collected),
                "other": float(other_collected),
            },
            "total_collected": float(payment_total),
            "total_expenses": float(total_expenses),
            "estimated_gross_profit": (
                float(estimated_gross_profit) if estimated_gross_profit is not None else None
            ),
            "estimated_net_profit": (
                float(estimated_net_profit) if estimated_net_profit is not None else None
            ),
            "total_profit": (
                float(estimated_net_profit) if estimated_net_profit is not None else 0.0
            ),  # legacy numeric field; check profit_estimate_available before displaying.
            "profit_estimate_available": profit_available,
            "cost_coverage_percent": cost_coverage_pct,
            "bill_count": bill_count,
            "top_product": top_product_name,
            "top_product_qty": float(top_product_qty),
            "customer_credit_outstanding": float(credit_outstanding),
            "outstanding_invoices": outstanding_by_invoice[:200],
            "outstanding_invoice_count": len(outstanding_by_invoice),
            "stock_alert_count": len(low_stock),
            "low_stock_products": low_stock,
            "expiry_alert_count": len(expiry_alerts),
            "expiry_alerts": expiry_alerts,
            "expired_stock_units": float(expired_stock_units),
            "expiring_stock_units_next_30_days": float(expiring_stock_units),
            "refund_required_collections": float(refund_required_total),
            "refund_required_transaction_ids": [int(row.id) for row in refund_required_rows],
            "sources": {
                "invoice_ids": invoice_ids[:200],
                "payment_ids": payment_ids[:200],
                "expense_ids": expense_ids[:200],
                "return_ids": return_ids[:200],
                "low_stock_product_ids": [int(row.id) for row in low_stock_rows],
            },
        }

    @staticmethod
    def generate_daily_report(db: Session, user_id: int, report_date: date = None) -> dict:
        """Generate or refresh the live daily business summary."""
        if report_date is None:
            report_date = _local_business_date()

        summary = ReportService._calculate_business_day_summary(db, user_id, report_date)
        report = db.query(DailyReport).filter_by(
            user_id=user_id,
            report_date=report_date,
        ).order_by(DailyReport.id.desc()).first()

        # Refresh an existing row instead of returning stale numbers from the
        # first time a report happened to be requested during the day.
        if report is None:
            report = DailyReport(user_id=user_id, report_date=report_date)
            db.add(report)

        report.total_revenue = Decimal(str(summary["net_sales"]))
        report.total_expenses = Decimal(str(summary["total_expenses"]))
        report.total_profit = Decimal(str(summary["estimated_net_profit"] or 0))
        report.bill_count = int(summary["bill_count"])
        report.top_product_name = str(summary["top_product"])
        report.top_product_qty = int(summary["top_product_qty"])
        report.cash_collected = Decimal(str(summary["payment_collections"]["cash"]))
        report.upi_collected = Decimal(str(summary["payment_collections"]["upi"]))
        report.card_collected = Decimal(str(summary["payment_collections"]["card"]))
        try:
            db.commit()
            db.refresh(report)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to save daily business summary.") from exc

        return {
            "report_id": report.id,
            **summary,
            "whatsapp_sent": bool(report.whatsapp_sent),
        }

    @staticmethod
    def get_report(db: Session, report_id: int) -> dict:
        """Return the report's current figures, recomputed from source records."""
        report = db.query(DailyReport).filter_by(id=report_id).first()
        if not report:
            return {"error": "Report not found"}
        summary = ReportService._calculate_business_day_summary(
            db, report.user_id, report.report_date
        )
        return {
            "report_id": report.id,
            **summary,
            "whatsapp_sent": bool(report.whatsapp_sent),
        }

    @staticmethod
    def format_whatsapp_message(report: dict, shop_name: str) -> str:
        """Format the daily summary without presenting unknown margin as fact."""
        profit_line = (
            f"Estimated net profit: ₹{report['estimated_net_profit']:.2f}"
            if report.get("profit_estimate_available") and report.get("estimated_net_profit") is not None
            else "Profit estimate unavailable — enter purchase costs for all sold products."
        )
        collections = report.get("payment_collections") or {}
        message = f"""📊 Daily Business Summary - {report['report_date']}
{shop_name}

🧾 Gross sales: ₹{report.get('gross_sales', report.get('total_revenue', 0)):.2f}
↩️ Returns: ₹{report.get('returns', 0):.2f}
✅ Net sales: ₹{report.get('net_sales', report.get('total_revenue', 0)):.2f}
💳 Payments collected: ₹{report.get('total_collected', 0):.2f}
   Cash: ₹{collections.get('cash', report.get('cash', 0)):.2f}
   UPI/transfer: ₹{collections.get('upi', report.get('upi', 0)):.2f}
   Card: ₹{collections.get('card', report.get('card', 0)):.2f}
   Other: ₹{collections.get('other', 0):.2f}
📒 Customer credit outstanding: ₹{report.get('customer_credit_outstanding', 0):.2f}
📦 Actual recorded expenses: ₹{report.get('total_expenses', 0):.2f}
📈 {profit_line}
⚠️ Low-stock products: {report.get('stock_alert_count', 0)}
🧾 Bills recognized: {report.get('bill_count', 0)}

Generated: {datetime.now(_REPORT_TZ).strftime('%I:%M %p')}"""
        return message

    @staticmethod
    def send_daily_report_whatsapp(db: Session, user_id: int, owner_phone: str) -> dict:
        """Prepare a WhatsApp summary, leaving sending to the owner's client."""
        report_data = ReportService.generate_daily_report(db, user_id)
        if "error" in report_data:
            return report_data

        from models import ShopProfile
        shop = db.query(ShopProfile).filter(ShopProfile.shop_id == user_id).first()
        shop_name = shop.shop_name if shop and shop.shop_name else "Your Shop"
        message = ReportService.format_whatsapp_message(report_data, shop_name)

        report = db.query(DailyReport).filter_by(id=report_data["report_id"]).first()
        if report:
            report.whatsapp_sent = True
            report.whatsapp_sent_at = datetime.now(timezone.utc)
            try:
                db.commit()
            except Exception as exc:
                db.rollback()
                raise HTTPException(status_code=500, detail="Failed to mark report as sent.") from exc

        return {
            "status": "ready_to_send",
            "recipient": owner_phone,
            "message": message,
            "action": "Send this WhatsApp message to owner",
            "report": report_data,
        }

    @staticmethod
    def get_weekly_reports(db: Session, user_id: int) -> list:
        """Get last 7 days of reports"""
        from datetime import timedelta
        start_date = date.today() - timedelta(days=7)
        
        reports = db.query(DailyReport).filter(
            DailyReport.user_id == user_id,
            DailyReport.report_date >= start_date
        ).order_by(DailyReport.report_date.desc()).all()
        
        return [{
            "date": r.report_date.isoformat(),
            "revenue": float(r.total_revenue),
            "profit": float(r.total_profit),
            "bills": r.bill_count,
            "top_product": r.top_product_name
        } for r in reports]
    
    @staticmethod
    def get_monthly_summary(db: Session, user_id: int, year: int, month: int) -> dict:
        """Get monthly summary report"""
        from datetime import datetime as dt
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        reports = db.query(DailyReport).filter(
            DailyReport.user_id == user_id,
            DailyReport.report_date >= start_date,
            DailyReport.report_date < end_date
        ).all()
        
        if not reports:
            return {"error": "No reports for this period"}
        
        total_revenue = sum(float(r.total_revenue) for r in reports)
        total_profit = sum(float(r.total_profit) for r in reports)
        total_bills = sum(r.bill_count for r in reports)
        avg_daily_revenue = total_revenue / len(reports) if reports else 0
        
        return {
            "period": f"{month}/{year}",
            "total_revenue": total_revenue,
            "total_profit": total_profit,
            "total_bills": total_bills,
            "avg_daily_revenue": avg_daily_revenue,
            "days_with_sales": len(reports),
            "profit_margin": (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        }
    
    @staticmethod
    def schedule_daily_report(db: Session, user_id: int, owner_phone: str, 
                             scheduled_time: str = "18:00") -> dict:
        """
        Schedule daily report at specific time (e.g., 6 PM)
        Returns info for Flutter notification scheduling
        """
        return {
            "status": "scheduled",
            "scheduled_time": scheduled_time,
            "message": f"Daily report will be sent to {owner_phone} every day at {scheduled_time}",
            "action": "Use Flutter's flutter_local_notifications to schedule this"
        }
