# Para o TCC

## Temas que o projeto permite discutir
- **Máquina de estados × IA generativa** em domínio regulado: previsibilidade, auditoria e privacidade.
- **Humano no circuito**: a aprovação como controle de risco e o custo operacional disso.
- **Fonte da verdade externa**: falhar fechado quando o sistema oficial não responde.
- **Alocação de recursos**: o motor de vagas como problema de emparelhamento (profissional único em várias funções).
- **Privacidade por padrão**: LGPD no código, no banco, nos logs e no git.

## Como medir
- Tempo médio da recepção por agendamento, antes e depois.
- Percentual de pedidos do bot aprovados sem alteração, e de propostas de horário aceitas (`aprovacoes.status`).
- Conversas que precisaram da equipe, por motivo (`conversas.motivo_humano`).
- Taxa de falta com e sem lembrete (`/api/painel/indicadores`).

## Próximos passos
1. Gravação automática no sistema externo, com trava por empresa e tratamento de resposta incerta.
2. Exames por função (GHE/PCMSO): sugerir os exames a partir da empresa, cargo e tipo de ASO. O cadastro
   da empresa já acompanha quem fez o PCMSO e até quando vale.
3. Convocação de periódicos a vencer.
4. API oficial do WhatsApp.
5. Multi-clínica (multi-tenant) com Postgres.
6. Autenticação em dois fatores para o painel.
