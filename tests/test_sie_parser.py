"""Tests for SIE parser."""

import pytest
from io import StringIO
import sys
import os

# Add the parent directory to the path so we can import sie_parser
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sie_parser


def test_parse_simple_sie():
    """Test parsing a simple SIE file."""
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
    """Test BAS account type detection."""
    assert sie_parser.get_bas_account_type("1910") == sie_parser.AccountType.ASSET
    assert sie_parser.get_bas_account_type("2440") == sie_parser.AccountType.LIABILITY
    assert sie_parser.get_bas_account_type("3010") == sie_parser.AccountType.INCOME
    assert sie_parser.get_bas_account_type("4010") == sie_parser.AccountType.EXPENSE
    assert sie_parser.get_bas_account_type("8010") == sie_parser.AccountType.INCOME


def test_account_balance_properties():
    """Test account balance properties."""
    # Test debit accounts
    asset_account = sie_parser.SieAccount(number="1910", name="Kassa", type=sie_parser.AccountType.ASSET)
    expense_account = sie_parser.SieAccount(number="4010", name="Kostnader", type=sie_parser.AccountType.EXPENSE)
    
    assert asset_account.normal_balance == "debit"
    assert asset_account.balance_multiplier == 1
    assert expense_account.normal_balance == "debit"
    assert expense_account.balance_multiplier == 1
    
    # Test credit accounts
    liability_account = sie_parser.SieAccount(number="2610", name="Leverantörsskulder", type=sie_parser.AccountType.LIABILITY)
    income_account = sie_parser.SieAccount(number="3010", name="Försäljning", type=sie_parser.AccountType.INCOME)
    
    assert liability_account.normal_balance == "credit"
    assert liability_account.balance_multiplier == -1
    assert income_account.normal_balance == "credit"
    assert income_account.balance_multiplier == -1


def test_parse_error():
    """Test that parse errors are raised correctly."""
    sie_content = '''#FLAGGA 1
#IB 0 1910 invalid_amount
'''
    
    file_obj = StringIO(sie_content)
    with pytest.raises(sie_parser.SieParseError) as exc_info:
        sie_parser.parse_sie(file_obj)
    
    assert "Line 2" in str(exc_info.value)


def test_empty_file():
    """Test parsing an empty file."""
    file_obj = StringIO("")
    result = sie_parser.parse_sie(file_obj)
    
    assert result.company_name == ""
    assert len(result.accounts) == 0
    assert len(result.entries) == 0


def test_ktyp_override():
    """Test that KTYP entries correctly override account types regardless of order."""
    # Load the test SIE file
    test_file_path = os.path.join(os.path.dirname(__file__), 'test_sie4.se')
    result = sie_parser.parse_sie_file(test_file_path)
    
    # Test account 1510 - KTYP before definition
    assert result.accounts['1510'].type == sie_parser.AccountType.INCOME, \
        "Account 1510 should be Income due to KTYP override, not Asset as per BAS"
    
    # Test account 3010 - KTYP after definition
    assert result.accounts['3010'].type == sie_parser.AccountType.LIABILITY, \
        "Account 3010 should be Liability due to KTYP override, not Income as per BAS"
    
    # Verify that other accounts still follow BAS conventions
    assert result.accounts['1910'].type == sie_parser.AccountType.ASSET, \
        "Account 1910 should follow BAS convention and be Asset"
    assert result.accounts['2610'].type == sie_parser.AccountType.LIABILITY, \
        "Account 2610 should follow BAS convention and be Liability"
    assert result.accounts['8010'].type == sie_parser.AccountType.INCOME, \
        "Account 8010 should follow BAS convention and be Income"


def test_account_balance_multipliers():
    """Test that accounts have correct balance multipliers based on their type."""
    # Load the test SIE file
    test_file_path = os.path.join(os.path.dirname(__file__), 'test_sie4.se')
    result = sie_parser.parse_sie_file(test_file_path)
    
    # Test balance multipliers for each account type
    # Asset accounts (1xxx) should have multiplier 1 (debit)
    assert result.accounts['1910'].balance_multiplier == 1, \
        "Asset account 1910 should have balance_multiplier 1 (debit)"
    assert result.accounts['1910'].normal_balance == "debit", \
        "Asset account 1910 should have normal_balance 'debit'"
    
    # Liability accounts (2xxx) should have multiplier -1 (credit)
    assert result.accounts['2610'].balance_multiplier == -1, \
        "Liability account 2610 should have balance_multiplier -1 (credit)"
    assert result.accounts['2610'].normal_balance == "credit", \
        "Liability account 2610 should have normal_balance 'credit'"
    
    # Revenue accounts (3xxx) should have multiplier -1 (credit) - but this one is overridden by KTYP
    assert result.accounts['3010'].balance_multiplier == -1, \
        "Revenue account 3010 should have balance_multiplier -1 (credit)"
    assert result.accounts['3010'].normal_balance == "credit", \
        "Revenue account 3010 should have normal_balance 'credit'"
    
    # Cost accounts (4xxx) should have multiplier 1 (debit)
    assert result.accounts['4010'].balance_multiplier == 1, \
        "Cost account 4010 should have balance_multiplier 1 (debit)"
    assert result.accounts['4010'].normal_balance == "debit", \
        "Cost account 4010 should have normal_balance 'debit'"
    
    # Financial income accounts (8xxx) should have multiplier -1 (credit)
    assert result.accounts['8010'].balance_multiplier == -1, \
        "Financial income account 8010 should have balance_multiplier -1 (credit)"
    assert result.accounts['8010'].normal_balance == "credit", \
        "Financial income account 8010 should have normal_balance 'credit'"
    
    # Financial expense accounts (8xxx) should have multiplier 1 (debit)
    assert result.accounts['8020'].balance_multiplier == 1, \
        "Financial expense account 8020 should have balance_multiplier 1 (debit)"
    assert result.accounts['8020'].normal_balance == "debit", \
        "Financial expense account 8020 should have normal_balance 'debit'"
    
    # Test that KTYP overrides affect both type and balance multiplier
    assert result.accounts['1510'].balance_multiplier == -1, \
        "Account 1510 should have balance_multiplier -1 since KTYP overrides its type to Income (credit account)"
    assert result.accounts['1510'].normal_balance == "credit", \
        "Account 1510 should have normal_balance 'credit' since KTYP overrides its type to Income"


def test_comprehensive_sie_parsing():
    """Test parsing a comprehensive SIE file with all features."""
    test_file_path = os.path.join(os.path.dirname(__file__), 'test_sie4.se')
    result = sie_parser.parse_sie_file(test_file_path)
    
    # Test company information
    assert result.company_name == "Testföretag AB"
    assert result.company_id == "556677-8899"
    assert result.period_start == "20240101"
    assert result.period_end == "20241231"
    
    # Test file metadata
    assert result.file_flag == "0"
    assert result.program == "Test SIE4 Generator"
    assert result.file_format == "PC8"
    assert result.generation_date == "20240315"
    assert result.sie_type == "4"
    assert result.account_plan_type == "EUBAS97"
    assert result.currency == "SEK"
    assert result.tax_year == "2024"
    
    # Test address information
    assert result.contact_person == "Testföretag AB"
    assert result.address_line1 == "Testgatan 1"
    assert result.address_line2 == "123 45 Stockholm"
    assert result.phone == "08-123 45 67"
    
    # Test that we have the expected number of accounts
    assert len(result.accounts) > 20
    
    # Test that we have transactions
    assert len(result.entries) > 0
    
    # Test specific account names
    assert result.accounts['1010'].name == "Utvecklingsutgifter"
    assert result.accounts['1920'].name == "Bank"
    assert result.accounts['3010'].name == "Försäljning inom Sverige (Revenue according to BAS but Liability since KTYP S)"
    
    # Test voucher parsing
    voucher_a1_entries = [e for e in result.entries if e.voucher_index == "A1"]
    assert len(voucher_a1_entries) == 3
    
    # Test transaction amounts
    kassa_entry = next((e for e in voucher_a1_entries if e.account_number == "1910"), None)
    assert kassa_entry is not None
    assert kassa_entry.amount == -1000.0
    assert kassa_entry.description == "Testverifikation 1"


def test_official_sie4_example_file():
    """Test parsing the official SIE4 example file to validate real-world compatibility."""
    example_file_path = os.path.join(os.path.dirname(__file__), '..', 'SIE4 spec', 'SIE4 Exempelfil.SE')
    
    # Skip test if example file doesn't exist
    if not os.path.exists(example_file_path):
        pytest.skip("Official SIE4 example file not found")
    
    result = sie_parser.parse_sie_file(example_file_path)
    
    # Test basic file metadata
    assert result.company_name == "Övningsbolaget AB"
    assert result.company_id == "555555-5555"
    assert result.period_start == "20210101"
    assert result.period_end == "20211231"
    assert result.file_flag == "1"
    assert result.sie_type == "4"
    assert result.currency == "SEK"
    assert result.account_plan_type == "EUBAS97"
    
    # Test address information
    assert result.contact_person == "Siw Eriksson"
    assert result.address_line1 == "Box 1"
    assert result.address_line2 == "123 45 STORSTAD"
    assert result.phone == "012-34 56 78"
    
    # Test that we have a substantial number of accounts (the file has many)
    assert len(result.accounts) > 100, f"Expected >100 accounts, got {len(result.accounts)}"
    
    # Test specific accounts with KTYP overrides
    # Many 1xxx accounts are overridden to EXPENSE (T) instead of default ASSET (K)
    assert "1060" in result.accounts
    assert result.accounts["1060"].name == "Hyresrätt"
    assert result.accounts["1060"].type == sie_parser.AccountType.EXPENSE  # KTYP override
    
    assert "1110" in result.accounts
    assert result.accounts["1110"].name == "Byggnader"
    assert result.accounts["1110"].type == sie_parser.AccountType.EXPENSE  # KTYP override
    
    # Test SRU codes
    assert result.accounts["1060"].sru_code == "7201"
    assert result.accounts["1110"].sru_code == "7214"
    
    # Test that we have opening balances for both current (0) and previous (-1) year
    current_year_balances = [b for b in result.opening_balances if b.period == 0]
    previous_year_balances = [b for b in result.opening_balances if b.period == -1]
    
    assert len(current_year_balances) > 20, f"Expected >20 current year balances, got {len(current_year_balances)}"
    assert len(previous_year_balances) > 20, f"Expected >20 previous year balances, got {len(previous_year_balances)}"
    
    # Test specific opening balances
    cash_balance = next((b for b in current_year_balances if b.account_number == "1910"), None)
    assert cash_balance is not None, "Cash account (1910) should have opening balance"
    assert cash_balance.amount == 1339.00
    
    # Test that we have transactions
    assert len(result.entries) > 100, f"Expected >100 transactions, got {len(result.entries)}"
    
    # Test specific voucher transactions
    # Voucher A1 should have transactions for accounts 1910, 2641, 7690
    a1_entries = [e for e in result.entries if e.voucher_index == "A1"]
    assert len(a1_entries) == 3, f"Voucher A1 should have 3 transactions, got {len(a1_entries)}"
    
    # Check specific amounts in voucher A1
    cash_entry = next((e for e in a1_entries if e.account_number == "1910"), None)
    assert cash_entry is not None
    assert cash_entry.amount == -195.00
    assert cash_entry.description == "Kaffebröd"
    
    # Test voucher with multiple series (A and B series should exist)
    a_series_entries = [e for e in result.entries if e.voucher_index and e.voucher_index.startswith("A")]
    b_series_entries = [e for e in result.entries if e.voucher_index and e.voucher_index.startswith("B")]
    
    assert len(a_series_entries) > 50, f"Expected >50 A-series entries, got {len(a_series_entries)}"
    assert len(b_series_entries) > 50, f"Expected >50 B-series entries, got {len(b_series_entries)}"
    
    # Test account type classification with real accounts
    # Account 1400 (Lager/inventory) is overridden by KTYP to be EXPENSE in the official file
    if "1400" in result.accounts:  # Lager (inventory) - overridden by KTYP T
        assert result.accounts["1400"].type == sie_parser.AccountType.EXPENSE  # KTYP override to T
    
    # Liability accounts
    if "2091" in result.accounts:  # Balanserad vinst/förlust
        assert result.accounts["2091"].type == sie_parser.AccountType.LIABILITY
    
    # Test balance multipliers work correctly with real data
    if "1910" in result.accounts:  # Cash - should be debit normal balance
        assert result.accounts["1910"].normal_balance == "debit"
        assert result.accounts["1910"].balance_multiplier == 1
    
    if "2091" in result.accounts:  # Equity - should be credit normal balance
        assert result.accounts["2091"].normal_balance == "credit"
        assert result.accounts["2091"].balance_multiplier == -1


def test_ver_format_parsing():
    """Test parsing of VER records with different formats according to SIE specification."""
    # Test VER format: #VER series verno verdate vertext regdate sign
    
    # Test 1: Basic VER with quoted description
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
    assert len(result.entries) == 1
    assert result.entries[0].description == "Test description"
    assert result.entries[0].voucher_index == "A1"
    
    # Test 2: VER with unquoted single-word description
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
    assert len(result.entries) == 1
    assert result.entries[0].description == "Kaffebröd"
    assert result.entries[0].voucher_index == "A2"
    
    # Test 3: VER with multi-word quoted description
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#VER A 3 20240315 "Multi word description" 20240316
{
#TRANS 1910 {} 750.00
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert len(result.entries) == 1
    assert result.entries[0].description == "Multi word description"
    assert result.entries[0].voucher_index == "A3"
    
    # Test 4: VER with minimal fields (no regdate, no sign)
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
    assert len(result.entries) == 1
    assert result.entries[0].description == "Minimal"
    assert result.entries[0].voucher_index == "A4"
    
    # Test 5: VER with empty description
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
    assert len(result.entries) == 1
    assert result.entries[0].description == ""
    assert result.entries[0].voucher_index == "A5"


def test_trans_object_list_parsing():
    """Test parsing of TRANS records with object lists according to SIE specification."""
    # Test TRANS format: #TRANS account no {object list} amount transdate transtext quantity sign
    
    # Test 1: Empty object list
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
    assert len(result.entries) == 1
    assert result.entries[0].account_number == "1910"
    assert result.entries[0].amount == 1000.00
    
    # Test 2: Simple object list with dimension-object pairs
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
    
    # First transaction should have the complex object list
    salary_entry = next(e for e in result.entries if e.account_number == "7010")
    assert salary_entry.amount == 13200.00
    assert salary_entry.description == "Cash salary"
    
    # Second transaction should have empty object list
    cash_entry = next(e for e in result.entries if e.account_number == "1910")
    assert cash_entry.amount == -13200.00
    
    # Test 3: TRANS with additional optional fields
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#VER A 1 20240315 "Test"
{
#TRANS 1910 {} 1000.00 20240315 "Transaction text" 10.5 "User1"
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert len(result.entries) == 1
    assert result.entries[0].account_number == "1910"
    assert result.entries[0].amount == 1000.00
    
    # Test 4: TRANS without object list braces
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
    assert len(result.entries) == 1
    assert result.entries[0].account_number == "1910"
    assert result.entries[0].amount == 1000.00


def test_cp437_encoding_requirement():
    """Test that the parser uses CP437 encoding as per SIE specification."""
    import tempfile
    import os
    
    # Create a test file with basic SIE content
    test_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#FNAMN "Test Company AB"
#KONTO 1910 "Kassa"
'''
    
    # Test 1: File with proper CP437 encoding should work
    with tempfile.NamedTemporaryFile(mode='w', encoding='cp437', delete=False, suffix='.sie') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
        result = sie_parser.parse_sie_file(temp_file)
        assert result.company_name == "Test Company AB"
        assert "1910" in result.accounts
    finally:
        os.unlink(temp_file)
    
    # Test 2: Test that explicit encoding parameter works
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.sie') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
        # This should work when we explicitly specify UTF-8
        result = sie_parser.parse_sie_file(temp_file, encoding='utf-8')
        assert result.company_name == "Test Company AB"
        
        # Test that default encoding is CP437 (this should also work for basic ASCII content)
        result = sie_parser.parse_sie_file(temp_file)  # Uses default CP437
        assert result.company_name == "Test Company AB"
    finally:
        os.unlink(temp_file)


def test_specification_compliance():
    """Test compliance with specific SIE 4B specification requirements."""
    
    # Test 1: FORMAT field should specify PC8
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert result.file_format == "PC8"
    
    # Test 2: VER must be followed by TRANS items within braces
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#KONTO 2640 "VAT"
#VER A 1 20240315 "Test verification"
{
#TRANS 1910 {} -1000.00
#TRANS 2640 {} 200.00
#TRANS 4010 {} 800.00
}
'''
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert len(result.entries) == 3
    
    # Verify that all transactions have the same voucher index
    voucher_indices = {e.voucher_index for e in result.entries}
    assert len(voucher_indices) == 1
    assert "A1" in voucher_indices
    
    # Test 3: Verifications should balance (sum to zero)
    total_amount = sum(e.amount for e in result.entries)
    assert abs(total_amount) < 0.01  # Allow for floating point precision
    
    # Test 4: Account numbers should be numeric (as per specification)
    sie_content = '''#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#KONTO 1910 "Kassa"
#KONTO ABC "Invalid"  # Non-numeric account number
'''
    # This should still parse but the account type detection might default
    result = sie_parser.parse_sie(StringIO(sie_content))
    assert "1910" in result.accounts
    assert "ABC" in result.accounts


if __name__ == "__main__":
    pytest.main([__file__]) 