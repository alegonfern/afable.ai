import xmlrpc.client
import socket


class OdooConnectionError(Exception):
    pass


class OdooClient:
    def __init__(self, url: str, db: str, username: str, api_key: str):
        self.url = url.rstrip('/')
        self.db = db
        self.username = username
        self.api_key = api_key
        self._uid = None

    def authenticate(self) -> int:
        try:
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common', allow_none=True)
            uid = common.authenticate(self.db, self.username, self.api_key, {})
            if not uid:
                raise OdooConnectionError('Credenciales inválidas.')
            self._uid = uid
            return uid
        except ConnectionRefusedError:
            raise OdooConnectionError(f'No se pudo conectar a {self.url}')
        except socket.gaierror:
            raise OdooConnectionError(f'Host no encontrado: {self.url}')
        except xmlrpc.client.Fault as e:
            raise OdooConnectionError(f'Error Odoo: {e.faultString}')
        except Exception as e:
            raise OdooConnectionError(str(e))

    @property
    def uid(self) -> int:
        if self._uid is None:
            self.authenticate()
        return self._uid

    def execute(self, model: str, method: str, args: list = None, kwargs: dict = None):
        try:
            models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object', allow_none=True)
            return models.execute_kw(
                self.db, self.uid, self.api_key,
                model, method,
                args or [],
                kwargs or {},
            )
        except xmlrpc.client.Fault as e:
            raise OdooConnectionError(f'Error Odoo ({model}.{method}): {e.faultString}')
        except Exception as e:
            raise OdooConnectionError(str(e))

    def search_read(
        self,
        model: str,
        domain: list = None,
        fields: list = None,
        limit: int = 100,
        order: str = None,
        offset: int = 0,
    ) -> list:
        kwargs = {
            'fields': fields or [],
            'limit': limit,
            'offset': offset,
        }
        if order:
            kwargs['order'] = order
        return self.execute(model, 'search_read', [domain or []], kwargs)

    def search_count(self, model: str, domain: list = None) -> int:
        return self.execute(model, 'search_count', [domain or []])
