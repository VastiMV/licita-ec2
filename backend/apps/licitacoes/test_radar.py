"""O Radar (GEN-68, 14/11/2026): busca automática de compras parecidas com as
salvas nos últimos 30 dias e com o que a Inside ganhou, em todos os portais,
às 8h e às 18h. A sugestão fica 7 dias."""

from __future__ import annotations

import datetime as dt

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import ItemParticipado, OportunidadeSalva, SugestaoRadar
from .radar import DIAS_NO_RADAR, limpar, rodar, termos_da_base

HOJE = dt.date(2026, 11, 14)


def edital(seq: str, *, uf="SP", publicada="2026-11-13", prazo="2026-11-25", objeto="Aquisição de ração"):
    return {
        "cnpj_orgao": "11111111000111",
        "ano_compra": "2026",
        "sequencial_compra": seq,
        "numero_controle_pncp": f"11111111000111-1-{seq}/2026",
        "orgao_nome": "Prefeitura de Teste",
        "uasg": "",
        "uf": uf,
        "municipio": "Cidade",
        "modalidade": "Pregão - Eletrônico",
        "objeto": objeto,
        "data_publicacao": publicada,
        "data_encerramento_proposta": prazo,
    }


class FakePncp:
    """Responde à busca textual com os editais de `por_termo` (por palavra
    contida no termo); o link diz de que portal a compra é."""

    def __init__(self, por_termo: dict[str, list[dict]], links: dict[str, str] | None = None):
        self.por_termo = por_termo
        self.links = links or {}
        self.termos: list[str] = []

    def buscar_editais(self, termo, **_):
        self.termos.append(termo)
        for palavra, editais in self.por_termo.items():
            if palavra in termo.lower():
                return [dict(e) for e in editais], len(editais)
        return [], 0

    detalhes = 0

    def detalhar_compra(self, *, cnpj, ano, sequencial):
        self.detalhes += 1
        return {
            "link_plataforma": self.links.get(
                str(sequencial), "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras"
            )
        }

    def listar_itens(self, **_):
        return [
            {"numero_item": 1, "descricao_resumida": "Ração para aves", "quantidade": 10, "valor_total": 100.0},
        ]

    def close(self):
        pass


def salva(seq: str, descricao: str, dias_atras: int = 1, cnpj="22222222000122", **campos) -> OportunidadeSalva:
    s = OportunidadeSalva.objects.create(
        cnpj_orgao=cnpj,
        ano_compra="2026",
        sequencial_compra=seq,
        objeto="Objeto",
        itens=[{"descricao_resumida": descricao}],
        **campos,
    )
    quando = timezone.make_aware(dt.datetime.combine(HOJE - dt.timedelta(days=dias_atras), dt.time(10)))
    OportunidadeSalva.objects.filter(pk=s.pk).update(criada_em=quando)
    return s


class BaseDoRadarTests(APITestCase):
    def test_salvas_dos_ultimos_30_dias_e_ganhos(self):
        salva("1", "Ração para aves", dias_atras=5)
        salva("2", "Cadeira de rodas", dias_atras=40)  # fora dos 30 dias
        velha = salva("3", "Luva de procedimento", dias_atras=200)
        ItemParticipado.objects.create(
            oportunidade=velha, numero_item="1", descricao="Luva de procedimento", vencedor_e_a_empresa=True
        )

        termos = termos_da_base(HOJE)

        origens = [(origem, ganho) for _, origem, ganho in termos]
        self.assertEqual(origens[0], ("Luva de procedimento", True))  # ganho primeiro
        self.assertIn(("Ração para aves", False), origens)
        self.assertNotIn("Cadeira de rodas", [o for o, _ in origens])

    def test_tirada_da_lista_nao_entra_na_base(self):
        s = salva("1", "Ração para aves")
        s.remover()

        self.assertEqual(termos_da_base(HOJE), [])

    def test_mesmo_termo_nao_repete(self):
        salva("1", "Ração para aves")
        salva("2", "Ração para aves")

        self.assertEqual(len(termos_da_base(HOJE)), 1)


class RodadaTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_acha_compra_nova_de_qualquer_portal(self):
        salva("1", "Ração para aves")
        pncp = FakePncp(
            {"racao": [edital("10"), edital("11", uf="MG")]},
            links={"11": "https://www.portaldecompraspublicas.com.br/processos/123"},
        )

        resumo = rodar(HOJE, pncp)

        self.assertEqual(resumo["novas"], 2)  # as duas, sem filtro de portal
        # O Radar não pede o detalhe da compra (limite por IP do PNCP): o
        # portal e o link vêm quando o card é aberto.
        self.assertEqual(pncp.detalhes, 0)
        compras = SugestaoRadar.objects.get(sequencial_compra="10")
        self.assertEqual(compras.parecido_com, "Ração para aves")
        self.assertEqual(compras.expira_em, HOJE + dt.timedelta(days=DIAS_NO_RADAR))
        self.assertEqual(compras.itens[0]["contratacao_sequencial_compra"], "10")

    def test_ja_salva_ou_ja_no_radar_nao_volta(self):
        salva("1", "Ração para aves")
        salva("10", "", cnpj="11111111000111")  # a compra 10 já está salva
        pncp = FakePncp({"racao": [edital("10"), edital("12")]})

        primeira = rodar(HOJE, pncp)
        segunda = rodar(HOJE, pncp)

        self.assertEqual(list(SugestaoRadar.objects.values_list("sequencial_compra", flat=True)), ["12"])
        self.assertEqual((primeira["novas"], segunda["novas"]), (1, 0))

    def test_publicada_antes_da_janela_ou_prazo_vencido_nao_entra(self):
        salva("1", "Ração para aves")
        pncp = FakePncp({"racao": [edital("20", publicada="2026-11-01"), edital("21", prazo="2026-11-10")]})

        self.assertEqual(rodar(HOJE, pncp)["novas"], 0)

    def test_disputa_antes_dos_7_dias_some_no_dia_seguinte_a_abertura(self):
        # Ajuste da operação (14/11/2026): 7 dias OU a abertura da disputa,
        # o que vier primeiro. No dia da abertura ainda aparece.
        salva("1", "Ração para aves")
        rodar(HOJE, FakePncp({"racao": [edital("10", prazo="2026-11-17")]}))

        self.assertEqual(SugestaoRadar.objects.get().expira_em, dt.date(2026, 11, 18))
        self.assertEqual(limpar(dt.date(2026, 11, 17)), 0)
        self.assertEqual(limpar(dt.date(2026, 11, 18)), 1)

    def test_some_depois_de_7_dias(self):
        salva("1", "Ração para aves")
        rodar(HOJE, FakePncp({"racao": [edital("10")]}))

        self.assertEqual(limpar(HOJE + dt.timedelta(days=6)), 0)
        self.assertEqual(limpar(HOJE + dt.timedelta(days=7)), 1)


class RadarApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client.force_authenticate(User.objects.create_user(email="op@empresa.com", password="x"))
        salva("1", "Ração para aves", dias_atras=1)
        hoje = timezone.localdate()
        rodar(hoje, FakePncp({"racao": [
            edital("10", publicada=hoje.isoformat(), prazo=(hoje + dt.timedelta(days=10)).isoformat()),
            edital("11", uf="MG", publicada=hoje.isoformat(), prazo=(hoje + dt.timedelta(days=10)).isoformat()),
        ]}))  # fmt: skip

    def test_lista_com_filtro_de_uf_e_total(self):
        tudo = self.client.get("/api/licitacoes/radar/").data
        mg = self.client.get("/api/licitacoes/radar/", {"uf": "mg"}).data

        self.assertEqual(tudo["count"], 2)
        self.assertEqual([l["sequencial_compra"] for l in mg["results"]], ["11"])
        self.assertEqual(self.client.get("/api/licitacoes/radar/total/").data, {"total": 2})

    def test_salvar_pelo_card_tira_do_radar(self):
        linha = self.client.get("/api/licitacoes/radar/", {"uf": "SP"}).data["results"][0]

        resposta = self.client.post("/api/licitacoes/salvas/", {"itens": linha["itens"]}, format="json")

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(self.client.get("/api/licitacoes/radar/total/").data, {"total": 1})


class PncpPacienteTests(APITestCase):
    """Achado da rodada real (14/11/2026): 429 no detalhe fazia o Radar
    perder a compra calado."""

    def test_429_espera_e_tenta_de_novo(self):
        from unittest import mock

        from apps.integracoes.clients.pncp import PncpClient, PncpClientError

        from .radar import PncpPaciente

        respostas = [PncpClientError("PNCP respondeu 429 em /x"), PncpClientError("PNCP respondeu 429 em /x"), "ok"]

        def falso(self, caminho, params):
            r = respostas.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch.object(PncpClient, "_get_com_repeticao", falso), mock.patch("apps.licitacoes.radar.time.sleep") as dormir:
            self.assertEqual(PncpPaciente()._get_com_repeticao("/x", {}), "ok")
        self.assertEqual([c.args[0] for c in dormir.call_args_list], [5, 10])

    def test_outro_erro_nao_repete(self):
        from unittest import mock

        from apps.integracoes.clients.pncp import PncpClient, PncpClientError

        from .radar import PncpPaciente

        with mock.patch.object(PncpClient, "_get_com_repeticao", side_effect=PncpClientError("PNCP respondeu 404 em /x")):
            with self.assertRaises(PncpClientError):
                PncpPaciente()._get_com_repeticao("/x", {})


class ComandoRadarTests(APITestCase):
    def test_roda_e_mostra_se_os_itens_vieram(self):
        from io import StringIO
        from unittest import mock

        from django.core.management import call_command

        cache.clear()
        salva("1", "Ração para aves")
        pncp = FakePncp({"racao": [edital("10", publicada=timezone.localdate().isoformat(),
                                          prazo=(timezone.localdate() + dt.timedelta(days=9)).isoformat())]})
        saida = StringIO()
        with mock.patch("apps.licitacoes.radar.PncpPaciente", return_value=pncp):
            call_command("radar", stdout=saida)

        texto = saida.getvalue()
        self.assertIn("Base: 1 termos", texto)
        self.assertIn("Novas: 1 · com itens do PNCP: 1", texto)



class ItensQueFaltaramTests(APITestCase):
    """Teste no servidor (15/11/2026): o serviço de itens do PNCP fora do ar,
    67 sugestões entraram sem itens."""

    def setUp(self):
        cache.clear()

    def test_rodada_seguinte_completa_os_itens(self):
        salva("1", "Ração para aves")
        fora = FakePncp({"racao": [edital("10")]})
        fora.listar_itens = lambda **_: (_ for _ in ()).throw(__import__("apps.integracoes.clients.pncp", fromlist=["x"]).PncpClientError("503"))
        rodar(HOJE, fora)
        self.assertIsNone(SugestaoRadar.objects.get().itens[0]["descricao_resumida"])

        resumo = rodar(HOJE, FakePncp({"racao": []}))

        sugestao = SugestaoRadar.objects.get()
        self.assertEqual(resumo["itens_completados"], 1)
        self.assertEqual(sugestao.itens[0]["descricao_resumida"], "Ração para aves")
        self.assertEqual(sugestao.itens[0]["contratacao_sequencial_compra"], "10")  # os dados da compra ficam
        self.assertEqual(sugestao.valor_total_estimado, 100)

    def test_salva_so_com_o_item_vazio_conta_como_sem_itens(self):
        from .completar import falta_dados, sem_itens

        s = salva("1", "")
        s.itens = [{"descricao_resumida": None, "contratacao_objeto": "x"}]
        s.orgao_nome = "Órgão"
        s.data_encerramento_proposta = HOJE
        s.save()

        self.assertTrue(sem_itens(s.itens))
        self.assertTrue(falta_dados(s))
        self.assertIn(s, OportunidadeSalva.objects.filter(__import__("apps.licitacoes.completar", fromlist=["x"])._sem_dados()))



class NomeDoItemTests(APITestCase):
    """Teste no servidor (15/11/2026): termos fracos ("... tipo") puxavam
    compras sem relação."""

    def test_nome_antes_do_primeiro_atributo(self):
        from .radar import _nome_do_item

        casos = {
            "Tonômetro modelo: goldman, tipo base: móvel, tipo": "Tonômetro",
            "Lâmpada Fenda aplicação: serviço de oftalmologia,": "Lâmpada Fenda",
            "Facoemulsificador composição: vitrectomia anterior": "Facoemulsificador",
            "Equipamento - Uso Oftalmológico tipo: tomógrafo ót": "Equipamento - Uso Oftalmológico",
            "Ração para aves": "Ração para aves",
            "Seringa descartável": "Seringa descartável",
        }
        for descricao, nome in casos.items():
            self.assertEqual(_nome_do_item(descricao), nome, descricao)


class SoComItemQueCasaTests(APITestCase):
    """Regra da operação (17/11/2026): só entra a compra com pelo menos 1 item
    com todas as palavras do termo. Teste real sem a regra: 46 de 69 sem
    relação ("lâmpada fenda" trazia abraçadeira e alicate)."""

    def setUp(self):
        cache.clear()

    def test_casamento_de_palavras(self):
        from .radar import item_casa

        self.assertTrue(item_casa("lampada fenda", {"descricao_resumida": "LÂMPADA DE FENDA TIPO GALILEU"}))
        self.assertTrue(item_casa("luva de procedimento", {"descricao_resumida": "LUVAS PARA PROCEDIMENTO CX C/100"}))
        self.assertFalse(item_casa("lampada fenda", {"descricao_resumida": "Chave de fenda"}))
        self.assertFalse(item_casa("lampada fenda", {"descricao_resumida": "Lâmpada LED 9W"}))

    def test_compra_sem_item_que_casa_nao_entra(self):
        salva("1", "Lâmpada Fenda aplicação: serviço de oftalmologia")
        pncp = FakePncp({"lampada": [edital("10")]})
        pncp.listar_itens = lambda **_: [{"numero_item": 1, "descricao_resumida": "Abraçadeira de nylon", "valor_total": 5.0}]

        resumo = rodar(HOJE, pncp)

        self.assertEqual((resumo["novas"], resumo["sem_item_que_casa"]), (0, 1))
        self.assertFalse(SugestaoRadar.objects.exists())

    def test_le_todas_as_paginas_e_poe_o_item_que_casa_primeiro(self):
        salva("1", "Seringa descartável")
        pncp = FakePncp({"seringa": [edital("10")]})
        paginas = {
            1: [{"numero_item": n, "descricao_resumida": f"Item {n}", "valor_total": 1.0} for n in range(1, 51)],
            2: [{"numero_item": 120, "descricao_resumida": "SERINGA DESCARTÁVEL 5 ML", "valor_total": 1.0}],
        }
        pncp.listar_itens = lambda pagina=1, **_: paginas.get(pagina, [])

        rodar(HOJE, pncp)

        sugestao = SugestaoRadar.objects.get()
        self.assertEqual(len(sugestao.itens), 51)
        self.assertEqual(sugestao.itens[0]["numero_item"], 120)

    def test_sem_itens_fica_pendente_e_nao_aparece(self):
        from .radar import visiveis

        salva("1", "Ração para aves")
        hoje = timezone.localdate()
        fora = FakePncp({"racao": [edital("10", publicada=hoje.isoformat(), prazo=(hoje + dt.timedelta(days=9)).isoformat())]})

        def falha(**_):
            from apps.integracoes.clients.pncp import PncpClientError

            raise PncpClientError("503")

        fora.listar_itens = falha
        rodar(hoje, fora)

        self.assertEqual(SugestaoRadar.objects.count(), 1)
        self.assertEqual(visiveis(hoje).count(), 0)



class RemoverDoRadarTests(APITestCase):
    """GEN-93 (17/11/2026): "Remover do Radar" — sai da lista, não volta, e
    fica guardada como exemplo do que ele não quer."""

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(User.objects.create_user(email="op2@empresa.com", password="x"))
        salva("1", "Ração para aves", dias_atras=1)
        self.hoje = timezone.localdate()
        self.pncp = FakePncp({"racao": [edital("10", publicada=self.hoje.isoformat(),
                                               prazo=(self.hoje + dt.timedelta(days=10)).isoformat())]})
        rodar(self.hoje, self.pncp)
        self.sugestao = SugestaoRadar.objects.get()

    def test_remover_tira_da_lista_e_do_numero(self):
        resposta = self.client.post(f"/api/licitacoes/radar/{self.sugestao.pk}/remover/")

        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(self.client.get("/api/licitacoes/radar/").data["count"], 0)
        self.assertEqual(self.client.get("/api/licitacoes/radar/total/").data, {"total": 0})
        self.sugestao.refresh_from_db()
        self.assertIsNotNone(self.sugestao.removida_por)

    def test_removida_nao_volta_e_fica_guardada_depois_dos_7_dias(self):
        from .radar import limpar

        self.client.post(f"/api/licitacoes/radar/{self.sugestao.pk}/remover/")
        cache.clear()
        rodar(self.hoje, self.pncp)  # o PNCP acha a mesma compra de novo

        self.assertEqual(SugestaoRadar.objects.count(), 1)
        limpar(self.hoje + dt.timedelta(days=30))
        self.assertTrue(SugestaoRadar.objects.filter(pk=self.sugestao.pk).exists())

    def test_remover_duas_vezes_da_404(self):
        self.client.post(f"/api/licitacoes/radar/{self.sugestao.pk}/remover/")

        self.assertEqual(self.client.post(f"/api/licitacoes/radar/{self.sugestao.pk}/remover/").status_code, 404)


class AgrupamentoNaoEProdutoTests(APITestCase):
    """Operação, 17/11/2026: "Grupo 3" não é produto — buscar isso traz lixo."""

    def test_grupo_lote_item(self):
        from .radar import _sem_agrupamento

        self.assertEqual(_sem_agrupamento("Grupo 3"), "")
        self.assertEqual(_sem_agrupamento("LOTE 02"), "")
        self.assertEqual(_sem_agrupamento("Lote 2 - Luva de procedimento"), "Luva de procedimento")
        self.assertEqual(_sem_agrupamento("Luva de procedimento"), "Luva de procedimento")

    def test_grupo_fica_fora_da_base(self):
        salva("1", "Grupo 3")
        salva("2", "Ração para aves")

        self.assertEqual([o for _, o, _ in termos_da_base(HOJE)], ["Ração para aves"])


class FakeIA:
    """O cliente da Anthropic de mentira: nota por palavra no objeto."""

    def __init__(self, notas: dict[str, int] | None = None, falha=False):
        self.notas = notas or {}
        self.falha = falha
        self.perguntas: list[str] = []
        self.messages = self

    def parse(self, **kw):
        from types import SimpleNamespace

        from .radar_ia import Avaliacao

        pergunta = kw["messages"][0]["content"]
        self.perguntas.append(pergunta)
        if self.falha:
            import anthropic
            import httpx

            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))
        nota = next((n for palavra, n in self.notas.items() if palavra in pergunta), 5)
        return SimpleNamespace(stop_reason="end_turn", parsed_output=Avaliacao(nota=nota, motivo="teste"))


class IADoRadarTests(APITestCase):
    """GEN-93 (17/11/2026): a IA dá nota 0–10; abaixo de 7 não aparece, mas
    fica guardada (não é julgada de novo). Sem chave, a IA fica desligada."""

    def setUp(self):
        from unittest import mock

        cache.clear()
        self.hoje = timezone.localdate()
        salva("1", "Ração para aves")
        datas = {"publicada": self.hoje.isoformat(), "prazo": (self.hoje + dt.timedelta(days=9)).isoformat()}
        self.pncp = FakePncp({"racao": [edital("10", objeto="Ração para o zoológico", **datas),
                                        edital("11", objeto="Bandana e ração decorativa", **datas)]})
        self.ia = FakeIA({"zoológico": 9, "Bandana": 2})
        self.patches = [mock.patch("apps.licitacoes.radar_ia.ligada", return_value=True)]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def rodar_com_ia(self, ia=None):
        from unittest import mock

        from . import radar_ia

        original = radar_ia.avaliar
        with mock.patch.object(radar_ia, "avaliar", lambda *a, **kw: original(*a, cliente=ia or self.ia)):
            return rodar(self.hoje, self.pncp)

    def test_so_a_nota_alta_aparece_e_a_baixa_fica_guardada(self):
        from .radar import visiveis

        resumo = self.rodar_com_ia()

        self.assertEqual((resumo["aprovadas_ia"], resumo["reprovadas_ia"]), (1, 1))
        self.assertEqual([s.sequencial_compra for s in visiveis(self.hoje)], ["10"])
        self.assertEqual(SugestaoRadar.objects.get(sequencial_compra="11").nota_ia, 2)
        segunda = self.rodar_com_ia()
        self.assertEqual(segunda["aprovadas_ia"] + segunda["reprovadas_ia"], 0)  # não julga de novo

    def test_falha_da_ia_nao_guarda_e_tenta_na_proxima(self):
        resumo = self.rodar_com_ia(FakeIA(falha=True))

        self.assertEqual(resumo["ia_falhou"], 2)
        self.assertFalse(SugestaoRadar.objects.exists())

    def test_a_lixeira_vai_para_a_ia_como_exemplo_do_que_ele_nao_quer(self):
        from django.utils import timezone as tz

        SugestaoRadar.objects.create(
            cnpj_orgao="3", ano_compra="2026", sequencial_compra="1", objeto="Ração para peixes ornamentais",
            itens=[{"descricao_resumida": "Ração para peixes"}], expira_em=self.hoje, removida_em=tz.now(),
        )

        self.rodar_com_ia()

        self.assertIn("REMOVEU", self.ia.perguntas[0])
        self.assertIn("Ração para peixes", self.ia.perguntas[0])

    def test_referencias_incluem_salvas_descartadas_e_o_que_participou(self):
        from .models import ItemParticipado
        from .radar_ia import referencias

        descartada = salva("5", "Ração extrusada para aves silvestres")
        descartada.remover()
        ItemParticipado.objects.create(oportunidade=descartada, numero_item="1", descricao="Ração para aves de postura")

        refs = referencias("racao para aves")

        self.assertIn("Ração extrusada para aves silvestres", refs)
        self.assertIn("Ração para aves de postura", refs)



class IALigadaSoComChaveTests(APITestCase):
    def test_sem_chave_desligada_com_chave_ligada(self):
        from types import SimpleNamespace
        from unittest import mock

        from .radar_ia import ligada

        with mock.patch("apps.licitacoes.radar_ia.env", SimpleNamespace(anthropic_api_key="")):
            self.assertFalse(ligada())
        with mock.patch("apps.licitacoes.radar_ia.env", SimpleNamespace(anthropic_api_key="chave-de-teste")):
            self.assertTrue(ligada())



class ChaveRecusadaTests(IADoRadarTests):
    """Teste no servidor (17/11/2026): com a chave errada, o Radar fez 100
    perguntas iguais. Agora para na primeira e nada entra sem nota."""

    def test_chave_recusada_para_na_primeira(self):
        import anthropic
        import httpx

        from . import radar_ia

        class IARecusa(FakeIA):
            def parse(self, **kw):
                self.perguntas.append(kw)
                resposta = httpx.Response(401, request=httpx.Request("POST", "https://x"))
                raise anthropic.AuthenticationError("invalid x-api-key", response=resposta, body=None)

        ia = IARecusa()
        self.patches[0].stop()
        self.patches = []
        from types import SimpleNamespace
        from unittest import mock

        with mock.patch("apps.licitacoes.radar_ia.env", SimpleNamespace(anthropic_api_key="errada")):
            resumo = self.rodar_com_ia(ia)
        radar_ia._chave_recusada = False

        self.assertEqual(len(ia.perguntas), 1)
        self.assertEqual(resumo["ia_falhou"], 2)
        self.assertFalse(SugestaoRadar.objects.exists())
