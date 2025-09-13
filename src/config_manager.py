"""
Trading Project 004 - Configuration Manager
Handles loading and validation of configuration settings from YAML and environment files.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging
from dotenv import load_dotenv


@dataclass
class IBConfig:
    """Interactive Brokers configuration settings"""
    host: str
    port: int
    client_id: int
    timeout: int
    account_id: str
    paper_trading: bool
    market_data_type: int
    max_retries: int
    retry_delay: int


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    primary: str
    sqlite_path: str
    sqlite_backup_path: str
    sqlite_journal_mode: str
    sqlite_synchronous: str
    sqlite_cache_size: int
    sqlite_temp_store: str
    postgresql_host: str
    postgresql_port: int
    postgresql_database: str
    postgresql_username: str
    postgresql_password: str
    postgresql_sslmode: str
    postgresql_connect_timeout: int
    postgresql_command_timeout: int
    postgresql_application_name: str
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    pool_pre_ping: bool
    query_echo: bool
    query_echo_pool: bool
    max_identifier_length: int


@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    level: str
    file_enabled: bool
    file_path: str
    file_max_size: str
    file_backup_count: int
    file_format: str
    console_enabled: bool
    console_level: str
    console_format: str
    module_levels: Dict[str, str]


class ConfigManager:
    """Main configuration manager for the trading project"""
    
    def __init__(self, config_path: Optional[str] = None, env_path: Optional[str] = None):
        """
        Initialize the configuration manager
        
        Args:
            config_path: Path to the YAML configuration file
            env_path: Path to the .env environment file
        """
        self.project_root = Path(__file__).parent.parent
        self.config_path = config_path or self.project_root / "config" / "config.yaml"
        self.env_path = env_path or self.project_root / "config" / ".env"
        
        self._config_data: Dict[str, Any] = {}
        self._load_configuration()
    
    def _load_configuration(self) -> None:
        """Load configuration from YAML and environment files"""
        # Load environment variables first
        if self.env_path.exists():
            load_dotenv(self.env_path)
        
        # Load YAML configuration
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as file:
            self._config_data = yaml.safe_load(file)
        
        # Override with environment variables where applicable
        self._apply_environment_overrides()
        
        # Validate configuration
        self._validate_configuration()
    
    def _apply_environment_overrides(self) -> None:
        """Apply environment variable overrides to configuration"""
        # Interactive Brokers overrides
        if 'interactive_brokers' in self._config_data:
            ib_config = self._config_data['interactive_brokers']
            ib_config['host'] = os.getenv('IB_HOST', ib_config.get('host'))
            ib_config['port'] = int(os.getenv('IB_PORT', ib_config.get('port', 7497)))
            ib_config['client_id'] = int(os.getenv('IB_CLIENT_ID', ib_config.get('client_id', 1)))
            ib_config['account_id'] = os.getenv('IB_ACCOUNT_ID', ib_config.get('account_id', ''))
        
        # Database overrides
        if 'database' in self._config_data and 'postgresql' in self._config_data['database']:
            db_config = self._config_data['database']['postgresql']
            db_config['host'] = os.getenv('DB_HOST', db_config.get('host'))
            db_config['port'] = int(os.getenv('DB_PORT', db_config.get('port', 5432)))
            db_config['database'] = os.getenv('DB_NAME', db_config.get('database'))
            db_config['username'] = os.getenv('DB_USER', db_config.get('username', ''))
            db_config['password'] = os.getenv('DB_PASSWORD', db_config.get('password', ''))
        
        # Application overrides
        if 'application' in self._config_data:
            app_config = self._config_data['application']
            app_config['environment'] = os.getenv('ENVIRONMENT', app_config.get('environment'))
            app_config['debug'] = os.getenv('DEBUG', '').lower() in ('true', '1', 'yes')
        
        # Logging overrides
        if 'logging' in self._config_data:
            log_config = self._config_data['logging']
            log_config['level'] = os.getenv('LOG_LEVEL', log_config.get('level'))
    
    def _validate_configuration(self) -> None:
        """Validate the loaded configuration"""
        required_sections = ['application', 'interactive_brokers', 'database', 'logging']
        
        for section in required_sections:
            if section not in self._config_data:
                raise ValueError(f"Missing required configuration section: {section}")
        
        # Basic validation
        ib_config = self._config_data['interactive_brokers']
        if not ib_config.get('host'):
            raise ValueError("Interactive Brokers host is required")
        if not isinstance(ib_config.get('port'), int):
            raise ValueError("Interactive Brokers port must be an integer")
        
        db_config = self._config_data['database']
        if 'sqlite' not in db_config and 'postgresql' not in db_config:
            raise ValueError("At least one database configuration (sqlite or postgresql) is required")
        
        # Create required directories
        self._create_required_directories()
    
    def validate_full(self) -> 'ValidationResult':
        """
        Perform comprehensive validation using ConfigValidator
        Returns ValidationResult object
        """
        # Import here to avoid circular imports
        from config_validator import ConfigValidator, ValidationResult
        
        try:
            validator = ConfigValidator()
            return validator.validate_all()
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Validation error: {e}"],
                warnings=[],
                info=[]
            )
    
    def _create_required_directories(self) -> None:
        """Create required directories if they don't exist"""
        directories = [
            self.project_root / "data" / "raw",
            self.project_root / "data" / "processed",
            self.project_root / "data" / "cache",
            self.project_root / "data" / "exports",
            self.project_root / "logs",
            self.project_root / "backups",
            self.project_root / "database"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_ib_config(self) -> IBConfig:
        """Get Interactive Brokers configuration"""
        ib_data = self._config_data['interactive_brokers']
        return IBConfig(
            host=ib_data['host'],
            port=ib_data['port'],
            client_id=ib_data['client_id'],
            timeout=ib_data['timeout'],
            account_id=ib_data['account_id'],
            paper_trading=ib_data['paper_trading'],
            market_data_type=ib_data['market_data_type'],
            max_retries=ib_data['max_retries'],
            retry_delay=ib_data['retry_delay']
        )
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration"""
        db_data = self._config_data['database']
        sqlite_data = db_data.get('sqlite', {})
        postgresql_data = db_data.get('postgresql', {})
        pool_data = db_data.get('connection_pool', {})
        query_data = db_data.get('query', {})
        
        return DatabaseConfig(
            primary=db_data.get('primary', 'sqlite'),
            sqlite_path=str(self.project_root / sqlite_data.get('path', 'database/trading_data.db')),
            sqlite_backup_path=str(self.project_root / sqlite_data.get('backup_path', 'backups/database/')),
            sqlite_journal_mode=sqlite_data.get('journal_mode', 'WAL'),
            sqlite_synchronous=sqlite_data.get('synchronous', 'NORMAL'),
            sqlite_cache_size=sqlite_data.get('cache_size', 10000),
            sqlite_temp_store=sqlite_data.get('temp_store', 'MEMORY'),
            postgresql_host=postgresql_data.get('host', 'localhost'),
            postgresql_port=postgresql_data.get('port', 5432),
            postgresql_database=postgresql_data.get('database', 'trading_db'),
            postgresql_username=postgresql_data.get('username', ''),
            postgresql_password=postgresql_data.get('password', ''),
            postgresql_sslmode=postgresql_data.get('sslmode', 'prefer'),
            postgresql_connect_timeout=postgresql_data.get('connect_timeout', 10),
            postgresql_command_timeout=postgresql_data.get('command_timeout', 60),
            postgresql_application_name=postgresql_data.get('application_name', 'trading_project_004'),
            pool_size=pool_data.get('pool_size', 5),
            max_overflow=pool_data.get('max_overflow', 10),
            pool_timeout=pool_data.get('pool_timeout', 30),
            pool_recycle=pool_data.get('pool_recycle', 3600),
            pool_pre_ping=pool_data.get('pool_pre_ping', True),
            query_echo=query_data.get('echo', False),
            query_echo_pool=query_data.get('echo_pool', False),
            max_identifier_length=query_data.get('max_identifier_length', 63)
        )
    
    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration"""
        log_data = self._config_data['logging']
        file_data = log_data.get('file', {})
        console_data = log_data.get('console', {})
        modules_data = log_data.get('modules', {})
        
        return LoggingConfig(
            level=log_data['level'],
            file_enabled=file_data.get('enabled', True),
            file_path=str(self.project_root / file_data.get('path', 'logs/trading_project.log')),
            file_max_size=file_data.get('max_size', '10MB'),
            file_backup_count=file_data.get('backup_count', 5),
            file_format=file_data.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            console_enabled=console_data.get('enabled', True),
            console_level=console_data.get('level', 'INFO'),
            console_format=console_data.get('format', '%(asctime)s - %(levelname)s - %(message)s'),
            module_levels=modules_data
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)"""
        keys = key.split('.')
        value = self._config_data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_application_config(self) -> Dict[str, Any]:
        """Get application configuration"""
        return self._config_data.get('application', {})
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.get('application.environment') == 'development'
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.get('application.environment') == 'production'
    
    def is_debug_enabled(self) -> bool:
        """Check if debug mode is enabled"""
        return self.get('application.debug', False)
    
    def reload(self) -> None:
        """Reload configuration from files"""
        self._load_configuration()


# Global configuration instance
config = ConfigManager()


def get_config() -> ConfigManager:
    """Get the global configuration instance"""
    return config


if __name__ == "__main__":
    # Test the configuration manager
    try:
        cfg = ConfigManager()
        print("Configuration loaded successfully!")
        print(f"Environment: {cfg.get('application.environment')}")
        print(f"Debug mode: {cfg.is_debug_enabled()}")
        print(f"IB Host: {cfg.get_ib_config().host}")
        print(f"IB Port: {cfg.get_ib_config().port}")
        print(f"Database Path: {cfg.get_database_config().sqlite_path}")
    except Exception as e:
        print(f"Configuration error: {e}")