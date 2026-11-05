# Arquitetura

```text
 WhatsApp ── WAHA ──webhook──▶  API (FastAPI)  ◀──────▶  painel React (/)
                                    │
                                    ▼
                         banco (SQLite WAL ou Postgres)
                                    ▲
                                    │
                                  worker ──▶ leitura da agenda externa
                                         ──▶ avisos automáticos
                                         ──▶ fila de saída do WhatsApp
```

Dois processos com o mesmo código: **app** (API, webhook e painel estático) e **worker** (o que roda sozinho).

## Pastas
| Caminho | Conteúdo |
|---|---|
| `backend/ocupabot/dominio/` | Código puro, sem banco: vagas, CPF/CNPJ, datas, texto |
| `backend/ocupabot/servicos/` | Regras com banco: agenda, aprovações, conversas, avisos, auditoria |
| `backend/ocupabot/bot/` | Máquina de estados (`maquina.py`) e reconhecimento de intenções |
| `backend/ocupabot/integracoes/` | Portas: canal de mensagens e agenda externa (com simulador) |
| `backend/ocupabot/api/` | Rotas, dependências de acesso e gerador de CRUD com auditoria |
| `backend/ocupabot/worker.py` | Laço de etapas isoladas com batimento |
| `backend/alembic/` | Migrations |
| `frontend/src/` | Painel React (HashRouter) |

## Um pedido pelo bot, passo a passo
1. O WAHA chama `/api/webhook/whatsapp`. O token é conferido em tempo constante; mensagem repetida (mesmo id) é descartada.
2. A mensagem é gravada com CPF/RG redigidos e a máquina de estados avança.
3. Antes de oferecer horário, o bot confere se a leitura da agenda externa é válida. Se não for, passa para a equipe.
4. O motor de vagas sugere o horário livre mais próximo; a pessoa aceita ou escolhe outro.
5. O agendamento nasce `AGUARDANDO_APROVACAO` (já segurando a vaga) e uma aprovação é aberta.
6. A recepção aprova, altera ou recusa no painel. A resposta sai como mensagem da equipe pela fila.

## Motor de vagas
`dominio/vagas.py` recebe um *retrato* (expediente, grade, exceções, capacidades, ocupações e bloqueios externos)
e responde, para um horário e um conjunto de funções, qual profissional diferente atende cada função. É uma
busca com retrocesso (emparelhamento) pequena e determinística, testada sem banco.

## Decisões
| Decisão | Por quê |
|---|---|
| Bot sem IA | Previsível, auditável e nenhum dado de saúde vai para terceiros |
| Humano aprova | O bot erra pouco, mas o custo de um erro na agenda é alto |
| `BEGIN IMMEDIATE` no SQLite | Duas reservas simultâneas não conferem a mesma vaga ao mesmo tempo |
| Portas (`Canal`, `AgendaExterna`) | Trocar WAHA pela API oficial ou plugar outro sistema não mexe no bot |
| Falha fechada no bot | Sem leitura confiável da agenda oficial, o bot não oferece horário |
| Worker em etapas isoladas | Uma etapa com erro não para as outras |
