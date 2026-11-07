# Agenda a task `licitacoes.sincronizar_pncp` no Celery Beat (DatabaseScheduler)
# todo dia às 8h, horário de Brasília — antes de a operação começar o dia.
# Mesmo padrão de apps/capag/migrations/0002_agenda_sync_capag.py.
from django.db import migrations

NOME = "Sincronizar vitórias e atas no PNCP"


def criar_agendamento(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    horario, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="8",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="America/Sao_Paulo",
    )
    PeriodicTask.objects.get_or_create(
        name=NOME,
        defaults={"task": "licitacoes.sincronizar_pncp", "crontab": horario},
    )


def remover_agendamento(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=NOME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("licitacoes", "0006_torre_de_controle"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(criar_agendamento, remover_agendamento),
    ]
