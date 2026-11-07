"""Descartadas (`/api/licitacoes/descartadas/`) — as salvas que a equipe
tirou da lista antes do prazo vencer (ver `encerradas.descartadas`)."""

from __future__ import annotations

import datetime as dt

from .test_encerradas import Base

URL = "/api/licitacoes/descartadas/"


class DescartadasTests(Base):
    def listar(self, **params):
        resposta = self.client.get(URL, params)
        self.assertEqual(resposta.status_code, 200)
        return resposta.data

    def test_tiradas_da_lista_e_vencidas_sem_cotacao(self):
        self.salva("1", 5)  # ainda na lista
        self.salva("2", -3)  # venceu sem cotação: Descartada
        self.salva("3", 5).remover(por=self.user)  # tirada da lista
        self.salva("4", None).remover(por=self.user)  # sem prazo, tirada da lista
        tarde = self.salva("5", -10)
        tarde.remover(por=self.user)  # venceu sem cotação, removida depois
        cotada = self.salva("6", -2)
        self.cotar(cotada)  # venceu COM cotação: Encerrada, não aparece aqui

        linhas = self.por_sequencial(self.listar())

        self.assertEqual(sorted(linhas), ["2", "3", "4", "5"])
        self.assertEqual(linhas["3"]["motivo"], "descartada")
        self.assertEqual(linhas["3"]["motivo_label"], "Tirada da lista")
        self.assertEqual(linhas["3"]["removida_por"], "Vasti")
        self.assertEqual(linhas["3"]["descartada_em"], str(self.hoje))
        self.assertEqual(linhas["3"]["estava_em"], "oportunidade")
        self.assertEqual(linhas["2"]["motivo"], "prazo_oportunidade")
        self.assertEqual(linhas["2"]["motivo_label"], "Prazo venceu sem cotação")
        self.assertEqual(linhas["2"]["descartada_em"], str(self.hoje - dt.timedelta(days=3)))
        # Removida depois do prazo: o prazo veio primeiro, é ele que conta.
        self.assertEqual(linhas["5"]["motivo"], "prazo_oportunidade")
        self.assertEqual(linhas["5"]["descartada_em"], str(self.hoje - dt.timedelta(days=10)))

    def test_filtra_por_motivo(self):
        self.salva("1", -3)
        self.salva("2", 5).remover(por=self.user)

        prazo = self.listar(motivo="prazo_oportunidade")
        tiradas = self.listar(motivo="descartada")

        self.assertEqual(sorted(self.por_sequencial(prazo)), ["1"])
        self.assertEqual(sorted(self.por_sequencial(tiradas)), ["2"])

    def test_processo_da_vencida_sem_cotacao_explica_o_prazo(self):
        salva = self.salva("1", -3)

        desfecho = self.client.get(f"/api/licitacoes/salvas/{salva.pk}/processo/").data["desfecho"]

        self.assertEqual(desfecho["tipo"], "prazo_oportunidade")

    def test_descartada_com_cotacao_mostra_a_cotacao(self):
        cotada = self.salva("1", 5)
        self.cotar(cotada)
        cotada.remover(por=self.user)

        linha = self.listar()["results"][0]

        self.assertEqual(linha["estava_em"], "cotacao")
        self.assertIsNotNone(linha["cotacao_id"])
        self.assertIsNotNone(linha["valor_cotado"])

    def test_nao_aparece_em_encerradas(self):
        self.salva("1", 5).remover(por=self.user)

        self.assertEqual(self.client.get("/api/licitacoes/encerradas/").data["count"], 0)
        self.assertEqual(self.listar()["count"], 1)

    def test_filtra_por_periodo_uf_e_busca(self):
        antiga = self.salva("1", 30, uf="RJ")
        antiga.remover(por=self.user, quando=dias_atras(self.hoje, 20))
        self.salva("2", 30, objeto="Cadeira de rodas").remover(por=self.user)

        recentes = self.listar(data_inicial=str(self.hoje - dt.timedelta(days=5)))
        self.assertEqual(sorted(self.por_sequencial(recentes)), ["2"])
        self.assertEqual(sorted(self.por_sequencial(self.listar(uf="rj"))), ["1"])

    def test_mais_recente_primeiro(self):
        self.salva("1", 30).remover(por=self.user, quando=dias_atras(self.hoje, 3))
        self.salva("2", 30).remover(por=self.user)

        ordem = [linha["sequencial_compra"] for linha in self.listar()["results"]]

        self.assertEqual(ordem, ["2", "1"])

    def test_processo_da_descartada_conta_quem_tirou(self):
        salva = self.salva("1", 5)
        salva.remover(por=self.user)

        desfecho = self.client.get(f"/api/licitacoes/salvas/{salva.pk}/processo/").data["desfecho"]

        self.assertEqual(desfecho["tipo"], "descartada")
        self.assertEqual(desfecho["por"], "Vasti")


def dias_atras(hoje: dt.date, dias: int) -> dt.datetime:
    """Meio-dia de `dias` atrás, no fuso local — a remoção guarda data e hora."""

    from django.utils import timezone

    return timezone.make_aware(dt.datetime.combine(hoje - dt.timedelta(days=dias), dt.time(12)))
