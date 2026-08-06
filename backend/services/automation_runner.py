"""
Ejecución de Automatizaciones y Rutinas.

Ambas corren el MISMO agente del chat (run_agent_live: tool-use con datos
reales de los sistemas conectados) con el mismo system prompt que usa el chat
(_build_onboarding_context), así el resultado es idéntico a preguntarlo a mano.

Usado por:
- el comando `run_automations` (scheduler: las vencidas por intervalo)
- los endpoints "ejecutar ahora" de la UI
"""
import logging
import re

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

_MAX_RESULT_CHARS = 8000       # tope al guardar resultados en BD
_STEP_CONTEXT_CHARS = 3000     # tope del contexto que un paso hereda del anterior
_IMG_RE = re.compile(r'!\[([^\]]*)\]\(data:image/[^)]+\)')


def _strip_images(text: str) -> str:
    """Los gráficos van embebidos en base64: fuera del correo y del contexto entre pasos."""
    return _IMG_RE.sub(r'[gráfico: \1]', text or '')


def _run_prompt(user, organization, prompt: str, agent=None) -> str:
    """Ejecuta un prompt con el agente del chat y devuelve el texto final."""
    from apps.agents.views import _build_onboarding_context
    from services.agent_service import run_agent_live, chat_direct

    # El prompt de la automatizacion hace de consulta: si el corpus de documentos no
    # cabe en el contexto, es lo que decide que fragmentos entran.
    ctx = _build_onboarding_context(user, agent, consulta=prompt)
    system_prompt = ctx.get('system_prompt', '')
    if ctx.get('mode') == 'con_herramientas':
        salida = run_agent_live(
            [{'role': 'user', 'content': prompt}], organization, system_prompt,
            model=ctx.get('agent_model'), allowed_ids=ctx.get('allowed_ids'),
            allowed_doc_ids=ctx.get('allowed_doc_ids'), agente=agent,
        )
    else:
        salida = chat_direct([{'role': 'user', 'content': prompt}], system_prompt)
    return _limpiar_para_leer(salida)


def _limpiar_para_leer(texto: str) -> str:
    """Saca del texto lo que es protocolo y no respuesta.

    Por acá salen las Tareas y las Automatizaciones: nadie ejecuta acciones ni
    herramientas con este resultado, se lee y se guarda. El chat sí las ejecuta, y por
    eso limpia recién después de extraerlas — acá hay que hacerlo nosotros.

    Sin esto, el resultado de una Tarea ejecutada por un agente llegaba con
    `__ACTION__{"type":"search",...}` pegado adelante: el modelo intenta invocar
    escribiendo, porque no todos usan el campo `tool_calls`.
    """
    from apps.agents.views import _strip_action
    from services.agent_service import _quitar_llamadas_visibles

    return _quitar_llamadas_visibles(_strip_action(texto or '')).strip()


def publicar_en_sesion(automation, texto: str, titulo: str = ''):
    """El agente abre una conversación en la Sesión con lo que encontró.

    Esto es lo que vuelve al agente un miembro del equipo y no una herramienta: la
    conversación aparece en el feed de la Sesión como cualquier otra, la ve todo el que
    entra, y NADIE la pidió. Antes el resultado se iba por correo a una sola persona y el
    equipo no se enteraba.

    Se escriben los dos turnos —el encargo y la respuesta— y no solo la respuesta, porque
    quien lo lee tres días después necesita saber qué se le había pedido. Y queda marcada
    con `autonoma` para que el feed pueda decir que la trajo el agente solo.
    """
    from apps.agents.models import Conversation, Message

    agente = automation.agent or _agente_por_omision(automation.organization)
    if agente is None:
        # Sin ningún agente en la empresa no hay a quién atribuirle el hilo, y
        # `Conversation.agent` no admite vacío.
        raise RuntimeError('La empresa no tiene ningún agente con el que publicar.')

    conv = Conversation.objects.create(
        agent=agente, sesion=automation.sesion, user=automation.user,
        title=(titulo or automation.name)[:500], autonoma=True,
    )
    Message.objects.create(
        conversation=conv, role='user',
        content=automation.prompt or f'Encargo permanente: {automation.name}',
    )
    Message.objects.create(
        conversation=conv, role='assistant', content=texto, agent=agente,
    )
    return conv


def _agente_por_omision(organization):
    from apps.agents.models import Agent

    return Agent.objects.filter(organization=organization, is_active=True).first()


def anotar_tarea(automation, texto: str):
    """Deja el pendiente anotado en la Sesión, con el resultado adentro.

    Para los encargos que terminan en algo que alguien tiene que hacer: "avisame si hay
    facturas sin pagar" no se resuelve leyendo el aviso, se resuelve pagándolas. La tarea
    nace ya con el resultado y firmada por el agente, así que el equipo ve de dónde salió.
    """
    from apps.sesiones.models import Task

    return Task.objects.create(
        sesion=automation.sesion,
        title=automation.name[:255],
        description=automation.prompt or '',
        agent=automation.agent or _agente_por_omision(automation.organization),
        resultado=texto[:_MAX_RESULT_CHARS],
        ejecutada_at=timezone.now(),
        # `created_by` vacío a propósito: NADIE la escribió, la dejó el agente. Es el
        # mismo par que usa la herramienta `crear_tarea` (`created_by` vacío + `agent`
        # puesto) para que las dos vías se lean igual en la lista. Quién configuró el
        # encargo se ve en el Disparador, que es donde importa.
    )


def entregar(automation, texto: str, asunto: str = '') -> str:
    """Manda el resultado a donde el encargo dijo. Devuelve el error si algo falló.

    Los destinos conviven: el correo avisa afuera, la Sesión deja el registro adentro. Se
    intentan los dos por separado a propósito — que falle el SMTP no puede hacer perder la
    publicación, que es la que queda guardada.
    """
    problemas = []

    if automation.sesion_id:
        try:
            publicar_en_sesion(automation, texto, asunto)
            if automation.crear_tarea:
                anotar_tarea(automation, texto)
        except Exception as e:
            logger.exception('Automation %s: fallo publicando en la Sesión', automation.id)
            problemas.append(f'no se pudo publicar en la Sesión: {e}')

    if automation.notify_email:
        try:
            _send_result_email(
                automation.notify_email, f'Afable — {asunto or automation.name}', texto,
            )
        except Exception as e:
            logger.exception('Automation %s: fallo enviando correo', automation.id)
            problemas.append(f'falló el correo: {e}')

    return ('Se ejecutó pero ' + '; '.join(problemas))[:500] if problemas else ''


def _send_result_email(to_email: str, subject: str, body: str):
    send_mail(
        subject=subject,
        message=_strip_images(body),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'afable@localhost'),
        recipient_list=[to_email],
        fail_silently=False,
    )


def execute_automation(automation, contexto_extra: str = '') -> dict:
    """
    Corre una Automation y persiste el resultado.
    Devuelve {ok, result|error} y, en las de evento, 'fired' (si disparó o no).

    `contexto_extra` es lo que trae el disparador cuando trae algo: hoy, el cuerpo
    que mandó el sistema externo por webhook. Va antes del prompt para que el agente
    conteste SOBRE ese aviso y no en abstracto.
    """
    if automation.trigger_type == 'event':
        return _execute_event_automation(automation)
    automation.last_run_at = timezone.now()
    automation.run_count += 1
    try:
        prompt = automation.prompt
        if contexto_extra:
            prompt = (
                'Otro sistema avisó de algo y esto es lo que mandó:\n\n'
                f'{contexto_extra}\n\n'
                f'Con eso a la vista: {automation.prompt}'
            )
        result = _run_prompt(
            automation.user, automation.organization, prompt, agent=automation.agent,
        )
        automation.last_result = result[:_MAX_RESULT_CHARS]
        automation.last_error = entregar(automation, result)
        automation.save()
        return {'ok': True, 'result': automation.last_result, 'error': automation.last_error}
    except Exception as e:
        logger.exception('Automation %s falló', automation.id)
        automation.last_error = str(e)[:500]
        automation.save()
        return {'ok': False, 'error': automation.last_error}


def _execute_event_automation(automation) -> dict:
    """
    Revisa el evento (snapshot vs estado actual). Si no dispara, solo actualiza
    el snapshot en silencio (no cuenta como ejecución). Si dispara: correo con
    el detalle y, si hay prompt, se ejecuta el agente con el evento como contexto.
    """
    from services.event_detector import check_event

    automation.last_run_at = timezone.now()
    check = check_event(automation)  # actualiza automation.event_state

    if check['error']:
        automation.last_error = check['error'][:500]
        automation.save()
        return {'ok': False, 'fired': False, 'error': automation.last_error}

    if not check['fired']:
        automation.last_error = ''
        automation.save()
        return {'ok': True, 'fired': False, 'result': '', 'error': ''}

    automation.run_count += 1
    body = check['details']
    try:
        if automation.prompt.strip():
            full_prompt = (
                f"EVENTO DETECTADO EN LOS SISTEMAS CONECTADOS:\n{check['details']}\n\n---\n\n"
                f"TAREA (a raíz de este evento):\n{automation.prompt}"
            )
            result = _run_prompt(
                automation.user, automation.organization, full_prompt,
                agent=automation.agent,
            )
            body = f"{check['details']}\n\n---\n\n{result}"
        automation.last_result = body[:_MAX_RESULT_CHARS]
        # Mismo camino que el encargo programado: si hay Sesión, el equipo se entera del
        # evento ahí. Antes el aviso solo existía en la casilla de una persona.
        automation.last_error = entregar(automation, body)
        automation.save()
        return {'ok': True, 'fired': True, 'result': automation.last_result, 'error': automation.last_error}
    except Exception as e:
        logger.exception('Automation %s falló ejecutando el prompt del evento', automation.id)
        automation.last_result = check['details'][:_MAX_RESULT_CHARS]
        automation.last_error = str(e)[:500]
        automation.save()
        return {'ok': False, 'fired': True, 'error': automation.last_error}


def execute_routine(routine) -> dict:
    """
    Corre los pasos de una Routine en orden. El resultado de cada paso se
    inyecta como contexto del siguiente. Un paso que falla corta la rutina.
    Devuelve {ok, steps_results, error}.
    """
    from apps.agents.models import Agent

    routine.last_run_at = timezone.now()
    routine.run_count += 1
    steps_results = []
    prev_context = ''

    try:
        for i, step in enumerate(routine.steps, start=1):
            prompt = (step.get('prompt') or '').strip()
            if not prompt:
                continue
            agent = None
            if step.get('agent_id'):
                agent = Agent.objects.filter(id=step['agent_id'], user=routine.user).first()

            full_prompt = prompt
            if prev_context:
                full_prompt = (
                    f"RESULTADO DEL PASO ANTERIOR DE LA RUTINA (úsalo como insumo):\n"
                    f"{prev_context}\n\n---\n\nTAREA DE ESTE PASO:\n{prompt}"
                )

            result = _run_prompt(routine.user, routine.organization, full_prompt, agent)
            clean = _strip_images(result)
            steps_results.append({
                'step': i, 'prompt': prompt,
                'agent': agent.name if agent else None,
                'result': result[:_MAX_RESULT_CHARS], 'error': '',
            })
            prev_context = clean[:_STEP_CONTEXT_CHARS]

        routine.last_steps_results = steps_results
        routine.last_error = ''

        if routine.notify_email and steps_results:
            body_parts = [f'Rutina «{routine.name}» — {len(steps_results)} pasos ejecutados:\n']
            for r in steps_results:
                who = f' (agente: {r["agent"]})' if r['agent'] else ''
                body_parts.append(f'── Paso {r["step"]}{who}: {r["prompt"]}\n\n{_strip_images(r["result"])}\n')
            try:
                _send_result_email(routine.notify_email, f'Afable — Rutina: {routine.name}', '\n'.join(body_parts))
            except Exception as e:
                logger.exception('Routine %s: fallo enviando correo', routine.id)
                routine.last_error = f'Se ejecutó pero falló el correo: {e}'

        routine.save()
        return {'ok': True, 'steps_results': steps_results, 'error': routine.last_error}
    except Exception as e:
        logger.exception('Routine %s falló en el paso %d', routine.id, len(steps_results) + 1)
        steps_results.append({
            'step': len(steps_results) + 1, 'prompt': '', 'agent': None,
            'result': '', 'error': str(e)[:500],
        })
        routine.last_steps_results = steps_results
        routine.last_error = str(e)[:500]
        routine.save()
        return {'ok': False, 'steps_results': steps_results, 'error': routine.last_error}
