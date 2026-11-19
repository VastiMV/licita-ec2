from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from . import telegram
from .models import Notificacao
from .servico import avisar

LIGADO = SimpleNamespace(telegram_token="123:abc", telegram_chats="111, 222")
DESLIGADO = SimpleNamespace(telegram_token="", telegram_chats="")


class TelegramTests(TestCase):
    def test_aviso_novo_vai_para_o_telegram_depois_de_gravar(self):
        with mock.patch.object(telegram, "env", LIGADO), mock.patch.object(telegram.enviar_telegram, "delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                avisar("convocacao", "Convocação · Pregão 61/2026", chave="c1", nivel="alerta")
            with self.captureOnCommitCallbacks(execute=True):
                avisar("convocacao", "Convocação · Pregão 61/2026", chave="c1", nivel="alerta")  # repetida

        delay.assert_called_once_with(Notificacao.objects.get(chave="c1").pk)

    def test_desligado_nao_manda(self):
        with mock.patch.object(telegram, "env", DESLIGADO), mock.patch.object(telegram.enviar_telegram, "delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                avisar("data", "Data alterada", chave="d1")

        delay.assert_not_called()

    def test_manda_para_cada_chat_com_o_texto_formatado(self):
        n = Notificacao.objects.create(tipo="recurso", nivel="alerta", titulo="Recurso <item 22>", texto="Brava & Sul", chave="r")
        with mock.patch.object(telegram, "env", LIGADO), mock.patch.object(telegram.httpx, "post") as post:
            enviados = telegram.enviar_telegram(n.pk)

        self.assertEqual(enviados, 2)
        corpo = post.call_args.kwargs["json"]
        self.assertTrue(corpo["text"].startswith("🔴 <b>Recurso &lt;item 22&gt;</b>"))
        self.assertIn("Brava &amp; Sul", corpo["text"])
        self.assertEqual(corpo["parse_mode"], "HTML")

    def test_falha_do_telegram_nao_quebra(self):
        n = Notificacao.objects.create(tipo="data", titulo="x", chave="y")
        with mock.patch.object(telegram, "env", LIGADO), mock.patch.object(
            telegram.httpx, "post", side_effect=telegram.httpx.ConnectError("sem rede")
        ):
            self.assertEqual(telegram.enviar_telegram(n.pk), 0)


class ChaveNuncaApareceTests(TestCase):
    def test_erro_do_telegram_nao_mostra_a_chave(self):
        resposta = mock.Mock(status_code=404)
        with mock.patch.object(telegram, "env", LIGADO), mock.patch.object(telegram.httpx, "get", return_value=resposta):
            with self.assertRaises(telegram.RoboRecusou) as erro:
                telegram.quem_falou_com_o_robo()

        self.assertNotIn("123:abc", str(erro.exception))
        self.assertIn("404", str(erro.exception))


class TesteTelegramApiTests(TestCase):
    def test_botao_de_teste_manda_para_os_chats(self):
        from rest_framework.test import APIClient

        from apps.accounts.models import User

        cliente = APIClient()
        cliente.force_authenticate(User.objects.create_user(email="v@x.com", password="x", nome="Vasti"))
        with mock.patch.object(telegram, "env", LIGADO), mock.patch.object(
            telegram.httpx, "post", return_value=mock.Mock(status_code=200)
        ) as post:
            resposta = cliente.post("/api/notificacoes/teste-telegram/", {}, format="json")

        self.assertEqual(resposta.json(), {"ligado": True, "enviados": 2, "chats": 2})
        self.assertIn("Pedido por Vasti", post.call_args.kwargs["json"]["text"])


class TarefasRegistradasNoWorkerTests(TestCase):
    """GEN-103 (19/11/2026): o worker só carrega tarefas de `tasks.py`
    (`autodiscover_tasks`). A do Telegram estava só em `telegram.py` e o
    worker jogava fora todo aviso ("unregistered task"). Roda num processo
    novo, como o worker ao subir: aqui dentro o `telegram.py` já foi
    importado pelos outros testes e esconderia o defeito."""

    def test_toda_tarefa_do_projeto_e_vista_pelo_worker(self):
        import re
        import subprocess
        import sys
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[2]
        nomes = set()
        for arquivo in (raiz / "apps").rglob("*.py"):
            nomes.update(re.findall(r'@shared_task\(name="([^"]+)"', arquivo.read_text(encoding="utf-8")))
        self.assertIn("notificacoes.enviar_telegram", nomes)

        script = (
            "import django; django.setup()\n"
            "from config.celery import app\n"
            "app.loader.import_default_modules()\n"
            "print('\\n'.join(sorted(app.tasks)))\n"
        )
        saida = subprocess.run(
            [sys.executable, "-c", script], cwd=raiz, capture_output=True, text=True, check=True
        ).stdout.split()
        self.assertEqual(sorted(nomes - set(saida)), [])
