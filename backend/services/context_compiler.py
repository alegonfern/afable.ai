"""
Compila los ContextCubicle de una organización en un único documento Markdown
y lo persiste como archivo real en disco (media/contexto/org_<id>.md).

Existe para que alguien sin ninguna idea de "contexto de IA" / Copilot pueda
ver con sus propios ojos, en un archivo de verdad, de dónde sale exactamente
lo que el agente sabe de su empresa — no es una caja negra.
"""
import os
from django.conf import settings


def compile_context_markdown(org) -> str:
    from apps.organizations.models import ContextCubicle

    cubicles = ContextCubicle.objects.filter(organization=org)
    lines = [f"# Contexto de {org.name}", ""]
    if not cubicles.exists():
        lines.append(
            "_Todavía no hay cubículos de contexto. Agrega el primero para "
            "que este archivo empiece a llenarse._"
        )
    else:
        for c in cubicles:
            lines.append(f"## {c.title}")
            lines.append("")
            lines.append(c.content)
            lines.append("")
    return "\n".join(lines)


def write_context_markdown_file(org) -> str:
    content = compile_context_markdown(org)
    directory = os.path.join(settings.MEDIA_ROOT, 'contexto')
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f'org_{org.id}.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path
