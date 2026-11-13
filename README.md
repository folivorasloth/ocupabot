# OcupaBot

Agendamento de exames ocupacionais pelo WhatsApp, com agenda unificada e um painel web para a recepção.
O bot conversa e propõe, e **uma pessoa da equipe aprova**.

> Projeto acadêmico e de código aberto (MIT). Todos os dados do repositório são fictícios.

## O problema
Em clínicas de saúde ocupacional, os pedidos de exame (ASO) chegam por WhatsApp, a agenda fica em planilhas e
lembretes, e a agenda oficial costuma estar num sistema de gestão separado. A recepção confere tudo à mão, entre
várias fontes. O OcupaBot junta isso num lugar só:

| Peça | O que faz |
|---|---|
| **Bot de WhatsApp** | Agenda, remarca e cancela por uma máquina de estados explícita, **sem IA**. Dá para voltar um passo, e várias mensagens seguidas recebem uma resposta só |
| **Motor de vagas** | Calcula horários livres por expediente, grade, exceções, capacidade e profissionais |
| **Aprovação humana** | Tudo o que o bot pede espera a equipe, com a vaga segura enquanto isso. Outro horário? A equipe propõe e a pessoa confirma |
| **Quem agenda** | RH, credenciadora e contabilidade: um contato pode agendar por várias empresas |
| **Equipe no WhatsApp** | Quem é da equipe marca presença, falta, cancela, remarca e vê a agenda por mensagem, sempre com confirmação |
| **Painel web** | Hoje em abas, agenda, pedidos do bot, conversas (assumir/devolver), cadastros, PCMSO das empresas, grade, textos do bot e auditoria. Funciona no celular e pode ser instalado na tela de início |
| **Sistema externo** | A agenda oficial fica atrás de uma interface, com um simulador incluído |
| **Avisos** | Confirmação, lembrete do dia anterior, falta e remarcação, com uma trava geral |

## Telas
Hoje · Agenda · Pedidos do bot · Conversas · Testar o bot · Empresas e pacientes (com "Quem agenda") ·
Grade, folgas e feriados · Mensagens do bot e regras · Usuários · Auditoria

## Pilha
Python 3.11+ · FastAPI · SQLAlchemy 2 · Alembic · SQLite (WAL) ou Postgres · React 18 · Vite · Tailwind · Docker

## Rodando localmente
```bash
# backend
cd backend
pip install -e ".[dev]"
python -m pytest                      # testes
python -m ocupabot.cli demo           # banco fictício (logins: admin, supervisao, recepcao / senha ocupabot-demo)
OCUPABOT_SIMULADOR_ATIVO=true uvicorn ocupabot.api.app:app --reload
python -m ocupabot.worker             # em outro terminal: avisos e fila de envio

# painel
cd frontend
npm ci
npm run dev                           # http://localhost:5173 (usa a API em :8000)
npm run build                         # gera frontend/dist, servido pela API em http://localhost:8000
```

Conversar com o bot no terminal, sem WhatsApp:
```bash
cd backend && python -m ocupabot.cli conversar
```

## Rodando com Docker
```bash
cp .env.example .env                  # preencha OCUPABOT_SEGREDO e o resto
docker compose up -d --build
docker compose exec app python -m ocupabot.cli usuario --login admin --nome "Admin" --perfil ADMIN
```
Com WhatsApp (WAHA, integração não oficial): `docker compose --profile whatsapp up -d`.

## Segurança por padrão
- O bot nasce **desligado**, o WhatsApp nasce em **modo teste** e os envios automáticos nascem **desligados**.
- CPF, RG e nascimento não ficam legíveis no histórico da conversa nem na auditoria; o WhatsApp nunca leva
  resultado de exame.
- Senhas com Argon2 e política mínima; senha dada pelo admin é trocada no primeiro acesso. Cookie HttpOnly e
  SameSite, limite de tentativas, perfis conferidos rota a rota.
- Toda alteração vai para a auditoria, e também as tentativas de acesso recusadas. O `.env` e os bancos nunca
  entram no git (verificado na CI).
- O app não sobe com o WhatsApp ligado se `OCUPABOT_SEGREDO` ainda for o valor de exemplo.

## Documentação
| Arquivo | Conteúdo |
|---|---|
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Componentes, fluxo de um pedido e decisões técnicas |
| [docs/REGRAS.md](docs/REGRAS.md) | Regras de negócio e vocabulário |
| [docs/BOT.md](docs/BOT.md) | A máquina de estados do bot |
| [docs/INTEGRACOES.md](docs/INTEGRACOES.md) | WhatsApp e como ligar o sistema de gestão da sua clínica |
| [docs/SEGURANCA.md](docs/SEGURANCA.md) | Ameaças, controles e LGPD |
| [docs/TCC.md](docs/TCC.md) | Temas de pesquisa e próximos passos |

## Licença
[MIT](LICENSE)
