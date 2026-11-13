# Segurança e LGPD

O sistema trata dados pessoais e dados de saúde, que a LGPD trata como sensíveis.
**Regra número 1: nenhum dado real no repositório, nos testes ou em conversas com assistentes de IA.**

## Controles
| Risco | Controle |
|---|---|
| Força bruta no login | Argon2 e limite de 5 tentativas por login+IP a cada 5 minutos; as recusas vão para a auditoria e, acima de `alerta_seguranca_limite` em 24 h, viram alerta para o administrador |
| Senha fraca ou conhecida por outra pessoa | Mínimo de 10 caracteres; recusa só números, senha comum e o login dentro da senha. Senha criada ou redefinida pelo admin é trocada no primeiro acesso |
| Sessão roubada | Cookie HttpOnly e SameSite=Strict; trocar senha/perfil derruba as sessões abertas. O token nunca vai no corpo da resposta |
| Pedido forjado de outro site | Escrita com o cookie do painel só vale vinda do próprio painel (`Origin` / `Sec-Fetch-Site`) |
| Acesso indevido | Perfis conferidos rota a rota; sempre existe ao menos um administrador ativo |
| CPF/RG em conversa | Redigidos antes de gravar a mensagem, com qualquer separador; CPF, nascimento e RG digitados ao bot viram marcador no histórico e saem dos dados da conversa quando o pedido é feito |
| CPF/RG em texto livre | Observação, motivo e resposta da equipe recusam CPF e RG na entrada |
| Dado pessoal na auditoria | CPF, RG e nascimento entram mascarados; texto livre sai redigido |
| Bot revelando quem é paciente | CPF já cadastrado recebe a mesma conversa de um CPF novo; a divergência vira marcador para a recepção |
| Erro devolvendo o que foi digitado | As respostas 422 dizem o campo e o motivo, sem repetir o valor |
| Dado em cache do navegador | `Cache-Control: no-store` em toda a API; HSTS quando há HTTPS |
| Segredo de exemplo em produção | O app não sobe com o WhatsApp ligado se `OCUPABOT_SEGREDO` for o valor publicado |
| Mensagem a quem pediu SAIR | Avisos e respostas da equipe não saem; o painel mostra que é preciso ligar |
| Dado pessoal em log | `hide_parameters` no SQLAlchemy; o log do console mostra só os 4 últimos dígitos |
| XSS e clickjacking | CSP, `X-Frame-Options: DENY`, React sem HTML cru |
| Corpo gigante | Limite de 1 MB por requisição |
| Webhook falso | Token comparado em tempo constante; recusa registrada na auditoria |
| Exposição de rede | Portas só em 127.0.0.1; `/api/docs` desligado por padrão |
| Vazamento pelo git | `.gitignore` + `scripts/verificar_dados.py` no pre-commit e na CI |
| Bot fazendo besteira sozinho | Bot, envios e integrações nascem desligados; humano aprova os pedidos |

## Limites conhecidos
- CPF e data de nascimento não provam identidade; a aprovação humana reduz o risco, mas não elimina.
- O HTTPS fica a cargo de um proxy reverso (Caddy, Nginx, Cloudflare Tunnel…).
- Backup e criptografia em repouso dependem do ambiente onde o sistema roda.
- Este repositório não substitui avaliação jurídica nem o papel do encarregado de dados (DPO).
