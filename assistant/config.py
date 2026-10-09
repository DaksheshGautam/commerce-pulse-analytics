from dataclasses import dataclass, field
import os
import ssl
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    api_key: str = field(repr=False, default='')
    model: str = 'gemini-3.5-flash-lite'
    max_requests: int = 30
    embedding_model: str = 'gemini-embedding-001'
    ssl_ca_pem: str = field(repr=False, default='')
    ssl_ca_file: str = ''

    @classmethod
    def load(cls):
        values = dotenv_values(ROOT / '.env')
        def get(name, default=''):
            return os.getenv(name, values.get(name) or default)
        return cls(
            host=get('MYSQL_HOST', '127.0.0.1'), port=int(get('MYSQL_PORT', '3306')),
            database=get('MYSQL_DATABASE', 'ecommerce_db'),
            user=get('MYSQL_ASSISTANT_USER') or get('MYSQL_USER'),
            password=get('MYSQL_ASSISTANT_PASSWORD') if get('MYSQL_ASSISTANT_USER') else get('MYSQL_PASSWORD'),
            api_key=get('GEMINI_API_KEY'), model=get('GEMINI_MODEL', 'gemini-3.5-flash-lite'),
            max_requests=max(1, min(int(get('ASSISTANT_MAX_REQUESTS', '30')), 100)),
            embedding_model=get('GEMINI_EMBEDDING_MODEL', 'gemini-embedding-001'),
            ssl_ca_pem=get('MYSQL_SSL_CA_PEM'), ssl_ca_file=get('MYSQL_SSL_CA_FILE'),
        )

    @property
    def gemini_ready(self):
        return bool(self.api_key.strip()) and not self.api_key.startswith(('your_', 'replace_'))

    def mysql_connect_args(self):
        options = {'connect_timeout': 8, 'read_timeout': 20, 'write_timeout': 8,
                   'init_command': 'SET SESSION TRANSACTION READ ONLY'}
        if self.ssl_ca_pem or self.ssl_ca_file:
            context = ssl.create_default_context(
                cafile=self.ssl_ca_file or None, cadata=self.ssl_ca_pem or None)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            options['ssl'] = context
        elif self.host not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Remote MySQL requires MYSQL_SSL_CA_PEM or MYSQL_SSL_CA_FILE.')
        return options
