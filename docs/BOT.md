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
2. `SAIR` vale sempre.
3. Com a equipe, o bot só registra.
4. Pedido de atendente ou de resultado de exame vai para a equipe.
5. Quem saiu só volta com `SIM`.
6. Fluxo aberto continua; parado há mais de `fluxo_expira_horas`, recomeça do menu.
7. Resposta a aviso (lembrete, falta, remarcação).
8. Menu.

Respostas não entendidas seguidas (`erros_ate_humano`, padrão 3) chamam a equipe.

## Fluxo de agendamento
`MENU → QUEM → CNPJ/ESCOLHER_EMPRESA → TIPO → NOME → CPF → NASCIMENTO → [RG → SETOR → CARGO] → EXAMES → SUGESTAO → [ESCOLHA → CONFIRMAR]`

Contato já cadastrado como RH pula direto para o tipo de exame. A remarcação reaproveita `SUGESTAO`, `ESCOLHA`
e `CONFIRMAR`.

## Testando
```bash
cd backend
python -m pytest tests/test_bot.py -v
python -m ocupabot.cli conversar
```
Ou pelo **Simulador do bot** no painel (`OCUPABOT_SIMULADOR_ATIVO=true`).
