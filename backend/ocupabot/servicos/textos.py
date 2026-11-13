"""Textos do bot. Ficam no banco para a equipe editar; aqui estão os valores iniciais."""

import re

from sqlalchemy.orm import Session

from ..config import config
from ..modelos import Texto

PADROES: dict[str, str] = {
    "menu": "Olá! Aqui é o assistente da {clinica}.\n1 - Agendar exame\n2 - Falar com a equipe",
    "menu_dica": "Para agendar, responda 1. Para falar com a equipe, responda 2.",
    "nao_entendi": "Desculpe, não entendi. {dica}",
    "fora_expediente": "Nossa equipe atende {horario_atendimento}. Por aqui eu consigo agendar a qualquer hora.",
    "chamar_equipe": "Certo! Vou chamar alguém da equipe para continuar com você.",
    "chamar_equipe_fora": "Certo! Nossa equipe está fora do horário agora e retorna em breve "
    "({horario_atendimento}).",
    "resultado_nao_enviado": "Por segurança, não enviamos resultado de exame pelo WhatsApp. "
    "Vou passar para a equipe.",
    "optout_confirmado": "Pronto, você não vai mais receber mensagens automáticas. Se precisar, é só escrever.",
    "optout_ativo": "Você tinha pedido para não receber mensagens. Quer voltar? Responda SIM. "
    "Para falar com a equipe, responda ATENDENTE.",
    "optout_reativado": "Pronto, você voltou a receber nossas mensagens. Para parar, mande SAIR.",
    "fluxo_recomecado": "Tudo bem, deixei esse agendamento de lado.",
    "midia_nao_suportada": "Não consigo ouvir áudio nem abrir arquivos. Escreva sua mensagem, por favor.",
    "com_a_equipe": "Sua conversa está com a nossa equipe, que responde por aqui ({horario_atendimento}).",
    "escolher_empresa_do_contato": "Para qual empresa é o exame?\n{opcoes}\nResponda com o número, "
    "ou 0 se for outra.",
    "perguntar_quem": "O exame é para funcionário de uma empresa ou particular?\n1 - Empresa\n2 - Particular",
    "pedir_cnpj": "Qual o CNPJ da empresa? (Se não souber, mande o nome da empresa.)",
    "cnpj_invalido": "Esse CNPJ não parece válido. Confere e me manda de novo, por favor.",
    "empresa_nao_encontrada": "Não encontrei essa empresa no cadastro. Vou passar para a equipe, "
    "que faz o cadastro e continua com você.",
    "escolher_empresa": "Achei estas empresas:\n{opcoes}\nResponda com o número, ou 0 se não for nenhuma.",
    "empresa_encontrada": "Empresa: {empresa}.",
    "pedir_tipo": "Qual o tipo de exame?\n{opcoes}",
    "pedir_nome": "Nome completo do paciente:",
    "pedir_cpf": "CPF do paciente:",
    "cpf_invalido": "CPF inválido: {problema} Confere e me manda de novo.",
    "pedir_nascimento": "Data de nascimento do paciente (dd/mm/aaaa):",
    "nascimento_invalido": "Não entendi a data de nascimento. Use dd/mm/aaaa.",
    "pedir_rg": "RG do paciente:",
    "pedir_setor": "Setor em que vai trabalhar:",
    "pedir_cargo": "Função (cargo):",
    "pedir_exames": "Quais exames? Responda com os números separados por vírgula:\n{opcoes}",
    "exames_invalidos": "Não entendi os exames. Use os números da lista, ex.: 1,2",
    "exames_especialista": "Esses exames dependem da agenda dos especialistas ({exames}). "
    "Registrei o pedido e a equipe vai retornar com o horário.",
    "sem_leitura_externa": "Não consigo conferir a agenda agora. Vou passar para a equipe, "
    "que confirma o horário com você.",
    "ja_agendado_externo": "Esse paciente já tem um agendamento conosco. Vou passar para a equipe conferir.",
    "sugestao": "O horário livre mais próximo para {paciente} ({tipo}) é {data} às {horario}.\n"
    "Posso agendar? Responda SIM, ou NÃO para ver outros horários.",
    "sem_vagas": "Não encontrei horário livre nos próximos dias. Vou passar para a equipe.",
    "listar_horarios": "Horários livres:\n{lista}\n\nResponda com o dia e a hora (ex.: {exemplo}), "
    "ou mande outra data.",
    "listar_horarios_dia": "Horários livres em {data}:\n{lista}\n\nResponda com a hora (ex.: {exemplo}).",
    "dia_sem_vaga": "Não tenho vaga em {data}. {resto}",
    "data_invalida": "Não entendi a data. Use o formato dd/mm (ou dd/mm/aaaa).",
    "data_fora_prazo": "Essa data já passou ou está longe demais. Me manda outra (dd/mm).",
    "horario_indisponivel": "{data} às {horario} não está livre. Escolha um horário da lista.",
    "confirmar_resumo": "Confere:\nPaciente: {paciente}\nExame: {tipo}\nData: {data} às {horario}\n"
    "Confirma? (SIM/NÃO)",
    "desistiu": "Tudo bem, não agendei. Quando quiser, é só mandar uma mensagem.",
    "aguardando_aprovacao": "Recebi o pedido: {paciente}, {data} às {horario}. A equipe vai conferir "
    "e confirmar por aqui em breve.",
    "agendado": "Agendado! {paciente}, {data} às {horario}. {orientacoes}",
    "proposta_horario": "Não temos o horário que você pediu. Podemos em {data} às {horario}? "
    "Responda 1 para confirmar ou 2 para outro horário.",
    "proposta_outro_horario": "Certo, a equipe vai falar com você para combinar outro horário.",
    "proposta_expirada": "Essa proposta expirou; a equipe vai falar com você.",
    "proposta_indisponivel": "Esse horário não está mais livre. A equipe vai falar com você para combinar outro.",
    "aprovacao_recusada": "Não conseguimos confirmar o seu pedido. Alguém da equipe vai falar com você por aqui.",
    "cancelamento_confirmado": "Cancelamento confirmado: {paciente}, {data} às {horario}. "
    "Quando quiser marcar outro dia, é só mandar uma mensagem.",
    "confirmacao": "{clinica}: agendamento de {paciente} em {data} às {horario}. {orientacoes}",
    "lembrete_d1": "{clinica}: lembrete do exame de {paciente} amanhã, {data} às {horario}. "
    "Confirma a presença? Responda SIM ou NÃO.",
    "lembrete_sim": "Obrigado! Presença confirmada.",
    "lembrete_nao": "Certo, cancelei e liberei o horário. Quer remarcar? Responda 1.",
    "lembrete_nao_aprovacao": "Certo, pedi o cancelamento para a equipe, que vai confirmar por aqui. "
    "Quer remarcar? Responda 1.",
    "aviso_falta": "{clinica}: {paciente} não compareceu ao exame de {data} às {horario}. "
    "Quer remarcar? Responda 1.",
    "aviso_remarcar": "{clinica}: precisamos remarcar o exame de {paciente} de {data} às {horario}. "
    "Responda 1 para escolher outro dia ou 2 para falar com a equipe.",
}

DESCRICOES = {
    "menu": "Primeira mensagem e menu principal",
    "sugestao": "Oferta do horário livre mais próximo",
    "agendado": "Confirmação depois da aprovação",
    "confirmacao": "Confirmação de agendamento feito pela equipe no painel",
    "lembrete_d1": "Lembrete enviado no dia anterior",
    "midia_nao_suportada": "Resposta a áudio, foto, figurinha ou arquivo (o bot só lê texto)",
    "com_a_equipe": "Aviso, uma vez só, de que a conversa está com a equipe",
    "escolher_empresa_do_contato": "Contato que agenda por várias empresas escolhe a empresa",
    "proposta_horario": "A equipe propõe outro horário (só vale quando a pessoa responde 1)",
    "proposta_outro_horario": "Resposta 2 à proposta (a conversa vai para a equipe)",
    "proposta_expirada": "Resposta à proposta depois do prazo",
    "proposta_indisponivel": "Resposta 1 à proposta quando o horário deixou de valer",
}


def variaveis(t: str) -> list[str]:
    return sorted(set(re.findall(r"{(\w+)}", t)))


def garantir_padroes(s: Session) -> None:
    existentes = {t.chave for t in s.query(Texto.chave)}
    for chave, t in PADROES.items():
        if chave not in existentes:
            s.add(Texto(chave=chave, texto=t, descricao=DESCRICOES.get(chave, ""),
                        variaveis=",".join(variaveis(t))))
    s.flush()


class _Seguro(dict):
    def __missing__(self, chave):
        return "{" + chave + "}"


def renderizar(modelo: str, **valores) -> str:
    """Troca só {variavel}: chave solta ou formato estranho no texto editado não derruba o envio."""
    valores.setdefault("clinica", config().nome_clinica)
    seguro = _Seguro({k: "" if v is None else str(v) for k, v in valores.items()})
    return re.sub(r"{(\w+)}", lambda m: seguro[m.group(1)], modelo).strip()


def texto(s: Session, chave: str, **valores) -> str:
    from . import parametros

    registro = s.get(Texto, chave)
    modelo = registro.texto if registro else PADROES[chave]
    if "{horario_atendimento}" in modelo:
        valores.setdefault("horario_atendimento", parametros.texto(s, "horario_atendimento"))
    if "{orientacoes}" in modelo:
        valores.setdefault("orientacoes", parametros.texto(s, "orientacoes"))
    return renderizar(modelo, **valores)
