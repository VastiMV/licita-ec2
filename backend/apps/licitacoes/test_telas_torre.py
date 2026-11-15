"""As telas de Oportunidades e do Cotador = Torre › Oportunidade e Torre ›
Cotação (GEN-87, 14/11/2026).

Caso real (produção, 14/11): a tela de Oportunidades tinha 14 linhas e a
Torre › Oportunidade, 6. As 9 a mais eram compras que o Carlinhos só
acompanha (já em Encerradas), trazidas pela Sentinela sem prazo: sem prazo,
o filtro antigo (sem cotação + prazo aberto) nunca as tirava. E a suspensa
com preço lançado só no Compras.gov estava em Torre › Cotação, mas não na
tela do Cotador (o filtro antigo exigia cotação no Licita).

Regra da operação: fica em Oportunidades (e na Torre) tudo cujo prazo não
passou, mais as que voltam por estar suspensas ou sem data. Tem preço no
Compras.gov e não no Licita: aparece no Cotador.
"""

from __future__ import annotations

from apps.propostas.models import Proposta

from .models import ItemParticipado, ParticipacaoCompra
from .test_encerradas import Base
from .torre import montar_torre


class TelasIguaisATorreTests(Base):
    def ids(self, url: str) -> set[int]:
        resposta = self.client.get(url, {"page_size": 100})
        self.assertEqual(resposta.status_code, 200)
        return {linha["id"] for linha in resposta.data["results"]}

    def oportunidades(self) -> set[int]:
        return self.ids("/api/licitacoes/salvas/")

    def cotador(self) -> set[int]:
        return self.ids("/api/licitacoes/cotacoes/")

    def na_torre(self, etapa: str) -> set[int]:
        return {
            c["id"] for e in montar_torre()["estagios"] for c in e["cartoes"] if c["etapa"] == etapa
        }

    def test_so_acompanhando_sem_prazo_sai_de_oportunidades(self):
        # Minhas participações, depois da sessão, sem cotação, sem prazo: está
        # em Encerradas (acompanhando). Antes ficava também em Oportunidades.
        salva = self.salva("1", None, plataforma_id="compras_gov")
        ParticipacaoCompra.objects.create(oportunidade=salva, fase_compra="4", proposta_cadastrada=True)
        ItemParticipado.objects.create(oportunidade=salva, numero_item="1", situacao_proposta="5")

        self.assertNotIn(salva.pk, self.oportunidades())
        self.assertIn(salva.pk, {l["id"] for l in self.listar()["results"]})

    def test_suspensa_sem_cotacao_volta_para_oportunidades_mesmo_com_prazo_vencido(self):
        salva = self.salva("1", -5, plataforma_id="compras_gov")
        ParticipacaoCompra.objects.create(oportunidade=salva, fase_compra="1", situacao_compra="SU")

        self.assertIn(salva.pk, self.oportunidades())

    def test_preco_so_no_compras_gov_aparece_no_cotador(self):
        # Butantan 9/2026: suspensa antes da sessão, preço lançado no
        # Compras.gov, nenhuma cotação no Licita.
        salva = self.salva("1", -5, plataforma_id="compras_gov")
        ParticipacaoCompra.objects.create(
            oportunidade=salva, fase_compra="1", situacao_compra="SU", proposta_cadastrada=True
        )
        ItemParticipado.objects.create(
            oportunidade=salva, numero_item="1", fase_item="LS", valor_proposta_inicial=100
        )

        resposta = self.client.get("/api/licitacoes/cotacoes/")
        linha = next(l for l in resposta.data["results"] if l["id"] == salva.pk)

        self.assertIsNone(linha["cotacao_id"])
        self.assertIsNone(linha["valor_cotado"])
        self.assertEqual(linha["selo"]["texto"], "Sem cotação no Licita")
        self.assertNotIn(salva.pk, self.oportunidades())

    def test_telas_iguais_a_torre_em_todos_os_casos(self):
        self.salva("oportunidade", 5)
        self.salva("sem_prazo", None)
        cotada = self.salva("cotacao", 5)
        self.cotar(cotada)
        com_proposta = self.salva("com_proposta", 5)
        self.cotar(com_proposta)
        Proposta.objects.create(oportunidade=com_proposta, valor=100)
        self.salva("venceu_sem_cotacao", -3)
        suspensa = self.salva("suspensa", -5, plataforma_id="compras_gov")
        ParticipacaoCompra.objects.create(oportunidade=suspensa, fase_compra="1", situacao_compra="SU")
        preco = self.salva("preco_compras", -5, plataforma_id="compras_gov")
        ParticipacaoCompra.objects.create(
            oportunidade=preco, fase_compra="1", situacao_compra="SU", proposta_cadastrada=True
        )
        ItemParticipado.objects.create(oportunidade=preco, numero_item="1", valor_proposta_inicial=100)
        acompanha = self.salva("acompanha", None, plataforma_id="compras_gov")
        ParticipacaoCompra.objects.create(oportunidade=acompanha, fase_compra="4", proposta_cadastrada=True)
        ItemParticipado.objects.create(oportunidade=acompanha, numero_item="1", situacao_proposta="5")
        tirada = self.salva("tirada", 5)
        tirada.remover(por=self.user)

        self.assertEqual(self.oportunidades(), self.na_torre("oportunidade"))
        self.assertEqual(self.cotador(), self.na_torre("cotacao"))
        self.assertEqual(len(self.oportunidades()), 3)  # oportunidade, sem_prazo, suspensa
        self.assertEqual(len(self.cotador()), 3)  # cotacao, com_proposta, preco_compras
