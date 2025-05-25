"""Tests for SIE CLI functionality.

These tests ensure the CLI commands work correctly and catch regressions
during refactoring.
"""

import pytest
import sys
import os
from io import StringIO
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sie_cli
import sie_parser


@pytest.fixture
def sample_sie_data():
    """Create a sample SieFile object for testing."""
    sie_data = sie_parser.SieFile()
    sie_data.company_name = "Test Company AB"
    sie_data.company_id = "555555-5555"
    sie_data.period_start = "20240101"
    sie_data.period_end = "20241231"
    sie_data.file_format = "PC8"
    sie_data.sie_type = "4"
    sie_data.currency = "SEK"
    sie_data.program = "Test Program"
    sie_data.generation_date = "20240315"
    sie_data.contact_person = "Test Person"
    sie_data.address_line1 = "Test Street 1"
    sie_data.address_line2 = "123 45 Test City"
    sie_data.phone = "08-123 45 67"
    
    # Add some accounts
    sie_data.accounts = {
        "1910": sie_parser.SieAccount("1910", "Kassa", sie_parser.AccountType.ASSET),
        "2610": sie_parser.SieAccount("2610", "Leverantörsskulder", sie_parser.AccountType.LIABILITY),
        "3010": sie_parser.SieAccount("3010", "Försäljning", sie_parser.AccountType.INCOME, sru_code="3001"),
        "4010": sie_parser.SieAccount("4010", "Kostnader", sie_parser.AccountType.EXPENSE),
    }
    
    # Add some transactions
    sie_data.entries = [
        sie_parser.SieEntry("20240315", "1910", 1000.0, "Test transaction 1", "A1"),
        sie_parser.SieEntry("20240315", "2610", -500.0, "Test transaction 1", "A1"),
        sie_parser.SieEntry("20240315", "4010", -500.0, "Test transaction 1", "A1"),
        sie_parser.SieEntry("20240316", "3010", -2000.0, "Test transaction 2", "A2"),
        sie_parser.SieEntry("20240316", "1910", 2000.0, "Test transaction 2", "A2"),
    ]
    
    # Add some opening balances
    sie_data.opening_balances = [
        sie_parser.SieBalance("1910", 0, 5000.0),
        sie_parser.SieBalance("2610", 0, -1000.0),
    ]
    
    return sie_data


class TestListAccounts:
    """Test the list_accounts function."""
    
    def test_list_accounts_basic_output(self, sample_sie_data, capsys):
        """Test basic accounts listing output."""
        sie_cli.list_accounts(sample_sie_data, non_zero_only=False, csv_output=False)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Check header
        assert "Account" in output
        assert "Name" in output
        assert "Type" in output
        assert "Balance" in output
        
        # Check account data
        assert "1910" in output
        assert "Kassa" in output
        assert "ASSET" in output
        assert "2610" in output
        assert "Leverantörsskulder" in output
        assert "LIABILITY" in output
        
        # Check total count
        assert "Total accounts: 4" in output
    
    def test_list_accounts_non_zero_filter(self, sample_sie_data, capsys):
        """Test accounts listing with non-zero filter."""
        sie_cli.list_accounts(sample_sie_data, non_zero_only=True, csv_output=False)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Should show fewer accounts (only those with balances)
        assert "Total accounts:" in output
        # The exact count depends on which accounts have non-zero balances
        
    def test_list_accounts_csv_output(self, sample_sie_data, capsys):
        """Test accounts listing with CSV output."""
        sie_cli.list_accounts(sample_sie_data, non_zero_only=False, csv_output=True)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Check CSV header
        assert "number,name,type,balance,normal_balance,sru_code" in output
        
        # Check CSV data format
        lines = output.strip().split('\n')
        assert len(lines) >= 2  # Header + at least one data line
        
        # Check that account data is in CSV format
        assert "1910,Kassa,ASSET," in output
        assert "3010,Försäljning,INCOME," in output and "3001" in output  # SRU code


class TestListVouchers:
    """Test the list_vouchers function."""
    
    def test_list_vouchers_basic_output(self, sample_sie_data, capsys):
        """Test basic vouchers listing output."""
        sie_cli.list_vouchers(sample_sie_data, csv_output=False)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Check header
        assert "Voucher" in output
        assert "Date" in output
        assert "Description" in output
        assert "Trans" in output
        assert "Balance" in output
        
        # Check voucher data
        assert "A1" in output
        assert "A2" in output
        assert "20240315" in output
        assert "20240316" in output
        
        # Check summary
        assert "Total vouchers:" in output
        assert "Balanced vouchers:" in output
    
    def test_list_vouchers_csv_output(self, sample_sie_data, capsys):
        """Test vouchers listing with CSV output."""
        sie_cli.list_vouchers(sample_sie_data, csv_output=True)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Check CSV header
        assert "voucher,date,description,transactions,total_amount,balance,balanced" in output
        
        # Check CSV data format
        lines = output.strip().split('\n')
        assert len(lines) >= 2  # Header + at least one data line
        
        # Check voucher data in CSV format
        assert "A1,20240315," in output
        assert "A2,20240316," in output


class TestShowSummary:
    """Test the show_summary function."""
    
    def test_show_summary_basic_output(self, sample_sie_data, capsys):
        """Test basic summary output."""
        sie_cli.show_summary(sample_sie_data, csv_output=False)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Check main sections
        assert "SIE File Summary" in output
        assert "Company Information:" in output
        assert "Contact Information:" in output
        assert "File Information:" in output
        assert "Data Summary:" in output
        
        # Check company info
        assert "Test Company AB" in output
        assert "555555-5555" in output
        assert "20240101 - 20241231" in output
        
        # Check contact info
        assert "Test Person" in output
        assert "Test Street 1" in output
        assert "08-123 45 67" in output
        
        # Check file info
        assert "PC8" in output
        assert "Test Program" in output
        
        # Check data summary
        assert "Total Accounts: 4" in output
        assert "Total Transactions: 5" in output
        assert "Total Vouchers: 2" in output
    
    def test_show_summary_csv_output(self, sample_sie_data, capsys):
        """Test summary with CSV output."""
        sie_cli.show_summary(sample_sie_data, csv_output=True)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Check CSV header contains expected fields
        assert "company_name" in output
        assert "total_accounts" in output
        assert "total_entries" in output
        assert "total_vouchers" in output
        
        # Check CSV data
        lines = output.strip().split('\n')
        assert len(lines) == 2  # Header + one data line
        
        # Check some key data points
        assert "Test Company AB" in output
        assert "555555-5555" in output


class TestCLIMain:
    """Test the main CLI function and argument parsing."""
    
    @patch('sie_cli.sie_parser.parse_sie_file')
    def test_main_accounts_command(self, mock_parse, sample_sie_data):
        """Test main function with accounts command."""
        mock_parse.return_value = sample_sie_data
        
        with patch('sys.argv', ['sie_cli.py', 'accounts', 'test.sie']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                sie_cli.main()
        
        mock_parse.assert_called_once_with('test.sie', encoding='cp437')
        output = mock_stdout.getvalue()
        assert "Account" in output
        assert "Total accounts:" in output
    
    @patch('sie_cli.sie_parser.parse_sie_file')
    def test_main_vouchers_command(self, mock_parse, sample_sie_data):
        """Test main function with vouchers command."""
        mock_parse.return_value = sample_sie_data
        
        with patch('sys.argv', ['sie_cli.py', 'vouchers', 'test.sie']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                sie_cli.main()
        
        mock_parse.assert_called_once_with('test.sie', encoding='cp437')
        output = mock_stdout.getvalue()
        assert "Voucher" in output
        assert "Total vouchers:" in output
    
    @patch('sie_cli.sie_parser.parse_sie_file')
    def test_main_summary_command(self, mock_parse, sample_sie_data):
        """Test main function with summary command."""
        mock_parse.return_value = sample_sie_data
        
        with patch('sys.argv', ['sie_cli.py', 'summary', 'test.sie']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                sie_cli.main()
        
        mock_parse.assert_called_once_with('test.sie', encoding='cp437')
        output = mock_stdout.getvalue()
        assert "SIE File Summary" in output
        assert "Company Information:" in output
    
    @patch('sie_cli.sie_parser.parse_sie_file')
    def test_main_with_csv_flag(self, mock_parse, sample_sie_data):
        """Test main function with CSV output flag."""
        mock_parse.return_value = sample_sie_data
        
        with patch('sys.argv', ['sie_cli.py', 'accounts', 'test.sie', '--csv']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                sie_cli.main()
        
        output = mock_stdout.getvalue()
        assert "number,name,type,balance" in output
    
    @patch('sie_cli.sie_parser.parse_sie_file')
    def test_main_with_non_zero_flag(self, mock_parse, sample_sie_data):
        """Test main function with non-zero flag."""
        mock_parse.return_value = sample_sie_data
        
        with patch('sys.argv', ['sie_cli.py', 'accounts', 'test.sie', '--non-zero']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                sie_cli.main()
        
        # Should execute without error
        mock_parse.assert_called_once()
    
    @patch('sie_cli.sie_parser.parse_sie_file')
    def test_main_with_custom_encoding(self, mock_parse, sample_sie_data):
        """Test main function with custom encoding."""
        mock_parse.return_value = sample_sie_data
        
        with patch('sys.argv', ['sie_cli.py', 'summary', 'test.sie', '--encoding', 'utf-8']):
            with patch('sys.stdout', new_callable=StringIO):
                sie_cli.main()
        
        mock_parse.assert_called_once_with('test.sie', encoding='utf-8')
    
    @patch('sie_cli.sie_parser.parse_sie_file')
    def test_main_file_not_found_error(self, mock_parse):
        """Test main function handles file not found error."""
        mock_parse.side_effect = FileNotFoundError("File not found")
        
        with patch('sys.argv', ['sie_cli.py', 'summary', 'nonexistent.sie']):
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit) as exc_info:
                    sie_cli.main()
        
        assert exc_info.value.code == 1
        error_output = mock_stderr.getvalue()
        assert "File 'nonexistent.sie' not found" in error_output
    
    @patch('sie_cli.sie_parser.parse_sie_file')
    def test_main_parse_error(self, mock_parse):
        """Test main function handles parse errors."""
        mock_parse.side_effect = sie_parser.SieParseError("Invalid SIE format", 5, "bad line")
        
        with patch('sys.argv', ['sie_cli.py', 'summary', 'bad.sie']):
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit) as exc_info:
                    sie_cli.main()
        
        assert exc_info.value.code == 1
        error_output = mock_stderr.getvalue()
        assert "Error parsing SIE file:" in error_output
        assert "Invalid SIE format" in error_output


class TestCLIIntegration:
    """Integration tests using real test files."""
    
    def test_cli_with_real_test_file(self):
        """Test CLI commands with the actual test SIE file."""
        test_file_path = os.path.join(os.path.dirname(__file__), 'test_sie4.se')
        
        if not os.path.exists(test_file_path):
            pytest.skip("Test SIE file not found")
        
        # Test summary command
        with patch('sys.argv', ['sie_cli.py', 'summary', test_file_path]):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                sie_cli.main()
        
        summary_output = mock_stdout.getvalue()
        assert "SIE File Summary" in summary_output
        assert "Testföretag AB" in summary_output
        
        # Test accounts command
        with patch('sys.argv', ['sie_cli.py', 'accounts', test_file_path, '--non-zero']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                sie_cli.main()
        
        accounts_output = mock_stdout.getvalue()
        assert "Account" in accounts_output
        assert "Total accounts:" in accounts_output
        
        # Test vouchers command
        with patch('sys.argv', ['sie_cli.py', 'vouchers', test_file_path]):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                sie_cli.main()
        
        vouchers_output = mock_stdout.getvalue()
        assert "Voucher" in vouchers_output
        assert "Total vouchers:" in vouchers_output


if __name__ == "__main__":
    pytest.main([__file__]) 