# Regras de negócio

## Vocabulário
| Termo | Significado |
|---|---|
| ASO | Atestado de Saúde Ocupacional: admissional, periódico, demissional, retorno, mudança de função |
| Função | Quem executa um exame (clínico, audiometria, enfermagem…) |
| Grade | Quem atende cada função em cada dia da semana e turno |
| Exceção | Férias, folga, ausência (de um profissional) ou feriado (da clínica) |
| Sistema externo | O sistema de gestão onde fica a agenda oficial da clínica |

## Vaga livre
Um horário serve para um conjunto de exames quando:
- cabe no expediente do dia;
- não há feriado no dia/turno;
- cada função tem um profissional **diferente** na grade confirmada, sem exceção, livre naquele horário e abaixo
  da capacidade por hora da função.

O profissional é um recurso único: se faz clínico e audiometria, ocupado numa, está ocupado na outra.
Exames de funções com agenda própria (psicologia, EEG…) vão para a equipe.

## O sistema externo tem prioridade
- Sem leitura válida e recente da agenda externa, o bot não oferece horário.
- Horário ocupado no externo não é oferecido pelo bot.
- Paciente que já tem agendamento no externo não ganha outro pelo bot.
- Cancelar ou remarcar o que já está no externo exige a **Supervisão**.

## Aprovação
- O bot pede; a vaga fica segura em `AGUARDANDO_APROVACAO`.
- A equipe aprova, altera o horário e aprova, ou recusa (com motivo).
- Aprovar confere tudo de novo: a data não passou e a vaga ainda existe.
- Recusar libera a vaga e passa a conversa para a equipe.
- Pode ser desligado no parâmetro `aprovacao_equipe` (aí o bot agenda direto).

## Perfis
| Perfil | Pode |
|---|---|
| ADMIN | Tudo, inclusive usuários e parâmetros |
| SUPERVISAO | Tudo da recepção, grade, textos do bot e mexer no que está no sistema externo |
| RECEPCAO | Agenda, aprovações, conversas, cadastros e exceções |
| LEITURA | Só consulta, com dados mascarados e sem ler mensagens |

## Avisos
- Nascem desligados (`envios_automaticos`).
- Lembrete do dia anterior pede SIM ou NÃO. NÃO vira pedido de cancelamento.
- Falta marcada no painel oferece remarcação; exceção nova pode avisar os afetados.
- SAIR funciona em qualquer momento; quem saiu só volta respondendo SIM.
