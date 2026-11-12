"""O estado da Sentinela para o botão do topo do Licita (o "vigia").

| Estado | Cor no topo | Quando |
|---|---|---|
| `nao_instalada` | cinza/âmbar | nunca falou |
| `ok` | verde | falou há pouco, tudo certo |
| `precisa_de_voce` | âmbar | a última notícia foi sessão caída, aba sem sessão, captcha pedido ou nenhuma aba aberta |
| `parada` | vermelho | em horário de trabalho, sem notícia há mais de `MINUTOS_PARADA` |

Fora do horário de trabalho (noite, fim de semana) o silêncio é normal:
continua `ok`, com a hora da última notícia.

Desde a Sentinela 0.2.6 (GEN-45, 12/11/2026) ela avisa a queda **uma vez**
e fica quieta enquanto a sessão estiver fora: a última notícia continua
sendo a queda, e o topo fica âmbar até ela avisar que a sessão voltou.
"""

from __future__ import annotations

import datetime as dt

from django.utils import timezone

from .models import Pulso

MINUTOS_PARADA = 15
HORARIO = (8, 18)  # das 8h às 18h, de segunda a sexta


def em_horario_de_trabalho(agora: dt.datetime) -> bool:
    local = timezone.localtime(agora)
    return local.weekday() < 5 and HORARIO[0] <= local.hour < HORARIO[1]


def estado_atual(agora: dt.datetime | None = None) -> dict:
    agora = agora or timezone.now()
    ultimo = Pulso.objects.first()
    if not ultimo:
        return {"estado": "nao_instalada", "ultimo_pulso": None, "ultima_captura": None, "detalhe": ""}
    captura = Pulso.objects.exclude(captura="").first()
    base = {
        "ultimo_pulso": ultimo.recebido_em,
        "ultima_captura": captura.recebido_em if captura else None,
        "detalhe": ultimo.get_estado_display() if ultimo.estado != Pulso.Estado.OK else ultimo.detalhe,
    }
    if ultimo.estado != Pulso.Estado.OK:
        return {"estado": "precisa_de_voce", **base}
    parada = agora - ultimo.recebido_em > dt.timedelta(minutes=MINUTOS_PARADA)
    if parada and em_horario_de_trabalho(agora):
        return {"estado": "parada", **base}
    return {"estado": "ok", **base}
