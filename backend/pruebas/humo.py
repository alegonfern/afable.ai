"""Ejecuta las acciones de escritura de la app y reporta las que revientan.

No busca 4xx (esos son respuestas legitimas: falta un campo, no tiene permiso). Busca
**500**: el camino que nadie recorrio desde la cirugia y que revienta al primer intento.
"""
import json, urllib.request, urllib.error

BASE = 'http://localhost:8001/api/v1'

def pedir(metodo, ruta, token, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(f'{BASE}{ruta}', data=datos, method=metodo)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e)[:200]

tok = json.loads(pedir('POST', '/auth/login/', '', 
      {'email': 'alegonfern@gmail.com', 'password': 'afable123'})[1])['access']
EMP = 'workspace-de-alexis'

acciones = [
    ('crear Workspace',      'POST',   f'/workspaces/{EMP}/espacios/', {'name': 'Humo', 'visibility': 'abierto'}),
    ('invitar persona',      'POST',   f'/workspaces/{EMP}/invitations/', {'email': 'humo@afable.test', 'role': 'miembro'}),
    ('editar empresa',       'PATCH',  f'/workspaces/{EMP}/', {'description': 'prueba de humo'}),
    ('crear Sesion',         'POST',   '/sesiones/', {'workspace': EMP, 'name': 'Humo'}),
    ('crear agente',         'POST',   '/agents/constructor/', {'workspace': EMP, 'name': 'Humo', 'instructions': 'Prueba.'}),
    ('crear habilidad',      'POST',   '/agents/habilidades/', {'name': 'Humo', 'instructions': 'Prueba.'}),
    ('crear disparador',     'POST',   '/agents/automations/', {'name': 'Humo', 'prompt': 'x', 'interval_minutes': 1440, 'notify_email': 'a@b.cl'}),
    ('crear carpeta',        'POST',   f'/archivos/carpetas/?workspace={EMP}', {'nombre': 'Humo', 'workspace': EMP}),
    ('explorador',           'GET',    f'/archivos/?workspace={EMP}', None),
    ('compartir archivo',    'POST',   f'/archivos/compartir/?workspace={EMP}', {'workspace': EMP}),
    ('facturacion: estado',  'GET',    f'/workspaces/{EMP}/facturacion/', None),
    ('suscribir',            'POST',   f'/workspaces/{EMP}/facturacion/suscribir/', {'plan_id': 'afable_starter_monthly'}),
    ('primeros pasos',       'POST',   f'/workspaces/{EMP}/primeros-pasos/', {'mostrar': True}),
    ('mensaje a soporte',    'POST',   '/soporte/', {'texto': 'prueba de humo'}),
    ('chat directo',         'POST',   '/agents/direct-chat/', {'message': 'hola', 'workspace': EMP}),
    ('tareas del workspace', 'GET',    f'/tareas/?workspace={EMP}', None),
    ('galeria de agentes',   'GET',    f'/agents/gallery/?workspace={EMP}', None),
    ('feed de la Sesion',    'GET',    f'/sesiones/cliente-rever/feed/?workspace={EMP}', None),
    ('tareas de la Sesion',  'POST',   f'/sesiones/cliente-rever/tareas/', {'workspace': EMP, 'title': 'Humo'}),
    ('conexiones',           'GET',    '/organizations/connections/', None),
    ('contexto de empresa',  'GET',    '/organizations/dashboard/', None),
    ('modelos',              'GET',    '/agents/models/', None),
    ('conversaciones',       'GET',    '/agents/conversations/', None),
]

print(f'{"":3} {"accion":24} {"codigo"}')
malos = []
for nombre, metodo, ruta, cuerpo in acciones:
    codigo, cuerpo_resp = pedir(metodo, ruta, tok, cuerpo)
    marca = '💥' if codigo in (0, 500) else ('  ' if codigo < 400 else '· ')
    print(f'{marca} {nombre:24} {codigo}')
    if codigo in (0, 500):
        malos.append((nombre, ruta, cuerpo_resp[:160]))

print()
print('REVIENTAN:', len(malos))
for n, r, c in malos:
    print(f'  · {n} ({r})')
