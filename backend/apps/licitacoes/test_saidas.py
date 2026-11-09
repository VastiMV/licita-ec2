"""Saídas do ciclo com os fatos da Torre: Encerradas (participou) e
Descartadas (não participou), em acordo com `torre.py`.

A regra de ouro do `encerradas.py` continua: **cada licitação está em um
lugar só** — um cartão na Torre, uma linha em Encerradas ou uma linha em
Descartadas. O último teste confere isso para todos os casos juntos.
"""

from __future__ import annotations

from apps.propostas.models import Proposta

from .models import ItemParticipado, ParticipacaoCompra
from .test_encerradas import Base
from .torre import montar_torre


class SaidasComFatosDaTorreTests(Base):
    def encerradas(self):
        return self.por_sequencial(self.listar())

    def descartadas(self):
        resposta = self.client.get("/api/licitacoes/descartadas/")
        self.assertEqual(resposta.status_code, 200)
        return self.por_sequencial(resposta.data)

    def processo(self, salva):
        resposta = self.client.get(f"/api/licitacoes/salvas/{salva.pk}/processo/")
        self.assertEqual(resposta.status_code, 200)
        return resposta.data

    # -- Encerradas ---------------------------------------------------------

    def test_todos_os_itens_perdidos_e_encerrada_como_perdida(self):
        salva = self.salva("1", -10)
        ItemParticipado.objects.create(oportunidade=salva, numero_item="1", situacao_proposta="1")
        ItemParticipado.objects.create(oportunidade=salva, numero_item="2", vencedor_e_a_empresa=False)

        linha = self.encerradas()["1"]

        self.assertEqual(linha["motivo"], "perdida")
        self.assertEqual(linha["motivo_label"], "Perdida")
        self.assertIn("perd", self.processo(salva)["desfecho"]["porque"])

    def test_um_item_ainda_vivo_mantem_na_torre(self):
        salva = self.salva("1", -10)
        ItemParticipado.objects.create(oportunidade=salva, numero_item="1", situacao_proposta="1")
        ItemParticipado.objects.create(oportunidade=salva, numero_item="2", classificacao=1, fase_item="E")

        self.assertNotIn("1", self.encerradas())
        self.assertNotIn("1", self.descartadas())

    def test_compra_deserta_revogada_anulada_ou_fracassada_e_encerrada(self):
        for sequencial, situacao, motivo in (
            ("1", "DE", "deserta"),
            ("2", "RE", "revogada"),
            ("3", "AN", "anulada"),
            ("4", "FR", "fracassada"),
        ):
            salva = self.salva(sequencial, -10)
            ParticipacaoCompra.objects.create(oportunidade=salva, situacao_compra=situacao)

        motivos = {seq: linha["motivo"] for seq, linha in self.encerradas().items()}

        self.assertEqual(motivos, {"1": "deserta", "2": "revogada", "3": "anulada", "4": "fracassada"})

    def test_suspensa_nao_sai_do_ciclo(self):
        salva = self.salva("1", -10)
        ParticipacaoCompra.objects.create(oportunidade=salva, situacao_compra="SU", proposta_cadastrada=True)

        self.assertEqual(self.encerradas(), {})
        self.assertEqual(self.descartadas(), {})

    # -- Descartadas --------------------------------------------------------

    def test_participou_sem_proposta_e_descartada_sem_proposta(self):
        salva = self.salva("1", -20)
        self.cotar(salva)
        ParticipacaoCompra.objects.create(oportunidade=salva, fase_compra="4", proposta_cadastrada=False)

        linha = self.descartadas()["1"]

        self.assertEqual(linha["motivo"], "sem_proposta")
        self.assertEqual(linha["motivo_label"], "Sem proposta cadastrada")
        self.assertIn("sem proposta", self.processo(salva)["desfecho"]["porque"])

    def test_compras_gov_com_cotacao_e_prazo_vencido_espera_a_sentinela(self):
        salva = self.salva("1", -3, plataforma_id="compras_gov")
        self.cotar(salva)

        self.assertEqual(self.descartadas(), {})

    def test_outro_portal_com_cotacao_e_prazo_vencido_continua_descartada(self):
        salva = self.salva("1", -3, plataforma_id="")
        self.cotar(salva)

        self.assertEqual(self.descartadas()["1"]["motivo"], "prazo_cotacao")

    def test_com_proposta_gerada_nao_e_descartada_pelo_prazo(self):
        salva = self.salva("1", -3)
        self.cotar(salva)
        Proposta.objects.create(oportunidade=salva, valor=100)

        self.assertEqual(self.descartadas(), {})

    def test_vitoria_trazida_pelo_pncp_nao_e_descartada(self):
        salva = self.salva("1", -38, plataforma_id="compras_gov")
        ItemParticipado.objects.create(oportunidade=salva, numero_item="49", vencedor_e_a_empresa=True)

        self.assertEqual(self.descartadas(), {})
        self.assertEqual(self.encerradas(), {})

    # -- Um lugar só --------------------------------------------------------

    def test_cada_licitacao_esta_em_um_lugar_so(self):
        casos = []
        casos.append(self.salva("oportunidade", 5))
        cotada = self.salva("cotacao", 5)
        self.cotar(cotada)
        casos.append(cotada)
        casos.append(self.salva("venceu_sem_cotacao", -3))
        outra = self.salva("venceu_outro_portal", -3)
        self.cotar(outra)
        casos.append(outra)
        espera = self.salva("espera_sentinela", -3, plataforma_id="compras_gov")
        self.cotar(espera)
        casos.append(espera)
        tirada = self.salva("tirada", 5)
        tirada.remover(por=self.user)
        casos.append(tirada)
        sem = self.salva("sem_proposta", -20)
        ParticipacaoCompra.objects.create(oportunidade=sem, fase_compra="4", proposta_cadastrada=False)
        casos.append(sem)
        perdida = self.salva("perdida", -10)
        ItemParticipado.objects.create(oportunidade=perdida, numero_item="1", situacao_proposta="5")
        casos.append(perdida)
        deserta = self.salva("deserta", -10)
        ParticipacaoCompra.objects.create(oportunidade=deserta, situacao_compra="DE")
        casos.append(deserta)
        ganha = self.salva("ganha", -40)
        ItemParticipado.objects.create(oportunidade=ganha, numero_item="2", vencedor_e_a_empresa=True)
        casos.append(ganha)

        torre = montar_torre()
        na_torre = {c["id"] for e in torre["estagios"] for c in e["cartoes"]}
        em_encerradas = {linha["id"] for linha in self.listar()["results"]}
        em_descartadas = {
            linha["id"] for linha in self.client.get("/api/licitacoes/descartadas/").data["results"]
        }

        for salva in casos:
            lugares = [salva.pk in na_torre, salva.pk in em_encerradas, salva.pk in em_descartadas]
            self.assertEqual(sum(lugares), 1, f"{salva.sequencial_compra} está em {lugares}")
        self.assertEqual(torre["saidas"]["encerradas"], len(em_encerradas))
        # Os números do menu são os das listas (inclusive a tirada da lista).
        self.assertEqual(torre["saidas"]["descartadas"], len(em_descartadas))
