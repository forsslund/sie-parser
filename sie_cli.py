#!/usr/bin/env python3
"""
SIE CLI - Command line interface for SIE file analysis.

Provides functionality to list accounts and vouchers from SIE files
with optional CSV output format.
"""

import argparse
import csv
import sys
from collections import defaultdict
from typing import Dict, List

import sie_parser


def list_accounts(sie_data: sie_parser.SieFile, non_zero_only: bool = False, csv_output: bool = False) -> None:
    """List accounts with their balances and types."""
    
    # Calculate account balances from transactions
    account_balances: Dict[str, float] = defaultdict(float)
    for entry in sie_data.entries:
        account_balances[entry.account_number] += entry.amount
    
    # Add opening balances (use period 0 for current year)
    for balance in sie_data.opening_balances:
        if balance.period == 0:  # Current year
            account_balances[balance.account_number] += balance.amount
    
    # Prepare account data
    account_data = []
    for account_number, account in sie_data.accounts.items():
        balance = account_balances.get(account_number, 0.0)
        
        # Skip zero balance accounts if requested
        if non_zero_only and abs(balance) < 0.01:
            continue
            
        account_data.append({
            'number': account_number,
            'name': account.name,
            'type': account.type.name,
            'balance': balance,
            'normal_balance': account.normal_balance,
            'sru_code': account.sru_code or ''
        })
    
    # Sort by account number
    account_data.sort(key=lambda x: x['number'])
    
    if csv_output:
        writer = csv.DictWriter(sys.stdout, fieldnames=['number', 'name', 'type', 'balance', 'normal_balance', 'sru_code'])
        writer.writeheader()
        writer.writerows(account_data)
    else:
        print(f"{'Account':<10} {'Name':<30} {'Type':<10} {'Balance':<15} {'Normal':<8} {'SRU':<8}")
        print("-" * 85)
        for account in account_data:
            print(f"{account['number']:<10} {account['name']:<30} {account['type']:<10} "
                  f"{account['balance']:>15.2f} {account['normal_balance']:<8} {account['sru_code']:<8}")
        
        print(f"\nTotal accounts: {len(account_data)}")


def show_summary(sie_data: sie_parser.SieFile, csv_output: bool = False) -> None:
    """Show a comprehensive summary of the SIE file."""
    
    # Calculate account balances to count non-zero accounts
    account_balances: Dict[str, float] = defaultdict(float)
    for entry in sie_data.entries:
        account_balances[entry.account_number] += entry.amount
    
    # Add opening balances (use period 0 for current year)
    for balance in sie_data.opening_balances:
        if balance.period == 0:  # Current year
            account_balances[balance.account_number] += balance.amount
    
    # Count non-zero accounts
    non_zero_accounts = sum(1 for balance in account_balances.values() if abs(balance) >= 0.01)
    
    # Count vouchers
    vouchers = set()
    for entry in sie_data.entries:
        if entry.voucher_index:
            vouchers.add(entry.voucher_index)
    
    # Count balanced vouchers
    voucher_balances: Dict[str, float] = defaultdict(float)
    for entry in sie_data.entries:
        if entry.voucher_index:
            voucher_balances[entry.voucher_index] += entry.amount
    
    balanced_vouchers = sum(1 for balance in voucher_balances.values() if abs(balance) < 0.01)
    
    # Prepare summary data
    summary_data = {
        'company_name': sie_data.company_name,
        'company_id': sie_data.company_id,
        'period_start': sie_data.period_start,
        'period_end': sie_data.period_end,
        'file_format': sie_data.file_format,
        'sie_type': sie_data.sie_type,
        'currency': sie_data.currency,
        'program': sie_data.program,
        'generation_date': sie_data.generation_date,
        'contact_person': sie_data.contact_person,
        'address_line1': sie_data.address_line1,
        'address_line2': sie_data.address_line2,
        'phone': sie_data.phone,
        'total_accounts': len(sie_data.accounts),
        'non_zero_accounts': non_zero_accounts,
        'total_entries': len(sie_data.entries),
        'total_vouchers': len(vouchers),
        'balanced_vouchers': balanced_vouchers,
        'opening_balances': len(sie_data.opening_balances),
        'closing_balances': len(sie_data.closing_balances),
        'dimensions': len(sie_data.dimensions),
        'objects': len(sie_data.objects)
    }
    
    if csv_output:
        writer = csv.DictWriter(sys.stdout, fieldnames=summary_data.keys())
        writer.writeheader()
        writer.writerow(summary_data)
    else:
        print("SIE File Summary")
        print("=" * 50)
        print()
        
        # Company Information
        print("Company Information:")
        print(f"  Name: {summary_data['company_name']}")
        print(f"  ID: {summary_data['company_id']}")
        print(f"  Period: {summary_data['period_start']} - {summary_data['period_end']}")
        if summary_data['currency']:
            print(f"  Currency: {summary_data['currency']}")
        print()
        
        # Contact Information
        if any([summary_data['contact_person'], summary_data['address_line1'], summary_data['phone']]):
            print("Contact Information:")
            if summary_data['contact_person']:
                print(f"  Contact: {summary_data['contact_person']}")
            if summary_data['address_line1']:
                print(f"  Address: {summary_data['address_line1']}")
            if summary_data['address_line2']:
                print(f"           {summary_data['address_line2']}")
            if summary_data['phone']:
                print(f"  Phone: {summary_data['phone']}")
            print()
        
        # File Information
        print("File Information:")
        print(f"  Format: {summary_data['file_format']}")
        print(f"  SIE Type: {summary_data['sie_type']}")
        if summary_data['program']:
            print(f"  Generated by: {summary_data['program']}")
        if summary_data['generation_date']:
            print(f"  Generated on: {summary_data['generation_date']}")
        print()
        
        # Data Summary
        print("Data Summary:")
        print(f"  Total Accounts: {summary_data['total_accounts']}")
        print(f"  Non-zero Accounts: {summary_data['non_zero_accounts']}")
        print(f"  Total Transactions: {summary_data['total_entries']}")
        print(f"  Total Vouchers: {summary_data['total_vouchers']}")
        print(f"  Balanced Vouchers: {summary_data['balanced_vouchers']}/{summary_data['total_vouchers']}")
        
        if summary_data['opening_balances'] > 0:
            print(f"  Opening Balances: {summary_data['opening_balances']}")
        if summary_data['closing_balances'] > 0:
            print(f"  Closing Balances: {summary_data['closing_balances']}")
        if summary_data['dimensions'] > 0:
            print(f"  Dimensions: {summary_data['dimensions']}")
        if summary_data['objects'] > 0:
            print(f"  Dimension Objects: {summary_data['objects']}")


def list_vouchers(sie_data: sie_parser.SieFile, csv_output: bool = False) -> None:
    """List all vouchers with their transaction summaries."""
    
    # Group transactions by voucher
    vouchers: Dict[str, List[sie_parser.SieEntry]] = defaultdict(list)
    for entry in sie_data.entries:
        if entry.voucher_index:
            vouchers[entry.voucher_index].append(entry)
    
    # Prepare voucher data
    voucher_data = []
    for voucher_index, entries in vouchers.items():
        total_amount = sum(abs(entry.amount) for entry in entries)
        balance = sum(entry.amount for entry in entries)
        
        # Get voucher description from first entry
        description = entries[0].description if entries else ""
        
        # Get voucher date from first entry
        date = entries[0].date if entries and entries[0].date else ""
        
        voucher_data.append({
            'voucher': voucher_index,
            'date': date,
            'description': description,
            'transactions': len(entries),
            'total_amount': total_amount,
            'balance': balance,
            'balanced': 'Yes' if abs(balance) < 0.01 else 'No'
        })
    
    # Sort by voucher index
    voucher_data.sort(key=lambda x: x['voucher'])
    
    if csv_output:
        writer = csv.DictWriter(sys.stdout, fieldnames=['voucher', 'date', 'description', 'transactions', 'total_amount', 'balance', 'balanced'])
        writer.writeheader()
        writer.writerows(voucher_data)
    else:
        print(f"{'Voucher':<10} {'Date':<10} {'Description':<25} {'Trans':<6} {'Amount':<12} {'Balance':<12} {'Bal?':<5}")
        print("-" * 85)
        for voucher in voucher_data:
            print(f"{voucher['voucher']:<10} {voucher['date']:<10} {voucher['description']:<25} "
                  f"{voucher['transactions']:>6} {voucher['total_amount']:>12.2f} "
                  f"{voucher['balance']:>12.2f} {voucher['balanced']:<5}")
        
        print(f"\nTotal vouchers: {len(voucher_data)}")
        balanced_count = sum(1 for v in voucher_data if v['balanced'] == 'Yes')
        print(f"Balanced vouchers: {balanced_count}/{len(voucher_data)}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SIE file analyzer - List accounts and vouchers from Swedish SIE accounting files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s summary file.sie                    # Show file summary
  %(prog)s accounts file.sie                   # List all accounts
  %(prog)s accounts file.sie --non-zero        # List only accounts with balances
  %(prog)s accounts file.sie --csv             # Output as CSV
  %(prog)s vouchers file.sie                   # List all vouchers
  %(prog)s vouchers file.sie --csv             # Output vouchers as CSV
        """
    )
    
    parser.add_argument('command', choices=['accounts', 'vouchers', 'summary'], 
                       help='Command to execute')
    parser.add_argument('file', help='SIE file to analyze')
    parser.add_argument('--csv', action='store_true', 
                       help='Output in CSV format')
    parser.add_argument('--non-zero', action='store_true',
                       help='For accounts: only show accounts with non-zero balances')
    parser.add_argument('--encoding', default='cp437',
                       help='File encoding (default: cp437 per SIE specification)')
    
    args = parser.parse_args()
    
    try:
        # Parse the SIE file
        sie_data = sie_parser.parse_sie_file(args.file, encoding=args.encoding)
        
        # Execute the requested command
        if args.command == 'accounts':
            list_accounts(sie_data, non_zero_only=args.non_zero, csv_output=args.csv)
        elif args.command == 'vouchers':
            list_vouchers(sie_data, csv_output=args.csv)
        elif args.command == 'summary':
            show_summary(sie_data, csv_output=args.csv)
            
    except FileNotFoundError:
        print(f"Error: File '{args.file}' not found", file=sys.stderr)
        sys.exit(1)
    except sie_parser.SieParseError as e:
        print(f"Error parsing SIE file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 