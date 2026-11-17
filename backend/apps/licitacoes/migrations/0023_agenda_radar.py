# Agenda o `licitacoes.radar` (GEN-68, 14/11/2026): todo dia às 8h e às 18h,
# Brasília (decisão da operação, cartão GEN-68).
from django.db import migrations

NOME = "Radar (compras parecidas com as salvas e as ganhas)"


def criar_agendamento(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    horario, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="8,18",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="America/Sao_Paulo",
    )
    PeriodicTask.objects.get_or_create(name=NOME, defaults={"task": "licitacoes.radar", "crontab": horario})


def remover_agendamento(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=NOME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("licitacoes", "0022_radar"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [migrations.RunPython(criar_agendamento, remover_agendamento)]
