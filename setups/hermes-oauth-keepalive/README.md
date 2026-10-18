# Hermes OAuth keepalive

Um cron diário que mantém vivas as contas do Claude e do ChatGPT/Codex que você
logou no Hermes e te avisa quando uma delas precisa de login de novo.

## O problema

O Hermes guarda várias contas por provedor e usa a primeira até ela esgotar a
cota; as outras ficam de reserva. Uma conta que passa uns 4 a 8 dias sem uso
perde o login: a renovação responde `HTTP 400 invalid_grant` ("Refresh token
expired"). Ou seja, as reservas morrem justamente por serem reservas, e quando a
primeira esgota não sobra nenhuma. Na prática isso aparece como "toda semana os
provedores quebram".

## O que o script faz

Uma vez por dia, para cada conta OAuth que o próprio Hermes logou
(`hermes auth add ... --type oauth`):

- renova o login da conta (`try_refresh_matching` do pool do Hermes), o que
  reinicia o prazo de validade;
- pula contas em cooldown de cota, para não apagar o cooldown;
- pula contas emprestadas de outros programas (por exemplo a do Claude Code) e
  chaves de API, que não são dele;
- se alguma conta está morta ou não renovou, imprime um aviso com o nome da
  conta e como refazer o login. Sem problema, não imprime nada e o cron fica
  em silêncio.

Processos do Hermes que já estão abertos pegam o login renovado do `auth.json`;
não é preciso reiniciar nada.

## Instalar

Requer o Hermes Agent instalado (o script usa o pool de contas dele).

```bash
python oauth_keepalive.py --install --deliver telegram
```

Isso copia o script para `HERMES_HOME/scripts/` e cria o cron `oauth-keepalive`
(todo dia às 04:10, sem agente: só o script roda, nenhum modelo é chamado).
`--deliver` é para onde vai o aviso (`telegram`, `all`, ...; o padrão `local`
só grava em `HERMES_HOME/cron/output/`). `--at "0 6 * * *"` muda o horário.
Rodar `--install` de novo só atualiza o script.

Para testar na hora: `hermes cron run <id do job>`.

### Máquina sem gateway de mensagens

Se esta máquina não tem Telegram configurado mas outra tem, crie
`HERMES_HOME/scripts/oauth_keepalive.json`:

```json
{"forward_ssh": "usuario@servidor", "ssh_key": "~/.ssh/minha_chave"}
```

O aviso é repassado por ssh e enviado lá com `hermes send -t telegram`.

## Quando chegar um aviso

```bash
hermes auth remove anthropic NOME
hermes auth add anthropic --type oauth --label NOME
```

Saia da conta no navegador antes do `add`; senão o navegador reaproveita a
sessão aberta e você loga a mesma conta duas vezes.

## Verificar

```bash
python -B test_oauth_keepalive.py -v
```

Os 5 testes rodam o script de verdade contra um pool falso em pasta temporária:
contas saudáveis renovadas em silêncio, conta morta e renovação falha geram
aviso, contas em cooldown/emprestadas/chave de API/bloqueadas não são tocadas,
provedor ilegível vira aviso sem derrubar os outros, e `--install` copia o
script. Também rodou contra contas reais em Windows e Ubuntu (Hermes v0.22.2):
renovou as contas vivas e avisou as mortas no Telegram.

## Limites

- Não ressuscita conta já morta: isso exige login interativo seu.
- Não sabe o prazo exato do provedor; um refresh por dia foi suficiente nas
  contas medidas, mas a Anthropic pode mudar o prazo.
- Uma execução por vez; não rode dois ticks simultâneos no mesmo `HERMES_HOME`.
