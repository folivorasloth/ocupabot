# Integrações

## WhatsApp
O bot fala com a interface `Canal` (`integracoes/mensageria.py`), que tem `enviar()` e `status()`.

- **`console`** (padrão): só registra no log. Bom para desenvolvimento.
- **`waha`**: [WAHA](https://waha.devlike.pro/), integração **não oficial**. O número pode ser bloqueado pelo
  WhatsApp; use por sua conta e risco.
- **API oficial (WhatsApp Cloud API)**: escreva uma classe com os mesmos dois métodos e registre em `canal()`.

Entrada: `POST /api/webhook/whatsapp` com o cabeçalho `X-Webhook-Token`. Só eventos `message`, sem grupos nem
mensagens próprias. Em **modo teste** (padrão), só os números de `OCUPABOT_NUMEROS_TESTE` conversam.
Mensagem sem texto e com mídia (áudio, foto, arquivo) chega ao bot como "não consigo ouvir áudio".

O webhook só guarda a mensagem; a resposta sai quando o número fica alguns segundos sem escrever
(veja "Mensagens seguidas" em [BOT.md](BOT.md)).

A saída passa por uma fila (`mensagens` com status `PENDENTE`): o app tenta enviar na hora, e o worker
reenvia o que falhou até a validade (2 h para o bot, 24 h para a equipe).

## Sistema de gestão externo
Cada clínica usa um sistema diferente. Para ligar o seu, implemente `AgendaExterna`
(`integracoes/agenda_externa.py`):

```python
class MinhaAgenda:
    def ler(self, de: date, ate: date) -> list[Compromisso]:
        # consulte a API/relatório do seu sistema e devolva os horários ocupados
        ...
```

Registre-a em `agenda_externa()` e ligue `OCUPABOT_AGENDA_EXTERNA`. O worker grava cada leitura em
`leituras_externas`; o bot só oferece horário se a última leitura for válida e tiver menos de
`leitura_externa_validade_min` minutos. Do CPF lido, só fica um hash com sal.

O `Simulador` incluído gera ocupações fictícias e determinísticas e serve de exemplo e de teste.

A gravação no sistema externo fica manual: o painel marca o agendamento como "no sistema externo". Gravar
automaticamente é um próximo passo natural (veja [TCC.md](TCC.md)).
