"""`manage.py sincronizar_pncp` — roda a sincronia com o PNCP na hora, sem
depender de Celery/RabbitMQ. Útil para trazer as vitórias logo depois do
deploy, sem esperar as 8h do dia seguinte."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.licitacoes.sincronia_pncp import sincronizar_pncp


class Command(BaseCommand):
    help = "Traz do PNCP os itens ganhos e as atas de cada CNPJ ativo (ver apps/licitacoes/sincronia_pncp.py)."

    def handle(self, *args, **options):
        self.stdout.write("Sincronizando com o PNCP...")
        resumo = sincronizar_pncp()
        self.stdout.write(
            self.style.SUCCESS(
                f"PNCP sincronizado: {resumo['empresas']} CNPJ(s), {resumo['itens']} item(ns) ganho(s), "
                f"{resumo['atas']} item(ns) de ata, {resumo['salvas_criadas']} licitação(ões) nova(s)."
            )
        )
