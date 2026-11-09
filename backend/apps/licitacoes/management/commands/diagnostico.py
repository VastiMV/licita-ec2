"""`python manage.py diagnostico <consulta> [argumento]` — **só leitura**.

Consultas fixas para conferir o Licita em produção sem abrir o banco (rodam
pelo botão "Consultar EC2" do GitHub Actions, `.github/workflows/consultar-ec2.yml`):

- `itens-suspeitos` — itens da Sentinela sem preço, sem marca e sem posição
  (o defeito do 59/2026, item 1, corrigido em 09/11/2026);
- `compra <código de 17 dígitos ou id>` — a compra, os itens, a etapa e o
  sinal de cada item, e as propostas lidas;
- `torre` — quantas licitações em cada etapa e quantas saíram;
- `sentinela` — o que a Sentinela fez nas últimas 24 horas.

Nada aqui grava no banco.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone

from apps.licitacoes.models import ItemParticipado, OportunidadeSalva
from apps.licitacoes.torre import avaliar, montar_torre, posicao_efetiva, rotulo_da_compra

CONSULTAS = ("itens-suspeitos", "compra", "torre", "sentinela")


def itens_suspeitos():
    return (
        ItemParticipado.objects.filter(
            fonte="sentinela",
            marca="",
            classificacao__isnull=True,
            valor_proposta_inicial__isnull=True,
            valor_lance_final__isnull=True,
        )
        .select_related("oportunidade")
        .order_by("oportunidade_id", "numero_item")
    )


class Command(BaseCommand):
    help = "Consultas de conferência, só leitura: " + ", ".join(CONSULTAS)

    def add_arguments(self, parser):
        parser.add_argument("consulta", choices=CONSULTAS)
        parser.add_argument("argumento", nargs="?", default="")

    def handle(self, *args, consulta, argumento, **options):
        getattr(self, consulta.replace("-", "_"))(argumento)

    def linha(self, texto: str = "") -> None:
        self.stdout.write(texto)

    def itens_suspeitos(self, _):
        itens = list(itens_suspeitos())
        self.linha(f"Itens suspeitos (Sentinela, sem preço, sem marca, sem posição): {len(itens)}")
        for item in itens:
            salva = item.oportunidade
            self.linha(
                f"- salva {salva.pk} · {rotulo_da_compra(salva)} · {salva.orgao_nome[:50]} · "
                f"item {item.numero_item} · {item.descricao[:40]} · gravado {item.atualizado_em:%d/%m %H:%M}"
            )

    def compra(self, argumento):
        if argumento.isdigit() and len(argumento) == 17:
            salva = OportunidadeSalva.objects.filter(link_plataforma__contains=f"compra={argumento}").first()
        elif argumento.isdigit():
            salva = OportunidadeSalva.objects.filter(pk=int(argumento)).first()
        else:
            raise CommandError("Informe o código da compra (17 dígitos) ou o id da salva.")
        if not salva:
            raise CommandError(f"Compra {argumento} não encontrada.")
        cartao, saida = avaliar(salva, timezone.localdate())
        self.linha(f"Salva {salva.pk} · {rotulo_da_compra(salva)} · {salva.orgao_nome} · UASG {salva.uasg}")
        self.linha(f"Removida: {salva.removida_em or 'não'} · link: {salva.link_plataforma}")
        if saida:
            self.linha(f"Fora da Torre: {saida.para} ({saida.motivo})")
        else:
            self.linha(
                f"Torre: {cartao['estagio']} › {cartao['etapa_rotulo']} · ganhando "
                f"{cartao['itens_ganhando']} de {cartao['itens_com_posicao']} · etiquetas: "
                f"{', '.join(e['texto'] for e in cartao['etiquetas']) or '—'}"
            )
        try:
            p = salva.participacao
            self.linha(
                f"Participação: fase {p.fase_compra or '—'} · situação {p.situacao_compra or '—'} · "
                f"proposta cadastrada {p.proposta_cadastrada} · fonte {p.fonte}"
            )
        except OportunidadeSalva.participacao.RelatedObjectDoesNotExist:
            self.linha("Participação: nenhuma (a Sentinela não leu)")
        sinais = {c["numero"]: c for c in (cartao or {}).get("itens", [])}
        for item in salva.itens_participados.annotate(n=Count("propostas")).order_by("id"):
            c = sinais.get(item.numero_item, {})
            self.linha(
                f"  item {item.numero_item:>4} · {item.descricao[:35]:35} · pos {item.classificacao or '—'} "
                f"(de verdade {posicao_efetiva(item) or '—'}) · situação {item.situacao_proposta or '—'} · "
                f"fase {item.fase_item or '—'} · venceu {item.vencedor_e_a_empresa} · "
                f"etapa {c.get('etapa') or 'perdido'} · sinal {c.get('sinal') or '—'} · "
                f"propostas {item.n} · lidas {item.propostas_lidas_em:%d/%m %H:%M}"
                if item.propostas_lidas_em
                else f"  item {item.numero_item:>4} · {item.descricao[:35]:35} · pos {item.classificacao or '—'} · "
                f"situação {item.situacao_proposta or '—'} · fase {item.fase_item or '—'} · "
                f"venceu {item.vencedor_e_a_empresa} · etapa {c.get('etapa') or 'perdido'} · "
                f"sinal {c.get('sinal') or '—'} · fonte {item.fonte} · propostas não lidas"
            )

    def torre(self, _):
        torre = montar_torre()
        for estagio in torre["estagios"]:
            etapas = " · ".join(f"{e['rotulo']} {e['total']}" for e in estagio["etapas"])
            self.linha(f"{estagio['rotulo']} ({estagio['total']}): {etapas}")
            for c in estagio["cartoes"]:
                self.linha(
                    f"  - salva {c['id']} · {c['compra']} · {c['orgao_nome'][:40]} · {c['etapa_rotulo']} · "
                    f"{len(c['itens'])} itens · ganhando {c['itens_ganhando']}/{c['itens_com_posicao']}"
                )
        self.linha(f"Saíram: {torre['saidas']}")

    def sentinela(self, _):
        from apps.sentinela.models import Pulso

        desde = timezone.now() - dt.timedelta(hours=24)
        pulsos = list(Pulso.objects.filter(recebido_em__gte=desde).order_by("recebido_em"))
        self.linha(f"Notícias nas últimas 24h: {len(pulsos)}")
        self.linha(f"Por estado: {dict(Counter(p.estado for p in pulsos if not p.captura))}")
        self.linha(f"Capturas: {dict(Counter(p.captura for p in pulsos if p.captura))}")
        self.linha(f"Versões: {sorted({p.versao for p in pulsos if p.versao})}")
        for p in pulsos[-8:]:
            self.linha(f"  {timezone.localtime(p.recebido_em):%d/%m %H:%M} · {p.estado} · {p.captura or '—'} · {p.detalhe}")
        self.linha(
            f"Itens com propostas lidas: {ItemParticipado.objects.filter(propostas_lidas_em__isnull=False).count()}"
            f" de {ItemParticipado.objects.filter(classificacao__isnull=False).count()} com posição"
        )
