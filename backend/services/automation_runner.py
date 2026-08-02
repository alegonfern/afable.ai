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

    ctx = _build_onboarding_context(user, agent)
    system_prompt = ctx.get('system_prompt', '')
    if ctx.get('mode') == 'connected_systems':
        return run_agent_live(
            [{'role': 'user', 'content': prompt}], organization, system_prompt,
            model=ctx.get('agent_model'), allowed_ids=ctx.get('allowed_ids'),
        )
    return chat_direct([{'role': 'user', 'content': prompt}], system_prompt)


def _send_result_email(to_email: str, subject: str, body: str):
    send_mail(
        subject=subject,
        message=_strip_images(body),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'afable@localhost'),
        recipient_list=[to_email],
        fail_silently=False,
    )


def execute_automation(automation) -> dict:
    """
    Corre una Automation y persiste el resultado.
    Devuelve {ok, result|error} y, en las de evento, 'fired' (si disparó o no).
    """
    if automation.trigger_type == 'event':
        return _execute_event_automation(automation)
    automation.last_run_at = timezone.now()
    automation.run_count += 1
    try:
        result = _run_prompt(automation.user, automation.organization, automation.prompt)
        automation.last_result = result[:_MAX_RESULT_CHARS]
        automation.last_error = ''
        try:
            _send_result_email(
                automation.notify_email,
                f'Afable — {automation.name}',
                result,
            )
        except Exception as e:
            logger.exception('Automation %s: fallo enviando correo', automation.id)
            automation.last_error = f'Se ejecutó pero falló el correo: {e}'
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
            result = _run_prompt(automation.user, automation.organization, full_prompt)
            body = f"{check['details']}\n\n---\n\n{result}"
        automation.last_result = body[:_MAX_RESULT_CHARS]
        automation.last_error = ''
        try:
            _send_result_email(automation.notify_email, f'Afable — {automation.name}', body)
        except Exception as e:
            logger.exception('Automation %s: fallo enviando correo', automation.id)
            automation.last_error = f'El evento disparó pero falló el correo: {e}'
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
