"""
Trading Project 004 - Configuration Validator
Advanced validation for all configuration parameters
"""

import os
import re
import socket
from typing import List, Dict, Any, Tuple
from pathlib import Path
import yaml
from dataclasses import dataclass

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))
from config_manager import get_config


@dataclass
class ValidationResult:
    """Validation result structure"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    info: List[str]


class ConfigValidator:
    """Advanced configuration validator"""
    
    def __init__(self):
        self.config = get_config()
        
    def validate_all(self) -> ValidationResult:
        """Validate all configuration sections"""
        result = ValidationResult(True, [], [], [])
        
        # Validate each section
        sections = [
            self._validate_application,
            self._validate_interactive_brokers,
            self._validate_database,
            self._validate_logging,
            self._validate_paths,
            self._validate_environment
        ]
        
        for validator in sections:
            section_result = validator()
            result.errors.extend(section_result.errors)
            result.warnings.extend(section_result.warnings)
            result.info.extend(section_result.info)
            
            if not section_result.is_valid:
                result.is_valid = False
        
        return result
    
    def _validate_application(self) -> ValidationResult:
        """Validate application configuration"""
        result = ValidationResult(True, [], [], [])
        app_config = self.config.get_application_config()
        
        # Required fields
        required_fields = ['name', 'version', 'environment']
        for field in required_fields:
            if not app_config.get(field):
                result.errors.append(f"Application {field} is required")
                result.is_valid = False
        
        # Environment validation
        valid_environments = ['development', 'testing', 'production']
        env = app_config.get('environment', '')
        if env not in valid_environments:
            result.errors.append(f"Invalid environment: {env}. Must be one of: {valid_environments}")
            result.is_valid = False
        
        # Version format validation
        version = app_config.get('version', '')
        if version and not re.match(r'^\d+\.\d+\.\d+$', version):
            result.warnings.append(f"Version format should be X.Y.Z (semver): {version}")
        
        result.info.append(f"Application: {app_config.get('name')} v{version} ({env})")
        return result
    
    def _validate_interactive_brokers(self) -> ValidationResult:
        """Validate Interactive Brokers configuration"""
        result = ValidationResult(True, [], [], [])
        ib_config = self.config.get_ib_config()
        
        # Host validation
        if not ib_config.host:
            result.errors.append("IB host is required")
            result.is_valid = False
        elif not self._is_valid_ip_or_hostname(ib_config.host):
            result.errors.append(f"Invalid IB host format: {ib_config.host}")
            result.is_valid = False
        
        # Port validation
        if not (1 <= ib_config.port <= 65535):
            result.errors.append(f"Invalid IB port: {ib_config.port}. Must be 1-65535")
            result.is_valid = False
        
        # Port recommendations
        if ib_config.port == 7497:
            result.info.append("Using TWS Demo port (7497)")
        elif ib_config.port == 7496:
            result.info.append("Using TWS Live port (7496) - LIVE TRADING")
        elif ib_config.port == 4002:
            result.info.append("Using Gateway Demo port (4002)")
        elif ib_config.port == 4001:
            result.info.append("Using Gateway Live port (4001) - LIVE TRADING")
        else:
            result.warnings.append(f"Non-standard IB port: {ib_config.port}")
        
        # Client ID validation
        if not (1 <= ib_config.client_id <= 32):
            result.warnings.append(f"IB Client ID should be 1-32: {ib_config.client_id}")
        
        # Account ID validation
        if not ib_config.account_id:
            result.warnings.append("IB Account ID not configured")
        elif not re.match(r'^[DU]\d+$', ib_config.account_id):
            result.warnings.append(f"IB Account ID format seems incorrect: {ib_config.account_id}")
        
        # Timeout validation
        if ib_config.timeout < 5:
            result.warnings.append(f"IB timeout might be too short: {ib_config.timeout}s")
        elif ib_config.timeout > 60:
            result.warnings.append(f"IB timeout might be too long: {ib_config.timeout}s")
        
        # Connection test (if possible)
        if self._can_connect_to_host(ib_config.host, ib_config.port):
            result.info.append(f"IB connection test successful: {ib_config.host}:{ib_config.port}")
        else:
            result.warnings.append(f"Cannot connect to IB at {ib_config.host}:{ib_config.port}")
        
        return result
    
    def _validate_database(self) -> ValidationResult:
        """Validate database configuration"""
        result = ValidationResult(True, [], [], [])
        db_config = self.config.get_database_config()
        
        # Primary database type
        valid_types = ['sqlite', 'postgresql']
        if db_config.primary not in valid_types:
            result.errors.append(f"Invalid primary database type: {db_config.primary}")
            result.is_valid = False
        
        # SQLite validation
        if db_config.primary == 'sqlite' or db_config.sqlite_path:
            sqlite_path = Path(db_config.sqlite_path)
            
            # Check if directory exists or can be created
            if not sqlite_path.parent.exists():
                try:
                    sqlite_path.parent.mkdir(parents=True)
                    result.info.append(f"Created SQLite directory: {sqlite_path.parent}")
                except Exception as e:
                    result.errors.append(f"Cannot create SQLite directory: {e}")
                    result.is_valid = False
            
            # Check permissions
            if sqlite_path.exists() and not os.access(sqlite_path, os.R_OK | os.W_OK):
                result.errors.append(f"No read/write access to SQLite file: {sqlite_path}")
                result.is_valid = False
            
            # Validate SQLite settings
            valid_journal_modes = ['DELETE', 'TRUNCATE', 'PERSIST', 'MEMORY', 'WAL', 'OFF']
            if db_config.sqlite_journal_mode not in valid_journal_modes:
                result.errors.append(f"Invalid SQLite journal_mode: {db_config.sqlite_journal_mode}")
                result.is_valid = False
            
            valid_sync_modes = ['OFF', 'NORMAL', 'FULL', 'EXTRA']
            if db_config.sqlite_synchronous not in valid_sync_modes:
                result.errors.append(f"Invalid SQLite synchronous: {db_config.sqlite_synchronous}")
                result.is_valid = False
        
        # PostgreSQL validation
        if db_config.primary == 'postgresql':
            if not db_config.postgresql_host:
                result.errors.append("PostgreSQL host is required")
                result.is_valid = False
            
            if not (1 <= db_config.postgresql_port <= 65535):
                result.errors.append(f"Invalid PostgreSQL port: {db_config.postgresql_port}")
                result.is_valid = False
            
            if not db_config.postgresql_database:
                result.errors.append("PostgreSQL database name is required")
                result.is_valid = False
            
            if not db_config.postgresql_username:
                result.warnings.append("PostgreSQL username not configured")
            
            if not db_config.postgresql_password:
                result.warnings.append("PostgreSQL password not configured")
        
        # Connection pool validation
        if db_config.pool_size < 1:
            result.errors.append(f"Database pool_size must be >= 1: {db_config.pool_size}")
            result.is_valid = False
        
        if db_config.max_overflow < 0:
            result.errors.append(f"Database max_overflow must be >= 0: {db_config.max_overflow}")
            result.is_valid = False
        
        if db_config.pool_timeout <= 0:
            result.errors.append(f"Database pool_timeout must be > 0: {db_config.pool_timeout}")
            result.is_valid = False
        
        result.info.append(f"Primary database: {db_config.primary}")
        return result
    
    def _validate_logging(self) -> ValidationResult:
        """Validate logging configuration"""
        result = ValidationResult(True, [], [], [])
        log_config = self.config.get_logging_config()
        
        # Log level validation
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_config.level not in valid_levels:
            result.errors.append(f"Invalid log level: {log_config.level}")
            result.is_valid = False
        
        # File logging validation
        if log_config.file_enabled:
            log_path = Path(log_config.file_path)
            
            # Check directory
            if not log_path.parent.exists():
                try:
                    log_path.parent.mkdir(parents=True)
                    result.info.append(f"Created log directory: {log_path.parent}")
                except Exception as e:
                    result.errors.append(f"Cannot create log directory: {e}")
                    result.is_valid = False
            
            # Check write permissions
            if log_path.exists() and not os.access(log_path, os.W_OK):
                result.errors.append(f"No write access to log file: {log_path}")
                result.is_valid = False
            
            # Validate backup count
            if log_config.file_backup_count < 0:
                result.errors.append(f"Log backup_count must be >= 0: {log_config.file_backup_count}")
                result.is_valid = False
        
        # Console level validation
        if log_config.console_level not in valid_levels:
            result.errors.append(f"Invalid console log level: {log_config.console_level}")
            result.is_valid = False
        
        result.info.append(f"Logging level: {log_config.level}")
        return result
    
    def _validate_paths(self) -> ValidationResult:
        """Validate all path configurations"""
        result = ValidationResult(True, [], [], [])
        
        # Get paths from config
        paths = self.config.get('paths', {})
        
        # Required directories
        required_dirs = [
            'data/raw', 'data/processed', 'data/cache', 'data/exports',
            'logs', 'backups', 'database'
        ]
        
        for dir_path in required_dirs:
            full_path = self.config.project_root / dir_path
            
            if not full_path.exists():
                try:
                    full_path.mkdir(parents=True)
                    result.info.append(f"Created directory: {dir_path}")
                except Exception as e:
                    result.errors.append(f"Cannot create directory {dir_path}: {e}")
                    result.is_valid = False
            
            # Check permissions
            if full_path.exists() and not os.access(full_path, os.R_OK | os.W_OK):
                result.errors.append(f"No read/write access to directory: {dir_path}")
                result.is_valid = False
        
        return result
    
    def _validate_environment(self) -> ValidationResult:
        """Validate environment variables"""
        result = ValidationResult(True, [], [], [])
        
        # Check for .env file
        env_path = self.config.project_root / "config" / ".env"
        if not env_path.exists():
            result.warnings.append("No .env file found. Using defaults and environment variables.")
        else:
            result.info.append(".env file found and loaded")
        
        # Check critical environment variables
        critical_vars = ['IB_ACCOUNT_ID']
        for var in critical_vars:
            if not os.getenv(var):
                result.warnings.append(f"Environment variable {var} not set")
        
        return result
    
    def _is_valid_ip_or_hostname(self, host: str) -> bool:
        """Validate IP address or hostname format"""
        # Check if it's localhost
        if host.lower() in ['localhost', '127.0.0.1', '::1']:
            return True
        
        # Check if it's a valid IP address
        try:
            socket.inet_aton(host)
            return True
        except socket.error:
            pass
        
        # Check if it's a valid hostname
        if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', host):
            return True
        
        return False
    
    def _can_connect_to_host(self, host: str, port: int, timeout: int = 3) -> bool:
        """Test if we can connect to a host:port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False


def validate_configuration() -> ValidationResult:
    """Main validation function"""
    validator = ConfigValidator()
    return validator.validate_all()


def print_validation_results(result: ValidationResult):
    """Print validation results in a formatted way"""
    print("=" * 60)
    print("CONFIGURATION VALIDATION RESULTS")
    print("=" * 60)
    
    if result.is_valid:
        print("Status: VALID")
    else:
        print("Status: INVALID")
    
    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for error in result.errors:
            print(f"  - {error}")
    
    if result.warnings:
        print(f"\nWARNINGS ({len(result.warnings)}):")
        for warning in result.warnings:
            print(f"  - {warning}")
    
    if result.info:
        print(f"\nINFO ({len(result.info)}):")
        for info in result.info:
            print(f"  - {info}")
    
    print("=" * 60)


if __name__ == "__main__":
    result = validate_configuration()
    print_validation_results(result)
    
    if not result.is_valid:
        sys.exit(1)