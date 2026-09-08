# Turnover Comercial

Dashboard Streamlit para análise de movimentação de pessoas da área comercial, recriando o visual e os gráficos do painel original em `assets/painel_cidade_CLT_media_turnover.html`.

## Estrutura de pastas

```
Turnover Comercial/
├── app.py                 # Ponto de entrada Streamlit (orquestração da página)
├── requirements.txt
├── .streamlit/
│   └── config.toml        # Tema (cores, tipografia) alinhado à identidade visual original
├── assets/
│   └── painel_cidade_CLT_media_turnover.html   # Painel HTML original — fonte dos dados da V1
└── src/
    ├── data_logic.py       # Carga de dados e regras de negócio (turnover, headcount, filtros)
    ├── charts.py           # Gráficos Plotly que replicam os gráficos Chart.js do HTML original
    ├── components.py       # KPIs, cartões de gráfico e tabela analítica (HTML/CSS)
    └── styles.py           # Paleta de cores, fonte DM Sans e CSS injetado no app
```

## V1: dados locais

A primeira versão lê, sem alterar os dados ou os cálculos, o payload embutido em `assets/painel_cidade_CLT_media_turnover.html`. A fonte está isolada em `src/data_logic.py`; a futura conexão com Databricks poderá substituir `load_source_data()` sem mexer nos cálculos ou na interface.

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
- Dois indicadores complementares: Permanência Média (Ativos × Desligados) e Curva de Retenção por Coorte de Admissão (3/6/12 meses).

O turnover real e o indicador legado seguem as fórmulas existentes no HTML original — ver `Context.md`, que também documenta as limitações atuais de dados (UF inferida manualmente; sem campo de gestor/executivo, previsto para quando entrar o Databricks).
