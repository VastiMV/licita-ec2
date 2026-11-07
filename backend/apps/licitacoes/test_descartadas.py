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

    def test_os_quatro_casos_com_o_motivo_certo(self):
        self.salva("1", 5)  # ainda na lista: não aparece
        self.salva("2", 5).remover(por=self.user)  # tirada, sem cotação
        cotada_tirada = self.salva("3", 5)
        self.cotar(cotada_tirada)
        cotada_tirada.remover(por=self.user)  # tirada, com cotação
        self.salva("4", -3)  # venceu sem cotação
        cotada_vencida = self.salva("5", -2)
        self.cotar(cotada_vencida)  # venceu com cotação

        linhas = self.por_sequencial(self.listar())

        self.assertEqual(sorted(linhas), ["2", "3", "4", "5"])
        self.assertEqual(
            {seq: (linha["motivo"], linha["estava_em"]) for seq, linha in linhas.items()},
            {
                "2": ("descartada", "oportunidade"),
                "3": ("descartada", "cotacao"),
                "4": ("prazo_oportunidade", "oportunidade"),
                "5": ("prazo_cotacao", "cotacao"),
            },
        )
        self.assertEqual(linhas["2"]["motivo_label"], "Tirada da lista")
        self.assertEqual(linhas["4"]["motivo_label"], "Prazo venceu sem cotação")
        self.assertEqual(linhas["5"]["motivo_label"], "Prazo venceu com cotação")
        self.assertEqual(linhas["2"]["removida_por"], "Vasti")
        self.assertEqual(linhas["2"]["descartada_em"], str(self.hoje))
        self.assertEqual(linhas["4"]["descartada_em"], str(self.hoje - dt.timedelta(days=3)))
        self.assertIsNotNone(linhas["5"]["cotacao_id"])

    def test_tirada_depois_do_prazo_vale_o_prazo(self):
        salva = self.salva("1", -10)
        salva.remover(por=self.user)

        linha = self.listar()["results"][0]

        self.assertEqual(linha["motivo"], "prazo_oportunidade")
        self.assertEqual(linha["descartada_em"], str(self.hoje - dt.timedelta(days=10)))

    def test_filtra_por_motivo(self):
        self.salva("1", -3)
        self.salva("2", 5).remover(por=self.user)
        cotada = self.salva("3", -2)
        self.cotar(cotada)

        def motivo(m):
            return sorted(self.por_sequencial(self.listar(motivo=m)))

        self.assertEqual(motivo("prazo_oportunidade"), ["1"])
        self.assertEqual(motivo("descartada"), ["2"])
        self.assertEqual(motivo("prazo_cotacao"), ["3"])

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

    def test_filtra_por_uasg(self):
        self.salva("1", 5, uasg="925001").remover(por=self.user)
        self.salva("2", 5, uasg="926002").remover(por=self.user)

        self.assertEqual(sorted(self.por_sequencial(self.listar(uasg="926002"))), ["2"])
        # Parte do código também acha (quem digita os primeiros números).
        self.assertEqual(sorted(self.por_sequencial(self.listar(uasg=" 9250"))), ["1"])

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
