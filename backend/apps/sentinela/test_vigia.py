"""Vigia, datas, acompanhadas e o sino (definidos com a operação em 09/11/2026)."""

from __future__ import annotations

import copy
import datetime as dt
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.empresas.models import Empresa
from apps.licitacoes.conferencia_diaria import conferir
from apps.licitacoes.encerradas import classificar
from apps.licitacoes.models import (
    EventoOportunidadeSalva,
    ItemAcompanhado,
    ItemParticipado,
    OportunidadeSalva,
    ParticipacaoCompra,
)
from apps.notificacoes.models import Notificacao
from apps.tenants.atual import tenant_atual

from .ingestao import receber
from .ronda import consultas
from .test_propostas import CNPJ, CUBATAO, HOJE, cartao, exemplo

BASE = "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-fase-externa/v1/compras"


def salva(codigo=CUBATAO, prazo_dias=-10, **extra):
    return OportunidadeSalva.objects.create(
        cnpj_orgao="47492806000108",
        ano_compra="2026",
        sequencial_compra=str(OportunidadeSalva.objects.count() + 1),
        uasg=codigo[:6],
        orgao_nome="ÓRGÃO TESTE",
        data_encerramento_proposta=HOJE + dt.timedelta(days=prazo_dias),
        link_plataforma=f"https://x/acompanhamento-compra?compra={codigo}",
        **extra,
    )


def textos(s):
    c = cartao(s)
    return [e["texto"] for e in c["etiquetas"]] if c else None


class _Base(TestCase):
    def setUp(self):
        Empresa.objects.create(tenant=tenant_atual(), nome="Inside", cnpj=CNPJ)
        patcher = mock.patch("django.utils.timezone.localdate", return_value=HOJE)
        patcher.start()
        self.addCleanup(patcher.stop)


class SuspensaESemPrazoTests(_Base):
    def test_suspensa_fica_em_oportunidade_com_o_aviso(self):
        s = salva()
        ParticipacaoCompra.objects.create(oportunidade=s, fase_compra="99", situacao_compra="SU")

        self.assertEqual(cartao(s)["etapa"], "oportunidade")
        self.assertIn("Compra suspensa", textos(s))
        self.assertNotIn(s.pk, classificar(HOJE))

    def test_sem_prazo_definido_fica_em_oportunidade_com_o_aviso(self):
        s = salva()
        ParticipacaoCompra.objects.create(oportunidade=s, fase_compra="99", situacao_compra="PD")

        self.assertEqual(cartao(s)["etapa"], "oportunidade")
        self.assertIn("Sem prazo definido", textos(s))

    def test_suspensa_no_pncp_tambem(self):
        s = salva(prazo_dias=5, situacao_pncp="suspensa")

        self.assertIn("Compra suspensa", textos(s))


class SessaoSemDataTests(_Base):
    """GEN-72 (14/11/2026): o Licita guarda quando o Compras.gov **disse** que
    a sessão não tem data ("Sem prazo definido") — fase 99, Disputa agendada,
    sem data de abertura. Diferente de data ainda não lida."""

    def participacao(self, codigo):
        return ParticipacaoCompra.objects.get(oportunidade__link_plataforma__contains=f"compra={codigo}")

    def test_exemplo_real_de_minhas_participacoes(self):
        # Na lista real, o Butantan (fase 99) vem sem o campo da data; o 142
        # (fase 1) vem com a data.
        receber(**exemplo("participacoes"))

        self.assertIs(self.participacao("99004505000092026").sessao_sem_data, True)
        self.assertIs(self.participacao("20010905001422026").sessao_sem_data, False)

    def test_campo_vazio_na_fase_99_tambem_e_sem_data(self):
        salva(prazo_dias=-19)
        receber(f"{BASE}/{CUBATAO}/participacao", {"numeroUasg": "986371", "faseCompraFaseExterna": "99",
                                                   "dataHoraPrevisaoAbertura": None})  # fmt: skip

        self.assertIs(self.participacao(CUBATAO).sessao_sem_data, True)

    def test_data_nao_lida_em_outra_fase_nao_marca(self):
        salva(prazo_dias=-19)
        receber(f"{BASE}/{CUBATAO}/participacao", {"numeroUasg": "986371", "faseCompraFaseExterna": "1"})

        self.assertIs(self.participacao(CUBATAO).sessao_sem_data, False)

    def test_saiu_a_data_desmarca(self):
        s = salva(prazo_dias=-19)
        ParticipacaoCompra.objects.create(oportunidade=s, fase_compra="99", sessao_sem_data=True)

        receber(f"{BASE}/{CUBATAO}/participacao", {"numeroUasg": "986371", "faseCompraFaseExterna": "1",
                                                   "dataHoraPrevisaoAbertura": "2026-11-20T09:00:00"})  # fmt: skip

        self.assertIs(self.participacao(CUBATAO).sessao_sem_data, False)


class DataAlteradaTests(_Base):
    def test_o_orgao_adiou_o_prazo_historico_e_sino(self):
        s = salva(prazo_dias=1)
        ParticipacaoCompra.objects.create(oportunidade=s, fase_compra="1")
        dados = [{"compra": {"numeroUasg": "986371", "modalidade": "5", "numero": "55", "ano": "2026",
                             "faseCompraFaseExterna": "1",
                             "dataHoraFimPropostas": f"{HOJE + dt.timedelta(days=8)}T09:00:00"}}]  # fmt: skip

        receber(f"{BASE}/{CUBATAO}/participacao", dados[0]["compra"])

        s.refresh_from_db()
        self.assertEqual(s.data_encerramento_proposta, HOJE + dt.timedelta(days=8))
        evento = s.eventos.get(tipo=EventoOportunidadeSalva.Tipo.DATA_ALTERADA)
        self.assertIn("prazo da proposta", evento.descricao)
        self.assertTrue(Notificacao.objects.filter(tipo="data", oportunidade=s).exists())


class VoltaDaVigiaTests(_Base):
    def setUp(self):
        super().setUp()
        self.s = salva()
        self.item = ItemParticipado.objects.create(
            oportunidade=self.s, numero_item="2", classificacao=5, vencedor_e_a_empresa=False
        )

    def test_perdido_vai_para_encerradas(self):
        self.assertEqual(classificar(HOJE)[self.s.pk][:2], ("encerradas", "perdida"))

    def test_convocacao_traz_de_volta_em_vermelho_e_avisa_no_sino(self):
        url = f"{BASE}/{CUBATAO}/em-selecao-fornecedores/participacoes/{CNPJ}/itens/2/propostas"
        receber(url, [{"identificador": "2", "propostaItem": {
            "participante": {"identificacao": CNPJ}, "classificacao": 5,
            "situacaoUltimaSolicitacaoAnexos": "S",
            "valores": {"valorPropostaInicial": {"valorInformado": 10}}}}])  # fmt: skip

        self.assertIsNotNone(cartao(self.s))
        self.assertTrue(any("convocação" in t for t in textos(self.s)))
        self.assertTrue(Notificacao.objects.filter(tipo="convocacao", nivel="alerta").exists())

    def test_recurso_aguardando_decisao_traz_de_volta(self):
        ItemParticipado.objects.filter(pk=self.item.pk).update(recursos=[{"nome": "BRAVA SUL"}])

        self.assertIsNotNone(cartao(self.s))

    def test_recurso_indeferido_nao_traz(self):
        ItemParticipado.objects.filter(pk=self.item.pk).update(recursos=[{"nome": "X"}], decisao_recurso="N")

        self.assertIsNone(cartao(self.s))


class VigiaDiariaTests(_Base):
    def setUp(self):
        super().setUp()
        self.s = salva()
        self.item = ItemParticipado.objects.create(
            oportunidade=self.s, numero_item="2", classificacao=5, vencedor_e_a_empresa=False,
            homologado_em=HOJE - dt.timedelta(days=10),
        )  # fmt: skip

    def vigia(self):
        return [c for c in consultas() if "/participacoes/" in c or "fase-recursal" in c]

    def test_perdido_entra_uma_vez_por_dia(self):
        self.assertEqual(len(self.vigia()), 2)  # proposta dele + recurso

        url = f"{BASE}/{CUBATAO}/em-selecao-fornecedores/participacoes/{CNPJ}/itens/2/propostas"
        receber(url, [{"identificador": "2", "propostaItem": {"participante": {"identificacao": CNPJ}, "classificacao": 5}}])

        self.assertEqual(self.vigia(), [])

    def test_180_dias_depois_da_homologacao_a_vigia_acaba(self):
        ItemParticipado.objects.filter(pk=self.item.pk).update(homologado_em=HOJE - dt.timedelta(days=181))

        self.assertEqual(self.vigia(), [])
        self.item.refresh_from_db()
        self.assertIn("180 dias", self.item.vigia_motivo)


class FakePncp:
    def __init__(self, detalhe=None, itens=None):
        self.detalhe = detalhe or {}
        self.itens = itens or []

    def detalhar_compra(self, **_):
        return self.detalhe

    def listar_itens(self, **_):
        return self.itens


class FakeCompras:
    def __init__(self, atas=None, contratos=None, codigo_orgao="36000", falha=None):
        self.atas = atas or []
        self.contratos = contratos or []
        self.codigo_orgao = codigo_orgao
        self.falha = falha
        self.consultas_de_contrato = []
        self.uasgs_consultadas = []

    def itens_de_ata_da_unidade(self, *_):
        return self.atas

    def codigo_orgao_da_uasg(self, uasg):
        self.uasgs_consultadas.append(uasg)
        return self.codigo_orgao

    def itens_de_contrato_da_compra(self, codigo_orgao, id_compra, inicio, fim):
        if self.falha:
            raise self.falha
        self.consultas_de_contrato.append((codigo_orgao, id_compra, inicio, fim))
        return self.contratos


def contrato(numero_item="00002", fornecedor="35569716000199", **extra):
    """Um item de contrato como vem do Contratos.gov.br (formato visto ao vivo em 18/11/2026)."""

    return {"idCompra": CUBATAO, "numeroItem": numero_item, "niFornecedor": fornecedor,
            "nomeRazaoSocialFornecedor": "VL-LOJA", "numeroContrato": "2026NE000023",
            "dataVigenciaInicial": "2026-11-05T00:00:00", "contratoExcluido": False,
            "contratoItemExcluido": False, **extra}  # fmt: skip


class ConferenciaDiariaTests(_Base):
    def test_pncp_adiou_e_suspendeu(self):
        s = salva(prazo_dias=3)
        pncp = FakePncp({"data_encerramento_proposta": str(HOJE + dt.timedelta(days=10)), "situacao_id": 4})

        resumo = conferir(HOJE, pncp, FakeCompras())

        s.refresh_from_db()
        self.assertEqual((resumo["datas"], resumo["situacoes"]), (1, 1))
        self.assertEqual(s.data_encerramento_proposta, HOJE + dt.timedelta(days=10))
        self.assertIn("Compra suspensa", textos(s))

    def test_acompanhada_ganha_os_itens_do_pncp(self):
        s = salva()
        ParticipacaoCompra.objects.create(oportunidade=s, fase_compra="4")
        pncp = FakePncp(itens=[{"numero_item": 1, "descricao_resumida": "Cadeira", "quantidade": 3},
                               {"numero_item": 2, "descricao_resumida": "Mesa", "quantidade": 1}])  # fmt: skip

        conferir(HOJE, pncp, FakeCompras())

        self.assertEqual(sorted(s.itens_acompanhados.values_list("numero_item", flat=True)), ["1", "2"])
        self.assertEqual(len([c for c in consultas() if "/em-selecao-fornecedores/itens/" in c]), 2)

    def test_ata_assinada_com_outra_empresa_encerra_a_vigia(self):
        s = salva()
        item = ItemParticipado.objects.create(oportunidade=s, numero_item="2", vencedor_e_a_empresa=False)
        atas = [{"idCompra": CUBATAO, "numeroItem": "00002", "niFornecedor": "35569716000199",
                 "nomeRazaoSocialFornecedor": "VL-LOJA", "dataAssinatura": "2026-11-05T00:00:00"}]  # fmt: skip

        resumo = conferir(HOJE, FakePncp(), FakeCompras(atas))

        item.refresh_from_db()
        self.assertEqual(resumo["vigias_encerradas"], 1)
        self.assertIn("VL-LOJA", item.vigia_motivo)


class FimDaVigiaPorContratoTests(_Base):
    """GEN-46 (18/11/2026): contrato, empenho ou termo de adesão do item com
    outra empresa no Contratos.gov.br encerra a vigia."""

    def setUp(self):
        super().setUp()
        self.s = salva()
        self.item = ItemParticipado.objects.create(oportunidade=self.s, numero_item="2", vencedor_e_a_empresa=False)

    def conferir(self, compras):
        resumo = conferir(HOJE, FakePncp(), compras)
        self.item.refresh_from_db()
        return resumo

    def test_contrato_com_outra_empresa_encerra_a_vigia(self):
        compras = FakeCompras(contratos=[contrato()])

        resumo = self.conferir(compras)

        self.assertEqual(resumo["vigias_encerradas"], 1)
        self.assertIsNotNone(self.item.vigia_encerrada_em)
        self.assertIn("contrato 2026NE000023", self.item.vigia_motivo)
        self.assertIn("VL-LOJA", self.item.vigia_motivo)
        self.assertEqual(compras.uasgs_consultadas, [CUBATAO[:6]])
        self.assertEqual(compras.consultas_de_contrato[0][:2], ("36000", CUBATAO))

    def test_um_codigo_de_orgao_por_uasg(self):
        outra = salva()  # mesma UASG, outra compra
        ItemParticipado.objects.create(oportunidade=outra, numero_item="1", vencedor_e_a_empresa=False)
        compras = FakeCompras()

        self.conferir(compras)

        self.assertEqual(compras.uasgs_consultadas, [CUBATAO[:6]])

    def test_contrato_com_a_propria_empresa_nao_encerra(self):
        self.conferir(FakeCompras(contratos=[contrato(fornecedor=CNPJ)]))

        self.assertIsNone(self.item.vigia_encerrada_em)

    def test_contrato_de_outro_item_nao_encerra(self):
        self.conferir(FakeCompras(contratos=[contrato(numero_item="00003")]))

        self.assertIsNone(self.item.vigia_encerrada_em)

    def test_contrato_ou_item_excluido_nao_encerra(self):
        self.conferir(FakeCompras(contratos=[contrato(contratoExcluido=True), contrato(contratoItemExcluido=True)]))

        self.assertIsNone(self.item.vigia_encerrada_em)

    def test_orgao_sem_codigo_nao_consulta(self):
        compras = FakeCompras(contratos=[contrato()], codigo_orgao=None)

        self.conferir(compras)

        self.assertEqual(compras.consultas_de_contrato, [])
        self.assertIsNone(self.item.vigia_encerrada_em)

    def test_ata_ja_encerrou_nao_consulta_contrato(self):
        atas = [{"idCompra": CUBATAO, "numeroItem": "2", "niFornecedor": "35569716000199"}]
        compras = FakeCompras(atas=atas, contratos=[contrato()])

        resumo = self.conferir(compras)

        self.assertEqual(resumo["vigias_encerradas"], 1)
        self.assertEqual(compras.consultas_de_contrato, [])
        self.assertIn("ata", self.item.vigia_motivo)

    def test_api_fora_do_ar_nao_para_a_conferencia(self):
        # Decisão de 18/11/2026: registra a falha e tenta no dia seguinte.
        resumo = self.conferir(FakeCompras(falha=RuntimeError("fora do ar")))

        self.assertEqual(resumo["vigias_encerradas"], 0)
        self.assertIsNone(self.item.vigia_encerrada_em)


class AcompanhadaTests(_Base):
    def setUp(self):
        super().setUp()
        self.s = salva()
        ParticipacaoCompra.objects.create(oportunidade=self.s, fase_compra="4")
        ItemAcompanhado.objects.create(oportunidade=self.s, numero_item="2")
        self.captura = exemplo("propostas_cubatao_item_2")

    def dados_sem_a_inside(self, homologado):
        dados = copy.deepcopy(self.captura["dados"])
        for p in dados[0]["propostasItem"]:
            if p["participante"]["identificacao"] == CNPJ:
                p["participante"]["identificacao"] = "11111111000111"
        dados[0]["homologado"] = homologado
        return dados

    def test_le_as_propostas_e_avisa_quando_sai_o_resultado(self):
        receber(self.captura["url"], self.dados_sem_a_inside(False))  # 1ª leitura: sem resultado
        receber(self.captura["url"], self.dados_sem_a_inside(True))

        item = ItemAcompanhado.objects.get()
        self.assertTrue(item.decidido)
        self.assertEqual(item.propostas.count(), 31)
        self.assertTrue(Notificacao.objects.filter(tipo="resultado", texto__contains="VL-LOJA").exists())
        self.assertTrue(Notificacao.objects.filter(tipo="relatorio").exists())

    def test_varios_itens_viram_um_aviso_por_compra(self):
        # GEN-104 (19/11/2026): a Dispensa 12/2026 deu 7 avisos de uma vez.
        ItemAcompanhado.objects.create(oportunidade=self.s, numero_item="3")
        url3 = self.captura["url"].replace("/itens/2/", "/itens/3/")
        for url, numero in ((self.captura["url"], "2"), (url3, "3")):
            for homologado in (False, True):
                dados = self.dados_sem_a_inside(homologado)
                dados[0]["identificador"] = numero
                receber(url, dados)

        aviso = Notificacao.objects.get(tipo="resultado")
        self.assertTrue(aviso.titulo.endswith("· 2 itens"))
        self.assertEqual([l.split(":")[0] for l in aviso.texto.split("\n")], ["Item 2", "Item 3"])

    def test_resultado_antigo_na_primeira_leitura_nao_avisa(self):
        # GEN-104 (2a, 19/11/2026): o resultado já tinha saído quando o
        # Licita leu o item pela primeira vez — grava, mas não avisa.
        receber(self.captura["url"], self.dados_sem_a_inside(True))

        self.assertTrue(ItemAcompanhado.objects.get().decidido)
        self.assertFalse(Notificacao.objects.filter(tipo__in=["resultado", "relatorio"]).exists())

    def test_compra_que_virou_dele_para_de_ler_os_outros_itens(self):
        # GEN-104 (1a, 19/11/2026): Dispensa 12/2026 — a rede de segurança
        # achou a proposta da Inside num item; os outros não são mais lidos.
        ItemAcompanhado.objects.create(oportunidade=self.s, numero_item="3")
        receber(self.captura["url"], self.captura["dados"])  # item 2: tem a Inside

        self.assertEqual(list(self.s.itens_acompanhados.values_list("numero_item", flat=True)), ["3"])
        self.assertEqual([c for c in consultas() if "/em-selecao-fornecedores/itens/3/" in c], [])

    def test_rede_de_seguranca_tinha_proposta_dele_volta_para_a_torre(self):
        receber(self.captura["url"], self.captura["dados"])

        self.assertFalse(ItemAcompanhado.objects.exists())
        self.assertEqual(self.s.itens_participados.get().classificacao, 23)
        self.assertEqual(ParticipacaoCompra.objects.get(oportunidade=self.s).proposta_cadastrada, True)


class SinoApiTests(APITestCase):
    def test_lista_marca_lida_por_pessoa(self):
        Notificacao.objects.create(tipo="data", titulo="Data alterada", chave="a")
        Notificacao.objects.create(tipo="convocacao", nivel="alerta", titulo="Convocação", chave="b")
        ana = User.objects.create_user(email="ana@x.com", password="x")
        bia = User.objects.create_user(email="bia@x.com", password="x")

        # GEN-104 (19/11/2026): o número conta só "Precisa de você" (a
        # convocação); a data alterada é "Para saber".
        self.client.force_authenticate(ana)
        sino = self.client.get("/api/notificacoes/").json()
        self.assertEqual((sino["nao_lidas"], sino["para_saber_nao_lidas"]), (1, 1))
        self.client.post("/api/notificacoes/lidas/", {}, format="json")
        sino = self.client.get("/api/notificacoes/").json()
        self.assertEqual((sino["nao_lidas"], sino["para_saber_nao_lidas"]), (0, 0))

        self.client.force_authenticate(bia)
        self.assertEqual(self.client.get("/api/notificacoes/").json()["nao_lidas"], 1)

    def test_repetida_nao_duplica(self):
        from apps.notificacoes.servico import avisar

        self.assertTrue(avisar("data", "x", chave="k"))
        self.assertFalse(avisar("data", "x", chave="k"))


class CaixaDeMensagensTests(_Base):
    """A caixa de mensagens do fornecedor (HAR de 07/11/2026, 7 mensagens)."""

    def receber_caixa(self, agora):
        captura = exemplo("mensagens")
        with mock.patch("apps.sentinela.ingestao.timezone.now", return_value=agora):
            return receber(captura["url"], captura["dados"])

    def test_cada_mensagem_vira_um_aviso_uma_vez_so(self):
        farroupilha = salva("15812705000612026", 0)
        agora = timezone.make_aware(dt.datetime(2026, 11, 7, 9, 0))

        resumo = self.receber_caixa(agora)
        de_novo = self.receber_caixa(agora)

        self.assertEqual((resumo["mensagens"], de_novo["novas"]), (7, 0))
        self.assertEqual(resumo["novas"], Notificacao.objects.filter(tipo="mensagem").count())
        aviso = Notificacao.objects.filter(tipo="mensagem", oportunidade=farroupilha).first()
        self.assertIsNotNone(aviso)
        self.assertIn("Retornaremos", Notificacao.objects.filter(tipo="mensagem").order_by("-id").first().texto + "".join(
            Notificacao.objects.filter(tipo="mensagem").values_list("texto", flat=True)))

    def test_mensagens_antigas_nao_inundam_o_sino(self):
        resumo = self.receber_caixa(timezone.make_aware(dt.datetime(2026, 11, 20, 9, 0)))

        self.assertEqual(resumo["novas"], 0)

    def test_a_ronda_le_a_caixa_primeiro(self):
        self.assertTrue(consultas()[0].startswith("/comprasnet-mensagem/v1/mensagens?"))



class CotouENaoParticipouTests(_Base):
    """Geriatria 34/2026 (10/11/2026): prazo vencido, com cotação, fora dos
    favoritos no Compras.gov — não fica esperando a Sentinela para sempre."""

    def setUp(self):
        super().setUp()
        from apps.cotador.models import Cotacao
        from apps.integracoes.plataformas import plataforma_padrao

        self.s = salva("09018705000342026", -1, plataforma_id=plataforma_padrao().id)
        Cotacao.objects.create(oportunidade=self.s)

    def test_fora_dos_favoritos_vai_para_descartadas(self):
        OportunidadeSalva.objects.filter(pk=self.s.pk).update(favorita_no_compras=False)

        self.assertEqual(classificar(HOJE)[self.s.pk][:2], ("descartadas", "prazo_cotacao"))

    def test_nos_favoritos_tambem_vai_para_descartadas(self):
        """Decisão de 10/11/2026 (Guarulhos 461): sem participação lida, o dia
        seguinte ao prazo já é Descartadas — favorito não prova proposta."""

        OportunidadeSalva.objects.filter(pk=self.s.pk).update(favorita_no_compras=True)

        self.assertEqual(classificar(HOJE)[self.s.pk][:2], ("descartadas", "prazo_cotacao"))


class JulgamentoEncerradoSemAInsideTests(_Base):
    """GEN-78 (14/11/2026): `JE` sem a Inside ganhar sai para Encerradas, mas
    é lido a cada ronda (10 min), não só na vigia diária: o 2º colocado pode
    ser convocado com prazo de horas."""

    CAMINHO = (
        f"/comprasnet-fase-externa/v1/compras/{CUBATAO}/em-selecao-fornecedores/participacoes/{CNPJ}/itens/3/propostas?filtro=2"
    )

    def setUp(self):
        super().setUp()
        self.s = salva()
        ParticipacaoCompra.objects.create(oportunidade=self.s, fase_compra="4", proposta_cadastrada=True)
        ItemParticipado.objects.create(oportunidade=self.s, numero_item="3", classificacao=2, fase_item="JE")

    def test_sai_para_encerradas(self):
        self.assertIsNone(cartao(self.s))
        self.assertEqual(classificar(HOJE)[self.s.pk][:2], ("encerradas", "perdida"))

    def test_continua_na_ronda_depois_de_lido(self):
        self.assertIn(self.CAMINHO, consultas())

        url = f"{BASE}/{CUBATAO}/em-selecao-fornecedores/participacoes/{CNPJ}/itens/3/propostas"
        receber(
            url,
            [{"identificador": "3", "fase": "JE", "propostaItem": {"participante": {"identificacao": CNPJ}, "classificacao": 2}}],
        )

        self.assertIn(self.CAMINHO, consultas())
