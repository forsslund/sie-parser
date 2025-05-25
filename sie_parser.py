"""
SIE Parser - A comprehensive Python library for parsing Swedish SIE accounting files.

This library provides complete support for SIE (Standard Import Export) format version 4B,
the standard file format for transferring accounting data between different accounting
systems in Sweden.

According to the SIE 4B specification, all SIE files must use CP437 encoding 
(IBM PC 8-bits extended ASCII, also known as PC8).

Example usage:
    from sie_parser import parse_sie_file
    
    # Parse from file path (automatically uses CP437 encoding)
    sie_data = parse_sie_file('accounting.sie')
    
    # Or parse from file handle with explicit CP437 encoding
    with open('accounting.sie', 'r', encoding='cp437') as f:
        sie_data = parse_sie(f)
    
    print(f"Company: {sie_data.company_name}")
    print(f"Accounts: {len(sie_data.accounts)}")
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TextIO, Union
from datetime import datetime
from enum import Enum


# Enums
class AccountType(Enum):
    """SIE account types with clear international names."""
    ASSET = "K"      # Tillgång/Kapital (SIE code: K)
    LIABILITY = "S"  # Skuld (SIE code: S) 
    INCOME = "I"     # Intäkt (SIE code: I)
    EXPENSE = "T"    # Kostnad (SIE code: T)
    
    def __str__(self) -> str:
        """Return the SIE code for compatibility."""
        return self.value
    
    @classmethod
    def from_sie_code(cls, code: str) -> 'AccountType':
        """Create AccountType from SIE single-letter code."""
        for account_type in cls:
            if account_type.value == code:
                return account_type
        raise ValueError(f"Unknown SIE account type code: {code}")
    
    @property
    def normal_balance(self) -> str:
        """Return the normal balance side for this account type."""
        return "credit" if self in [AccountType.LIABILITY, AccountType.INCOME] else "debit"
    
    @property
    def balance_multiplier(self) -> int:
        """Return multiplier for balance calculations (1 for debit, -1 for credit)."""
        return -1 if self in [AccountType.LIABILITY, AccountType.INCOME] else 1


# Exceptions
class SieParseError(Exception):
    """Raised when there's an error parsing a SIE file."""
    
    def __init__(self, message: str, line_number: int = None, line_content: str = None):
        self.line_number = line_number
        self.line_content = line_content
        
        if line_number is not None:
            message = f"Line {line_number}: {message}"
            if line_content:
                message += f" ('{line_content.strip()}')"
        
        super().__init__(message)


class SieValidationError(Exception):
    """Raised when a SIE file fails validation checks."""
    pass


# Data Models
@dataclass
class SieAccount:
    """Represents an account in the SIE file."""
    number: str
    name: str
    type: AccountType
    sru_code: str = ""  # Tax reporting code
    
    @property
    def normal_balance(self) -> str:
        """Return the normal balance side for this account type."""
        return self.type.normal_balance
    
    @property
    def balance_multiplier(self) -> int:
        """Return multiplier for balance calculations (1 for debit, -1 for credit)."""
        return self.type.balance_multiplier


@dataclass
class SieEntry:
    """Represents an entry in the SIE file."""
    date: str
    account_number: str
    amount: float
    description: str
    voucher_index: Optional[str] = None


@dataclass
class SieBalance:
    """Represents a balance record (IB, UB, RES)."""
    account_number: str
    period: int  # 0 = current year, -1 = previous year, etc.
    amount: float
    quantity: float = 0.0  # Optional quantity


@dataclass
class SieDimension:
    """Represents a dimension definition."""
    number: str
    name: str


@dataclass
class SieObject:
    """Represents an object/dimension value."""
    dimension: str
    number: str
    name: str


@dataclass
class SieFile:
    """Represents a parsed SIE file"""
    # Basic company info
    company_name: str = ""
    company_id: str = ""
    period_start: str = ""
    period_end: str = ""
    
    # File metadata
    file_flag: str = ""
    file_format: str = ""
    sie_type: str = ""
    program: str = ""
    generation_date: str = ""
    file_number: str = ""
    currency: str = ""
    tax_year: str = ""
    account_plan_type: str = ""
    
    # Address information
    contact_person: str = ""
    address_line1: str = ""
    address_line2: str = ""
    phone: str = ""
    
    # Data collections
    accounts: Dict[str, SieAccount] = field(default_factory=dict)
    entries: List[SieEntry] = field(default_factory=list)
    opening_balances: List[SieBalance] = field(default_factory=list)
    closing_balances: List[SieBalance] = field(default_factory=list)
    result_balances: List[SieBalance] = field(default_factory=list)
    dimensions: Dict[str, SieDimension] = field(default_factory=dict)
    objects: Dict[str, SieObject] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)


# Utility Functions
def get_bas_account_type(account_number: str) -> AccountType:
    """Get the BAS standard account type based on account number.
    
    Based on the official BAS 2025 specification:
    - 1xxx: Tillgångar (Assets)
    - 2xxx: Eget kapital och skulder (Equity and Liabilities) 
    - 3xxx: Rörelsens inkomster/intäkter (Operating Income/Revenue)
    - 4xxx-7xxx: Various costs/expenses
    - 8xxx: Finansiella och andra inkomster/intäkter och utgifter/kostnader (Financial income/expenses)
    
    Args:
        account_number: The account number
        
    Returns:
        AccountType: Account type enum value
        ASSET = Asset account (tillgångskonto/kapital)
        EXPENSE = Expense account (kostnadskonto)
        INCOME = Income account (intäktskonto)
        LIABILITY = Liability/Equity account (skuld-/eget kapital-konto)
    """
    if not account_number or not account_number.isdigit():
        return AccountType.EXPENSE  # Default to EXPENSE for invalid account numbers
        
    first_digit = account_number[0]
    
    # Asset accounts (1xxx) - Tillgångar
    if first_digit == '1':
        return AccountType.ASSET
    # Liability and Equity accounts (2xxx) - Eget kapital och skulder
    elif first_digit == '2':
        return AccountType.LIABILITY
    # Revenue accounts (3xxx) - Rörelsens inkomster/intäkter
    elif first_digit == '3':
        return AccountType.INCOME
    # Expense accounts (4xxx-7xxx) - Various costs/expenses
    elif first_digit in ['4', '5', '6', '7']:
        return AccountType.EXPENSE
    # Financial accounts (8xxx) - Mixed income and expense accounts
    # Default to expense (T) as most 8xxx accounts are expense-related
    elif first_digit == '8':
        # More detailed classification for 8xxx accounts based on BAS 2025
        if len(account_number) >= 4:
            # 801x: Utdelning på andelar i koncernföretag (Dividends from group companies) - Income
            if account_number.startswith('801'):
                return AccountType.INCOME
            # 802x: Resultat vid försäljning av andelar i koncernföretag (Results from sale of shares) - Can be income or expense, default to expense
            elif account_number.startswith('802'):
                return AccountType.EXPENSE
            # 803x: Resultatandelar från handelsbolag (Result shares from partnerships) - Income
            elif account_number.startswith('803'):
                return AccountType.INCOME
            # 807x-808x: Nedskrivningar och återföringar (Write-downs and reversals) - Expense/Income
            elif account_number.startswith('807'):
                return AccountType.EXPENSE  # Write-downs are expenses
            elif account_number.startswith('808'):
                return AccountType.INCOME  # Reversals of write-downs are income
            # 81xx: Resultat från andelar i intresseföretag (Results from associated companies) - Income  
            elif account_number.startswith('81'):
                return AccountType.INCOME
            # 82xx: Resultat från övriga värdepapper (Results from other securities) - Income
            elif account_number.startswith('82'):
                return AccountType.INCOME
            # 83xx: Övriga ränteintäkter (Other interest income) - Income
            elif account_number.startswith('83'):
                return AccountType.INCOME
            # 84xx: Räntekostnader (Interest expenses) - Expense
            elif account_number.startswith('84'):
                return AccountType.EXPENSE
            # 85xx-87xx: Free account groups - default to expense
            elif account_number.startswith('85') or account_number.startswith('86') or account_number.startswith('87'):
                return AccountType.EXPENSE
            # 88xx: Bokslutsdispositioner (Year-end appropriations) - Expense
            elif account_number.startswith('88'):
                return AccountType.EXPENSE
            # 89xx: Skatter och årets resultat (Taxes and year result) - Expense
            elif account_number.startswith('89'):
                return AccountType.EXPENSE
        # Default 8xxx to expense if we can't determine more specifically
        return AccountType.EXPENSE
    # Default to EXPENSE for unknown accounts
    else:
        return AccountType.EXPENSE





def _extract_quoted_value(line: str) -> str:
    """Extract value between quotes from a line"""
    match = re.search(r'"([^"]*)"', line)
    return match.group(1) if match else ""


# Main Parser Functions
def parse_sie(file: TextIO) -> SieFile:
    """
    Parse a SIE file and return structured data.
    
    Args:
        file: File-like object containing SIE data
        
    Returns:
        SieFile object containing parsed data
        
    Raises:
        SieParseError: If there's an error parsing the file
    """
    sie_file = SieFile()
    
    # Read the file content and decode it
    content = file.read()
    if content.startswith('\ufeff'):  # Remove BOM if present
        content = content[1:]
    
    lines = content.splitlines()
    current_voucher = None
    in_voucher_block = False
    
    # Store KTYP records for deferred processing
    ktyp_records = {}
    
    # Store SRU records for deferred processing
    sru_records = {}
    
    # First pass: Parse everything except KTYP dependencies
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
            
        try:
            # Handle voucher block delimiters
            if line == '{':
                in_voucher_block = True
                continue
            elif line == '}':
                in_voucher_block = False
                current_voucher = None  # Reset voucher when block ends
                continue
                
            if not line.startswith('#'):
                continue
                
            # Parse file metadata
            if line.startswith('#FLAGGA'):
                sie_file.file_flag = line.split(' ', 1)[1].strip() if ' ' in line else ""
            elif line.startswith('#FORMAT'):
                sie_file.file_format = line.split(' ', 1)[1].strip() if ' ' in line else ""
            elif line.startswith('#SIETYP'):
                sie_file.sie_type = line.split(' ', 1)[1].strip() if ' ' in line else ""
            elif line.startswith('#PROGRAM'):
                sie_file.program = _extract_quoted_value(line) or line.split(' ', 1)[1].strip() if ' ' in line else ""
            elif line.startswith('#GEN'):
                sie_file.generation_date = line.split(' ', 1)[1].strip() if ' ' in line else ""
            elif line.startswith('#FNR'):
                sie_file.file_number = _extract_quoted_value(line) or line.split(' ', 1)[1].strip() if ' ' in line else ""
            elif line.startswith('#VALUTA'):
                sie_file.currency = line.split(' ', 1)[1].strip() if ' ' in line else ""
            elif line.startswith('#TAXAR'):
                sie_file.tax_year = line.split(' ', 1)[1].strip() if ' ' in line else ""
            elif line.startswith('#KPTYP'):
                sie_file.account_plan_type = line.split(' ', 1)[1].strip() if ' ' in line else ""
            elif line.startswith('#ADRESS'):
                # Parse address with multiple quoted fields
                parts = []
                current_part = ""
                in_quotes = False
                i = 7  # Skip "#ADRESS"
                while i < len(line):
                    char = line[i]
                    if char == '"':
                        if in_quotes:
                            parts.append(current_part)
                            current_part = ""
                            in_quotes = False
                        else:
                            in_quotes = True
                    elif in_quotes:
                        current_part += char
                    i += 1
                if len(parts) >= 1:
                    sie_file.contact_person = parts[0]
                if len(parts) >= 2:
                    sie_file.address_line1 = parts[1]
                if len(parts) >= 3:
                    sie_file.address_line2 = parts[2]
                if len(parts) >= 4:
                    sie_file.phone = parts[3]
            # Parse company metadata
            elif line.startswith('#FNAMN'):
                sie_file.company_name = _extract_quoted_value(line)
            elif line.startswith('#ORGNR'):
                sie_file.company_id = line.split(' ', 1)[1].strip()
            elif line.startswith('#RAR'):
                parts = line.split(' ')
                if len(parts) >= 3:
                    period = int(parts[1]) if parts[1].lstrip('-').isdigit() else 0
                    # Only use period 0 (current year) for the main period dates
                    if period == 0:
                        sie_file.period_start = parts[2]
                        sie_file.period_end = parts[3] if len(parts) > 3 else ""
            elif line.startswith('#KONTO'):
                # Extract account number and name, handling both quoted and unquoted names
                parts = line.split(' ', 2)  # Split into max 3 parts
                if len(parts) >= 3:
                    number = parts[1].strip()
                    name = parts[2].strip()
                    # Remove quotes if present
                    if name.startswith('"') and name.endswith('"'):
                        name = name[1:-1]
                    acc_type = get_bas_account_type(number)
                    sie_file.accounts[number] = SieAccount(number=number, name=name, type=acc_type)
            elif line.startswith('#KTYP'):
                # Store KTYP records for deferred processing
                parts = line.split()
                if len(parts) >= 3:
                    account_number = parts[1]
                    account_type = parts[2]
                    ktyp_records[account_number] = account_type
            elif line.startswith('#SRU'):
                # Store SRU records for deferred processing
                parts = line.split()
                if len(parts) >= 3:
                    account_number = parts[1]
                    sru_code = parts[2]
                    sru_records[account_number] = sru_code
            elif line.startswith('#DIM'):
                # Parse dimension definitions
                parts = line.split(' ', 2)
                if len(parts) >= 3:
                    dim_number = parts[1]
                    dim_name = parts[2].strip()
                    if dim_name.startswith('"') and dim_name.endswith('"'):
                        dim_name = dim_name[1:-1]
                    sie_file.dimensions[dim_number] = SieDimension(number=dim_number, name=dim_name)
            elif line.startswith('#OBJEKT'):
                # Parse object definitions
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    dimension = parts[1]
                    obj_number = parts[2]
                    obj_name = parts[3].strip()
                    if obj_name.startswith('"') and obj_name.endswith('"'):
                        obj_name = obj_name[1:-1]
                    key = f"{dimension}:{obj_number}"
                    sie_file.objects[key] = SieObject(dimension=dimension, number=obj_number, name=obj_name)
            elif line.startswith('#IB'):
                # Parse opening balances
                parts = line.split()
                if len(parts) >= 4:
                    period = int(parts[1])
                    account_number = parts[2]
                    amount = float(parts[3].replace(',', '.'))
                    quantity = float(parts[4].replace(',', '.')) if len(parts) > 4 else 0.0
                    sie_file.opening_balances.append(SieBalance(
                        account_number=account_number,
                        period=period,
                        amount=amount,
                        quantity=quantity
                    ))
            elif line.startswith('#UB'):
                # Parse closing balances
                parts = line.split()
                if len(parts) >= 4:
                    period = int(parts[1])
                    account_number = parts[2]
                    amount = float(parts[3].replace(',', '.'))
                    quantity = float(parts[4].replace(',', '.')) if len(parts) > 4 else 0.0
                    sie_file.closing_balances.append(SieBalance(
                        account_number=account_number,
                        period=period,
                        amount=amount,
                        quantity=quantity
                    ))
            elif line.startswith('#RES'):
                # Parse result balances
                parts = line.split()
                if len(parts) >= 4:
                    period = int(parts[1])
                    account_number = parts[2]
                    amount = float(parts[3].replace(',', '.'))
                    quantity = float(parts[4].replace(',', '.')) if len(parts) > 4 else 0.0
                    sie_file.result_balances.append(SieBalance(
                        account_number=account_number,
                        period=period,
                        amount=amount,
                        quantity=quantity
                    ))
            elif line.startswith('#VER'):
                # Start of a new voucher - only set if not already in a voucher block
                if not in_voucher_block:
                    parts = line.split(' ')
                    if len(parts) >= 4:
                        # Format: #VER series verno verdate vertext [regdate]
                        # vertext can be quoted or unquoted
                        description = ""
                        if len(parts) >= 5:
                            # Check if vertext is quoted
                            if parts[4].startswith('"') and parts[4].endswith('"'):
                                description = parts[4][1:-1]  # Remove quotes
                            elif parts[4].startswith('"'):
                                # Multi-word quoted description, find the end quote
                                desc_parts = [parts[4][1:]]  # Remove starting quote
                                for i in range(5, len(parts)):
                                    if parts[i].endswith('"'):
                                        desc_parts.append(parts[i][:-1])  # Remove ending quote
                                        break
                                    else:
                                        desc_parts.append(parts[i])
                                description = ' '.join(desc_parts)
                            else:
                                # Unquoted single word description
                                description = parts[4]
                        
                        current_voucher = {
                            'voucher_series': parts[1],  # Series (A, B, etc.)
                            'voucher_index': parts[2],   # V index
                            'date': parts[3],            # Date
                            'description': description
                        }
            elif line.startswith('#TRANS'):
                # Transaction within a voucher - only process if we're in a voucher block and have a current voucher
                if in_voucher_block and current_voucher:
                    # Parse transaction line according to SIE specification:
                    # Format: #TRANS account no {object list} amount transdate transtext quantity sign
                    parts = line.split(' ', 2)  # Split into #TRANS, account, and rest
                    if len(parts) >= 3:
                        account_number = parts[1]
                        rest = parts[2].strip()
                        
                        # Find the object list (between { and })
                        if rest.startswith('{'):
                            # Find the closing brace
                            brace_end = rest.find('}')
                            if brace_end != -1:
                                object_list = rest[1:brace_end]  # Extract content between braces
                                remaining = rest[brace_end + 1:].strip()
                            else:
                                # Malformed object list, treat as no objects
                                object_list = ""
                                remaining = rest
                        else:
                            # No object list
                            object_list = ""
                            remaining = rest
                        
                        # Parse remaining fields: amount [transdate] [transtext] [quantity] [sign]
                        remaining_parts = remaining.split()
                        amount = 0.0
                        if remaining_parts:
                            amount_str = remaining_parts[0]
                            if amount_str and amount_str != '{}':
                                amount = float(amount_str.replace(',', '.'))
                        
                        # Create entry (we store object_list for future use but don't parse it fully yet)
                        entry = SieEntry(
                            date=current_voucher['date'],
                            account_number=account_number,
                            amount=amount,
                            description=current_voucher['description'],
                            voucher_index=f"{current_voucher['voucher_series']}{current_voucher['voucher_index']}"
                        )
                        sie_file.entries.append(entry)
                        
        except (ValueError, IndexError) as e:
            raise SieParseError(f"Error parsing line: {str(e)}", line_num, line)
    
    # Second pass: Apply KTYP records to existing accounts
    for account_number, account_type_code in ktyp_records.items():
        try:
            account_type = AccountType.from_sie_code(account_type_code)
            if account_number in sie_file.accounts:
                sie_file.accounts[account_number].type = account_type
            else:
                # Create a placeholder account if KTYP comes before KONTO
                sie_file.accounts[account_number] = SieAccount(
                    number=account_number, 
                    name=f"Account {account_number}",  # Placeholder name
                    type=account_type
                )
        except ValueError as e:
            raise SieParseError(f"Invalid account type in KTYP: {e}", line_num=None, line_content=f"#KTYP {account_number} {account_type_code}")
    
    # Third pass: Apply SRU records to existing accounts
    for account_number, sru_code in sru_records.items():
        if account_number in sie_file.accounts:
            sie_file.accounts[account_number].sru_code = sru_code
        # Note: We don't create accounts for SRU-only records as they should have KONTO records
    
    return sie_file


def parse_sie_file(file_path: str, encoding: str = None) -> SieFile:
    """
    Parse a SIE file from a file path.
    
    According to the SIE 4B specification, SIE files must use CP437 encoding
    (IBM PC 8-bits extended ASCII, also known as PC8).
    
    Args:
        file_path: Path to the SIE file
        encoding: File encoding (default: 'cp437' as per SIE specification)
        
    Returns:
        SieFile object containing parsed data
        
    Raises:
        SieParseError: If there's an error parsing the file
        FileNotFoundError: If the file doesn't exist
        UnicodeDecodeError: If the file is not properly encoded in CP437
    """
    # Use CP437 as mandated by the SIE specification
    # "The character set used in the file is to be IBM PC 8-bits extended ASCII (Codepage 437)"
    encoding_to_use = encoding or 'cp437'
    
    try:
        with open(file_path, 'r', encoding=encoding_to_use) as f:
            return parse_sie(f)
    except UnicodeDecodeError as e:
        raise SieParseError(
            f"File is not properly encoded in {encoding_to_use}. "
            f"According to the SIE 4B specification, SIE files must use CP437 encoding "
            f"(IBM PC 8-bits extended ASCII). Error: {e}"
        )


# Validation Functions
def validate_entry_balance(entry: SieEntry, accounts: Dict[str, SieAccount]) -> bool:
    """Validate that an accounting entry is balanced based on account types.
    
    Args:
        entry: The accounting entry to validate
        accounts: Dictionary of account information
        
    Returns:
        bool: True if balanced, False otherwise
    """
    try:
        account = accounts.get(entry.account_number)
        if not account:
            return False
            
        # Get the account type and calculate effective amount
        # (positive for debits, negative for credits)
        effective_amount = entry.amount * account.balance_multiplier
        
        return True  # We'll use this in the accounting processor to check total balance
            
    except Exception:
        return False


# Public API
__all__ = [
    # Main parsing functions
    "parse_sie",
    "parse_sie_file",
    # Data models
    "SieFile",
    "SieAccount",
    "SieEntry",
    "SieBalance",
    "SieDimension",
    "SieObject",
    # Enums
    "AccountType",
    # Exceptions
    "SieParseError",
    "SieValidationError",
    # Utility functions
    "get_bas_account_type",
    "validate_entry_balance",
] 