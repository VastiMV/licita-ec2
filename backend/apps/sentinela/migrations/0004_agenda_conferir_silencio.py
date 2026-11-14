# Agenda no Celery Beat (django_celery_beat, DatabaseScheduler) a tarefa
# `sentinela.conferir_silencio`, a cada 10 minutos (GEN-73, 14/11/2026). Ela
# mesma confere o horário de trabalho. Mesmo padrão de
# apps/capag/migrations/0002_agenda_sync_capag.py.
from django.db import migrations

NOME = "Sentinela: alarme de silêncio"


def criar_agendamento(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    intervalo, _ = IntervalSchedule.objects.get_or_create(every=10, period="minutes")
    PeriodicTask.objects.get_or_create(
        name=NOME,
        defaults={"task": "sentinela.conferir_silencio", "interval": intervalo},
    )


def remover_agendamento(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=NOME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sentinela", "0003_estado_sem_sessao"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(criar_agendamento, remover_agendamento),
    ]
