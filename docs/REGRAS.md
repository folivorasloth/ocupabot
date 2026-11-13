# Regras de negócio

## Vocabulário
| Termo | Significado |
|---|---|
| ASO | Atestado de Saúde Ocupacional: admissional, periódico, demissional, retorno, mudança de função |
| Função | Quem executa um exame (clínico, audiometria, enfermagem…) |
| Grade | Quem atende cada função em cada dia da semana e turno |
| Exceção | Férias, folga, ausência (de um profissional) ou feriado (da clínica) |
| Sistema externo | O sistema de gestão onde fica a agenda oficial da clínica |
| PCMSO | Programa de Controle Médico de Saúde Ocupacional da empresa: define os exames de cada função |
| Quem agenda | O contato que pede exames por uma empresa: RH, credenciadora ou escritório de contabilidade |

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
- A equipe aprova, propõe outro horário ou recusa (o motivo é opcional).
- Aprovar confere tudo de novo: a data não passou, a vaga ainda existe e o agendamento de origem (no
  cancelamento e na remarcação) não mudou nesse meio-tempo.
- Recusar libera a vaga e passa a conversa para a equipe.
- Pode ser desligado no parâmetro `aprovacao_equipe` (aí o bot agenda direto).

### Proposta de outro horário
A equipe não agenda por conta própria um horário que a pessoa não pediu.
- Propor segura a vaga nova, libera a pedida e manda a pergunta: 1 confirma, 2 pede outro horário.
- Só o 1 agenda, e antes confere a vaga outra vez. O 2 (ou um horário que deixou de valer) libera a vaga e
  passa a conversa para a equipe.
- A proposta vence no que vier primeiro: `proposta_validade_horas` ou 2 h antes do exame. Vencida, a vaga é
  liberada e vira alerta no painel. Nenhuma mensagem sai sozinha.
- A equipe pode cancelar a proposta enquanto espera.

### Marcadores do pedido
Só avisam; quem decide é a recepção.
| Marcador | Quando aparece |
|---|---|
| RH não confirmado | Pedido para uma empresa feito por quem não é contato confirmado dela |
| Nascimento diferente do cadastro | O CPF já tinha cadastro e a data informada não confere (a conversa segue igual, para o bot não revelar quem é paciente; o cadastro não é alterado) |
| Já tem pedido pendente | Outro pedido em aberto do mesmo paciente |

## Quem agenda
- Um contato do tipo RH, credenciadora ou contabilidade fica ligado às empresas pelas quais agenda.
- Com uma empresa, o bot já sabe para quem é o exame. Com várias, pergunta. A opção 0 procura outra empresa.
- Os avisos (confirmação, lembrete, falta) vão para quem agendou.
- Paciente particular cadastrado com telefone ganha o contato que recebe os avisos.

## Agenda
- O bot só oferece horário com `antecedencia_minima_min` de folga (padrão 60). A equipe pode marcar em cima da hora.
- A equipe não agenda além de `agenda_max_dias_futuro` (padrão 365): evita data digitada errada.
- Presença e falta só podem ser marcadas a partir do dia do exame.
- A tela Hoje avisa o agendamento que passou 30 minutos do horário sem presença nem falta.

## PCMSO das empresas
No cadastro da empresa: quem elaborou (a clínica ou outra empresa), até quando vale e se o documento em vigor
chegou. Em branco, a clínica não acompanha. A tela Hoje avisa PCMSO vencido, vencendo em `pcmso_alerta_dias` e,
quando outra empresa elaborou, documento que ainda não chegou.

## Perfis
| Perfil | Pode |
|---|---|
| ADMIN | Tudo, inclusive usuários e parâmetros |
| SUPERVISAO | Tudo da recepção, grade, textos do bot e mexer no que está no sistema externo |
| RECEPCAO | Agenda, aprovações, conversas, cadastros e exceções |

Não existe perfil só de consulta. Sempre há ao menos um administrador ativo: o último não pode ser rebaixado
nem desativado.

## Avisos
- Nascem desligados (`envios_automaticos`).
- Lembrete do dia anterior pede SIM ou NÃO. NÃO vira pedido de cancelamento.
- Quem marca para amanhã depois da hora do lembrete recebe o lembrete logo, se ainda for antes de
  `lembrete_limite_hora`.
- Falta marcada no painel oferece remarcação; exceção nova pode avisar os afetados (quem já foi avisado não
  recebe de novo, e o lembrete do dia anterior é cancelado).
- SAIR funciona em qualquer momento e vale para o número com e sem o nono dígito; quem saiu volta respondendo
  SIM. A equipe também registra o SAIR no painel, quando o pedido chega por telefone.
- Quem pediu SAIR não recebe aviso automático nem resposta da equipe: o painel mostra que é preciso ligar.
