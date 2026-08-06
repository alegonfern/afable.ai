"""Cliente de PayPal para suscripciones en USD.

Espejo de `flow_client.py`, con la misma forma: un objeto que sabe firmar/autenticar y
un método por operación. Lo que cambia es el mecanismo — Flow firma cada llamada con
HMAC-SHA256, PayPal pide un token OAuth2 y lo manda en el encabezado.

**Por qué PayPal además de Flow:** Flow liquida en pesos chilenos y sirve a quien tiene
medios de pago chilenos. Para cobrarle a alguien de afuera hay que cobrar en dólares, y
esa es toda la razón de que existan dos pasarelas.

**Cómo se cobra una suscripción en PayPal**, que no es obvio y explica los tres pasos de
abajo: hay que crear un *producto* (qué se vende), después un *plan de facturación*
(cuánto y cada cuánto) y recién entonces una *suscripción* para una persona. Los dos
primeros se crean una vez por plan de Afable y se reusan; `asegurar_plan` es lo que
evita crearlos de nuevo en cada alta.

**La persona tiene que aprobar.** Crear la suscripción no cobra nada: devuelve un enlace
de aprobación al que hay que mandarla. Hasta que vuelva aprobada, la suscripción no da
acceso — por eso `Subscription.aprobada` existe.
"""

import base64
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PAYPAL_SANDBOX_URL = 'https://api-m.sandbox.paypal.com'
PAYPAL_PROD_URL = 'https://api-m.paypal.com'

# PayPal cobra cada mes; el plan de Afable también. Si algún día hay plan anual, esto
# pasa a ser un campo del Plan.
INTERVALO = 'MONTH'


class PayPalError(Exception):
    """Algo salió mal hablando con PayPal.

    Existe para que las vistas puedan distinguir "PayPal dijo que no" de un error de
    programación nuestro, y contestar 502 en vez de 500.
    """


class PayPalClient:
    def __init__(self):
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.secret = settings.PAYPAL_SECRET
        self.base_url = PAYPAL_SANDBOX_URL if settings.PAYPAL_SANDBOX else PAYPAL_PROD_URL
        self._token = None

    # ── Plomería ─────────────────────────────────────────────────────────────────

    @property
    def configurado(self):
        """Si hay credenciales. Sin esto, la pantalla ofrecería un botón que revienta."""
        return bool(self.client_id and self.secret)

    def _access_token(self):
        """Token OAuth2. Se pide una vez por instancia del cliente.

        No se cachea entre requests a propósito: un token guardado en memoria del
        proceso se vuelve una fuente de errores raros cuando expira o cuando corren
        varios trabajadores, y pedirlo cuesta una llamada.
        """
        if self._token:
            return self._token
        if not self.configurado:
            raise PayPalError('Falta configurar PAYPAL_CLIENT_ID y PAYPAL_SECRET.')

        credenciales = base64.b64encode(f'{self.client_id}:{self.secret}'.encode()).decode()
        try:
            resp = requests.post(
                f'{self.base_url}/v1/oauth2/token',
                headers={
                    'Authorization': f'Basic {credenciales}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                data={'grant_type': 'client_credentials'},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise PayPalError(f'PayPal no autenticó: {e}') from e

        self._token = resp.json().get('access_token')
        if not self._token:
            raise PayPalError('PayPal no devolvió un token de acceso.')
        return self._token

    def _request(self, metodo, endpoint, payload=None):
        try:
            resp = requests.request(
                metodo,
                f'{self.base_url}{endpoint}',
                headers={
                    'Authorization': f'Bearer {self._access_token()}',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=30,
            )
        except requests.RequestException as e:
            raise PayPalError(f'PayPal no respondió: {e}') from e

        if resp.status_code >= 400:
            # El cuerpo de PayPal trae el motivo real ("PLAN_ALREADY_EXISTS", etc.) y
            # sin él el error que ve el usuario no dice nada.
            logger.warning('PayPal %s %s → %s %s', metodo, endpoint, resp.status_code, resp.text[:500])
            raise PayPalError(f'PayPal respondió {resp.status_code}: {resp.text[:300]}')

        # Cancelar una suscripción devuelve 204 sin cuerpo.
        if not resp.content:
            return {}
        return resp.json()

    # ── Producto y plan ──────────────────────────────────────────────────────────

    def asegurar_producto(self, product_id, nombre, descripcion=''):
        """El producto, creándolo si es la primera vez.

        PayPal contesta 409 si ya existe; eso no es un error para nosotros, es el
        camino normal a partir del segundo cliente.
        """
        try:
            return self._request('GET', f'/v1/catalogs/products/{product_id}')
        except PayPalError:
            pass
        return self._request('POST', '/v1/catalogs/products', {
            'id': product_id,
            'name': nombre,
            'description': descripcion or nombre,
            'type': 'SERVICE',
            'category': 'SOFTWARE',
        })

    def asegurar_plan(self, plan_id, product_id, nombre, precio_usd, dias_de_prueba=0):
        """El plan de facturación, creándolo si no está.

        `plan_id` es el nuestro (`afable_growth_monthly`), no el que genera PayPal:
        así se puede volver a encontrar sin guardar otro identificador.
        """
        existente = self._buscar_plan(plan_id)
        if existente:
            return existente

        ciclos = []
        if dias_de_prueba:
            # PayPal cuenta la prueba en días sólo si el ciclo es DAY; un mes de
            # prueba con `MONTH` cobraría de más al que probó 14 días.
            ciclos.append({
                'tenure_type': 'TRIAL',
                'sequence': 1,
                'total_cycles': 1,
                'frequency': {'interval_unit': 'DAY', 'interval_count': dias_de_prueba},
                'pricing_scheme': {'fixed_price': {'value': '0', 'currency_code': 'USD'}},
            })
        ciclos.append({
            'tenure_type': 'REGULAR',
            'sequence': len(ciclos) + 1,
            # 0 = para siempre, hasta que alguien cancele.
            'total_cycles': 0,
            'frequency': {'interval_unit': INTERVALO, 'interval_count': 1},
            'pricing_scheme': {
                'fixed_price': {'value': f'{int(precio_usd)}', 'currency_code': 'USD'},
            },
        })

        return self._request('POST', '/v1/billing/plans', {
            'product_id': product_id,
            'name': nombre,
            'billing_cycles': ciclos,
            'payment_preferences': {'auto_bill_outstanding': True},
        })

    def _buscar_plan(self, plan_id):
        """El plan por su id, o None. PayPal no distingue "no existe" de otros 404."""
        try:
            return self._request('GET', f'/v1/billing/plans/{plan_id}')
        except PayPalError:
            return None

    # ── Suscripción ──────────────────────────────────────────────────────────────

    def crear_suscripcion(self, plan_id, email, url_retorno, url_cancelacion, nombre_empresa=''):
        """Crea la suscripción y devuelve `(id, url_de_aprobacion)`.

        No cobra nada todavía: hasta que la persona apruebe en el enlace, esto es una
        intención de pago.
        """
        payload = {
            'plan_id': plan_id,
            'subscriber': {'email_address': email},
            'application_context': {
                'brand_name': nombre_empresa or 'Afable',
                'locale': 'es-CL',
                'shipping_preference': 'NO_SHIPPING',
                # Que el botón diga "suscribirse" y no "continuar": la persona tiene
                # que entender que está autorizando un cobro que se repite.
                'user_action': 'SUBSCRIBE_NOW',
                'return_url': url_retorno,
                'cancel_url': url_cancelacion,
            },
        }
        data = self._request('POST', '/v1/billing/subscriptions', payload)
        aprobacion = next(
            (l['href'] for l in data.get('links', []) if l.get('rel') == 'approve'), '',
        )
        if not aprobacion:
            raise PayPalError('PayPal creó la suscripción sin enlace de aprobación.')
        return data.get('id', ''), aprobacion

    def obtener_suscripcion(self, subscription_id):
        return self._request('GET', f'/v1/billing/subscriptions/{subscription_id}')

    def cancelar_suscripcion(self, subscription_id, motivo='Cancelada desde Afable'):
        return self._request(
            'POST', f'/v1/billing/subscriptions/{subscription_id}/cancel', {'reason': motivo},
        )

    # ── Webhook ──────────────────────────────────────────────────────────────────

    def verificar_webhook(self, headers, cuerpo_crudo):
        """Le pregunta a PayPal si ese aviso lo mandó PayPal.

        Se verifica contra su API en vez de validar la firma acá: la verificación
        local exige descargar y cachear el certificado de PayPal, y una firma mal
        validada es peor que no validar, porque da confianza falsa.

        Sin `PAYPAL_WEBHOOK_ID` devuelve False: un webhook que no se puede verificar
        no se procesa. Aceptarlo sería dejar que cualquiera active suscripciones
        mandando un POST.
        """
        if not settings.PAYPAL_WEBHOOK_ID:
            logger.warning('Llegó un webhook de PayPal pero falta PAYPAL_WEBHOOK_ID.')
            return False

        payload = {
            'transmission_id': headers.get('Paypal-Transmission-Id', ''),
            'transmission_time': headers.get('Paypal-Transmission-Time', ''),
            'cert_url': headers.get('Paypal-Cert-Url', ''),
            'auth_algo': headers.get('Paypal-Auth-Algo', ''),
            'transmission_sig': headers.get('Paypal-Transmission-Sig', ''),
            'webhook_id': settings.PAYPAL_WEBHOOK_ID,
            'webhook_event': cuerpo_crudo,
        }
        try:
            data = self._request('POST', '/v1/notifications/verify-webhook-signature', payload)
        except PayPalError:
            return False
        return data.get('verification_status') == 'SUCCESS'
