import json
from typing import List, Dict, Any


class SQLConnectionError(Exception):
    pass


class SQLClient:
    """
    Connector genérico para MSSQL y PostgreSQL.
    Cubre SAP Business One (MSSQL), ERPs propios, y cualquier base de datos SQL.
    """

    def __init__(self, connector_type: str, config: dict):
        self.connector_type = connector_type  # 'mssql' | 'postgresql'
        self.config = config
        self._conn = None

    def connect(self):
        try:
            if self.connector_type == 'mssql':
                import pymssql
                self._conn = pymssql.connect(
                    server=self.config['host'],
                    port=int(self.config.get('port', 1433)),
                    user=self.config['username'],
                    password=self.config['password'],
                    database=self.config['database'],
                    timeout=10,
                    login_timeout=10,
                )
            elif self.connector_type == 'postgresql':
                import psycopg
                self._conn = psycopg.connect(
                    host=self.config['host'],
                    port=int(self.config.get('port', 5432)),
                    user=self.config['username'],
                    password=self.config['password'],
                    dbname=self.config['database'],
                    connect_timeout=10,
                )
            else:
                raise SQLConnectionError(f'Tipo de conector desconocido: {self.connector_type}')
        except ImportError as e:
            raise SQLConnectionError(f'Librería no instalada: {e}')
        except Exception as e:
            raise SQLConnectionError(str(e))
        return self

    def test_connection(self) -> dict:
        try:
            self.connect()
            tables = self.list_tables()
            self._conn.close()
            return {'success': True, 'tables_count': len(tables)}
        except SQLConnectionError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def list_tables(self) -> List[str]:
        if self.connector_type == 'mssql':
            sql = (
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
            )
        else:
            sql = (
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' ORDER BY tablename"
            )
        rows = self._execute_raw(sql)
        return [r[0] for r in rows]

    def describe_table(self, table_name: str) -> List[Dict]:
        if self.connector_type == 'mssql':
            sql = (
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME = %s ORDER BY ORDINAL_POSITION"
            )
        else:
            sql = (
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = %s AND table_schema = 'public' "
                "ORDER BY ordinal_position"
            )
        rows = self._execute_raw(sql, [table_name])
        return [{'column': r[0], 'type': r[1], 'nullable': r[2]} for r in rows]

    def sample_table(self, table_name: str, limit: int = 5) -> List[Dict]:
        if self.connector_type == 'mssql':
            sql = f'SELECT TOP {limit} * FROM [{table_name}]'
            rows = self._execute_raw(sql)
        else:
            sql = f'SELECT * FROM "{table_name}" LIMIT %s'
            rows = self._execute_raw(sql, [limit])
        cursor = self._conn.cursor()
        cursor.execute(sql if self.connector_type == 'postgresql' else f'SELECT TOP 1 * FROM [{table_name}]')
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, r)) for r in rows]

    def query_as_dict(self, sql: str, params=None, limit: int = 200) -> List[Dict]:
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()
        # Inject safety limit
        upper = sql.upper().strip()
        if self.connector_type == 'mssql' and 'TOP' not in upper[:30]:
            sql = sql.replace('SELECT ', f'SELECT TOP {limit} ', 1)
        elif self.connector_type == 'postgresql' and 'LIMIT' not in upper:
            sql = f'{sql} LIMIT {limit}'
        cursor.execute(sql, params or [])
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def list_relations(self) -> List[Dict]:
        """Relaciones (foreign keys) entre tablas: [{from_table, from_column, to_table, to_column}]."""
        if self.connector_type == 'mssql':
            sql = (
                "SELECT OBJECT_NAME(fk.parent_object_id) AS from_table, "
                "       COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS from_column, "
                "       OBJECT_NAME(fk.referenced_object_id) AS to_table, "
                "       COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS to_column "
                "FROM sys.foreign_keys fk "
                "JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id"
            )
        else:
            sql = (
                "SELECT tc.table_name AS from_table, kcu.column_name AS from_column, "
                "       ccu.table_name AS to_table, ccu.column_name AS to_column "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
                "JOIN information_schema.constraint_column_usage ccu "
                "  ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema "
                "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'"
            )
        rows = self._execute_raw(sql)
        return [{'from_table': r[0], 'from_column': r[1], 'to_table': r[2], 'to_column': r[3]} for r in rows]

    def count_rows(self, table_name: str) -> int:
        """Conteo de filas de una tabla (None si falla)."""
        try:
            if self.connector_type == 'mssql':
                rows = self._execute_raw(f'SELECT COUNT(*) FROM [{table_name}]')
            else:
                rows = self._execute_raw(f'SELECT COUNT(*) FROM "{table_name}"')
            return int(rows[0][0]) if rows else None
        except Exception:
            return None

    def build_schema_summary(self, max_tables: int = 30) -> dict:
        """Descubre el esquema de la base de datos para el contexto del agente."""
        tables = self.list_tables()[:max_tables]
        schema = {}
        for table in tables:
            try:
                schema[table] = self.describe_table(table)
            except Exception:
                schema[table] = []
        return schema

    def _execute_raw(self, sql: str, params=None) -> List:
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()
        cursor.execute(sql, params or [])
        return cursor.fetchall()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()
