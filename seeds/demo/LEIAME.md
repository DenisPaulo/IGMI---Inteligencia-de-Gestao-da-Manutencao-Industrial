# Seeds do dataset de demonstração (SINTÉTICOS)

Cadastros e catálogos **fictícios** usados pelo simulador (`tools/simular_demo.py`) e pelo pipeline demo (`python run.py demo`).
Nada aqui descreve uma planta real. Técnicos aparecem só como **função** (ex.: "Técnico Mec 1"), nunca por nome.

| Arquivo | O que é |
|---|---|
| `plantas.csv`, `linhas.csv` | planta e linhas (LR-01, LR-02), regime de operação e centro de custo |
| `centros_custo.csv` | centro de custo sintético e custo/h de parada **fictício** |
| `classes_equipamento.csv` | classes no estilo ISO 14224 (robô, transportador, dosador, visão, CLP, mesa de vácuo) |
| `equipamentos.csv` | hierarquia linha > equipamento > subconjunto, criticidade A/B/C e especialidade |
| `tipos_os.csv` | tipos de OS (EN 13306): corretiva emergencial/planejada, preventiva, preditiva/inspeção, melhoria |
| `especialidades.csv`, `tecnicos.csv` | especialidades, capacidade semanal e funções técnicas (sem nomes) |
| `modos_falha.csv`, `causas.csv`, `mecanismos.csv`, `acoes.csv` | catálogos ISO 14224 (modo filtrado por classe) |
| `planos_preventivos.csv` | planos com periodicidade, estratégia, horas estimadas e tolerância |
| `parametros_demo.csv` | regras configuráveis (reincidência 3× em 15 dias, Pareto, período, capacidade) |
