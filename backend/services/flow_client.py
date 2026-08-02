import hashlib
import hmac
import requests
from django.conf import settings

FLOW_SANDBOX_URL = 'https://sandbox.flow.cl/api'
FLOW_PROD_URL = 'https://www.flow.cl/api'


class FlowClient:
    def __init__(self):
        self.api_key = settings.FLOW_API_KEY
        self.secret_key = settings.FLOW_SECRET_KEY
        self.base_url = FLOW_SANDBOX_URL if settings.FLOW_SANDBOX else FLOW_PROD_URL

    def _sign(self, params: dict) -> str:
        sorted_keys = sorted(params.keys())
        to_sign = ''.join(f'{k}{params[k]}' for k in sorted_keys)
        return hmac.new(self.secret_key.encode(), to_sign.encode(), hashlib.sha256).hexdigest()

    def _post(self, endpoint: str, params: dict) -> dict:
        params['apiKey'] = self.api_key
        params['signature'] = self._sign(params)
        resp = requests.post(f'{self.base_url}{endpoint}', data=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _get(self, endpoint: str, params: dict) -> dict:
        params['apiKey'] = self.api_key
        params['signature'] = self._sign(params)
        resp = requests.get(f'{self.base_url}{endpoint}', params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def create_payment(self, commerce_order, subject, amount, email, url_confirmation, url_return):
        params = {
            'commerceOrder': str(commerce_order),
            'subject': subject,
            'currency': 'CLP',
            'amount': str(int(amount)),
            'email': email,
            'urlConfirmation': url_confirmation,
            'urlReturn': url_return,
        }
        return self._post('/payment/create', params)

    def get_payment_status(self, token):
        return self._get('/payment/getStatus', {'token': token})

    def create_plan(self, plan_id, name, amount, interval, interval_count=1, trial_period_days=0):
        params = {
            'planId': plan_id,
            'name': name,
            'amount': str(int(amount)),
            'currency': 'CLP',
            'interval': str(interval),
            'interval_count': str(interval_count),
            'trial_period_days': str(trial_period_days),
        }
        return self._post('/plans/create', params)

    def create_customer(self, name, email, external_id):
        params = {
            'name': name,
            'email': email,
            'externalId': str(external_id),
        }
        return self._post('/customer/create', params)

    def subscribe(self, customer_id, plan_id, trial_period_days=14):
        params = {
            'customerId': customer_id,
            'planId': plan_id,
            'trial_period_days': str(trial_period_days),
        }
        return self._post('/subscription/create', params)

    def cancel_subscription(self, subscription_id):
        return self._post('/subscription/cancel', {'subscriptionId': subscription_id})

    def get_subscription(self, subscription_id):
        return self._get('/subscription/get', {'subscriptionId': subscription_id})
