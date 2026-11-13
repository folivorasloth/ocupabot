# O bot

Uma máquina de estados explícita em `backend/ocupabot/bot/maquina.py`. Cada etapa é um método `e_<etapa>`; o
estado (fluxo, etapa e dados) fica na tabela `conversas`, então reiniciar o servidor não perde nada.
Os textos ficam na tabela `textos` e podem ser editados no painel.

## Estados da conversa
| Estado | Quem responde |
|---|---|
| `BOT` | O bot |
| `AGUARDANDO_HUMANO` | Ninguém ainda: a conversa espera a equipe |
| `HUMANO` | A equipe, pelo painel |

## Ordem de decisão
1. Mensagem repetida é ignorada.
2. Número de alguém da equipe: pode ser um comando (veja abaixo).
3. `SAIR` vale sempre; quem saiu volta com `SIM`, mesmo com a conversa esperando a equipe.
4. Com a equipe, o bot só registra. Se a pessoa ainda não sabe, avisa uma vez que a equipe responde.
5. Áudio, foto ou arquivo recebem "escreva sua mensagem" (não conta como erro).
6. Pedido de atendente ou de resultado de exame vai para a equipe.
7. Resposta a aviso (lembrete, falta, remarcação). Aviso antigo, de agendamento que a equipe já mudou, vai
   para a equipe em vez de remarcar por cima.
8. Fluxo aberto continua; parado há mais de `fluxo_expira_horas`, recomeça do menu.
9. Menu. Cancelar, remarcar e preço escritos por extenso vão para a equipe; "oi" repetido só repete o menu.

Respostas não entendidas seguidas (`erros_ate_humano`, padrão 3) chamam a equipe.

## Fluxo de agendamento
`MENU → QUEM → CNPJ/ESCOLHER_EMPRESA → TIPO → NOME → CPF → NASCIMENTO → [RG → SETOR → CARGO] → EXAMES → SUGESTAO → [ESCOLHA → CONFIRMAR]`

Contato que agenda por uma empresa pula direto para o tipo de exame; quem agenda por várias escolhe a empresa
antes. A remarcação reaproveita `SUGESTAO`, `ESCOLHA` e `CONFIRMAR`.

Cada etapa tem dois métodos: `p_<etapa>` faz a pergunta e `e_<etapa>` trata a resposta. É o que permite o
**VOLTAR** ("voltar", "corrigir", "errei"): a trilha das etapas fica nos dados da conversa e voltar é
perguntar de novo a etapa anterior. `MENU` recomeça do zero.

Datas podem vir como `10/11`, `amanhã`, `sexta` ou `dia 12`.

## Proposta de outro horário
Quando a equipe propõe outro horário em Pedidos do bot, a conversa entra no fluxo `PROPOSTA`: 1 (ou SIM)
confirma, 2 (ou NÃO) pede outro horário e a conversa vai para a equipe. Esse fluxo tem prazo próprio
(`proposta_validade_horas`).

## Mensagens seguidas
Quem escreve "oi", "bom dia", "quero agendar" em três mensagens recebe **uma** resposta
(`bot/rajadas.py`). O webhook só guarda a mensagem; o app responde quando o número fica
`agrupar_mensagens_segundos` (padrão 8) sem escrever, ou depois de 60 s se a pessoa não parar. As mensagens
passam em ordem pela mesma máquina de estados e sai só a resposta final; a que não fez a conversa andar
("obrigado" depois de uma resposta válida) fica só no histórico. Com 0, cada mensagem responde na hora.

## Comandos da equipe
Usuário ativo do painel com o WhatsApp cadastrado (Usuários → WhatsApp) fala com o bot por comandos
(`bot/equipe.py`):

| Mensagem | O que faz |
|---|---|
| `agenda`, `agenda de amanhã` | Lista o dia |
| `paciente das 14h compareceu` | Marca presença |
| `das 14h faltou`, `Ana Lima não veio` | Marca falta (quem agendou é avisado) |
| `das 14:30 cancelou` | Cancela |
| `das 14h remarcou para 12/11 9h` | Remarca |
| `ajuda` | Mostra os comandos |

Nada muda sem o **SIM**: o bot repete o que entendeu e espera a confirmação por 10 minutos. Valem as regras
do painel (presença e falta só a partir do dia; o que está no sistema externo, só a Supervisão) e tudo vai
para a auditoria com o ator `whatsapp_equipe`. O que não é comando segue para o bot de sempre.

## Testando
```bash
cd backend
python -m pytest tests/test_bot.py -v
python -m ocupabot.cli conversar
```
Ou pelo **Simulador do bot** no painel (`OCUPABOT_SIMULADOR_ATIVO=true`).
