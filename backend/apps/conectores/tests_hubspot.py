"""El conector de HubSpot contra un HubSpot simulado (sin red)."""
from datetime import timedelta
from unittest import mock

from django.utils import timezone

from apps.comercial.models import Pedido
from apps.comercial.tests import _Base
from apps.finanzas.models import Contacto

from . import servicio
from .models import Conexion, Sincronizacion


class Respuesta:
    def __init__(self, datos=None, status=200, headers=None):
        self._datos, self.status_code, self.headers = datos or {}, status, headers or {}

    def json(self):
        return self._datos


EMPRESAS = [
    {'id': '101', 'properties': {'name': 'Constructora Andes', 'phone': '+56 2 2222 2222', 'city': 'Santiago',
                                 'rut_empresa': '77.111.222-3'}},
    {'id': '102', 'properties': {'name': 'Inmobiliaria Sur', 'address': 'Av. Sur 100', 'rut_empresa': ''}},
]
CONTACTOS = [
    {'id': '201', 'properties': {'firstname': 'María', 'lastname': 'Pérez', 'email': 'maria@andes.test'},
     'associations': {'companies': {'results': [{'id': '101', 'type': 'contact_to_company'}]}}},
    {'id': '202', 'properties': {'firstname': 'Juan', 'lastname': 'Soto', 'email': 'juan@correo.test', 'phone': '+56 9 1111'}},
]
NEGOCIOS = [
    {'id': '301', 'properties': {'dealname': 'Obra Los Militares', 'amount': '1500000', 'deal_currency_code': 'CLP'}},
    {'id': '302', 'properties': {'dealname': 'Sin monto', 'amount': ''}},
]


class HubSpotFalso:
    """Responde como la API de HubSpot, con las listas en dos páginas para probar la paginación."""

    def __init__(self, token_bueno='pat-bueno', limite=False):
        self.token_bueno, self.limite, self.pedidos = token_bueno, limite, []

    def __call__(self, metodo, url, headers=None, params=None, json=None, timeout=None):
        self.pedidos.append((metodo, url))
        if headers.get('Authorization') != f'Bearer {self.token_bueno}':
            return Respuesta(status=401)
        if self.limite:
            return Respuesta(status=429, headers={'Retry-After': '10'})
        ruta = url.replace('https://api.hubapi.com', '')
        despues = (params or json or {}).get('after')
        if ruta == '/account-info/v3/details':
            return Respuesta({'portalId': 4242, 'timeZone': 'America/Santiago', 'companyCurrency': 'CLP'})
        if ruta == '/crm/v3/properties/companies':
            return Respuesta({'results': [{'name': 'name'}, {'name': 'rut_empresa'}]})
        listas = {'/crm/v3/objects/companies': EMPRESAS, '/crm/v3/objects/contacts': CONTACTOS,
                  '/crm/v3/objects/deals/search': NEGOCIOS}
        if ruta in listas:
            todos = listas[ruta]
            if despues:
                return Respuesta({'results': todos[1:]})
            return Respuesta({'results': todos[:1], 'paging': {'next': {'after': 'p2'}}})
        if ruta.startswith('/crm/v3/objects/deals/'):
            return Respuesta({'id': ruta.split('/')[-1], 'associations': {'companies': {'results': [{'id': '101'}]}}})
        return Respuesta(status=404)


class HubSpotTests(_Base):
    def setUp(self):
        super().setUp()
        self.url = f'/api/v1/workspaces/{self.org.slug}/conectores/hubspot'
        self.falso = HubSpotFalso()
        self.parche = mock.patch('apps.conectores.hubspot.requests.request', side_effect=self.falso)
        self.parche.start()

    def tearDown(self):
        self.parche.stop()
        super().tearDown()

    def _conectar(self, token='pat-bueno'):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{self.url}/conectar/', {'token': token}, format='json')
        self.client.force_authenticate(self.editor)
        return r

    def test_conectar_con_token_bueno_y_malo(self):
        r = self._conectar('pat-malo')
        self.assertEqual(r.status_code, 400)
        self.assertIn('no reconoce ese token', r.data['detail'])
        r = self._conectar()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.data['estado'], r.data['cuenta']['portal_id']), ('conectado', 4242))
        c = Conexion.objects.get(organization=self.org, tipo='hubspot')
        self.assertEqual(c.secreto, 'pat-bueno')
        self.assertNotIn('pat-bueno', c._secreto)  # cifrado

    def test_sincronizar_trae_clientes_y_cotizacion_sin_duplicar(self):
        self._conectar()
        r = self.client.post(f'{self.url}/sincronizar/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        res = r.data['resumen']
        self.assertEqual(res['empresas']['nuevas'], 1)  # Constructora Andes ya existía (por RUT): se completa
        self.assertEqual(res['contactos']['nuevos'], 1)
        self.assertEqual(res['cotizaciones']['nuevas'], 1)
        self.assertTrue(any('Sin monto' in a for a in res['avisos']))
        andes = Contacto.objects.get(organization=self.org, rut='77111222-3')
        self.assertEqual((andes.persona_contacto, andes.ciudad), ('María Pérez', 'Santiago'))
        self.assertTrue(Contacto.objects.filter(organization=self.org, razon_social='Inmobiliaria Sur', es_cliente=True).exists())
        self.assertTrue(Contacto.objects.filter(organization=self.org, razon_social='Juan Soto', email='juan@correo.test').exists())
        p = Pedido.objects.get(organization=self.org, referencia='HubSpot 301')
        self.assertEqual((p.estado, p.contacto_id, int(p.neto)), (Pedido.BORRADOR, andes.id, 1500000))
        # La segunda vez no duplica nada.
        antes = Contacto.objects.filter(organization=self.org).count()
        r = self.client.post(f'{self.url}/sincronizar/', {}, format='json')
        self.assertEqual(r.data['resumen']['cotizaciones'], {'nuevas': 0, 'ya_estaban': 1})
        self.assertEqual(Contacto.objects.filter(organization=self.org).count(), antes)
        self.assertEqual(Pedido.objects.filter(organization=self.org, referencia='HubSpot 301').count(), 1)
        self.assertEqual(Sincronizacion.objects.filter(conexion__organization=self.org).count(), 2)

    def test_opciones_apagadas_se_respetan(self):
        self._conectar()
        self.client.force_authenticate(self.admin)
        r = self.client.patch(self.url + '/', {'config': {'negocios_a_cotizacion': False, 'importar_contactos': False,
                                                          'otra_cosa': True}}, format='json')
        self.assertNotIn('otra_cosa', r.data['config'])
        self.client.force_authenticate(self.editor)
        res = self.client.post(f'{self.url}/sincronizar/', {}, format='json').data['resumen']
        self.assertEqual((res['contactos']['nuevos'], res['cotizaciones']['nuevas']), (0, 0))
        self.assertFalse(Pedido.objects.filter(organization=self.org, referencia__startswith='HubSpot').exists())
        self.assertFalse(any('/deals/' in u for _, u in self.falso.pedidos))

    def test_permisos(self):
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.post(f'{self.url}/conectar/', {'token': 'pat-bueno'}, format='json').status_code, 403)
        self._conectar()
        self.client.force_authenticate(self.miembro)
        self.assertEqual(self.client.post(f'{self.url}/sincronizar/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.get(f'{self.url}/historial/').status_code, 200)

    def test_limite_de_consultas_se_explica_y_queda_en_el_historial(self):
        self._conectar()
        self.falso.limite = True
        r = self.client.post(f'{self.url}/sincronizar/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('en 10 segundos', r.data['detail'])
        h = self.client.get(f'{self.url}/historial/').data
        self.assertEqual(h[0]['estado'], 'error')
        self.assertEqual(self.client.get(self.url + '/').data['estado'], 'error')

    def test_corre_solo_cada_seis_horas(self):
        self._conectar()
        self.assertEqual(servicio.procesar_programadas(), 1)
        self.assertEqual(servicio.procesar_programadas(), 0)  # recién corrió
        Conexion.objects.filter(organization=self.org).update(ultima_sincronizacion=timezone.now() - timedelta(hours=7))
        self.assertEqual(servicio.procesar_programadas(), 1)
        self.assertTrue(Sincronizacion.objects.filter(automatica=True).exists())
