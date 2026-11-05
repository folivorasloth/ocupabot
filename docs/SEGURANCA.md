# Segurança e LGPD

O sistema trata dados pessoais e dados de saúde, que a LGPD trata como sensíveis.
**Regra número 1: nenhum dado real no repositório, nos testes ou em conversas com assistentes de IA.**

## Controles
| Risco | Controle |
|---|---|
| Força bruta no login | Argon2 e limite de 5 tentativas por login+IP a cada 5 minutos |
| Sessão roubada | Cookie HttpOnly e SameSite=Strict; trocar senha/perfil derruba as sessões abertas |
| Acesso indevido | Perfis conferidos rota a rota; perfil LEITURA vê dados mascarados e não lê mensagens |
| CPF/RG em conversa | Redigidos antes de gravar a mensagem |
| Dado pessoal em log | `hide_parameters` no SQLAlchemy; o log do console mostra só os 4 últimos dígitos |
| XSS e clickjacking | CSP, `X-Frame-Options: DENY`, React sem HTML cru |
| Corpo gigante | Limite de 1 MB por requisição |
| Webhook falso | Token comparado em tempo constante |
| Exposição de rede | Portas só em 127.0.0.1; `/api/docs` desligado por padrão |
| Vazamento pelo git | `.gitignore` + `scripts/verificar_dados.py` no pre-commit e na CI |
| Bot fazendo besteira sozinho | Bot, envios e integrações nascem desligados; humano aprova os pedidos |

## Limites conhecidos
- CPF e data de nascimento não provam identidade; a aprovação humana reduz o risco, mas não elimina.
- O HTTPS fica a cargo de um proxy reverso (Caddy, Nginx, Cloudflare Tunnel…).
- Backup e criptografia em repouso dependem do ambiente onde o sistema roda.
- Este repositório não substitui avaliação jurídica nem o papel do encarregado de dados (DPO).
