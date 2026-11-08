"""As sincronias do PNCP e do Portal da Transparência só em dias úteis.

Fim de semana não tem movimentação (decisão da operação, 08/11/2026): de
segunda a sexta, nos mesmos horários (8h e 8h10, Brasília).
"""

from django.db import migrations
from django.utils import timezone

TAREFAS = {
    "licitacoes.sincronizar_pncp": ("0", "8"),
    "licitacoes.sincronizar_transparencia": ("10", "8"),
}


def mudar_dias(dias):
    def aplicar(apps, schema_editor):
        CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
        PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
        for task, (minuto, hora) in TAREFAS.items():
            horario, _ = CrontabSchedule.objects.get_or_create(
                minute=minuto,
                hour=hora,
                day_of_week=dias,
                day_of_month="*",
                month_of_year="*",
                timezone="America/Sao_Paulo",
            )
            PeriodicTask.objects.filter(task=task).update(crontab=horario)
        # `update()` não dispara os sinais do django-celery-beat: avisa o
        # agendador à mão, senão ele segue com a agenda antiga até reiniciar.
        PeriodicTasks = apps.get_model("django_celery_beat", "PeriodicTasks")
        PeriodicTasks.objects.update_or_create(ident=1, defaults={"last_update": timezone.now()})

    return aplicar


class Migration(migrations.Migration):
    dependencies = [
        ("licitacoes", "0009_agenda_sincronia_transparencia"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [migrations.RunPython(mudar_dias("1-5"), mudar_dias("*"))]
