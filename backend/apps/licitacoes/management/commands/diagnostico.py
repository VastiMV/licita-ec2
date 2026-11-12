"""`python manage.py diagnostico <consulta> [argumento]` — **só leitura**.

Consultas fixas para conferir o Licita em produção sem abrir o banco (rodam
pelo botão "Consultar EC2" do GitHub Actions, `.github/workflows/consultar-ec2.yml`):

- `itens-suspeitos` — itens da Sentinela sem preço, sem marca e sem posição
  (o defeito do 59/2026, item 1, corrigido em 09/11/2026);
- `compra <código de 17 dígitos ou id>` — a compra, os itens, a etapa e o
  sinal de cada item, e as propostas lidas;
- `torre` — quantas licitações em cada etapa e quantas saíram;
- `sentinela` — o que a Sentinela fez nas últimas 24 horas;
- `quedas [dias]` — as "sessão caiu" e "sem aba" dos últimos dias (padrão 7):
  por motivo, por dia, por hora e por versão, e os episódios (quedas a menos
  de 15 minutos uma da outra contam como um). Para o GEN-45 (12/11/2026):
  separar queda real (retoken), token velho (401 numa consulta da
  Sentinela) e aba sem sessão ("Aperte F5", aba pública);
- `telegram` — se o robô está ligado e quem mandou mensagem para ele (o
  número do chat que vai em `TELEGRAM_CHAT_IDS`).

Nada aqui grava no banco.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone

from apps.licitacoes.models import ItemParticipado, OportunidadeSalva
from apps.licitacoes.torre import avaliar, etapa_do_item, montar_torre, posicao_efetiva, rotulo_da_compra, sinal_do_item

CONSULTAS = ("itens-suspeitos", "compra", "torre", "sentinela", "quedas", "telegram")


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


def motivo_da_queda(detalhe: str) -> str:
    """Agrupa o texto do aviso em três causas (ver `sentinela/pagina.js` e
    `sentinela/fundo.js`)."""

    texto = detalhe or ""
    if texto.startswith("retoken"):
        return "retoken falhou (a própria página não renovou a sessão)"
    if "F5" in texto or "sem_sessao" in texto:
        return "aba sem sessão (F5, aba nova ou pública)"
    if "401" in texto or "login de novo" in texto:
        return "401 numa consulta da Sentinela"
    return f"outro: {texto or '—'}"


def episodios_de_queda(quedas, intervalo=dt.timedelta(minutes=15)):
    episodios: list[list] = []
    for p in quedas:
        if episodios and p.recebido_em - episodios[-1][-1].recebido_em <= intervalo:
            episodios[-1].append(p)
        else:
            episodios.append([p])
    return episodios


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
        hoje = timezone.localdate()
        sinais = {}
        for item in salva.itens_participados.prefetch_related("propostas"):
            r = etapa_do_item(item, [], [], hoje)
            sinais[item.numero_item] = {"etapa": r.etapa or f"perdido ({r.perdido})", "sinal": sinal_do_item(item, r)}
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

    def quedas(self, argumento):
        from apps.sentinela.models import Pulso

        dias = int(argumento) if argumento.isdigit() and int(argumento) > 0 else 7
        desde = timezone.now() - dt.timedelta(days=dias)
        pulsos = list(
            Pulso.objects.filter(recebido_em__gte=desde, estado__in=["sessao_caiu", "sem_aba"]).order_by("recebido_em")
        )
        quedas = [p for p in pulsos if p.estado == "sessao_caiu"]
        sem_aba = [p for p in pulsos if p.estado == "sem_aba"]
        self.linha(f"Últimos {dias} dias: {len(quedas)} 'sessão caiu' · {len(sem_aba)} 'sem aba'")

        self.linha("Sessão caiu, por motivo:")
        for motivo, n in Counter(motivo_da_queda(p.detalhe) for p in quedas).most_common():
            self.linha(f"  {n:4} · {motivo}")
        self.linha("Sessão caiu, por detalhe (texto exato):")
        for detalhe, n in Counter(p.detalhe or "—" for p in quedas).most_common(10):
            self.linha(f"  {n:4} · {detalhe}")
        self.linha(f"Sessão caiu, por versão: {dict(Counter(p.versao or '—' for p in quedas))}")
        self.linha("Por dia (sessão caiu / sem aba):")
        por_dia_q = Counter(f"{timezone.localtime(p.recebido_em):%d/%m %a}" for p in quedas)
        por_dia_a = Counter(f"{timezone.localtime(p.recebido_em):%d/%m %a}" for p in sem_aba)
        for dia in sorted(set(por_dia_q) | set(por_dia_a), key=lambda d: (d[3:5], d[:2])):
            self.linha(f"  {dia} · {por_dia_q.get(dia, 0):3} / {por_dia_a.get(dia, 0):3}")
        self.linha("Por hora (sessão caiu / sem aba):")
        por_hora_q = Counter(timezone.localtime(p.recebido_em).hour for p in quedas)
        por_hora_a = Counter(timezone.localtime(p.recebido_em).hour for p in sem_aba)
        for hora in sorted(set(por_hora_q) | set(por_hora_a)):
            self.linha(f"  {hora:02}h · {por_hora_q.get(hora, 0):3} / {por_hora_a.get(hora, 0):3}")

        episodios = episodios_de_queda(quedas)
        self.linha(f"Episódios (quedas a menos de 15 min uma da outra = um só): {len(episodios)}")
        for ep in episodios[-15:]:
            inicio, fim = timezone.localtime(ep[0].recebido_em), timezone.localtime(ep[-1].recebido_em)
            motivos = ", ".join(sorted({motivo_da_queda(p.detalhe) for p in ep}))
            self.linha(f"  {inicio:%d/%m %H:%M}–{fim:%H:%M} · {len(ep)} avisos · {motivos}")

    def telegram(self, _):
        from apps.notificacoes.telegram import RoboRecusou, chats, quem_falou_com_o_robo
        from config.settings.environment import env

        if not env.telegram_token:
            self.linha("Telegram: sem TELEGRAM_BOT_TOKEN no .env (desligado).")
            return
        self.linha(f"Telegram: robô configurado · chats que recebem: {chats() or 'nenhum ainda'}")
        try:
            conversas = quem_falou_com_o_robo()
        except RoboRecusou as exc:
            self.linha(f"Telegram: {exc}.")
            return
        self.linha(f"Quem mandou mensagem para o robô: {len(conversas)}")
        for c in conversas:
            self.linha(f"  chat {c['chat']} · {c['nome']} {('@' + c['usuario']) if c['usuario'] else ''}")

