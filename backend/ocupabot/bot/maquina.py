"""Máquina de estados do bot de WhatsApp — sem IA.

O estado fica em `conversas` (fluxo, etapa, dados): reiniciar o servidor não perde nada.

Ordem de decisão para cada mensagem recebida:
  1. mensagem repetida (mesmo id externo) é ignorada;
  2. número de alguém da equipe: pode ser um comando (ver `equipe.py`);
  3. SAIR vale em qualquer ponto; quem saiu volta respondendo SIM;
  4. com a equipe cuidando da conversa, o bot só registra (e avisa uma vez que a equipe responde);
  5. áudio, foto ou arquivo recebem "escreva sua mensagem";
  6. pedido de atendente ou de resultado de exame vai para a equipe;
  7. resposta a um aviso enviado (lembrete, falta, remarcação);
  8. fluxo aberto continua (largado há muito tempo recomeça do menu; VOLTAR desfaz um passo);
  9. menu.
Mensagens não entendidas seguidas (parâmetro `erros_ate_humano`) passam a conversa para a equipe.

Cada etapa tem dois métodos: `p_<etapa>` faz a pergunta e `e_<etapa>` trata a resposta. É o que
permite o VOLTAR: a trilha das etapas fica em `dados` e voltar é perguntar de novo a etapa anterior.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio import datas
from ..dominio.documentos import cnpj_valido, cpf_problema, so_digitos
from ..dominio.texto import normalizar, primeiro_nome
from ..dominio.vagas import agrupar_faixas
from ..enums import (
    STATUS_ATIVOS,
    STATUS_OCUPAM,
    Autor,
    EstadoConversa,
    Origem,
    StatusAgendamento,
    StatusAprovacao,
    StatusNotificacao,
    TipoAprovacao,
    TipoContato,
    TipoNotificacao,
)
from ..modelos import Agendamento, Aprovacao, Contato, Conversa, Empresa, Exame, Expediente, Paciente, TipoAso
from ..relogio import agora, hoje
from ..servicos import agenda, aprovacoes, contatos, conversas, notificacoes, parametros, textos
from . import equipe as comandos
from . import intencoes as it

NAO_ENTENDI = object()
# Etapas que não entram na trilha do VOLTAR
SEM_VOLTA = {"MENU", "OFERTA", "RESPOSTA"}
# O que a pessoa digita nestas etapas não fica legível no histórico
MARCAS = {"CPF": "[CPF]", "NASCIMENTO": "[NASCIMENTO]", "RG": "[RG]"}


def atender(s: Session, telefone: str, texto: str, id_externo: str | None = None, simulado: bool = False,
            gravar_saida: bool = True) -> Bot | None:
    """Passa uma mensagem pela máquina. None se for repetida. Com `gravar_saida=False` as respostas só
    ficam em `bot.saida` (quem chama decide o que vai para a fila: ver `rajadas.py`)."""
    texto = texto.strip()
    contato = conversas.contato(s, telefone)
    conv = conversas.conversa_de(s, contato)
    if simulado:
        conv.simulada = True
    anterior = conv.ultima_entrada_em
    if not registrar(s, conv, texto, id_externo):
        return None
    bot = Bot(s, conv, contato, simulado, anterior, gravar_saida)
    usuario = comandos.usuario_do_numero(s, telefone)
    if usuario is None or not comandos.Equipe(bot, usuario).processar(texto):
        bot.tratar(texto)
    bot.salvar()
    return bot


def registrar(s: Session, conv: Conversa, texto: str, id_externo: str | None = None) -> bool:
    """Grava a mensagem recebida no histórico, sem o dado sensível da etapa. False se for repetida."""
    marca = MARCAS.get(conv.etapa or "") if conv.estado == EstadoConversa.BOT else None
    gravado = marca if marca and sum(c.isdigit() for c in texto) >= 4 else texto
    return conversas.registrar_entrada(s, conv, gravado, id_externo) is not None


def processar(s: Session, telefone: str, texto: str, id_externo: str | None = None,
              simulado: bool = False) -> list[str]:
    """Ponto de entrada: recebe uma mensagem e devolve (e enfileira) as respostas do bot."""
    bot = atender(s, telefone, texto, id_externo, simulado)
    return bot.saida if bot else []


class Bot:
    def __init__(self, s: Session, conv: Conversa, contato: Contato, simulado: bool,
                 anterior: datetime | None, gravar_saida: bool = True) -> None:
        self.s, self.conv, self.contato, self.simulado = s, conv, contato, simulado
        self.anterior = anterior
        self.gravar_saida = gravar_saida
        self.d: dict = dict(conv.dados or {})
        self.saida: list[str] = []
        self.sem_avanco = False  # a mensagem não fez a conversa andar ("não entendi", repetição do menu...)

    # --- utilidades ---------------------------------------------------------------------------------

    def diz(self, chave: str, **valores) -> None:
        self.dizer(textos.texto(self.s, chave, **valores))

    def dizer(self, texto: str) -> None:
        self.saida.append(texto)
        if self.gravar_saida:
            conversas.enfileirar(self.s, self.conv, texto, Autor.BOT, simulado=self.simulado)

    def ir(self, fluxo: str | None, etapa: str | None) -> None:
        self.conv.fluxo, self.conv.etapa = fluxo, etapa

    def passo(self, etapa: str) -> None:
        """Avança para a etapa e faz a pergunta dela; a etapa de onde saiu entra na trilha do VOLTAR."""
        self._entrar(etapa)
        getattr(self, f"p_{etapa.lower()}")()

    def _entrar(self, etapa: str) -> None:
        atual = self.conv.etapa
        if atual and atual != etapa and atual not in SEM_VOLTA:
            trilha = self.d.setdefault("_trilha", [])
            if etapa in trilha:  # já passou por aqui: o que veio depois não vale mais
                del trilha[trilha.index(etapa):]
            else:
                trilha.append(atual)
        self.conv.etapa = etapa

    def voltar(self) -> None:
        trilha = list(self.d.get("_trilha") or [])
        if not trilha:
            self.zerar()
            self.mostrar_menu()
            return
        etapa = trilha.pop()
        self.d["_trilha"] = trilha
        self.conv.etapa = etapa
        self.conv.erros_seguidos = 0
        getattr(self, f"p_{etapa.lower()}")()

    def zerar(self) -> None:
        self.d = {}
        self.ir(None, None)
        self.conv.erros_seguidos = 0

    def salvar(self) -> None:
        self.conv.dados = dict(self.d) if self.conv.estado == EstadoConversa.BOT else {}

    def equipe(self, motivo: str, avisar: bool = True) -> None:
        if avisar:
            self.diz("chamar_equipe" if self.em_expediente() else "chamar_equipe_fora")
        conversas.passar_para_equipe(self.s, self.conv, motivo, avisado=True)
        self.d = {}

    def em_expediente(self) -> bool:
        a = agora()
        for e in self.s.scalars(select(Expediente).where(Expediente.dia_semana == a.weekday())):
            if e.inicio <= a.time() < e.fim:
                return True
        return False

    # --- decisão principal --------------------------------------------------------------------------

    def tratar(self, texto: str) -> None:
        if it.eh_sair(texto):
            contatos.marcar_sair(self.s, self.contato, True, ator="bot")
            self.zerar()
            self.diz("optout_confirmado")
            return
        if self.contato.optout_em is not None and it.eh_sim(texto):
            # vale também com a conversa esperando a equipe: senão quem saiu nunca mais conseguiria voltar
            contatos.marcar_sair(self.s, self.contato, False, ator="bot")
            self.diz("optout_reativado")
            if self.conv.estado == EstadoConversa.BOT:
                self.mostrar_menu()
            return
        if self.conv.estado != EstadoConversa.BOT:
            self.sem_avanco = True
            if self.conv.estado == EstadoConversa.AGUARDANDO_HUMANO and self.conv.aviso_equipe_em is None:
                self.conv.aviso_equipe_em = agora()
                self.diz("com_a_equipe")
            return
        if texto == conversas.MIDIA:
            self.sem_avanco = True
            self.diz("midia_nao_suportada")
            return
        if it.pede_resultado(texto):
            self.diz("resultado_nao_enviado")
            self.equipe("pediu resultado de exame", avisar=False)
            return
        if it.quer_atendente(texto):
            self.equipe("pedido do contato")
            return
        if self.contato.optout_em is not None:
            self.sem_avanco = True
            self.diz("optout_ativo")
            return

        if self.conv.etapa in (None, "MENU") and self.responder_aviso(texto):
            return

        if self.conv.etapa:
            expira = timedelta(hours=parametros.inteiro(self.s, "fluxo_expira_horas"))
            proposta = self.conv.fluxo == "PROPOSTA"  # tem prazo próprio (proposta_validade_horas)
            if not proposta and self.anterior and agora() - self.anterior > expira:
                self.zerar()
                self.diz("fluxo_recomecado")
            elif not proposta and it.eh_recomecar(texto):
                self.zerar()
                self.diz("fluxo_recomecado")
                self.mostrar_menu()
                return
            elif not proposta and it.eh_voltar(texto):
                self.voltar()
                return
            else:
                self.executar(texto)
                return

        primeira = self.anterior is None
        if texto == "1":
            self.iniciar_agendamento()
            return
        if texto == "2":
            self.equipe("pedido do contato")
            return
        if self.texto_livre(texto):
            return
        if primeira and not self.em_expediente():
            self.diz("fora_expediente")
        self.mostrar_menu()

    def texto_livre(self, texto: str) -> bool:
        """Cancelar, remarcar e preço escritos por extenso: o bot não adivinha; a equipe continua."""
        if it.quer_mudar_agendamento(texto):
            self.equipe("quer cancelar ou remarcar um agendamento")
            return True
        if it.pergunta_preco(texto):
            self.equipe("perguntou sobre preço")
            return True
        return False

    def executar(self, texto: str) -> None:
        etapa = self.conv.etapa or ""
        metodo: Callable[[str], object] | None = getattr(self, f"e_{etapa.lower()}", None)
        if metodo is None:
            self.zerar()
            self.mostrar_menu()
            return
        resultado = metodo(texto)
        if resultado is NAO_ENTENDI:
            self.sem_avanco = True
            self.conv.erros_seguidos += 1
            if self.conv.erros_seguidos >= parametros.inteiro(self.s, "erros_ate_humano"):
                self.equipe("o bot não entendeu as respostas")
            else:
                self.diz("nao_entendi", dica=self.d.get("_dica", ""))
        else:
            self.conv.erros_seguidos = 0

    def mostrar_menu(self) -> None:
        self.ir(None, "MENU")
        self.d["_dica"] = textos.texto(self.s, "menu_dica")
        self.diz("menu")

    def e_menu(self, texto: str):
        op = it.opcao(texto, 2)
        if op == 1:
            self.iniciar_agendamento()
        elif op == 2:
            self.equipe("pedido do contato")
        elif it.eh_saudacao(texto):  # "oi" de novo: repete o menu, sem contar como erro
            self.sem_avanco = True
            self.diz("menu")
        elif not self.texto_livre(texto):
            return NAO_ENTENDI

    # --- avisos enviados ---------------------------------------------------------------------------

    def responder_aviso(self, texto: str) -> bool:
        abertos = notificacoes.aguardando_resposta(self.s, self.contato.id)
        if not abertos:
            return False
        n = abertos[0]
        ag = n.agendamento
        if n.tipo == TipoNotificacao.LEMBRETE_D1:
            if not (it.eh_sim(texto) or it.eh_nao(texto)):
                return False
            if len(abertos) > 1:
                self.equipe("resposta a vários lembretes abertos")
                return True
            if ag is None or ag.data < hoje() or ag.status not in STATUS_ATIVOS:
                self.equipe("resposta a lembrete de exame que já passou ou mudou")
                return True
            if it.eh_sim(texto):
                n.status, n.resposta = StatusNotificacao.RESPONDIDA, "SIM"
                ag.status = StatusAgendamento.CONFIRMADO
                self.diz("lembrete_sim")
                return True
            n.status, n.resposta = StatusNotificacao.RESPONDIDA, "NAO"
            if parametros.ligado(self.s, "aprovacao_equipe"):
                aprovacoes.pedir(self.s, TipoAprovacao.CANCELAMENTO, ag, contato_id=self.contato.id)
                self.diz("lembrete_nao_aprovacao")
            else:
                agenda.cancelar(self.s, ag, "Cancelado pelo WhatsApp (lembrete)", ator="bot")
                self.diz("lembrete_nao")
            self.d = {"base_id": ag.id, "_dica": "Responda 1 para escolher outro dia."}
            self.ir("REMARCAR", "OFERTA")
            return True
        # FALTA ou REMARCAR
        op = it.opcao(texto, 2)
        if op not in (1, 2):
            return False
        if op == 2:
            n.status, n.resposta = StatusNotificacao.RESPONDIDA, "2"
            self.equipe("resposta a aviso")
            return True
        if len(abertos) > 1:
            self.equipe("resposta a vários avisos abertos")
            return True
        n.status, n.resposta = StatusNotificacao.RESPONDIDA, "1"
        if ag is None or not self._ainda_remarca(n.tipo, ag):
            # aviso antigo: a equipe já cancelou ou remarcou; o bot não passa por cima
            self.equipe("resposta a aviso de agendamento que já mudou")
            return True
        self.d = {"base_id": ag.id, "remarcar_de": ag.id}
        self.iniciar_remarcacao()
        return True

    def _ainda_remarca(self, tipo: TipoNotificacao, ag: Agendamento) -> bool:
        esperado = {StatusAgendamento.FALTOU} if tipo == TipoNotificacao.FALTA else STATUS_ATIVOS
        ja_remarcado = self.s.scalar(select(Agendamento.id).where(Agendamento.remarcado_de_id == ag.id,
                                                                  Agendamento.status.in_(STATUS_OCUPAM)).limit(1))
        return ag.status in esperado and ja_remarcado is None

    def e_oferta(self, texto: str):
        if it.opcao(texto, 1) == 1 or it.eh_sim(texto):
            self.iniciar_remarcacao()
            return None
        self.zerar()
        self.tratar(texto)
        return None

    def iniciar_remarcacao(self) -> None:
        base = self.s.get(Agendamento, self.d["base_id"])
        self.d.update(
            paciente_id=base.paciente_id, nome=base.paciente.nome, empresa_id=base.empresa_id,
            tipo_id=base.tipo_aso_id, tipo_nome=base.tipo_aso.nome if base.tipo_aso else "exames",
            exame_ids=[i.exame_id for i in base.itens],
        )
        self.conv.fluxo = "REMARCAR"
        self.passo("SUGESTAO")

    # --- proposta de outro horário (feita pela equipe em Aprovações) ---------------------------------

    def e_resposta(self, texto: str):
        ap = self.s.get(Aprovacao, self.d.get("proposta") or 0)
        if ap is None or ap.status != StatusAprovacao.AGUARDANDO_CLIENTE or aprovacoes.venceu(ap):
            if ap is not None and ap.status == StatusAprovacao.AGUARDANDO_CLIENTE:
                aprovacoes.encerrar_proposta(self.s, ap, "a pessoa não respondeu a tempo",
                                             StatusAprovacao.EXPIRADA, ator="sistema")
            self.diz("proposta_expirada")
            self.equipe("respondeu a uma proposta de horário vencida", avisar=False)
            return None
        op = it.opcao(texto, 2)
        if op == 1 or it.eh_sim(texto):
            try:
                ag = aprovacoes.confirmar_proposta(self.s, ap)
            except (agenda.VagaIndisponivel, agenda.OperacaoInvalida):
                aprovacoes.encerrar_proposta(self.s, ap, "o horário deixou de valer")
                self.diz("proposta_indisponivel")
                self.equipe("o horário proposto deixou de valer", avisar=False)
                return None
            self.diz("agendado", paciente=primeiro_nome(ag.paciente.nome), data=datas.curta(ag.data),
                     horario=datas.hora(ag.horario))
            self.zerar()
            return None
        if op == 2 or it.eh_nao(texto):
            aprovacoes.encerrar_proposta(self.s, ap, "a pessoa pediu outro horário")
            self.diz("proposta_outro_horario")
            self.equipe("pediu outro horário depois da proposta", avisar=False)
            return None
        return NAO_ENTENDI

    # --- agendamento: empresa -----------------------------------------------------------------------

    def iniciar_agendamento(self) -> None:
        self.d = {}
        self.ir("AGENDAR", None)
        if contatos.agenda_pela_empresa(self.contato):
            empresas = contatos.empresas_do_contato(self.s, self.contato)
            if len(empresas) == 1:
                self.d["empresa_id"] = empresas[0].id
                self.diz("empresa_encontrada", empresa=empresas[0].nome_fantasia or empresas[0].razao_social)
                self.passo("TIPO")
                return
            if 2 <= len(empresas) <= 9:  # contabilidade, credenciadora ou RH de mais de uma empresa
                self.d.update(opcoes_empresa=[e.id for e in empresas], do_contato=True)
                self.passo("ESCOLHER_EMPRESA")
                return
            if empresas:  # lista grande demais para um menu: procura pelo CNPJ ou pelo nome
                self.passo("CNPJ")
                return
        self.passo("QUEM")

    def p_quem(self) -> None:
        self.d["_dica"] = "Responda 1 para empresa ou 2 para particular."
        self.diz("perguntar_quem")

    def e_quem(self, texto: str):
        op = it.opcao(texto, 2)
        if op == 1:
            self.d.pop("particular", None)
            self.passo("CNPJ")
        elif op == 2:
            self.d["particular"] = True
            self.d.pop("empresa_id", None)
            self.passo("TIPO")
        else:
            return NAO_ENTENDI

    def p_cnpj(self) -> None:
        self.d["_dica"] = "Mande o CNPJ (só números) ou o nome da empresa."
        self.diz("pedir_cnpj")

    def e_cnpj(self, texto: str):
        digitos = so_digitos(texto)
        if len(digitos) >= 11 and len(digitos) >= len(texto.replace(" ", "")) * 0.6:
            if not cnpj_valido(digitos):
                self.diz("cnpj_invalido")
                return None
            emp = self.s.scalar(select(Empresa).where(Empresa.cnpj == digitos, Empresa.ativa.is_(True)))
            if emp is None:
                self.diz("empresa_nao_encontrada")
                self.equipe("CNPJ sem cadastro", avisar=False)
                return None
            return self.escolheu_empresa(emp)
        nome = normalizar(texto)
        if len(nome) < 3:
            return NAO_ENTENDI
        achadas = [
            e for e in self.s.scalars(select(Empresa).where(Empresa.ativa.is_(True)))
            if nome in normalizar(e.razao_social) or nome in normalizar(e.nome_fantasia or "")
        ]
        if not achadas:
            self.diz("empresa_nao_encontrada")
            self.equipe("empresa não encontrada pelo nome", avisar=False)
            return None
        if len(achadas) == 1:
            return self.escolheu_empresa(achadas[0])
        self.d.update(opcoes_empresa=[e.id for e in achadas[:5]], do_contato=False)
        self.passo("ESCOLHER_EMPRESA")
        return None

    def p_escolher_empresa(self) -> None:
        empresas = [self.s.get(Empresa, i) for i in self.d.get("opcoes_empresa", [])]
        opcoes = "\n".join(f"{i} - {e.nome_fantasia or e.razao_social}" for i, e in enumerate(empresas, 1))
        self.d["_dica"] = "Responda com o número da empresa, ou 0 se não for nenhuma."
        self.diz("escolher_empresa_do_contato" if self.d.get("do_contato") else "escolher_empresa", opcoes=opcoes)

    def e_escolher_empresa(self, texto: str):
        ids = self.d.get("opcoes_empresa", [])
        op = it.opcao(texto, len(ids))
        if op is None:
            return NAO_ENTENDI
        if op == 0 and self.d.get("do_contato"):  # outra empresa, fora das dele: procura no cadastro
            self.passo("CNPJ")
            return None
        if op == 0:
            self.diz("empresa_nao_encontrada")
            self.equipe("empresa não encontrada", avisar=False)
            return None
        return self.escolheu_empresa(self.s.get(Empresa, ids[op - 1]))

    def escolheu_empresa(self, emp: Empresa):
        self.d["empresa_id"] = emp.id
        self.diz("empresa_encontrada", empresa=emp.nome_fantasia or emp.razao_social)
        self.passo("TIPO")
        return None

    # --- agendamento: dados do paciente -------------------------------------------------------------

    def _tipos(self) -> list[TipoAso]:
        return list(self.s.scalars(select(TipoAso).order_by(TipoAso.ordem, TipoAso.id)))

    def p_tipo(self) -> None:
        tipos = self._tipos()
        self.d["_dica"] = f"Responda com um número de 1 a {len(tipos)}."
        self.diz("pedir_tipo", opcoes="\n".join(f"{i} - {t.nome}" for i, t in enumerate(tipos, 1)))

    def e_tipo(self, texto: str):
        tipos = self._tipos()
        op = it.opcao(texto, len(tipos))
        if not op:
            return NAO_ENTENDI
        t = tipos[op - 1]
        self.d.update(tipo_id=t.id, tipo_nome=t.nome, exige=t.exige_cadastro_completo)
        self.passo("NOME")

    def p_nome(self) -> None:
        self.d["_dica"] = "Mande o nome completo do paciente."
        self.diz("pedir_nome")

    def e_nome(self, texto: str):
        nome = " ".join(texto.split())
        if len(nome.split()) < 2 or any(c.isdigit() for c in nome) or len(nome) > 160:
            return NAO_ENTENDI
        self.d["nome"] = nome.title()
        self.passo("CPF")

    def p_cpf(self) -> None:
        self.d["_dica"] = "Mande o CPF com 11 números."
        self.diz("pedir_cpf")

    def e_cpf(self, texto: str):
        problema = cpf_problema(texto)
        if problema:
            self.diz("cpf_invalido", problema=problema[0].upper() + problema[1:])
            return None
        self.d["cpf"] = so_digitos(texto)
        self.passo("NASCIMENTO")

    def p_nascimento(self) -> None:
        self.d["_dica"] = "Use dd/mm/aaaa."
        self.diz("pedir_nascimento")

    def e_nascimento(self, texto: str):
        nasc = datas.ler_nascimento(texto, hoje())
        if nasc is None:
            self.diz("nascimento_invalido")
            return None
        existente = self.s.scalar(select(Paciente).where(Paciente.cpf == self.d["cpf"]))
        # CPF já cadastrado com outro nascimento segue a MESMA conversa de um CPF novo (senão o bot
        # revelaria quem é paciente); a divergência vira marcador para a recepção conferir.
        self.d["divergencia"] = bool(existente and existente.nascimento and existente.nascimento != nasc)
        self.d["nascimento"] = nasc.isoformat()
        self.passo("RG" if self.d.get("exige") else "EXAMES")

    def p_rg(self) -> None:
        self.d["_dica"] = "Mande o número do RG."
        self.diz("pedir_rg")

    def e_rg(self, texto: str):
        rg = "".join(c for c in texto if c.isalnum())
        if not 5 <= len(rg) <= 14:
            return NAO_ENTENDI
        self.d["rg"] = rg.upper()
        self.passo("SETOR")

    def p_setor(self) -> None:
        self.d["_dica"] = "Escreva o setor em que a pessoa vai trabalhar."
        self.diz("pedir_setor")

    def e_setor(self, texto: str):
        if len(texto.strip()) < 2:
            return NAO_ENTENDI
        self.d["setor"] = texto.strip()[:120]
        self.passo("CARGO")

    def p_cargo(self) -> None:
        self.d["_dica"] = "Escreva a função (cargo) da pessoa."
        self.diz("pedir_cargo")

    def e_cargo(self, texto: str):
        if len(texto.strip()) < 2:
            return NAO_ENTENDI
        self.d["cargo"] = texto.strip()[:120]
        self.passo("EXAMES")

    def _exames(self) -> list[Exame]:
        return list(self.s.scalars(select(Exame).where(Exame.ativo.is_(True)).order_by(Exame.ordem, Exame.id)))

    def p_exames(self) -> None:
        exames = self._exames()
        self.d["_dica"] = "Use os números da lista separados por vírgula, ex.: 1,2"
        self.diz("pedir_exames", opcoes="\n".join(f"{i} - {e.nome}" for i, e in enumerate(exames, 1)))

    def e_exames(self, texto: str):
        exames = self._exames()
        nums = it.lista_numeros(texto, len(exames))
        if not nums:
            return NAO_ENTENDI
        escolhidos = [exames[n - 1] for n in nums]
        ids = [e.id for e in escolhidos]
        especialista = agenda.exames_de_especialista(self.s, ids)
        if especialista:
            nomes = ", ".join(e.nome for e in especialista)
            self.diz("exames_especialista", exames=nomes)
            self.equipe(f"exames com especialista: {nomes}", avisar=False)
            return None
        self.d["exame_ids"] = ids
        if agenda.paciente_ocupado_externo(self.s, self.d.get("cpf")):
            self.diz("ja_agendado_externo")
            self.equipe("paciente já agendado no sistema externo", avisar=False)
            return None
        self.passo("SUGESTAO")
        return None

    # --- horários ---------------------------------------------------------------------------------

    def p_sugestao(self) -> None:
        if not agenda.leitura_externa_valida(self.s):
            self.diz("sem_leitura_externa")
            self.equipe("leitura da agenda externa indisponível", avisar=False)
            return
        dias = agenda.proximos_dias(self.s, self.d["exame_ids"], 1)
        if not dias:
            self.diz("sem_vagas")
            self.equipe("sem vaga no prazo", avisar=False)
            return
        d, hs = dias[0]
        self.d["sugestao"] = [d.isoformat(), hs[0].strftime("%H:%M")]
        self.d["_dica"] = "Responda SIM para agendar ou NÃO para ver outros horários."
        self.diz("sugestao", paciente=self.d["nome"], tipo=self.d.get("tipo_nome", "exames"),
                 data=datas.curta(d), horario=datas.hora(hs[0]))

    def e_sugestao(self, texto: str):
        if it.eh_sim(texto):
            d, h = self.d["sugestao"]
            return self.pedir(date.fromisoformat(d), time.fromisoformat(h))
        if it.eh_nao(texto):
            self.listar()
            return None
        return self.e_escolha(texto)

    def _formatar(self, dias: list[tuple[date, list[time]]]) -> str:
        passo = parametros.inteiro(self.s, "passo_min")
        linhas = []
        for d, hs in dias:
            faixas = ", ".join(
                datas.hora(a) if a == b else f"{datas.hora(a)} às {datas.hora(b)}"
                for a, b in agrupar_faixas(hs, passo)
            )
            linhas.append(f"{datas.curta(d)}: {faixas}")
        return "\n".join(linhas)

    def listar(self, a_partir: date | None = None, aviso: str | None = None) -> None:
        dias = agenda.proximos_dias(self.s, self.d["exame_ids"],
                                    parametros.inteiro(self.s, "dias_lista_horarios"), a_partir=a_partir)
        if not dias:
            self.diz("sem_vagas")
            self.equipe("sem vaga no prazo", avisar=False)
            return
        exemplo = f"{dias[0][0]:%d/%m} {datas.hora(dias[0][1][0])}"
        self._entrar("ESCOLHA")
        self.d.pop("dia", None)
        self.d["_dica"] = f"Responda com o dia e a hora, ex.: {exemplo}"
        corpo = textos.texto(self.s, "listar_horarios", lista=self._formatar(dias), exemplo=exemplo)
        if aviso:
            corpo = f"{aviso} {corpo}"
        self.dizer(corpo)

    p_escolha = listar

    def e_escolha(self, texto: str):
        d = datas.ler_data(texto, hoje())
        h = datas.ler_hora(texto)
        if d is None and self.d.get("dia") and h is not None:
            d = date.fromisoformat(self.d["dia"])
        if d is None:
            if "/" in texto:
                self.diz("data_invalida")
                return None
            return NAO_ENTENDI
        if not agenda.dentro_do_prazo(self.s, d):
            self.diz("data_fora_prazo")
            return None
        livres = agenda.livres(self.s, d, self.d["exame_ids"], para_bot=True)
        if h is None:
            if not livres:
                self.listar(a_partir=d, aviso=f"Não tenho vaga em {datas.curta(d)}.")
                return None
            self._entrar("ESCOLHA")
            self.d["dia"] = d.isoformat()
            exemplo = datas.hora(livres[0])
            self.d["_dica"] = f"Responda com a hora, ex.: {exemplo}"
            self.diz("listar_horarios_dia", data=datas.curta(d), lista=self._formatar([(d, livres)]),
                     exemplo=exemplo)
            return None
        if h not in livres:
            self.diz("horario_indisponivel", data=datas.curta(d), horario=datas.hora(h))
            return None
        self.d["escolha"] = [d.isoformat(), h.strftime("%H:%M")]
        self.passo("CONFIRMAR")
        return None

    def p_confirmar(self) -> None:
        d, h = self.d["escolha"]
        self.d["_dica"] = "Responda SIM para confirmar ou NÃO para desistir."
        self.diz("confirmar_resumo", paciente=self.d["nome"], tipo=self.d.get("tipo_nome", "exames"),
                 data=datas.curta(date.fromisoformat(d)), horario=h)

    def e_confirmar(self, texto: str):
        if it.eh_sim(texto):
            d, h = self.d["escolha"]
            return self.pedir(date.fromisoformat(d), time.fromisoformat(h))
        if it.eh_nao(texto):
            self.zerar()
            self.diz("desistiu")
            return None
        return NAO_ENTENDI

    # --- criação do pedido ---------------------------------------------------------------------

    def _paciente(self) -> Paciente:
        if self.d.get("paciente_id"):
            return self.s.get(Paciente, self.d["paciente_id"])
        p = self.s.scalar(select(Paciente).where(Paciente.cpf == self.d["cpf"]))
        if p is None:
            p = Paciente(cpf=self.d["cpf"], nome=self.d["nome"])
            self.s.add(p)
        if not self.d.get("divergencia"):  # cadastro que não confere fica como está até a recepção ver
            p.nome = self.d["nome"]
            p.nascimento = date.fromisoformat(self.d["nascimento"])
            p.empresa_id = self.d.get("empresa_id") or p.empresa_id
            for campo in ("rg", "setor", "cargo"):
                if self.d.get(campo):
                    setattr(p, campo, self.d[campo])
        if self.contato.tipo == TipoContato.DESCONHECIDO and self.d.get("particular"):
            self.contato.tipo = TipoContato.PARTICULAR
        self.s.flush()
        return p

    def pedir(self, d: date, h: time):
        aprovacao = parametros.ligado(self.s, "aprovacao_equipe")
        pac = self._paciente()
        original = self.s.get(Agendamento, self.d["remarcar_de"]) if self.d.get("remarcar_de") else None
        try:
            if original is not None and not aprovacao:
                ag = agenda.remarcar(self.s, original, d, h, ator="bot", origem=Origem.WHATSAPP)
            else:
                ag = agenda.criar(
                    self.s, paciente_id=pac.id, exame_ids=self.d["exame_ids"], data=d, horario=h,
                    origem=Origem.WHATSAPP, empresa_id=self.d.get("empresa_id"), contato_id=self.contato.id,
                    tipo_aso_id=self.d.get("tipo_id"), para_bot=True, ator="bot",
                    status=StatusAgendamento.AGUARDANDO_APROVACAO if aprovacao else StatusAgendamento.AGENDADO,
                    avisar_confirmacao=False,
                )
        except agenda.VagaIndisponivel:
            self.listar(aviso=f"{datas.curta(d)} às {datas.hora(h)} acabou de ser ocupado.")
            return None
        except agenda.OperacaoInvalida:
            self.equipe("erro ao agendar")
            return None
        nome = primeiro_nome(self.d["nome"])
        if aprovacao:
            tipo = TipoAprovacao.REMARCACAO if original is not None else TipoAprovacao.NOVO
            aprovacoes.pedir(self.s, tipo, ag, original=original, contato_id=self.contato.id,
                             divergencia=bool(self.d.get("divergencia")))
            self.diz("aguardando_aprovacao", paciente=nome, data=datas.curta(d), horario=datas.hora(h))
        else:
            self.diz("agendado", paciente=nome, data=datas.curta(d), horario=datas.hora(h))
        self.zerar()  # CPF, nascimento e RG saem dos dados da conversa assim que o pedido é feito
        return None
