# Dados SINTÉTICOS

Tudo nesta pasta é **sintético**, criado só para testar o pipeline. Nenhuma linha é OS, hora, equipamento ou causa real.
Os ids começam com `SINT-`, os textos com `[SINTÉTICO]` e os short ids com `ffff` (prefixo reservado para dados de teste).

- `entrada_csv/`: fallback CSV no schema do Data Connector (tasks, activities, equipments, tasks_tags, tags + `_parameters`), colunas na ordem de `contrato/conector_v0.json`.
- `parada/`: exemplo de CSV de parada no contrato v0 (`docs/contrato_parada_v0.md`).
