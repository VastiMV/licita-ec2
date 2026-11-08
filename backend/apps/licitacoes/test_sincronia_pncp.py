"""Testes da sincronia com o PNCP (`sincronia_pncp.py`).

Os registros são cópias dos que a API de Dados Abertos devolveu em
07/11/2026 para o CNPJ da Inside Solutions: o resultado do Pregão 201/2026
(UFVJM) e dois dos 17 itens do Pregão 112/2026 (IBAMA). O cliente é falso —
o formato é o real.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.test import TestCase

from apps.empresas.models import Empresa
from apps.tenants.atual import tenant_atual

from .models import DocumentoFinanceiro, EventoOportunidadeSalva, ItemParticipado, OportunidadeSalva
from .sincronia_pncp import sincronizar_pncp

CNPJ = "22015414000127"
HOJE = dt.date(2026, 11, 7)


def resultado(id_contratacao: str, id_compra: str, item: int, unitario: float, quantidade: float, data: str):
    return {
        "idCompraItem": f"{id_compra}{item:05d}",
        "idCompra": id_compra,
        "idContratacaoPNCP": id_contratacao,
        "numeroItemPncp": item,
        "niFornecedor": CNPJ,
        "nomeRazaoSocialFornecedor": "INSIDE SOLUTIONS LTDA",
        "quantidadeHomologada": quantidade,
        "valorUnitarioHomologado": unitario,
        "valorTotalHomologado": unitario * quantidade,
        "situacaoCompraItemResultadoId": 1,
        "situacaoCompraItemResultadoNome": "Informado",
        "dataResultadoPncp": f"{data}T00:00:00",
        "dataCancelamentoPncp": None,
        "numeroControlePNCPCompra": id_contratacao,
        "orgaoEntidadeCnpj": id_contratacao.split("-")[0],
    }


UFVJM = resultado("16888315000157-1-000041/2026", "15303605002012026", 2, 7250.0, 2.0, "2026-10-29")
IBAMA_49 = resultado("03659166002156-1-000075/2026", "19309905001122026", 49, 10.0, 8.0, "2026-10-09")
IBAMA_60 = resultado("03659166002156-1-000075/2026", "19309905001122026", 60, 92.0, 120.0, "2026-10-09")

ATA_UFVJM = {
    "numeroAtaRegistroPreco": "00041/2026",
    "codigoUnidadeGerenciadora": "153036",
    "dataAssinatura": "2026-11-05T00:00:00",
    "dataVigenciaInicial": "2026-11-06",
    "dataVigenciaFinal": "2027-11-06",
    "numeroItem": "00002",
    "descricaoItem": "Animal vivo",
    "quantidadeHomologadaItem": 2.0,
    "niFornecedor": CNPJ,
    "valorUnitario": 7250.0,
    "valorTotal": 14500.0,
    "idCompra": "15303605002012026",
    "numeroControlePncpCompra": "16888315000157-1-000041/2026",
    "quantidadeEmpenhada": 0.0,
    "itemExcluido": False,
    "numeroControlePncpAta": "16888315000157-1-000041/2026-000001",
}

CONTRATACOES = {
    "15303605002012026": {
        "id_compra": "15303605002012026",
        "uasg": "153036",
        "orgao_nome": "UNIV.FED.DOS VALES DO JEQUITINHONHA E MUCURI",
        "cnpj_orgao": "16888315000157",
        "uf": "MG",
        "municipio": "DIAMANTINA",
        "numero_compra": "90201",
        "ano_compra": 2026,
        "sequencial_compra": 41,
        "modalidade": "Pregão - Eletrônico",
        "codigo_modalidade": "05",
        "objeto": "Registro de preços para eventual aquisição de animais vivos",
        "processo": "23086011683202671",
        "situacao": "Divulgada no PNCP",
        "srp": True,
        "valor_total_estimado": 50000.0,
        "data_publicacao": "2026-10-07",
        "data_abertura_proposta": "2026-10-08",
        "data_encerramento_proposta": "2026-10-21",
    },
    "19309905001122026": {
        "id_compra": "19309905001122026",
        "uasg": "193099",
        "orgao_nome": "MMA-IBAMA - DEFIN/DF",
        "cnpj_orgao": "03659166002156",
        "uf": "DF",
        "municipio": "BRASÍLIA",
        "numero_compra": "90112",
        "ano_compra": 2026,
        "sequencial_compra": 75,
        "modalidade": "Pregão - Eletrônico",
        "codigo_modalidade": "05",
        "objeto": "Fornecimento de hortifrutigranjeiros e rações para o Centro de Triagem",
        "processo": "02001.015536/2024-21",
        "situacao": "Divulgada no PNCP",
        "srp": False,
        "valor_total_estimado": 90000.0,
        "data_publicacao": "2026-09-16",
        "data_abertura_proposta": "2026-09-17",
        "data_encerramento_proposta": "2026-09-30",
    },
}


class ClienteFalso:
    def __init__(self, resultados=(), atas=(), contratacoes=CONTRATACOES):
        self.resultados = list(resultados)
        self.atas = list(atas)
        self.contratacoes = contratacoes
        self.consultas: list[tuple[str, str, str, str]] = []

    def resultados_do_fornecedor(self, ni, inicio, fim):
        self.consultas.append(("resultados", ni, inicio, fim))
        return [r for r in self.resultados if r["niFornecedor"] == ni]

    def itens_de_ata_do_fornecedor(self, ni, inicio, fim):
        self.consultas.append(("atas", ni, inicio, fim))
        return [a for a in self.atas if a["niFornecedor"] == ni]

    def detalhar_contratacao(self, id_compra):
        return self.contratacoes.get(id_compra)


class SincroniaPncpTests(TestCase):
    def setUp(self):
        Empresa.objects.create(tenant=tenant_atual(), nome="Inside Solutions Ltda", cnpj=CNPJ)

    def rodar(self, cliente) -> dict:
        return sincronizar_pncp(hoje=HOJE, cliente=cliente)

    def test_vitoria_que_nao_estava_salva_vira_licitacao_no_licita(self):
        resumo = self.rodar(ClienteFalso(resultados=[UFVJM]))

        salva = OportunidadeSalva.objects.get()
        self.assertEqual((salva.cnpj_orgao, salva.ano_compra, salva.sequencial_compra), ("16888315000157", "2026", "41"))
        self.assertEqual(salva.uasg, "153036")
        self.assertEqual(salva.uf, "MG")
        self.assertEqual(salva.data_encerramento_proposta, dt.date(2026, 10, 21))
        self.assertEqual(salva.numero_processo, "23086011683202671")
        self.assertEqual(salva.plataforma_id, "compras_gov")
        self.assertEqual(resumo["salvas_criadas"], 1)
        evento = salva.eventos.get()
        self.assertEqual(evento.tipo, EventoOportunidadeSalva.Tipo.SALVA)
        self.assertIn("PNCP", evento.descricao)

    def test_item_homologado_fica_marcado_como_vencido_pela_empresa(self):
        self.rodar(ClienteFalso(resultados=[UFVJM]))

        item = ItemParticipado.objects.get()
        self.assertEqual(item.numero_item, "2")
        self.assertTrue(item.vencedor_e_a_empresa)
        self.assertEqual(item.valor_homologado, Decimal("7250"))
        self.assertEqual(item.quantidade, Decimal("2"))
        self.assertEqual(item.homologado_em, dt.date(2026, 10, 29))
        self.assertEqual(item.fonte, "pncp")

    def test_varios_itens_da_mesma_compra_ficam_numa_licitacao_so(self):
        self.rodar(ClienteFalso(resultados=[IBAMA_49, IBAMA_60]))

        salva = OportunidadeSalva.objects.get()
        self.assertEqual(sorted(salva.itens_participados.values_list("numero_item", flat=True)), ["49", "60"])

    def test_licitacao_ja_salva_e_reaproveitada(self):
        existente = OportunidadeSalva.objects.create(
            cnpj_orgao="16888315000157", ano_compra="2026", sequencial_compra="41", objeto="Salva antes"
        )

        resumo = self.rodar(ClienteFalso(resultados=[UFVJM]))

        self.assertEqual(OportunidadeSalva.objects.count(), 1)
        self.assertEqual(ItemParticipado.objects.get().oportunidade, existente)
        existente.refresh_from_db()
        self.assertEqual(existente.numero_processo, "23086011683202671")
        self.assertEqual(resumo["salvas_criadas"], 0)

    def test_rodar_duas_vezes_nao_duplica_nada(self):
        cliente = ClienteFalso(resultados=[UFVJM, IBAMA_49], atas=[ATA_UFVJM])

        self.rodar(cliente)
        self.rodar(cliente)

        self.assertEqual(OportunidadeSalva.objects.count(), 2)
        self.assertEqual(ItemParticipado.objects.count(), 2)
        self.assertEqual(DocumentoFinanceiro.objects.count(), 1)
        self.assertEqual(EventoOportunidadeSalva.objects.count(), 2)

    def test_ata_de_registro_de_precos_vira_documento_com_vigencia_e_saldo(self):
        self.rodar(ClienteFalso(resultados=[UFVJM], atas=[ATA_UFVJM]))

        ata = DocumentoFinanceiro.objects.get()
        self.assertEqual(ata.tipo, "ata")
        self.assertEqual(ata.fonte, "pncp")
        self.assertEqual(ata.item.numero_item, "2")
        self.assertEqual(ata.data, dt.date(2026, 11, 5))
        self.assertEqual(ata.vigente_ate, dt.date(2027, 11, 6))
        self.assertEqual(ata.valor, Decimal("14500.00"))
        self.assertEqual(ata.dados["quantidade_empenhada"], 0.0)

    def test_resultado_cancelado_e_ignorado(self):
        cancelado = {**UFVJM, "dataCancelamentoPncp": "2026-11-01T10:00:00"}

        self.rodar(ClienteFalso(resultados=[cancelado]))

        self.assertFalse(OportunidadeSalva.objects.exists())

    def test_consulta_cada_cnpj_ativo_uma_vez_numa_janela_que_cobre_a_ata(self):
        Empresa.objects.create(tenant=tenant_atual(), nome="Inside Log", cnpj="45723174000110")
        Empresa.objects.create(tenant=tenant_atual(), nome="Antiga", cnpj="11222333000181", ativa=False)
        cliente = ClienteFalso()

        self.rodar(cliente)

        consultados = sorted({c[1] for c in cliente.consultas})
        self.assertEqual(consultados, ["22015414000127", "45723174000110"])
        _, _, inicio, fim = cliente.consultas[0]
        self.assertEqual(fim, "2026-11-07")
        self.assertLessEqual(dt.date.fromisoformat(inicio), HOJE - dt.timedelta(days=365))

    def test_vitoria_aparece_na_torre_como_homologado_em_contratar(self):
        """Homologado é o começo de Contratar (pedido do Carlinhos, 08/11/2026):
        ganhou, agora é esperar contrato ou empenho."""

        from .torre import montar_torre

        self.rodar(ClienteFalso(resultados=[UFVJM]))

        torre = montar_torre(hoje=HOJE)
        contratar = next(e for e in torre["estagios"] if e["chave"] == "contratar")
        self.assertEqual([c["etapa"] for c in contratar["cartoes"]], ["homologado"])
        self.assertEqual(contratar["cartoes"][0]["estagio"], "contratar")
        self.assertEqual(contratar["cartoes"][0]["valor_ganho"], Decimal("14500"))

    def test_com_ata_a_vitoria_vai_para_contrato(self):
        from .torre import montar_torre

        self.rodar(ClienteFalso(resultados=[UFVJM], atas=[ATA_UFVJM]))

        torre = montar_torre(hoje=HOJE)
        contratar = next(e for e in torre["estagios"] if e["chave"] == "contratar")
        self.assertEqual([c["etapa"] for c in contratar["cartoes"]], ["contrato"])


class AgendamentoTests(TestCase):
    def test_sincronia_agendada_as_8h_de_brasilia_de_segunda_a_sexta(self):
        from django_celery_beat.models import PeriodicTask

        tarefa = PeriodicTask.objects.get(task="licitacoes.sincronizar_pncp")

        self.assertEqual((tarefa.crontab.minute, tarefa.crontab.hour), ("0", "8"))
        self.assertEqual(str(tarefa.crontab.timezone), "America/Sao_Paulo")
        # Fim de semana não tem movimentação (decisão da operação, 08/11/2026).
        self.assertEqual(tarefa.crontab.day_of_week, "1-5")
