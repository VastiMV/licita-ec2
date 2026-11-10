"""Os avisos do sino no Telegram (10/11/2026).

Cada notificação nova vai, em segundo plano (Celery), para os chats de
`TELEGRAM_CHAT_IDS`. Sem `TELEGRAM_BOT_TOKEN` ou sem chats: não faz nada.
Uma falha do Telegram nunca atrapalha o Licita — fica só no registro.
"""

from __future__ import annotations

import html
import logging

import httpx
from celery import shared_task

from config.settings.environment import env

logger = logging.getLogger(__name__)

API = "https://api.telegram.org"
ICONE = {"alerta": "🔴", "aviso": "🟡", "info": "🔵"}
SITE = "https://insidelicitacoes.com.br/torre"


def ligado() -> bool:
    return bool(env.telegram_token and chats())


def chats() -> list[str]:
    return [c.strip() for c in env.telegram_chats.split(",") if c.strip()]


def texto(notificacao) -> str:
    partes = [f"{ICONE.get(notificacao.nivel, '🔵')} <b>{html.escape(notificacao.titulo)}</b>"]
    if notificacao.texto:
        partes.append(html.escape(notificacao.texto[:1500]))
    partes.append(f'<a href="{SITE}">Abrir o Licita</a>')
    return "\n".join(partes)


@shared_task(name="notificacoes.enviar_telegram")
def enviar_telegram(notificacao_id: int) -> int:
    from .models import Notificacao

    if not ligado():
        return 0
    notificacao = Notificacao.objects.filter(pk=notificacao_id).first()
    if not notificacao:
        return 0
    enviados = 0
    for chat in chats():
        try:
            resposta = httpx.post(
                f"{API}/bot{env.telegram_token}/sendMessage",
                json={
                    "chat_id": chat,
                    "text": texto(notificacao),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            resposta.raise_for_status()
            enviados += 1
        except httpx.HTTPError:
            logger.warning("Telegram: falha ao mandar a notificação %s ao chat %s", notificacao_id, chat)
    return enviados


class RoboRecusou(Exception):
    """Erro do Telegram **sem** a chave do robô na mensagem."""


def quem_falou_com_o_robo() -> list[dict]:
    """Os chats que mandaram mensagem ao robô (para achar o número do chat)."""

    try:
        resposta = httpx.get(f"{API}/bot{env.telegram_token}/getUpdates", timeout=10)
    except httpx.HTTPError as exc:
        raise RoboRecusou("não consegui falar com o Telegram") from None
    if resposta.status_code != 200:
        # Nunca o endereço: ele leva a chave do robô.
        raise RoboRecusou(f"o Telegram respondeu {resposta.status_code} (chave errada ou trocada?)")
    vistos = {}
    for u in resposta.json().get("result", []):
        chat = (u.get("message") or u.get("my_chat_member") or {}).get("chat") or {}
        if chat.get("id"):
            nome = chat.get("title") or " ".join(p for p in (chat.get("first_name"), chat.get("last_name")) if p)
            vistos[chat["id"]] = {"chat": chat["id"], "nome": nome, "usuario": chat.get("username") or ""}
    return list(vistos.values())
