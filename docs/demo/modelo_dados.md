# Modelo de dados (dataset demo)

```mermaid
erDiagram
    PLANTA ||--o{ LINHA : tem
    LINHA ||--o{ EQUIPAMENTO : "linha > equipamento > subconjunto (pai_id)"
    LINHA }o--|| CENTRO_CUSTO : "custo/h fictício"
    EQUIPAMENTO }o--|| CLASSE_EQUIPAMENTO : "classe ISO 14224"
    EQUIPAMENTO ||--o{ OS : "tasks.equipment_id"
    EQUIPAMENTO ||--o{ PLANO_PREVENTIVO : tem
    PLANO_PREVENTIVO ||--o{ OS : "tag plano:"
    TIPO_OS ||--o{ OS : "tag tipo:"
    MODO_FALHA }o--|| CLASSE_EQUIPAMENTO : "filtrado por classe"
    MODO_FALHA ||--o{ OS : "tag modo:"
    CAUSA ||--o{ OS : "tag causa:"
    MECANISMO ||--o{ OS : "tag mec:"
    ACAO ||--o{ OS : "tag acao:"
    OS ||--o{ TAREFA : "activities (função técnica, minutos)"
    OS ||--o{ PARADA : "os_ref (contrato v2)"
    FUNCAO_TECNICA }o--|| ESPECIALIDADE : "Técnico Mec 1, Técnico Elet 2…"

    OS {
        string task_id "DEMO-T0001"
        string task_short_id "dd000001"
        string status "completed | scheduled | in_progress | canceled"
        timestamp scheduled_from "abertura/programação"
        timestamp scheduled_to "fim programado (horas estimadas)"
        timestamp done_date "fechamento"
        int cumulated_duration_in_minutes "Σ tarefas"
    }
    PARADA {
        string id_lancamento
        string os_ref
        timestamp hora_inicio
        int duracao_min
    }
    EQUIPAMENTO {
        string equipment_id
        string nivel "linha | equipamento | subconjunto"
        string pai_id
        string criticidade "A | B | C"
        string especialidade_id "MEC | ELE"
    }
```

- **Fonte**: o conector simulado usa o **mesmo schema** do Data Connector do pipeline principal (`contrato/conector_v0.json`): tasks, activities, equipments, tasks_tags, tags.
- A classificação (tipo, modo, causa, mecanismo, ação, plano) vai em **tags** `chave:valor`, como num CMMS real.
- **Gold** (`sql/demo/`): `dim_linha`, `dim_equipamento`, `fato_os_demo`, `falhas`, `kpi_equipamento`, `kpi_linha`, `kpi_mensal`, `kpi_pm`, `pm_ocorrencias`, `backlog_os`, `backlog_especialidade`, `aderencia_semanal`, `pareto_modo`, `alertas_reincidencia`, `qualidade_dado`.
