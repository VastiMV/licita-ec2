"""Alarme de silêncio e topo "ligada, mas sem ler" (GEN-73, 14/11/2026).

Caso real: de 11/11 22h42 a 14/11 10h50 a Sentinela mandou "ok" a cada 3
minutos e não leu nada; o topo ficou verde e as mensagens do pregoeiro só
chegaram dois dias depois.
"""

from __future__ import annotations

import datetime as dt
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.notificacoes.models import Notificacao

from .estado import estado_atual
from .models import Pulso
from .silencio import conferir_silencio, minutos_sem_leitura


def quando(dia: int, hora: int, minuto: int = 0) -> dt.datetime:
    """Novembro de 2026: 11 = quarta, 13 = sexta, 14 = sábado, 16 = segunda."""
    return timezone.make_aware(dt.datetime(2026, 11, dia, hora, minuto))


class _Base(TestCase):
    def pulso(self, em: dt.datetime, estado="ok", captura=""):
        p = Pulso.objects.create(estado=estado, captura=captura, versao="0.2.6")
        Pulso.objects.filter(pk=p.pk).update(recebido_em=em)

    def ligada_ate(self, agora: dt.datetime):
        """Sinais de vida "ok" a cada 3 min na última meia hora (o vigia)."""
        for m in range(0, 30, 3):
            self.pulso(agora - dt.timedelta(minutes=m))


class AlarmeDeSilencioTests(_Base):
    def test_ligada_e_sem_ler_ha_45_min_avisa_uma_vez_no_episodio(self):
        agora = quando(11, 10, 45)
        self.pulso(quando(11, 10, 0), captura="mensagens")
        self.ligada_ate(agora)

        self.assertTrue(conferir_silencio(agora))
        self.assertFalse(conferir_silencio(agora + dt.timedelta(minutes=10)))  # mesmo episódio

        aviso = Notificacao.objects.get()
        self.assertEqual((aviso.tipo, aviso.nivel), ("sentinela", "alerta"))
        self.assertIn("ligada, mas não lê o Compras.gov há 45 min", aviso.titulo)
        self.assertIn("F5", aviso.texto)

    def test_leitura_recente_nao_avisa(self):
        agora = quando(11, 10, 45)
        self.pulso(quando(11, 10, 35), captura="mensagens")
        self.ligada_ate(agora)

        self.assertFalse(conferir_silencio(agora))

    def test_nova_queda_depois_de_voltar_e_outro_episodio(self):
        self.pulso(quando(11, 9, 0), captura="mensagens")
        self.ligada_ate(quando(11, 9, 40))
        self.assertTrue(conferir_silencio(quando(11, 9, 40)))

        self.pulso(quando(11, 10, 0), captura="mensagens")  # voltou a ler
        self.ligada_ate(quando(11, 10, 40))
        self.assertTrue(conferir_silencio(quando(11, 10, 40)))

        self.assertEqual(Notificacao.objects.count(), 2)

    def test_sem_sinal_de_vida_o_aviso_e_de_parada(self):
        self.pulso(quando(11, 9, 0), captura="mensagens")

        self.assertTrue(conferir_silencio(quando(11, 10, 0)))
        self.assertIn("parada", Notificacao.objects.get().titulo)

    def test_fora_do_horario_nao_conta(self):
        self.pulso(quando(13, 17, 0), captura="mensagens")

        self.assertIsNone(minutos_sem_leitura(quando(14, 11, 0)))  # sábado
        self.assertIsNone(minutos_sem_leitura(quando(11, 20, 0)))  # quarta, 20h
        self.assertFalse(conferir_silencio(quando(14, 11, 0)))

    def test_segunda_cedo_o_fim_de_semana_nao_conta(self):
        self.pulso(quando(13, 17, 0), captura="mensagens")  # sexta

        self.assertEqual(minutos_sem_leitura(quando(16, 8, 20)), 20)
        self.assertFalse(conferir_silencio(quando(16, 8, 20)))
        self.assertTrue(conferir_silencio(quando(16, 8, 40)))


class TopoLigadaSemLerTests(_Base):
    def test_pulsos_ok_sem_leitura_deixam_o_topo_ambar(self):
        agora = quando(11, 11, 0)
        self.pulso(quando(11, 10, 0), captura="mensagens")
        self.ligada_ate(agora)

        estado = estado_atual(agora)

        self.assertEqual(estado["estado"], "precisa_de_voce")
        self.assertIn("Ligada, mas sem ler o Compras.gov há 60 min", estado["detalhe"])

    def test_lendo_fica_verde(self):
        agora = quando(11, 11, 0)
        self.pulso(quando(11, 10, 55), captura="mensagens")
        self.ligada_ate(agora)

        self.assertEqual(estado_atual(agora)["estado"], "ok")

    def test_fora_do_horario_continua_verde(self):
        agora = quando(14, 11, 0)  # sábado
        self.pulso(quando(13, 17, 0), captura="mensagens")
        self.ligada_ate(agora)

        self.assertEqual(estado_atual(agora)["estado"], "ok")


class ConsultaPorDiaTests(_Base):
    def test_dia_ligada_e_sem_leitura_aparece_marcado(self):
        agora = timezone.now()
        self.pulso(agora - dt.timedelta(days=2), captura="mensagens")
        self.pulso(agora - dt.timedelta(hours=1))
        self.pulso(agora - dt.timedelta(minutes=50))

        saida = StringIO()
        with mock.patch("apps.sentinela.silencio.em_horario_de_trabalho", return_value=False):
            call_command("diagnostico", "sentinela", stdout=saida)
        texto = saida.getvalue()

        self.assertIn("Dia a dia (últimos 7)", texto)
        self.assertIn("⚠ ligada e sem leitura", texto)
        self.assertIn("Agora: fora do horário de trabalho", texto)
