# Contrato v2 — CSV de parada da produção (proposta)

Status: **proposta** (15/10/2026). **Não vigente** até uma amostra real da produção confirmar nomes e formatos; a validação atual (`pmb/parada.py`) segue a v0. Nada de ingestão real foi implementado. A ingestão v2 roda **só sobre amostras SINTÉTICAS** (`dados_sinteticos/parada_v2/`, `pmb/parada_v2.py`, `sql/silver/02_parada_v2.sql`, `sql/gold/22_parada_v2.sql`); ver "Simulação" no fim.
Schema: `contrato/parada_v2.schema.json`.

## O que muda em relação ao formato anterior

| Tema | formato anterior (v0) | v2 (proposta) |
|---|---|---|
| Chave | `os_ref` + `data_parada` (soma) | **`id_lancamento`** (texto), número próprio de cada lançamento |
| Hora de início | não existe | **`hora_inicio`**, proposta `AAAA-MM-DDTHH:MM`, hora local no fuso da rede (`_parameters.network.timezone`), sem offset; **formato a confirmar** |
| Duração | `hora_lancada`, horas decimais, 2 casas | **`duracao_min`**, minutos inteiros > 0 (formato original da produção); **provisório**, nome e formato só confirmados com amostra |
| Data | coluna `data_parada` | derivada: `date(hora_inicio)` |
| Correção | pendente | o mesmo `id_lancamento` substitui o anterior, com trilha de auditoria |
| Exclusão | seed `seeds/parada_exclusoes.csv` | ver opções (a), (b), (c) abaixo; recomendação sem decisão |

## Colunas propostas

| Coluna | Tipo | Regra |
|---|---|---|
| `id_lancamento` | texto | obrigatória, não vazia; chave; nunca convertida para número (mesmo cuidado do `11112222`) |
| `os_ref` | texto | obrigatória; `^[0-9a-f]{8}$` (igual à v0) |
| `hora_inicio` | timestamp local | obrigatória; `^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}$` e data/hora existente |
| `duracao_min` | inteiro | obrigatória; `^[0-9]{1,5}$`; > 0 |
| `acao` | texto, opcional | `incluir` / `excluir`; só se o export tiver status/ação |
| `_arquivo`, `_linha`, `_sha256`, `_loaded_at`, `data_carga` | gerados | rastreio |

Carga: incremental (append), partição datada imutável `landing_parada/data_carga=AAAA-MM-DD/` fora do repo; o mesmo `_sha256` não faz nada.

## Correção (mesmo id substitui)

- Vale a **última versão** de cada `id_lancamento`, na ordem `data_carga` → `_arquivo` → `_linha`.
- A versão anterior vai para `silver.parada_auditoria`: `id_lancamento`, `versao`, `campo`, `valor_anterior`, `valor_novo`, `_arquivo`, `_sha256`, `_loaded_at`.
- Alertas (marca e segue): correção que **reduz** a duração; correção que chega mais de N dias depois de `hora_inicio` (N a definir pelo líder do projeto); mesmo id com `os_ref` diferente (QCP08).

## Correções e exclusões feitas pelo planejador: como chegam ao pipeline

Hoje quem corrige e exclui é o **planejador** (papel).

| Opção | Como funciona | Prós | Contras |
|---|---|---|---|
| **(a)** No próprio export | Correção volta no próximo export com o mesmo `id_lancamento`; exclusão vem com `acao = excluir` (ou status equivalente), **se o export tiver essa coluna** | Automático; a fonte é única; sem trabalho manual; trilha completa por id | Depende de o sistema da produção registrar exclusão no export (desconhecido). Se a linha excluída simplesmente some do incremental, a exclusão nunca chega |
| **(b)** Seed versionado | Planejador avisa; líder do projeto registra em `seeds/parada_exclusoes.csv` (com `id_lancamento`, motivo, data, validador = papel) | Explícito, revisado, versionado no Git; não depende da produção | Manual; depende de o aviso acontecer; atraso entre a exclusão e o BI; não cobre correções |
| **(c)** Export completo periódico | Além do incremental, um export completo (ex.: mensal) é comparado com o acumulado; id que sumiu vira **candidato a exclusão** na fila (QCP13), nunca apagado sozinho | Pega exclusões que ninguém avisou; serve de reconciliação geral (horas e contagens) | Precisa de um segundo tipo de export; a fila precisa de alguém para decidir; arquivo maior |

**Recomendação (a decidir pelo líder do projeto):** **(a) para correções** (o mesmo id já resolve), e para exclusões **(a) se a amostra mostrar uma coluna de status/ação**. Se não mostrar, **(b) como regra, com (c) como rede de segurança** periódica, para achar exclusões que não foram avisadas. Em qualquer caso, nada é apagado sem decisão registrada.

## Hora em minutos

Formato provisório da v2 = **minutos inteiros** (`duracao_min`). Dados em minutos são convertidos para horas só na hora de exibir (`hora_parada_min / 60`), sem arredondar linha a linha; arredondar cada linha para 2 casas e somar depois pode divergir da soma exata em alguns centésimos de hora.

## QCs da v2 (especificados; implementar quando a v2 for vigente)

Rejeitam o arquivo inteiro:
- **QCP01:** cabeçalho igual ao contrato e encoding confirmado.
- **QCP02:** `id_lancamento` vazio = 0.
- **QCP03:** `id_lancamento` duplicado dentro do mesmo arquivo = 0.
- **QCP04:** `os_ref` fora de `^[0-9a-f]{8}$` = 0.
- **QCP05:** `hora_inicio` fora do regex, ou data/hora inexistente = 0.
- **QCP06:** `duracao_min` não inteiro ou ≤ 0 = 0 (rejeita `0,33`, `1.5`, `00:20`, vazio).
- **QCP07:** `acao` fora de {`incluir`, `excluir`}, quando a coluna existir = 0.

Marcam e seguem:
- **QCP08:** mesmo `id_lancamento` com `os_ref` diferente da versão anterior: alerta e revisão.
- **QCP09:** `os_ref` sem OS no Mobility: `fila_parada_sem_os`, sem custo.
- **QCP10:** `hora_inicio` depois da `data_carga` do arquivo (futuro). O CSV de parada não traz `last_export_date`; na simulação vale a `data_carga` do manifesto.
- **QCP11:** lançamentos da mesma OS com intervalos sobrepostos (`hora_inicio` + `duracao_min`).
- **QCP12:** exclusão de `id_lancamento` que nunca foi carregado.
- **QCP13:** id que sumiu num export completo (opção c): candidato a exclusão, na fila; nunca apagado sozinho.

## Pedido à produção

1. Um **export de amostra anonimizado**, com algumas linhas, de preferência incluindo uma correção e uma exclusão.
2. Os **nomes exatos das colunas**, como saem do sistema (principalmente o número do lançamento, o ID da OS, o início e a duração).
3. O **encoding** (UTF-8, Latin-1/Windows-1252?) e o **separador** (vírgula ou ponto e vírgula).
4. O formato da **data/hora de início** (ex.: `dd/mm/aaaa hh:mm` ou `aaaa-mm-dd hh:mm`) e da **duração** (minutos inteiros, `hh:mm` ou decimal).
5. Se cada export é **incremental** (só o período novo) ou **completo**, e se é possível gerar um completo de vez em quando.
6. Como aparece um **lançamento excluído**: some do export, vem com status/ação, ou de outro jeito.

## Simulação (15/10/2026, dados SINTÉTICOS)

Manifesto `dados_sinteticos/parada_v2/cargas.csv` (data_carga, arquivo, tipo `incremental|completo`, cenário). Na simulação, o tipo do arquivo vem do manifesto; no real, vem da resposta ao item 5 do pedido.
- Crua: `raw/parada_v2/data_carga=…/` (fora do repo), imutável. Reprocessar o mesmo sha256 = `SEM_MUDANCA`; outro arquivo na mesma data = erro.
- Silver: `parada_linhas` (todas as linhas aceitas), `parada_versoes` (só quando algum valor muda), `parada` (vigente por id, sem excluídos), `parada_auditoria` (campo a campo), `parada_por_os`.
- Gold: `parada_diaria` (soma por OS + dia), `fila_parada_sem_os`, `fila_candidato_exclusao`, `alertas_parada`. A `fato_os.hora_parada_min` vem de `parada_por_os` (só OS sintéticas: QCV07). O custo segue QC01–05 e só sai em OS completed de centro de custo com taxa no seed.
- Checks novos QCV01–07 (bloqueantes) em `pmb/quality.py`. Os QCP01–07 ficam na validação do arquivo e os QCP08–13 em `gold.alertas_parada`.
- Desvio do texto acima: na simulação, a exclusão aceita `os_ref`/`hora_inicio`/`duracao_min` vazios quando `acao = excluir`. Também existe o alerta `ALERTA_REDUCAO` (correção que reduz a duração). O alerta de "N dias depois" não foi implementado, porque N não está definido.
