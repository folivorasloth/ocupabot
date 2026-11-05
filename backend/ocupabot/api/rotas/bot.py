import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ...bot.maquina import processar
from ...config import config
from ...dominio.texto import normalizar_telefone
from ...integracoes.mensageria import canal
from ...modelos import Usuario
from ...servicos import conversas
from ..deps import equipe, sessao
from ..esquemas import SimuladorEntrada

log = logging.getLogger("ocupabot.webhook")
r = APIRouter(tags=["bot"])


@r.post("/webhook/whatsapp", include_in_schema=False)
async def webhook(request: Request, x_webhook_token: str = Header(default=""), s: Session = Depends(sessao)):
    esperado = config().webhook_token
    if not esperado or not hmac.compare_digest(x_webhook_token.encode(), esperado.encode()):
        raise HTTPException(401, "token inválido")
    corpo = await request.json()
    if corpo.get("event") != "message":
        return {"ignorado": "evento"}
    p = corpo.get("payload") or {}
    origem = str(p.get("from", ""))
    if p.get("fromMe") or not origem.endswith("@c.us"):
        return {"ignorado": "própria mensagem ou grupo"}
    telefone = normalizar_telefone(origem.split("@")[0])
    texto = str(p.get("body") or "").strip()
    if not texto:
        return {"ignorado": "sem texto"}
    if not conversas.pode_falar(telefone):
        return {"ignorado": "modo teste"}
    if not config().bot_ativo:
        contato = conversas.contato(s, telefone)
        conversas.registrar_entrada(s, conversas.conversa_de(s, contato), texto, p.get("id"))
        return {"registrado": True, "bot": "desligado"}
    respostas = processar(s, telefone, texto, id_externo=p.get("id"))
    s.commit()
    # tenta enviar já; o que falhar o worker reenvia dentro da validade
    try:
        conversas.enviar_pendentes(s, canal(), limite=10)
    except Exception:  # noqa: BLE001
        log.exception("envio imediato falhou")
    return {"respostas": len(respostas)}


@r.post("/simulador/mensagem", summary="Conversa com o bot sem WhatsApp (grava no banco)")
def simulador(dados: SimuladorEntrada, s: Session = Depends(sessao), _: Usuario = Depends(equipe)):
    if not config().simulador_ativo:
        raise HTTPException(403, "simulador desligado (OCUPABOT_SIMULADOR_ATIVO)")
    return {"respostas": processar(s, dados.telefone, dados.texto, simulado=True)}
