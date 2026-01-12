#!/usr/bin/env python3
"""Test PSALDO parsing functionality."""

from sie_parser import parse_sie
from io import StringIO

def test_psaldo_parsing():
    """Test that PSALDO records are parsed correctly."""
    sie_content = """#FLAGGA 0
#PSALDO 0 202511 3230 {} -99334.05 0
#PSALDO 0 202511 3230 {1 "CS"} -65000 0
#PSALDO 0 202511 3230 {1 "SALE"} -34334.05 0
#PSALDO 0 202511 3230 {6 "CYBE"} -65000 0
"""

    sie = parse_sie(StringIO(sie_content))

    print(f"Parsed {len(sie.period_balances)} PSALDO records")
    assert len(sie.period_balances) == 4, f"Expected 4 PSALDO records, got {len(sie.period_balances)}"

    # Test first record (no dimensions)
    pb1 = sie.period_balances[0]
    print(f"\nRecord 1:")
    print(f"  Account: {pb1.account_number}")
    print(f"  Period: {pb1.period}")
    print(f"  Year Index: {pb1.year_index}")
    print(f"  Amount: {pb1.amount}")
    print(f"  Dimensions: {pb1.dimensions}")

    assert pb1.account_number == "3230"
    assert pb1.period == "202511"
    assert pb1.year_index == 0
    assert pb1.amount == -99334.05
    assert pb1.dimensions == {}

    # Test second record (with dimension)
    pb2 = sie.period_balances[1]
    print(f"\nRecord 2:")
    print(f"  Account: {pb2.account_number}")
    print(f"  Period: {pb2.period}")
    print(f"  Dimensions: {pb2.dimensions}")
    print(f"  Amount: {pb2.amount}")

    assert pb2.account_number == "3230"
    assert pb2.dimensions == {"1": "CS"}
    assert pb2.amount == -65000

    # Test third record
    pb3 = sie.period_balances[2]
    print(f"\nRecord 3:")
    print(f"  Dimensions: {pb3.dimensions}")
    print(f"  Amount: {pb3.amount}")
    assert pb3.dimensions == {"1": "SALE"}
    assert pb3.amount == -34334.05

    # Test fourth record
    pb4 = sie.period_balances[3]
    print(f"\nRecord 4:")
    print(f"  Dimensions: {pb4.dimensions}")
    print(f"  Amount: {pb4.amount}")
    assert pb4.dimensions == {"6": "CYBE"}
    assert pb4.amount == -65000

    print("\n✓ All PSALDO parsing tests passed!")

if __name__ == "__main__":
    test_psaldo_parsing()
