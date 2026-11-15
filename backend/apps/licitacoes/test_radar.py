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
