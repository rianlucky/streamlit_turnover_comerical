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
│   ├── dashboard.py          # Página principal (KPIs, gráficos, mapa, tabela)
│   ├── ranking.py            # Top 5 de turnover/desligamentos por Cidade, Cargo e Gestor
│   └── comparativo_turnover.py  # Comparativo das fórmulas de turnover (Comercial × D.O.)
├── OBSOLETO.md              # Registro de campos/colunas que existem mas o app não lê mais
└── src/
    ├── data_logic.py        # Carga de dados e regras de negócio (turnover, headcount, filtros)
    ├── charts.py            # Gráficos Plotly (inclui o mapa de concentração e o ranking em barra)
    ├── components.py        # KPIs, cartões de gráfico, tabela analítica e status da barra lateral
    ├── styles.py            # Paleta de cores, fonte DM Sans e CSS injetado no app (dash + login)
    ├── auth.py              # Login (hash bcrypt + Postgres/Neon), com bloqueio por tentativas
    └── auth_ui.py           # Telas de login (cartão dividido: marca + formulário)
```

Existe também um `NEXTSTEPS.md` na raiz — notas internas de risco/pendência da última auditoria, **não versionado** (uso local, ver `.gitignore`).

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

Depois de 5 tentativas de senha erradas seguidas, a conta fica bloqueada por 15 minutos (mitigação simples de força bruta, sem serviço externo — `src/auth.py`).

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
- **Cargo** (multiseleção por grupo agregado: Auxiliar, Assistentes, Analistas, Analistas Parcerias, Supervisor, Coordenador, Gerente, Executivos; vazio = todos).
- **Gestor** (multiseleção; cobertura parcial para desligados — ver `NEXTSTEPS.md`).
- **Equipe** (Vendas UH / Lotes Comerciais / Repasses — segmento de negócio, independente da Cidade real do colaborador).
- **Período** (calendário único, `st.date_input`). Padrão: últimos 12 meses a partir do último mês com dado na base.
- **Status** (multiseleção Ativo/Desligado, na tabela; padrão Ativo).
- Busca por nome, cargo, cidade (**sem acento** — "aracatuba" acha "Araçatuba") ou ID, ordenação por coluna, paginação de 20 em 20 e exportação para Excel.
- KPIs, 8 visualizações (admissões × demissões, turnover real, headcount ativo, saldo líquido, desligamentos por tipo, turnover voluntário, indicador legado, mapa de concentração de mão de obra) e tabela analítica com permanência humanizada.
- Indicador complementar: Permanência Média (Ativos × Desligados), com barra comparativa.
- Página **Ranking**: Top 5 de turnover médio e de total de desligamentos, por Cidade, Cargo e Gestor.
- Página **Comparativo Turnover**: compara a fórmula de turnover do Comercial (efetivo médio do mês) com a do D.O. (efetivo do fechamento do mês anterior).
- Barra lateral: data da última sincronização da base e contadores de cargo/cidade fora do mapeamento (texto cinza, embaixo da navegação).

O turnover real e o indicador legado seguem as fórmulas do painel original que este dashboard substituiu — ver `Context.md` (decisões e histórico) e `NEXTSTEPS.md` (riscos/limitações em aberto, não versionado).
