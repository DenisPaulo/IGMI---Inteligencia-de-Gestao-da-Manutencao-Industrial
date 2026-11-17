# IGMI 0.2.0 — Analista de Confiabilidade com IA

**Estado:** integração implementada e validada com mocks; **nenhuma chamada real à API OpenAI foi executada neste ambiente**. O usuário deve validar a integração real com uma chave própria. Os dados da demonstração são **100% sintéticos**.

## O que mudou

O modo anterior `python run.py igmi` continua **offline/determinístico** e não requer chave ou internet.

O novo modo `python run.py igmi-ia` utiliza a **Responses API** com `function_call` e JSON Schema estrito. O agente escolhe somente dentre ferramentas fixas existentes em `igmi.consultas` e a aplicação executa as consultas ao DuckDB em **somente leitura**. O modelo não recebe SQL livre nem pode alterar OS, planos, cadastros ou CLPs.

```text
Pergunta + linha + período explícito
              |
       validar QD 27/27
              |
     verificar carga OK
              |
  aceitar apenas período fechado
              |
         Responses API
              |
      ferramenta permitida
              |
 DuckDB (read_only=True) -> evidência E1/E2/...
              |
     Structured Outputs JSON
              |
 validação de evidências e números literais
              |
     relatório .md/.json
```

## Ambiente Windows + Git Bash

Na pasta do projeto, abra o terminal Git Bash no VS Code:

```bash
py -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements-ai.txt

# Evita UnicodeEncodeError em terminais com cp1252:
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# Gere o warehouse sintético e valide o relatório offline ANTES de habilitar API:
python run.py simular demo demo-preview
python run.py igmi --linha LT3 --formato markdown --saida export/igmi_relatorio_LT3.md
python run.py test
```

**Configure a API somente depois de validar os dados.** Não escreva uma chave de API no código, `.env.example`, no Git ou neste chat. Para evitar gravação do segredo no histórico do Git Bash, o comando abaixo lê a chave silenciosamente:

```bash
read -rs -p 'OPENAI_API_KEY: ' OPENAI_API_KEY; echo
export OPENAI_API_KEY
export IGMI_OPENAI_MODEL='gpt-4.1-mini'
```

O modelo acima é **um exemplo configurável**, não garantia de acesso ou preço. Confirme disponibilidade e preços da API na sua conta antes de executar. API e assinatura do ChatGPT têm cobranças separadas.

### Primeira pergunta com IA (pode gerar cobrança)

```bash
mkdir -p export
python run.py igmi-ia \
  --linha LT3 \
  --pergunta 'Analise a confiabilidade da LT3 de abril a setembro de 2026. Quais equipamentos merecem investigação e quais falhas reincidiram?' \
  --modelo "$IGMI_OPENAI_MODEL" \
  --limite-ferramentas 6 \
  --autorizar-api \
  --formato markdown \
  --saida export/igmi_ia_LT3.md

code export/igmi_ia_LT3.md
```

Para usar JSON, altere `--formato json --saida export/igmi_ia_LT3.json`. Use `python run.py igmi-ia --help` para ver os parâmetros.

### Desativar o segredo da sessão

```bash
unset OPENAI_API_KEY
```

## Regras de acesso e filtros

- `--linha LT3` ou `LT56`: precisa corresponder a uma linha existente.
- `--inicio` e `--fim` podem ser omitidos; se informados, **ambos devem coincidir com o período fechado do dataset**, de 2026-04-01 a 2026-09-30.
- Consultas por mês isolado, subconjunto do período, data atual, ou “últimos seis meses” são rejeitadas **em vez de usar KPIs agregados como se fossem KPIs filtrados**. Essa capacidade poderá evoluir com cálculo específico por período.
- Referências a outra linha na pergunta também são rejeitadas.
- O modelo só pode chamar `consultar_kpis`, `consultar_equipamentos`, `consultar_pareto`, `consultar_reincidencias`, `consultar_os`, `consultar_tendencia`, `consultar_backlog` e `consultar_qualidade`.
- Resultados de qualidade de `gold.qualidade_dado` são **globais da demonstração**, e não indicadores específicos da LT3 ou LT56. O escopo é explícito no registro da ferramenta.
- Nenhum resultado é fornecido ao modelo antes de `ConsultasDemo` confirmar os **27 checks QD**, a carga `OK` e a existência da linha. As consultas são `read_only`.
- Limite padrão: **6 ferramentas diferentes por pergunta**, configurable de 1 a 8. O agente não pode repetir ferramentas, mesmo que tente. Cada ferramenta tem limite de até 30 registros determinado pela aplicação.
- `max_output_tokens=1600` por requisição, timeout de 35s e zero tentativas automáticas (`max_retries=0`). **Não é um limite monetário**; configure restrições de uso e orçamento também no projeto da API.
- O programa registra no relatório IDs de evidências, ferramentas e uso de tokens informado pelo provedor. O SDK não armazena estado da conversa no servidor (`store=False`); a execução envia resultados de ferramentas ao provedor somente depois da autorização.

## Formato da resposta

A IA responde em JSON estrito e a aplicação valida:

- `resumo`;
- `fatos`: lista de afirmações com `evidencia_ids` que foram efetivamente consultados;
- `hipoteses`: não comprovadas;
- `recomendacoes`: para validação humana;
- `limitacoes`.

Qualquer ID de evidência inexistente, estrutura diferente, número literal inexistente nos resultados das ferramentas, chamada não autorizada ou resposta incompleta interrompe a análise com erro; não é apresentado como análise válida. **Essa checagem reduz alguns tipos de alucinação, mas não prova a correção semântica de toda afirmação**. Revisão humana continua necessária.

Os dados retornados pelo banco são tratados como dados não confiáveis e não como instruções operacionais. Sem acesso a SQL arbitrário, sem ferramentas externas e sem escrita no banco.

## Testes

```bash
python -m pytest -q tests_igmi
python run.py test
```

Foram executados **25 testes de `tests_igmi`**, todos aprovados, incluindo **17 novos** e **8 anteriores**, sem chamadas reais ao provedor. A execução local da suíte completa ficou bloqueada pela falta de instalação de `duckdb` e pela indisponibilidade de rede nesse ambiente. A execução anterior de **106 testes** no Windows foi relatada pelo usuário; a versão 0.2.0 precisa ser revalidada **integralmente no seu computador** antes de ser considerada homologada.

## Arquivos novos/modificados

- `igmi/ia.py`: orquestração Responses, lista de ferramentas, validação e relatório.
- `igmi/ia_cli.py`: CLI exclusiva com `--autorizar-api` obrigatório.
- `tests_igmi/test_ia.py`: testes com respostas simuladas.
- `requirements-ai.txt`: dependência opcional `openai`.
- `.env.example`: somente placeholders.
- `run.py`: novo comando `igmi-ia`, mantendo comandos anteriores.
- `igmi/__init__.py`: versão do pacote atualizada.
- `README.md`, `docs/IGMI_0.2.0.md`, `CHANGELOG.md`: instruções e evolução.

## Próxima versão, IGMI 0.3.0

Planejar **FastAPI e interface de conversa** somente após validação do CLI com a API e com os 106 testes legados. Em fase posterior, implementar filtros de período e autorização por usuário, métricas de custo e observabilidade mais completas. Não integrar sistemas reais sem política de acesso e tratamento de dados aprovada.

## Referências técnicas oficiais

- [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Preços de API](https://platform.openai.com/pricing/)


### Ajuste no validador de números

O IGMI bloqueia qualquer número criado pela IA que não apareça literalmente nas
ferramentas (por exemplo, um percentual calculado pelo modelo ou contagem inventada).
A checagem deliberadamente conservadora pode rejeitar enumerações ou números usados
em texto descritivo. As instruções agora pedem que as seções interpretativas não
contenham algarismos. Se a resposta ainda for rejeitada, a mensagem indicará a
seção e os números sem evidência; não remova o validador para contornar o bloqueio.
Uma nova execução com `--autorizar-api` poderá consumir créditos adicionais.
