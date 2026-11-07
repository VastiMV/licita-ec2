"""Lançamento manual do que nenhum sistema público informa (ou ainda não
informa): ordem de fornecimento, entrega e, por enquanto, contrato e o
empenho de estados e prefeituras.

- `GET/POST /api/licitacoes/salvas/<id>/documentos-financeiros/`
- `DELETE /api/licitacoes/documentos-financeiros/<id>/`
- `GET/POST /api/licitacoes/salvas/<id>/entregas/`
- `DELETE /api/licitacoes/entregas/<id>/`
"""

from __future__ import annotations

import datetime as dt

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import DocumentoFinanceiro, Entrega, Fonte, ItemParticipado, OportunidadeSalva
from .torre import montar_torre


class LancamentosTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="operador@empresa.com", password="x")
        self.client.force_authenticate(self.user)
        self.hoje = timezone.localdate()
        self.salva = OportunidadeSalva.objects.create(
            cnpj_orgao="03659166002156",
            ano_compra="2026",
            sequencial_compra="75",
            objeto="Alimentos para o Centro de Triagem",
            data_encerramento_proposta=self.hoje - dt.timedelta(days=40),
        )
        self.item = ItemParticipado.objects.create(
            oportunidade=self.salva, numero_item="49", vencedor_e_a_empresa=True, fonte=Fonte.PNCP
        )

    def url_docs(self, salva=None):
        return f"/api/licitacoes/salvas/{(salva or self.salva).pk}/documentos-financeiros/"

    def url_entregas(self, salva=None):
        return f"/api/licitacoes/salvas/{(salva or self.salva).pk}/entregas/"

    def etapa(self):
        for estagio in montar_torre(hoje=self.hoje)["estagios"]:
            for cartao in estagio["cartoes"]:
                if cartao["id"] == self.salva.pk:
                    return cartao["etapa"]
        return None

    def test_lancar_ordem_de_fornecimento_leva_para_empenho(self):
        resposta = self.client.post(
            self.url_docs(),
            {"tipo": "ordem_fornecimento", "numero": "OF 12/2026", "data": "2026-11-10", "valor": "1500.00"},
            format="json",
        )

        self.assertEqual(resposta.status_code, 201, resposta.data)
        documento = DocumentoFinanceiro.objects.get()
        self.assertEqual(documento.fonte, Fonte.MANUAL)
        self.assertEqual(documento.oportunidade, self.salva)
        self.assertEqual(resposta.data["tipo_rotulo"], "Ordem de fornecimento")
        self.assertEqual(self.etapa(), "empenho")

    def test_lancar_contrato_ligado_a_um_item(self):
        resposta = self.client.post(
            self.url_docs(),
            {"tipo": "contrato", "numero": "15/2026", "item_numero": "49", "vigente_ate": "2027-11-10"},
            format="json",
        )

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(DocumentoFinanceiro.objects.get().item, self.item)
        self.assertEqual(resposta.data["item_numero"], "49")
        self.assertEqual(self.etapa(), "contrato")

    def test_item_que_nao_e_desta_licitacao_e_recusado(self):
        resposta = self.client.post(
            self.url_docs(), {"tipo": "contrato", "item_numero": "999"}, format="json"
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("item_numero", resposta.data)
        self.assertFalse(DocumentoFinanceiro.objects.exists())

    def test_tipo_invalido_e_valor_negativo_sao_recusados(self):
        self.assertEqual(self.client.post(self.url_docs(), {"tipo": "boleto"}, format="json").status_code, 400)
        resposta = self.client.post(self.url_docs(), {"tipo": "empenho", "valor": "-1"}, format="json")
        self.assertEqual(resposta.status_code, 400)

    def test_mesmo_numero_lancado_duas_vezes_e_recusado_com_mensagem(self):
        dados = {"tipo": "ordem_fornecimento", "numero": "OF 7"}
        self.assertEqual(self.client.post(self.url_docs(), dados, format="json").status_code, 201)

        resposta = self.client.post(self.url_docs(), dados, format="json")

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("numero", resposta.data)

    def test_lista_mostra_os_lancados_e_os_que_vieram_dos_sistemas(self):
        DocumentoFinanceiro.objects.create(
            oportunidade=self.salva, tipo="ata", numero="ATA-1", fonte=Fonte.PNCP
        )
        self.client.post(self.url_docs(), {"tipo": "ordem_fornecimento", "numero": "OF 1"}, format="json")

        linhas = self.client.get(self.url_docs()).data

        self.assertEqual([(l["tipo"], l["fonte"]) for l in linhas], [("ata", "pncp"), ("ordem_fornecimento", "manual")])
        self.assertEqual(linhas[0]["fonte_rotulo"], "PNCP")

    def test_apaga_so_o_que_foi_lancado_a_mao(self):
        manual = DocumentoFinanceiro.objects.create(oportunidade=self.salva, tipo="contrato", numero="1")
        do_pncp = DocumentoFinanceiro.objects.create(
            oportunidade=self.salva, tipo="ata", numero="ATA-1", fonte=Fonte.PNCP
        )

        self.assertEqual(self.client.delete(f"/api/licitacoes/documentos-financeiros/{manual.pk}/").status_code, 204)
        recusa = self.client.delete(f"/api/licitacoes/documentos-financeiros/{do_pncp.pk}/")

        self.assertEqual(recusa.status_code, 400)
        self.assertEqual(list(DocumentoFinanceiro.objects.all()), [do_pncp])

    def test_lancar_entrega_leva_para_entrega(self):
        DocumentoFinanceiro.objects.create(oportunidade=self.salva, tipo="empenho", numero="2026NE1")

        resposta = self.client.post(
            self.url_entregas(),
            {"data": "2026-11-20", "nota_fiscal": "NF 345", "item_numero": "49", "observacao": "Recebido por João"},
            format="json",
        )

        self.assertEqual(resposta.status_code, 201, resposta.data)
        entrega = Entrega.objects.get()
        self.assertEqual(entrega.item, self.item)
        self.assertEqual(self.etapa(), "entrega")
        self.assertEqual(len(self.client.get(self.url_entregas()).data), 1)

    def test_entrega_sem_data_e_recusada_e_apagar_funciona(self):
        self.assertEqual(self.client.post(self.url_entregas(), {}, format="json").status_code, 400)

        entrega = Entrega.objects.create(oportunidade=self.salva, data=self.hoje)
        self.assertEqual(self.client.delete(f"/api/licitacoes/entregas/{entrega.pk}/").status_code, 204)
        self.assertFalse(Entrega.objects.exists())

    def test_licitacao_inexistente_e_404(self):
        self.assertEqual(self.client.get("/api/licitacoes/salvas/999999/documentos-financeiros/").status_code, 404)
        self.assertEqual(self.client.get("/api/licitacoes/salvas/999999/entregas/").status_code, 404)

    def test_sem_login_nao_entra(self):
        self.client.force_authenticate(None)

        self.assertEqual(self.client.get(self.url_docs()).status_code, 401)
