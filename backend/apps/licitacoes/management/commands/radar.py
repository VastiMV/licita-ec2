"""`python manage.py radar` — roda uma rodada do Radar agora (GEN-68).

Para testar antes do deploy (o ambiente de teste não tem o agendamento das
8h e 18h) e para rodar na mão em produção, se precisar. Mostra o resumo e,
de cada sugestão nova, se os itens vieram do PNCP.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.licitacoes.models import SugestaoRadar
from apps.licitacoes.completar import sem_itens
from apps.licitacoes.radar import rodar, termos_da_base, visiveis


class Command(BaseCommand):
    help = "Roda uma rodada do Radar agora e mostra o que achou."

    def handle(self, *args, **options):
        termos = termos_da_base()
        self.stdout.write(f"Base: {len(termos)} termos")
        for termo, origem, ganho in termos:
            self.stdout.write(f"  - {termo}  (de: {origem[:50]}{' · ganho' if ganho else ''})")
        antes = set(SugestaoRadar.objects.values_list("pk", flat=True))

        resumo = rodar()

        self.stdout.write(f"\nResumo: {resumo}")
        novas = SugestaoRadar.objects.exclude(pk__in=antes).order_by("-por_ganho", "uf")
        com_itens = sum(1 for s in novas if any((i or {}).get("descricao_resumida") for i in s.itens))
        self.stdout.write(f"Novas: {novas.count()} · com itens do PNCP: {com_itens}")
        todas = list(visiveis())
        todas_com_itens = sum(1 for s in todas if not sem_itens(s.itens))
        self.stdout.write(f"No Radar agora: {len(todas)} · com itens do PNCP: {todas_com_itens}\n")
        from apps.licitacoes import radar_ia

        if radar_ia._chave_recusada:
            estado_ia = "PARADA nesta rodada (chave recusada ou sem crédito: ver a linha de erro acima)"
        elif radar_ia.ligada():
            estado_ia = "ligada"
        else:
            estado_ia = "DESLIGADA (sem ANTHROPIC_API_KEY)"
        self.stdout.write(f"IA: {estado_ia}\n")
        for s in novas.order_by("-nota_ia")[:60]:
            itens = [i for i in s.itens if (i or {}).get("descricao_resumida")]
            nota = "--" if s.nota_ia is None else f"{s.nota_ia:2d}"
            marca = "ENTRA" if s.nota_ia is None or s.nota_ia >= radar_ia.NOTA_MINIMA else "fora "
            primeiro = (itens[0].get("descricao_resumida") or "")[:40] if itens else "-"
            self.stdout.write(
                f"  nota {nota} {marca} | {s.uf or '--'} | {s.objeto[:45]:45} | 1º item: {primeiro} | de: {s.parecido_com[:25]}"
            )
