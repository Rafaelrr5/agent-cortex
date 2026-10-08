# Modelos e Contas (painel do dashboard do Hermes)

Uma aba no dashboard do Hermes para quem não usa o aplicativo de janela: escolher o
modelo padrão, ordenar os provedores, ordenar e bloquear as contas de cada provedor e ver
quanto do limite de uso de cada assinatura já foi gasto.

Tudo fica dentro desta pasta: nenhum arquivo do Hermes é alterado, então `hermes update`
não conflita.

## Instalar

```bash
hermes plugins install Rafaelrr5/agent-cortex/plugins/modelos-contas --enable
hermes dashboard
```

Abra <http://127.0.0.1:9119/modelos-contas?profile=default>. Se o dashboard já estava
aberto, feche e abra de novo: as rotas do painel só carregam na inicialização.

`python abrir.py` (dentro da pasta do plugin) sobe o dashboard em segundo plano, se
preciso, e abre a aba no navegador.

## O que a tela faz

| Seção | O que dá para fazer |
|---|---|
| Ordem em que o Hermes tenta | Setas sobem e descem cada provedor; o primeiro vira o modelo padrão e os outros, as reservas. "Salvar ordem" grava as duas coisas. |
| Modelo padrão / Modelos de reserva | Trocar o modelo de cada posição, adicionar e remover reservas. |
| Contas e limites | Ordem das contas dentro do provedor, bloquear/liberar uma conta e o uso real de cada assinatura. |

**Bloquear** deixa a conta logada, mas o Hermes passa a pular ela (vai para a próxima conta
do mesmo provedor e, sem nenhuma, para a próxima reserva) até você liberar. O botão só
aparece quando o Hermes instalado tem `hermes auth disable`; sem isso o painel esconde a
opção em vez de fingir que bloqueia.

### Limites que o painel consegue ler

| Provedor | Fonte |
|---|---|
| Claude (`anthropic`, login de assinatura) | API de uso da Anthropic: sessão de 5h, semana e créditos extras |
| ChatGPT (`openai-codex`) | API de uso do ChatGPT: sessão de 5h e semana |
| Kiro (provedor `copilot-acp` apontado para o `kiro-cli`) | API de uso do Kiro: créditos do mês e data de renovação |

Para o Kiro, o painel lê o login que o próprio `kiro-cli` guarda no computador. Se ele
estiver vencido, pede para o `kiro-cli` renovar (o comando `/usage` não gasta crédito); o
painel nunca grava esse arquivo. Quando o `copilot-acp` aponta para o Kiro, o token do
GitHub que só serve para liberar esse provedor aparece no bloco "copilot · Kiro (via ACP)".

Provedores que estão na ordem mas não têm conta no pool (como o `copilot-acp`) também
aparecem, marcados como "login fora do pool".

## O que ele lê e escreve

- Lê `config.yaml` e o pool de credenciais pelas funções do próprio Hermes.
- Prioridade das contas, bloqueio e reservas usam as mesmas funções de `hermes auth
  priority`, `hermes auth disable|enable` e `hermes fallback`; o modelo padrão usa a rota
  nativa do dashboard.
- Para mostrar os limites, renova o acesso só em memória: `auth.json` nunca é reescrito
  por essa consulta, e nenhuma chave volta para o navegador.

## Testes

```bash
PYTHONPATH=<pasta do hermes-agent> <python do Hermes> -m pytest plugins/modelos-contas/tests
```

Rodam num `HERMES_HOME` temporário com credenciais falsas e conferem que a leitura não
reescreve o `auth.json`.

Autor: Rafael Rocha Ribeiro + Hermes. Licença MIT do repositório.
