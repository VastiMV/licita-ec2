"""A consulta `diagnostico quedas` (GEN-45, 12/11/2026): separa as "sessão
caiu" por causa, para saber se a queda é real ou alarme falso."""

from __future__ import annotations

import datetime as dt
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.licitacoes.management.commands.diagnostico import episodios_de_queda, motivo_da_queda

from .models import Pulso


class MotivoDaQuedaTests(TestCase):
    def test_os_tres_textos_que_a_extensao_manda(self):
        self.assertTrue(motivo_da_queda("retoken 401").startswith("retoken falhou"))
        self.assertTrue(motivo_da_queda("O Compras.gov pediu login de novo (401)").startswith("401"))
        self.assertTrue(motivo_da_queda("O Compras.gov pediu login de novo").startswith("401"))
        self.assertTrue(
            motivo_da_queda("Aperte F5 na aba do Compras.gov (a Sentinela ainda não viu a sessão)").startswith(
                "aba sem sessão"
            )
        )
        self.assertEqual(motivo_da_queda(""), "outro: —")


class ConsultaQuedasTests(TestCase):
    def pulso(self, minutos_atras, estado="sessao_caiu", detalhe="", versao="0.2.5"):
        p = Pulso.objects.create(estado=estado, detalhe=detalhe, versao=versao)
        Pulso.objects.filter(pk=p.pk).update(recebido_em=timezone.now() - dt.timedelta(minutes=minutos_atras))

    def test_conta_por_motivo_e_agrupa_episodios(self):
        self.pulso(300, detalhe="retoken 401")
        self.pulso(60, detalhe="O Compras.gov pediu login de novo (401)")
        self.pulso(59, detalhe="O Compras.gov pediu login de novo")  # a página e o fundo avisam o mesmo 401
        self.pulso(30, detalhe="Aperte F5 na aba do Compras.gov (a Sentinela ainda não viu a sessão)")
        self.pulso(20, estado="sem_aba", detalhe="Nenhuma aba do Compras.gov aberta")
        self.pulso(10, estado="ok")  # não entra
        self.pulso(60 * 24 * 10, detalhe="retoken 401")  # fora dos 7 dias

        saida = StringIO()
        call_command("diagnostico", "quedas", stdout=saida)
        texto = saida.getvalue()

        self.assertIn("Últimos 7 dias: 4 'sessão caiu' · 1 'sem aba'", texto)
        self.assertIn("   2 · 401 numa consulta da Sentinela", texto)
        self.assertIn("   1 · retoken falhou", texto)
        self.assertIn("   1 · aba sem sessão", texto)
        # Episódios: 300 min atrás; 60 e 59 (1 min de diferença); 30 (29 min depois do anterior).
        self.assertIn("Episódios (quedas a menos de 15 min uma da outra = um só): 3", texto)

    def test_dias_pelo_argumento(self):
        self.pulso(60 * 24 * 10, detalhe="retoken 401")

        saida = StringIO()
        call_command("diagnostico", "quedas", "30", stdout=saida)

        self.assertIn("Últimos 30 dias: 1 'sessão caiu'", saida.getvalue())


class EpisodiosTests(TestCase):
    def test_quedas_perto_viram_um_episodio(self):
        agora = timezone.now()

        class P:
            def __init__(self, minutos):
                self.recebido_em = agora + dt.timedelta(minutes=minutos)

        eps = episodios_de_queda([P(0), P(5), P(19), P(40)])

        self.assertEqual([len(e) for e in eps], [3, 1])
