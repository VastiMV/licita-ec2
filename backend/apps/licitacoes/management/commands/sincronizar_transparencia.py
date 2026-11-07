"""`manage.py sincronizar_transparencia` — roda a sincronia com o Portal da
Transparência na hora, sem depender de Celery/RabbitMQ."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.licitacoes.sincronia_transparencia import sincronizar_transparencia


class Command(BaseCommand):
    help = "Traz do Portal da Transparência empenhos, liquidações e pagamentos de cada CNPJ ativo."

    def handle(self, *args, **options):
        self.stdout.write("Sincronizando com o Portal da Transparência...")
        resumo = sincronizar_transparencia()
        if resumo["sem_chave"]:
            self.stdout.write(self.style.WARNING("Sem PORTAL_TRANSPARENCIA_CHAVE no ambiente: nada foi consultado."))
            return
        if resumo["erro"]:
            self.stdout.write(self.style.ERROR(f"O Portal respondeu com erro: {resumo['erro']}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"{resumo['documentos']} documento(s): {resumo['ligados']} ligado(s) a uma licitação, "
                f"{resumo['sem_licitacao']} sem licitação (ligar à mão)."
            )
        )
