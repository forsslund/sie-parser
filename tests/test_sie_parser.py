"""Tests for SIE parser.

This test suite validates the SIE parser's compliance with the SIE 4B specification
and ensures compatibility with real-world SIE files.
"""

import pytest
from io import StringIO
import sys
import os

# Add the parent directory to the path so we can import sie_parser
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sie_parser


def test_parse_simple_sie():
    """Test basic SIE parsing functionality with minimal valid file."""
    sie_content = '''#FLAGGA 1
#FORMAT PC8
#SIETYP 4
#FNAMN "Test Company AB"
#ORGNR 555555-5555
#RAR 0 20210101 20211231
#KONTO 1910 Kassa
#KTYP 1910 T
#VER A 1 20210101 "Test transaction"
{
   #TRANS 1910 {} 1000.00
}
'''
    
    file_obj = StringIO(sie_content)
    result = sie_parser.parse_sie(file_obj)
    
    assert result.company_name == "Test Company AB"
    assert result.company_id == "555555-5555"
    assert result.period_start == "20210101"
    assert result.period_end == "20211231"
    assert "1910" in result.accounts
    assert result.accounts["1910"].name == "Kassa"
    assert len(result.entries) == 1
    assert result.entries[0].amount == 1000.0


def test_account_type_detection():
    """Test BAS account plan type detection for Swedish standard accounts."""
    assert sie_parser.get_bas_account_type("1910") == sie_parser.AccountType.ASSET
    assert sie_parser.get_bas_account_type("2440") == sie_parser.AccountType.LIABILITY
    assert sie_parser.get_bas_account_type("3010") == sie_parser.AccountType.INCOME
    assert sie_parser.get_bas_account_type("4010") == sie_parser.AccountType.EXPENSE
    assert sie_parser.get_bas_account_type("8010") == sie_parser.AccountType.INCOME


def test_account_balance_properties():
    """Test that account types have correct normal balance and multiplier properties."""
    # Debit accounts (assets and expenses)
    asset_account = sie_parser.SieAccount(number="1910", name="Kassa", type=sie_parser.AccountType.ASSET)
    expense_account = sie_parser.SieAccount(number="4010", name="Kostnader", type=sie_parser.AccountType.EXPENSE)
    
    assert asset_account.normal_balance == "debit"
    assert asset_account.balance_multiplier == 1
    assert expense_account.normal_balance == "debit"
    assert expense_account.balance_multiplier == 1
    
    # Credit accounts (liabilities and income)
    liability_account = sie_parser.SieAccount(number="2610", name="Leverantörsskulder", type=sie_parser.AccountType.LIABILITY)
    income_account = sie_parser.SieAccount(number="3010", name="Försäljning", type=sie_parser.AccountType.INCOME)
    
    assert liability_account.normal_balance == "credit"
    assert liability_account.balance_multiplier == -1
    assert income_account.normal_balance == "credit"
    assert income_account.balance_multiplier == -1


def test_parse_error():
    """Test that malformed SIE content raises appropriate parse errors."""
    sie_content = '''#FLAGGA 1
#IB 0 1910 invalid_amount
'''
    
    file_obj = StringIO(sie_content)
    with pytest.raises(sie_parser.SieParseError) as exc_info:
        sie_parser.parse_sie(file_obj)
    
    assert "Line 2" in str(exc_info.value)


def test_empty_file():
    """Test that empty files are handled gracefully without errors."""
    file_obj = StringIO("")
    result = sie_parser.parse_sie(file_obj)
    
    assert result.company_name == ""
    assert len(result.accounts) == 0
    assert len(result.entries) == 0


def test_ktyp_override():
    """Test that KTYP records override BAS account types regardless of declaration order.
    
    This is critical because SIE files don't guarantee KTYP comes after KONTO records,
    so the parser must handle deferred processing.
    """
    test_file_path = os.path.join(os.path.dirname(__file__), 'test_sie4.se')
    result = sie_parser.parse_sie_file(test_file_path)
    
    # Account 1510 - KTYP before KONTO definition
    assert result.accounts['1510'].type == sie_parser.AccountType.INCOME
    
    # Account 3010 - KTYP after KONTO definition  
    assert result.accounts['3010'].type == sie_parser.AccountType.LIABILITY
    
    # Verify non-overridden accounts still follow BAS conventions
    assert result.accounts['1910'].type == sie_parser.AccountType.ASSET
    assert result.accounts['2610'].type == sie_parser.AccountType.LIABILITY


def test_voucher_scope_handling():
    """Test that transactions are only processed within voucher blocks.
    
    This prevents the bug where all transactions get associated with the first voucher
    when voucher scope isn't properly tracked.
    """
    test_file_path = os.path.join(os.path.dirname(__file__), 'test_sie4.se')
    result = sie_parser.parse_sie_file(test_file_path)
    
    # Verify we have multiple distinct vouchers
    voucher_indices = {e.voucher_index for e in result.entries if e.voucher_index}
    assert len(voucher_indices) > 1
    
    # Test specific voucher grouping
    voucher_a1_entries = [e for e in result.entries if e.voucher_index == "A1"]
    assert len(voucher_a1_entries) == 3
    
    # Verify transaction amounts within voucher
    kassa_entry = next((e for e in voucher_a1_entries if e.account_number == "1910"), None)
    assert kassa_entry is not None
    assert kassa_entry.amount == -1000.0


def test_comprehensive_file_parsing():
    """Test parsing a comprehensive SIE file with all major features.
    
    This validates the parser handles real-world complexity including metadata,
    addresses, dimensions, balances, and complex transactions.
    """
    test_file_path = os.path.join(os.path.dirname(__file__), 'test_sie4.se')
    result = sie_parser.parse_sie_file(test_file_path)
    
    # Company information
    assert result.company_name == "Testföretag AB"
    assert result.company_id == "556677-8899"
    assert result.period_start == "20240101"
    assert result.period_end == "20241231"
    
    # File metadata
    assert result.file_flag == "0"
    assert result.program == "Test SIE4 Generator"
    assert result.file_format == "PC8"
    assert result.sie_type == "4"
    assert result.currency == "SEK"
    
    # Address information
    assert result.contact_person == "Testföretag AB"
    assert result.address_line1 == "Testgatan 1"
    assert result.phone == "08-123 45 67"
    
    # Data completeness
    assert len(result.accounts) > 20
    assert len(result.entries) > 0


def test_official_sie4_example_file():
    """Test parsing the official SIE4 example file to validate real-world compatibility.
    
    This is the ultimate test - if we can parse the official example correctly,
    we should handle most real SIE files.
    """
    example_file_path = os.path.join(os.path.dirname(__file__), '..', 'SIE4 spec', 'SIE4 Exempelfil.SE')
    
    if not os.path.exists(example_file_path):
        pytest.skip("Official SIE4 example file not found")
    
    result = sie_parser.parse_sie_file(example_file_path)
    
    # Basic file validation
    assert result.company_name == "Övningsbolaget AB"
    assert result.company_id == "555555-5555"
    assert result.period_start == "20210101"
    assert result.period_end == "20211231"
    assert result.currency == "SEK"
    
    # Address information
    assert result.contact_person == "Siw Eriksson"
    assert result.address_line1 == "Box 1"
    assert result.phone == "012-34 56 78"
    
    # Data scale validation
    assert len(result.accounts) > 100
    assert len(result.entries) > 100
    assert len(result.opening_balances) > 40  # Both current and previous year
    
    # KTYP override validation (many 1xxx accounts overridden to EXPENSE)
    assert result.accounts["1060"].type == sie_parser.AccountType.EXPENSE
    assert result.accounts["1110"].type == sie_parser.AccountType.EXPENSE
    
    # SRU tax codes
    assert result.accounts["1060"].sru_code == "7201"
    assert result.accounts["1110"].sru_code == "7214"
    
    # Opening balance validation
    cash_balance = next((b for b in result.opening_balances 
                        if b.account_number == "1910" and b.period == 0), None)
    assert cash_balance is not None
    assert cash_balance.amount == 1339.00
    
    # Transaction validation
    a1_entries = [e for e in result.entries if e.voucher_index == "A1"]
    assert len(a1_entries) == 3
    
    cash_entry = next((e for e in a1_entries if e.account_number == "1910"), None)
    assert cash_entry.amount == -195.00
    assert cash_entry.description == "Kaffebröd"


def test_ver_format_parsing():
    """Test VER record parsing with various format combinations per SIE specification.
    
    VER format: #VER series verno verdate vertext regdate sign
    Tests quoted/unquoted descriptions and optional fields.
    """
    # Quoted description
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#VER A 1 20240315 "Test description" 20240316 "User1"
{
#TRANS 1910 {} 1000.00
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert result.entries[0].description == "Test description"
    assert result.entries[0].voucher_index == "A1"
    
    # Unquoted single-word description
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#VER A 2 20240315 Kaffebröd 20240316
{
#TRANS 1910 {} 500.00
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert result.entries[0].description == "Kaffebröd"
    
    # Minimal fields (no regdate, no sign)
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#VER A 4 20240315 "Minimal"
{
#TRANS 1910 {} 250.00
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert result.entries[0].description == "Minimal"
    
    # Empty description
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#VER A 5 20240315
{
#TRANS 1910 {} 100.00
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert result.entries[0].description == ""


def test_trans_object_list_parsing():
    """Test TRANS record parsing with dimension objects per SIE specification.
    
    TRANS format: #TRANS account no {object list} amount transdate transtext quantity sign
    Tests complex dimension objects like those in the official example.
    """
    # Empty object list
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#VER A 1 20240315 "Test"
{
#TRANS 1910 {} 1000.00
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert result.entries[0].account_number == "1910"
    assert result.entries[0].amount == 1000.00
    
    # Complex object list with dimension-object pairs (from official example)
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#DIM 1 "Department"
#DIM 7 "Employee"
#OBJEKT 1 "456" "Sales Dept"
#OBJEKT 7 "47" "John Doe"
#KONTO 7010 "Salaries"
#KONTO 1910 "Cash"
#VER A 567 20081216 "Cash salary"
{
#TRANS 7010 {"1" "456" "7" "47"} 13200.00
#TRANS 1910 {} -13200.00
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert len(result.entries) == 2
    
    salary_entry = next(e for e in result.entries if e.account_number == "7010")
    assert salary_entry.amount == 13200.00
    
    # TRANS without object list braces (legacy format)
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#VER A 1 20240315 "Test"
{
#TRANS 1910 1000.00
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert result.entries[0].amount == 1000.00


def test_cp437_encoding_requirement():
    """Test CP437 encoding compliance per SIE 4B specification.
    
    The specification mandates IBM PC 8-bits extended ASCII (Codepage 437).
    """
    import tempfile
    import os
    
    test_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#FNAMN "Test Company AB"
#KONTO 1910 "Kassa"
'''
    
    # Test proper CP437 encoding
    with tempfile.NamedTemporaryFile(mode='w', encoding='cp437', delete=False, suffix='.sie') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
        result = sie_parser.parse_sie_file(temp_file)
        assert result.company_name == "Test Company AB"
    finally:
        os.unlink(temp_file)
    
    # Test explicit encoding parameter override
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.sie') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
        result = sie_parser.parse_sie_file(temp_file, encoding='utf-8')
        assert result.company_name == "Test Company AB"
    finally:
        os.unlink(temp_file)


def test_specification_compliance():
    """Test compliance with key SIE 4B specification requirements.
    
    Validates voucher structure, balance requirements, and data integrity.
    """
    # FORMAT field should specify PC8
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert result.file_format == "PC8"
    
    # VER must be followed by TRANS items within braces
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#KONTO 2640 "VAT"
#KONTO 4010 "Expenses"
#VER A 1 20240315 "Test verification"
{
#TRANS 1910 {} -1000.00
#TRANS 2640 {} 200.00
#TRANS 4010 {} 800.00
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert len(result.entries) == 3
    
    # All transactions should have same voucher index
    voucher_indices = {e.voucher_index for e in result.entries}
    assert len(voucher_indices) == 1
    assert "A1" in voucher_indices
    
    # Verifications should balance (sum to zero)
    total_amount = sum(e.amount for e in result.entries)
    assert abs(total_amount) < 0.01


if __name__ == "__main__":
    pytest.main([__file__]) 