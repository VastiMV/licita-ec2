"""Encerradas e Descartadas: menu 10 × tela 1 (GEN-48, 14/11/2026).

Caso real (10/11/2026): o menu contava 10 encerradas; a tela, aberta em
"últimos 90 dias", mostrava 1. As outras 9 eram "acompanhando" sem data
de encerramento (compras trazidas pela Sentinela sem prazo) e nunca
passavam no filtro de data. Decisão da operação: a linha sem data sempre
aparece, e a tela recebe o número do menu (`total_geral`) para avisar
"Mostrando X de N — ver todas". Vale para as duas telas.
"""

from __future__ import annotations

import datetime as dt

from .models import ParticipacaoCompra
from .test_encerradas import Base


class SemDataSempreApareceTests(Base):
    def setUp(self):
        super().setUp()
        self.inicio = str(self.hoje - dt.timedelta(days=90))

    def test_acompanhando_sem_data_aparece_com_filtro_de_periodo(self):
        sem_data = self.salva("1", None, plataforma_id="compras_gov")
        ParticipacaoCompra.objects.create(oportunidade=sem_data, fase_compra="4")
        com_data = self.salva("2", -10)
        ParticipacaoCompra.objects.create(oportunidade=com_data, situacao_compra="RE")

        dados = self.listar(data_inicial=self.inicio, data_final=str(self.hoje))

        self.assertEqual(sorted(self.por_sequencial(dados)), ["1", "2"])
        self.assertEqual(self.por_sequencial(dados)["1"]["motivo"], "acompanhando")
        self.assertIsNone(self.por_sequencial(dados)["1"]["encerrada_em"])

    def test_total_geral_e_o_numero_do_menu(self):
        from .torre import montar_torre

        sem_data = self.salva("1", None, plataforma_id="compras_gov")
        ParticipacaoCompra.objects.create(oportunidade=sem_data, fase_compra="4")
        recente = self.salva("2", -10)
        ParticipacaoCompra.objects.create(oportunidade=recente, situacao_compra="RE")
        ParticipacaoCompra.objects.filter(oportunidade=recente).update(
            atualizada_em=dt.datetime.combine(self.hoje, dt.time(12), tzinfo=dt.timezone.utc)
        )
        fora = self.salva("3", -200)
        ParticipacaoCompra.objects.create(oportunidade=fora, situacao_compra="DE")
        ParticipacaoCompra.objects.filter(oportunidade=fora).update(
            atualizada_em=dt.datetime.combine(self.hoje - dt.timedelta(days=200), dt.time(12), tzinfo=dt.timezone.utc)
        )

        dados = self.listar(data_inicial=self.inicio, data_final=str(self.hoje))

        self.assertNotIn("3", self.por_sequencial(dados))  # data antiga: o filtro esconde
        self.assertEqual(dados["total_geral"], 3)
        self.assertEqual(dados["total_geral"], montar_torre()["saidas"]["encerradas"])

    def test_descartadas_tambem(self):
        tirada = self.salva("1", 5)
        tirada.remover(por=self.user)
        velha = self.salva("2", -200)  # prazo venceu há 200 dias, sem cotação

        resposta = self.client.get(
            "/api/licitacoes/descartadas/", {"data_inicial": self.inicio, "data_final": str(self.hoje)}
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(sorted(self.por_sequencial(resposta.data)), ["1"])
        self.assertEqual(resposta.data["total_geral"], 2)
        self.assertIsNotNone(velha.pk)
