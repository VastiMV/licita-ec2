# Agenda a `licitacoes.conferencia_diaria` (09/11/2026): seg–sex às 7h45,
# Brasília — antes da primeira ronda da Sentinela e das sincronias das 8h.
from django.db import migrations

NOME = "Conferência diária (PNCP, acompanhadas, fim da vigia)"


def criar_agendamento(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    horario, _ = CrontabSchedule.objects.get_or_create(
        minute="45",
        hour="7",
        day_of_week="1-5",
        day_of_month="*",
        month_of_year="*",
        timezone="America/Sao_Paulo",
    )
    PeriodicTask.objects.get_or_create(
        name=NOME,
        defaults={"task": "licitacoes.conferencia_diaria", "crontab": horario},
    )


def remover_agendamento(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=NOME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("licitacoes", "0017_vigia_acompanhados_e_pncp"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [migrations.RunPython(criar_agendamento, remover_agendamento)]
