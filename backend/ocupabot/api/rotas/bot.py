import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ...bot import rajadas
from ...bot.maquina import processar
from ...config import config
from ...dominio.texto import normalizar_telefone
from ...integracoes.mensageria import canal
from ...modelos import Usuario
from ...servicos import auditoria, conversas
from ..deps import equipe, ip, sessao
from ..esquemas import SimuladorEntrada

log = logging.getLogger("ocupabot.webhook")
r = APIRouter(tags=["bot"])


@r.post("/webhook/whatsapp", include_in_schema=False)
async def webhook(request: Request, x_webhook_token: str = Header(default=""), s: Session = Depends(sessao)):
    esperado = config().webhook_token
    # compara em bytes: token com caractere fora do ASCII é recusado (401), não derruba a rota
    if not esperado or not hmac.compare_digest(x_webhook_token.encode(), esperado.encode()):
        auditoria.seguranca(s, "webhook_recusado", ip(request))
        raise HTTPException(401, "token inválido")
    corpo = await request.json()
    if not isinstance(corpo, dict) or corpo.get("event") != "message":
        return {"ignorado": "evento"}
    p = corpo.get("payload") or {}
    origem = str(p.get("from", ""))
    if p.get("fromMe") or not origem.endswith("@c.us"):
        return {"ignorado": "própria mensagem ou grupo"}
    telefone = normalizar_telefone(origem.split("@")[0])
    texto = str(p.get("body") or "").strip()
    if not texto and (p.get("hasMedia") or p.get("media")):
        texto = conversas.MIDIA  # áudio, foto, figurinha ou arquivo: o bot só lê texto
    if not texto:
        return {"ignorado": "sem texto"}
    if not conversas.pode_falar(telefone):
        return {"ignorado": "modo teste"}
    id_externo = str(p.get("id") or "")[:120] or None
    if not config().bot_ativo:
        contato = conversas.contato(s, telefone)
        conversas.registrar_entrada(s, conversas.conversa_de(s, contato), texto, id_externo)
        return {"registrado": True, "bot": "desligado"}
    if rajadas.janela(s) > 0:
        # só guarda: o laço do app responde quando a pessoa parar de escrever (uma resposta por rajada)
        return {"guardada": rajadas.guardar(s, telefone, texto, id_externo)}
    respostas = processar(s, telefone, texto, id_externo=id_externo)
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
    respostas = processar(s, dados.telefone, dados.texto, simulado=True)
    conv = conversas.conversa_de(s, conversas.contato(s, dados.telefone))
    return {"respostas": respostas,
            "conversa": {"id": conv.id, "estado": conv.estado.value, "fluxo": conv.fluxo, "etapa": conv.etapa}}
