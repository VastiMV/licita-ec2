# Agenda a task `licitacoes.sincronizar_transparencia` no Celery Beat todo
# dia às 8h10, horário de Brasília — 10 minutos depois da sincronia com o
# PNCP, que traz as licitações ganhas às quais os empenhos se ligam.
from django.db import migrations

NOME = "Sincronizar empenhos e pagamentos no Portal da Transparência"


def criar_agendamento(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    horario, _ = CrontabSchedule.objects.get_or_create(
        minute="10",
        hour="8",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="America/Sao_Paulo",
    )
    PeriodicTask.objects.get_or_create(
        name=NOME,
        defaults={"task": "licitacoes.sincronizar_transparencia", "crontab": horario},
    )


def remover_agendamento(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=NOME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("licitacoes", "0008_processo_e_documento_sem_licitacao"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(criar_agendamento, remover_agendamento),
    ]
