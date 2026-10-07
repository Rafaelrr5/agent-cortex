# Modelos e Contas (painel do dashboard do Hermes)

Uma aba no dashboard do Hermes para quem não usa o aplicativo de janela: escolher o
modelo padrão, montar a lista de reservas, ordenar as contas de cada provedor e ver
quanto do limite de uso de cada assinatura (Claude e ChatGPT) já foi gasto.

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

## O que ele lê e escreve

- Lê `config.yaml` e o pool de credenciais pelas funções do próprio Hermes.
- Prioridade das contas e reservas usam as mesmas funções de `hermes auth priority` e
  `hermes fallback`; o modelo padrão usa a rota nativa do dashboard.
- Para mostrar os limites, renova o acesso só em memória: `auth.json` nunca é reescrito
  por essa consulta, e nenhuma chave volta para o navegador.

Autor: Rafael Rocha Ribeiro + Hermes. Licença MIT do repositório.
