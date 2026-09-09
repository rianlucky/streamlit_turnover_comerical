# Turnover Comercial

Dashboard Streamlit para análise de movimentação de pessoas da área comercial, recriando o visual e os gráficos de um painel HTML original.

## Estrutura de pastas

```
Turnover Comercial/
├── app.py                  # Roteador: autenticação + st.navigation/st.Page (ponto de entrada)
├── requirements.txt
├── .streamlit/
│   ├── config.toml          # Tema (cores, tipografia) alinhado à identidade visual original
│   └── secrets.toml.example  # Modelo do secrets.toml real (não versionado) — connection string do Neon
├── assets/
│   ├── icons/               # Ícone/logo do projeto (icone-turnover-comercial*.png/svg, logo_sidebar.png)
│   └── *.html                # Painel HTML original — fonte dos dados da V1 (⚠️ NÃO versionado, ver abaixo)
├── scripts/
│   ├── grant_access.py        # CLI para conceder/remover acesso de um e-mail (sem senha)
│   ├── load_people_data.py    # CLI para (re)carregar people_rows no Neon (HTML local ou CSV do Databricks)
│   ├── sync_from_databricks.py # CLI: roda a query direto no SQL Warehouse via OAuth e sobe pro Neon
│   ├── test_databricks.py     # CLI para testar a conexão com o SQL Warehouse (PAT ou OAuth M2M)
│   └── _neon_people.py        # Schema/upload de people_rows — compartilhado pelos dois scripts acima
├── app_pages/
│   ├── dashboard.py          # Página principal (KPIs, gráficos, tabela) — conteúdo que antes estava em app.py
│   └── comparativo_turnover.py  # Comparativo das fórmulas de turnover (Comercial × D.O.)
└── src/
    ├── data_logic.py        # Carga de dados e regras de negócio (turnover, headcount, filtros)
    ├── charts.py            # Gráficos Plotly que replicam os gráficos Chart.js do HTML original
    ├── components.py        # KPIs, cartões de gráfico e tabela analítica (HTML/CSS)
    ├── styles.py            # Paleta de cores, fonte DM Sans e CSS injetado no app
    ├── auth.py              # Login (hash bcrypt + Postgres/Neon)
    └── auth_ui.py           # Telas de login (e-mail -> sem acesso / criar senha / senha)
```

## Origem dos dados

`data_logic.load_source_data()` lê a base de colaboradores da tabela `people_rows` no mesmo Postgres (Neon) usado pro login — não do HTML local (isso mudou na v0.8.0; ver `Changelog.md`). Isso é o que faz o app publicado no Streamlit Cloud ter dado de verdade: o Cloud só recebe o que está no repositório, e a base real nunca vai pro git.

Duas formas de carregar/recarregar essa tabela:

```powershell
# recomendado: roda a query direto no SQL Warehouse do Databricks (login via
# OAuth no navegador, sem precisar de PAT/token) e já sobe pro Neon
python scripts/sync_from_databricks.py

# bootstrap a partir do HTML local (assets/*.html) — usado só na primeira carga
python scripts/load_people_data.py

# alternativa manual: CSV exportado à mão do Databricks SQL Editor (colunas
# Registro, Nome, Cargo Atual2, Cidade, Admissão, Demissão, Status)
python scripts/load_people_data.py --csv caminho/para/export.csv
```

`sync_from_databricks.py` precisa de `server_hostname`/`http_path` (connection details do SQL Warehouse) e `gestor_referencia` (nome do gestor usado no ranking de reportes da query — fica só no secrets, nunca no código, porque o repositório é público) em `.streamlit/secrets.toml` -> `[databricks]`.

**⚠️ Essa base tem dados reais de colaboradores (nome, cidade, datas de admissão/demissão, gestor).** O HTML local em `assets/` (usado só para o bootstrap) e qualquer `.csv` exportado do Databricks nunca são versionados (`.gitignore` exclui `assets/*.html` e `*.csv`) — a única cópia "oficial" pública dos dados é a tabela no Neon, acessada só pela connection string em `.streamlit/secrets.toml` (também fora do git).

O refresh da base ainda é manual (rodar `sync_from_databricks.py` de novo quando quiser atualizar) até existir um PAT/service principal (OAuth M2M — ver `scripts/test_databricks.py`) que permita automatizar isso sem login interativo.

## Login

O app exige login por e-mail. As credenciais ficam em uma tabela Postgres (Neon) — o sistema de arquivos do Streamlit Community Cloud é efêmero, então não dá pra guardar senha em arquivo local.

Fluxo: a pessoa digita o e-mail; se ele não tiver acesso liberado, o app orienta a solicitar a inclusão a `rian.jesus@pacaembu.com`; se tiver acesso e for o primeiro login, ela cria a própria senha; se já tiver senha, só digita ela.

1. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha `[connections.sql].url` com a connection string do seu projeto Neon (também precisa ser configurado nos "Secrets" do app quando publicado no Streamlit Cloud).
2. Conceda acesso aos e-mails autorizados (sem senha — cada um cria a própria):
   ```powershell
   python scripts/grant_access.py
   ```

## Executar

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Filtros e interações

- **Cidade** (multiseleção, exibida como "Cidade/UF"; vazio = Global/todas).
- **Cargo** (multiseleção com 7 grupos agregados: Auxiliar, Assistentes, Analistas, Analistas Parcerias, Supervisor, Coordenador, Gerente; vazio = todos).
- **Período** (De/Até, dois campos digitáveis). Padrão: últimos 12 meses a partir do último mês com dado na base.
- **Status** (multiseleção Ativo/Desligado; vazio = ambos).
- Busca por nome, cargo, cidade **ou ID**, ordenação por coluna e paginação de 20 em 20 na tabela de colaboradores.
- KPIs, 5 visualizações (admissões × demissões, turnover real, headcount ativo, saldo líquido, indicador legado — as 4 últimas com rótulo do maior/menor valor) e tabela analítica com permanência humanizada ("2 anos e 3 meses", "5 meses", "18 dias"...).
- Indicador complementar: Permanência Média (Ativos × Desligados).
- Segunda página na barra lateral, **Comparativo Turnover**: compara a fórmula de turnover do Comercial (efetivo médio do mês) com a do D.O. (efetivo do fechamento do mês anterior), lado a lado, com recomendação de qual seguir como indicador oficial.

O turnover real e o indicador legado seguem as fórmulas existentes no HTML original — ver `Context.md`, que também documenta as limitações atuais de dados (UF inferida manualmente; sem campo de gestor/executivo, previsto para quando entrar o Databricks).
