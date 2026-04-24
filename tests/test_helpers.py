from app.helper.helper_func import validate_vendor, validate_line_items, check_duplicate
from app.models.invoice_model import Vendor, Invoice, InvoiceLineItem
from datetime import datetime


def test_validate_vendor_found(db_session):
    # Seed the database with a vendor
    vendor = Vendor(name="Acme Corps", email="contact@acmecorps.com")
    db_session.add(vendor)
    db_session.commit()
    db_session.refresh(vendor) # Refresh to get the ID

    vendor_result = validate_vendor(db_session, "Acme Corps")
    assert vendor_result["passed"] is True
    assert vendor_result["vendor_id"] == vendor.id
    assert "found" in vendor_result["message"]

def test_validate_vendor_not_found(db_session):
    result = validate_vendor(db_session, "Nonexistent Corp")
    assert result["passed"] is False
    assert "not found" in result["message"]

def test_validate_line_items_match(db_session):
    # Seed a vendor
    vendor = Vendor(name="Test Vendor", email="contact@testvendor.com", gst_number="1234567890jhj", payment_terms=30, is_active=True)
    db_session.add(vendor)
    db_session.commit()
    db_session.refresh(vendor)

    invoice = Invoice(uploaded_by=3, vendor_id=vendor.id, file_name="test invoice", file_size_bytes=1024, status="COMPLETED", total_amount=110.0, tax_amount=10.0)
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    
    line_item = InvoiceLineItem(invoice_id=invoice.id, total_price=100.0, quantity=1, unit_price=100.0)
    db_session.add(line_item)
    db_session.commit()

    result = validate_line_items(db_session, invoice)
    assert result["passed"] is True
    assert "matching" in result["message"]

def test_validate_line_items_mismatch(db_session):
    # Seed a vendor
    vendor = Vendor(name="Test Vendor for Mismatch")
    db_session.add(vendor)
    db_session.commit()
    db_session.refresh(vendor)

    invoice = Invoice(uploaded_by=2, vendor_id=vendor.id, file_name="test invoice", file_size_bytes=1024, status="COMPLETED",total_amount=120.0, tax_amount=10.0) # Total amount is 120, but line item + tax is 110
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    
    line_item = InvoiceLineItem(invoice_id=invoice.id, total_price=100.0, quantity=1, unit_price=100.0)
    db_session.add(line_item)
    db_session.commit()

    result = validate_line_items(db_session, invoice)
    assert result["passed"] is False
    assert "MISMATCH" in result["message"]

def test_check_duplicate_found(db_session):
    # Seed a vendor
    vendor = Vendor(name="Test Vendor for Duplicate")
    db_session.add(vendor)
    db_session.commit()
    db_session.refresh(vendor)

    # Create an existing invoice
    existing_invoice = Invoice(uploaded_by=2, vendor_id=vendor.id, file_name="test invoice", file_size_bytes=1024,invoice_number="INV-001", status="COMPLETED",total_amount=120.0, tax_amount=10.0) # Total amount is 120, but line item + tax is 110

    # existing_invoice = Invoice(invoice_number="INV-001", vendor_id=vendor.id, uploaded_at=datetime.now())
    db_session.add(existing_invoice)
    db_session.commit()
    db_session.refresh(existing_invoice)

    # Create a new invoice object with the same number (not yet in DB or with different ID)
    new_invoice = Invoice(uploaded_by=2, vendor_id=vendor.id, file_name="test invoice", file_size_bytes=1024, invoice_number="INV-001", status="COMPLETED",total_amount=120.0, tax_amount=10.0) # Total amount is 120, but line item + tax is 110

    # new_invoice = Invoice(invoice_number="INV-001", vendor_id=vendor.id)
    # We don't add new_invoice to db_session here, as check_duplicate queries the DB for existing ones.
    # If we add it, it would be the same object in the session, and the query would exclude itself.

    result = check_duplicate(new_invoice, db_session)
    assert result["passed"] is False
    assert "DUPLICATE" in result["message"]

def test_check_duplicate_unique(db_session):
    invoice = Invoice(invoice_number="UNIQUE-123", vendor_id=1) # Vendor ID 1 might not exist, but for this test, it's fine as it won't query for vendor.
    # We don't add this invoice to the session before checking for duplicates, as it's meant to be unique.

    result = check_duplicate(invoice, db_session)
    assert result["passed"] is True
    assert "is unique" in result["message"]
