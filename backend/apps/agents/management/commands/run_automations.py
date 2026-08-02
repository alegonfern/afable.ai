"""
Corredor de Automatizaciones y Rutinas programadas.

Corre como proceso aparte (servicio `automations` en docker-compose): cada
CHECK_SECONDS revisa qué Automations/Routines están vencidas según su
intervalo y las ejecuta. Con --once hace una sola pasada (útil para probar).
"""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

CHECK_SECONDS = 30


class Command(BaseCommand):
    help = 'Ejecuta las automatizaciones y rutinas vencidas según su intervalo.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Una sola pasada y salir.')

    def handle(self, *args, **options):
        self.stdout.write('Corredor de automatizaciones iniciado (revisa cada %ss).' % CHECK_SECONDS)
        while True:
            self._tick()
            if options['once']:
                break
            time.sleep(CHECK_SECONDS)

    def _tick(self):
        from apps.agents.models import Automation, Routine
        from services.automation_runner import execute_automation, execute_routine
        from services.drive_sync import sync_due_connections

        now = timezone.now()

        sync_due_connections()

        for automation in Automation.objects.filter(is_active=True)\
                                            .select_related('user', 'organization', 'connection'):
            if not automation.is_due(now):
                continue
            self.stdout.write(f'→ Automatización #{automation.id} «{automation.name}»...')
            out = execute_automation(automation)
            if not out['ok']:
                self.stdout.write(self.style.ERROR(f'  error: {out["error"]}'))
            elif automation.trigger_type == 'event' and not out.get('fired'):
                self.stdout.write('  sin cambios')
            else:
                self.stdout.write(self.style.SUCCESS('  ok (evento disparado)'
                                                     if automation.trigger_type == 'event' else '  ok'))

        for routine in Routine.objects.filter(is_active=True, interval_minutes__isnull=False)\
                                      .select_related('user', 'organization'):
            if not routine.is_due(now):
                continue
            self.stdout.write(f'→ Rutina #{routine.id} «{routine.name}»...')
            out = execute_routine(routine)
            self.stdout.write(self.style.SUCCESS(f'  ok ({len(out["steps_results"])} pasos)') if out['ok']
                              else self.style.ERROR(f'  error: {out["error"]}'))
