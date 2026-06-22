# Harpia Parsing ETL

Pipeline para extrair resultados analíticos de PDFs laboratoriais usando uma taxonomy em Excel como configuração.

O projeto gera um Excel de saída com as abas definidas por template na taxonomia. No cadastro atual, as principais são:

- `results_extract`: resultados analíticos e QA/QC.
- `sample`: dados cadastrais e de coleta da amostra.
- `client`: identificação do cliente.
- `table_extraction_audit`: auditoria das colunas detectadas em cada tabela extraída.
- `classification_audit`: auditoria da identificação do template antes da extração.
- `validation_errors`: erros de validação da saída, vazia quando não houver inconsistências.

## Estrutura

```text
Harpia_Testes/
├─ run_batch.py
├─ run_pipeline.py
├─ README.md
├─ config/
│  ├─ taxonomy_config_consolidada_v1.xlsx
├─ data/
│  └─ input/
│     └─ *.pdf
├─ output/
│  └─ <tipo_laudo>/
│     └─ extracted_data.xlsx
└─ src/
   └─ harpia_parser/
      ├─ constants.py
      ├─ utils.py
      ├─ config/
      │  └─ loader.py
      ├─ core/
      │  ├─ context.py
      │  ├─ pipeline.py
      │  └─ scope.py
      ├─ extraction/
      │  ├─ pdf_reader.py
      │  ├─ metadata_extractor.py
      │  ├─ section_classifier.py
      │  └─ row_parser.py
      ├─ formatting/
      │  ├─ common.py
      │  ├─ laudo_agua.py
      │  ├─ laudo_fito.py
      │  ├─ laudo_sedimento.py
      │  └─ output_writer.py
      ├─ normalization/
      │  ├─ common.py
      │  ├─ laudo_agua.py
      │  ├─ laudo_fito.py
      │  └─ laudo_sedimento.py
      ├─ parsing/
      │  └─ measure_parser.py
      └─ validation/
         └─ schemas.py
```

## Como Rodar

Para auditar a identificacao de template de todos os PDFs da pasta padrao:

```powershell
cd "C:\Temp\Repositórios\harpia-pdf-extraction"
py .\run_batch.py classify
```

No modo `classify`, por padrao o script le as 3 primeiras paginas de cada PDF para acelerar a auditoria. Para ler todas as paginas:

```powershell
py .\run_batch.py classify --classify-pages 0
```

Para extrair todos os PDFs da pasta padrao:

```powershell
cd "C:\Temp\Repositórios\harpia-pdf-extraction"
py .\run_batch.py extract
```

Por padrão, as saídas são salvas em arquivos por tema:

```text
output/<tipo_laudo>/extracted_data.xlsx
```

Exemplos:

- `output/laudo_agua/extracted_data.xlsx`
- `output/laudo_fito/extracted_data.xlsx`
- `output/laudo_sedimento/extracted_data.xlsx`
- `output/laudo_mps/extracted_data.xlsx`
- `output/laudo_ect/extracted_data.xlsx`
- `output/laudo_zbt/extracted_data.xlsx`
- `output/laudo_dsl/extracted_data.xlsx`
- `output/laudo_dss/extracted_data.xlsx`
- `output/ficha_coleta_tommasi/extracted_data.xlsx`
- `output/ficha_recebimento_ethica/extracted_data.xlsx`
- `output/ficha_recebimento_labmar/extracted_data.xlsx`
- `output/ficha_recebimento_aplysia/extracted_data.xlsx`
- `output/ficha_subcontratacao_als/extracted_data.xlsx`
- `output/ficha_recebimento_bioagri/extracted_data.xlsx`

Para rodar um PDF único manualmente:

```powershell
py .\run_pipeline.py ".\data\input\arquivo.pdf"
```

Para escolher manualmente o arquivo de saída de um PDF único:

```powershell
py .\run_pipeline.py ".\data\input\arquivo.pdf" --out ".\output\resultado.xlsx"
```

Para informar outra pasta de PDFs:

```powershell
py .\run_batch.py extract --input "L:\Secure_DCS\BRBLH1PINFW001\COE_Digital\others\harpia_rd"
```

As saidas em lote sao salvas em `output/`, separadas por tema, e o resumo geral fica em `output/batch_extraction_summary.xlsx`.

## Configuracao

As regras ficam em `config/taxonomy_config_consolidada_v1.xlsx`. A taxonomy separa abas de regras de extracao, catalogos auxiliares e contratos de saida.

Depois que o template do PDF e identificado, o parser filtra as regras relacionais por `template_id`. Cada regra deve estar vinculada explicitamente a um template cadastrado; a taxonomy nao usa mais `template_id = *` como coringa. No estado atual, as regras textuais de `metadata`, `client` e `sample` ficam em `text_extraction_rules` e estao cadastradas para `template_laudo_agua_v1`, `template_laudo_fito_v1` e `template_laudo_sedimento_v1`; as demais matrizes ainda precisam de curadoria propria.

Campos booleanos da taxonomy, como `ativo`, `obrigatorio` e `extrair_subcategoria`, devem usar valores booleanos reais do Excel (`VERDADEIRO`/`FALSO`), sem misturar textos como `sim` ou `nao`.

### Abas da Taxonomy

- `README_FORMATO`: Descreve o objetivo das abas do arquivo consolidado.
- `templates`: Catalogo dos templates/modelos de documento reconhecidos pela taxonomia, com prioridade, score minimo e status ativo.
- `template_rules`: Regras de identificacao por template; avaliam regexes obrigatorias, positivas e negativas antes da extracao.
- `output_model`: Modelo de saida por template, incluindo abas geradas e campos de cada aba.
- `text_extraction_rules`: Regexes para extrair campos textuais de `metadata`, `sample` e `client`.
- `table_extraction_rules`: Regras tabulares por template, tipo de registro, campo e aliases de cabecalho, incluindo a posicao da coluna na tabela extraida do PDF.
- `section_rules`: Regras para reconhecer categoria, subcategoria, tipo de registro e local das secoes do PDF.
- `continuation_rules`: Padroes por template para detectar continuacao de tabelas de QA/QC entre paginas.

### Campos das Abas de Configuracao

Templates cadastrados atualmente: `laudo_agua`, `laudo_fito`, `laudo_sedimento`, `laudo_mps`, `laudo_ect`, `laudo_zbt`, `laudo_dsl`, `laudo_dss`, `ficha_coleta_tommasi`, `ficha_recebimento_ethica`, `ficha_recebimento_labmar`, `ficha_recebimento_aplysia`, `ficha_subcontratacao_als` e `ficha_recebimento_bioagri`.

#### `templates`
Registro dos templates/modelos de documento reconhecidos pela taxonomia. O template vencedor e escolhido antes da extracao.

- `template_id`: Identificador do template/modelo.
- `theme_id`: Tema/familia do documento, como `laudo_agua`, `laudo_fito` ou `laudo_sedimento`.
- `nome`: Nome legivel do template.
- `schema_ref`: Referencia do modelo de saida associado ao template.
- `descricao`: Descricao funcional do template.
- `prioridade`: Ordem de desempate quando mais de um template atinge o score minimo; numeros menores tem prioridade maior.
- `score_minimo`: Pontuacao minima para aceitar que o PDF pertence ao template.
- `ativo`: Indica se o template esta ativo.

#### `template_rules`
Regras de identificacao por template. O parser avalia essas regras logo apos ler o texto do PDF e antes de extrair os dados.

- `template_id`: Template/modelo ao qual a regra pertence.
- `tipo_regra`: Tipo da regra: `required`, `positive` ou `negative`.
- `fonte`: Fonte usada pela regra. Use sempre `text`; a classificacao nao deve depender do caminho ou nome do arquivo.
- `padrao_regex`: Regex usada para identificar sinais do template.
- `peso`: Pontos somados quando uma regra `positive` casa. Regras `required` e `negative` normalmente usam peso zero.
- `ativo`: Indica se a regra esta ativa.
- `descricao`: Explica o objetivo da regra.

#### `output_model`
Modelo de saida por template. Cada linha pode representar uma aba gerada ou um campo de uma aba.

- `template_id`: Template ao qual a aba/campo pertence.
- `theme_id`: Tema/familia do documento, usado tambem como pasta padrao de saida.
- `sheet_name`: Nome da aba no Excel final.
- `ordem_aba`: Ordem da aba no arquivo.
- `ativo_aba`: Indica se a aba deve ser criada.
- `descricao_aba`: Descricao funcional da aba.
- `ordem_campo`: Ordem do campo dentro da aba, quando aplicavel.
- `campo`: Nome da coluna de saida, quando aplicavel.
- `tipo_dado`: Tipo esperado do dado na saida.
- `obrigatorio`: Indica se o campo e obrigatorio no contrato da saida.
- `origem`: Origem do campo: regra textual, regra tabular, metadado, parser ou normalizacao.
- `descricao_campo`: Descricao funcional do campo.

#### `text_extraction_rules`
Regexes para extrair campos textuais.

- `regra_origem`: Grupo da regra textual: `metadata`, `sample` ou `client`.
- `template_id`: Template ao qual a regra pertence.
- `tabela_destino`: Tabela de saida relacionada a regra.
- `campo`: Nome do campo bruto preenchido pela regra.
- `padrao_regex`: Regex usada para extrair o campo do PDF. `DERIVADO_DO_NOME_DO_PDF` indica campo calculado pelo codigo.
- `ativo`: Indica se a regra esta ativa.
- `descricao`: Explica o objetivo da regra.

#### `table_extraction_rules`
Regras tabulares por template, tipo de registro, campo e alias de cabecalho.

- `regra_origem`: Grupo da regra tabular. Para layout de resultados, use `layout`; para reconhecer nomes de cabecalho, use `header_alias`.
- `template_id`: Template ao qual a regra pertence.
- `tabela_destino`: Tabela de saida relacionada a regra.
- `tipo_registro`: Tipo de tabela/registro ao qual o layout se aplica.
- `campo`: Campo interno preenchido a partir da tabela, como `resultado`, `lq`, `referencia` ou `faixa_aceitacao`.
- `coluna_origem`: Indice da coluna na tabela extraida do PDF.
- `header_regex`: Regex usada para reconhecer um nome de coluna do PDF e associa-lo ao campo informado. Exemplo: cabecalhos `CONAMA` e `COPAM/CERH` podem ser mapeados para campos proprios, fazendo o valor da linha sair em `conama` ou `copam_cerh`.
- `ativo`: Indica se a regra esta ativa.
- `descricao`: Explica o objetivo da regra.

#### `section_rules`
Regras para reconhecer secoes do PDF.

- `regra_origem`: Grupo da regra: `category_type`, `category_alias` ou `subcategory_alias`.
- `tipo_regra`: Tipo funcional da regra, alinhado ao grupo em `regra_origem`.
- `template_id`: Template ao qual a regra pertence.
- `prioridade`: Ordem de avaliacao; numeros menores sao avaliados primeiro.
- `padrao_regex`: Regex aplicada ao titulo/secao normalizado do PDF.
- `categoria`: Bloco principal da secao, como `Resultados Analiticos`, `Controle de Qualidade` ou `Provedores Externos`.
- `subcategoria`: Nome da secao interna. Quando estiver vazio, o parser preserva o titulo original reconhecido no PDF.
- `tipo_registro`: Tipo de tabela/registro: `AMOSTRA`, `BRANCO`, `DUPLICATA` ou `RECUPERACAO`.
- `local`: Local associado a secao, como campo ou laboratorio.
- `extrair_subcategoria`: Indica se a subcategoria deve ser derivada do titulo reconhecido.
- `ativo`: Indica se a regra esta ativa.
- `descricao`: Explica o objetivo da regra.

#### `continuation_rules`
Padroes para detectar continuacao de tabelas de QA/QC entre paginas.

- `template_id`: Template ao qual a regra pertence.
- `tipo_registro`: Tipo de registro ao qual a regra de continuacao se aplica.
- `padrao_regex`: Regex usada para identificar uma tabela continuada.
- `ativo`: Indica se a regra esta ativa.
- `descricao`: Explica o objetivo da regra.

## Saidas

O arquivo de extracao padrao e separado por tema em `output/<tipo_laudo>/extracted_data.xlsx`. As abas criadas e a ordem delas sao definidas na aba `output_model` da taxonomia. No estado atual, os templates cadastrados geram `results_extract`, `sample`, `client`, `table_extraction_audit`, `classification_audit` e `validation_errors`.

### `results_extract`
Resultados analiticos e QA/QC extraidos do PDF.

- `nome_do_arquivo`: Nome do PDF de origem da extracao.
- `template_id`: Template/modelo de laudo reconhecido pela taxonomia.
- `tipo_laudo`: Tema/familia do documento identificado pela taxonomia, como `laudo_agua`, `laudo_fito` ou `laudo_sedimento`.
- `id_sample`: Identificador da amostra na aba `results_extract`.
- `tipo`: Natureza do registro/tabela extraida: Amostra, Branco, Duplicata ou Recuperacao.
- `categoria`: Bloco principal do PDF, como `Resultados Analíticos`, `Controle de Qualidade` ou `Provedores Externos`.
- `subcategoria`: Secao interna do bloco principal, preservando o nome cadastrado/original do PDF, como `Metais` ou `Recuperação - Especiação`.
- `parameter`: Parametro/analise da linha de resultado.
- `resultado`: Resultado textual preservado como aparece no PDF.
- `resultado_tratado`: Resultado convertido para numero no Excel, com casas decimais preservadas e notacao cientifica exibida como decimal normal.
- `qualificador`: Qualificador do resultado, como `<` ou `>`.
- `unidade`: Unidade de medida do resultado.
- `local`: Local da medicao/analise, como campo ou laboratorio.
- `data_inicio`: Data de inicio da analise.
- `conama`: Valor extraido da coluna normativa CONAMA, quando esse cabecalho existir na tabela.
- `conama_operador`: Operador extraido do valor CONAMA.
- `conama_minimo`: Valor minimo extraido do campo CONAMA.
- `conama_maximo`: Valor maximo extraido do campo CONAMA.
- `conama_unidade`: Unidade de medida extraida do campo CONAMA.
- `copam_cerh`: Valor extraido da coluna normativa COPAM/CERH, quando esse cabecalho existir na tabela.
- `copam_cerh_operador`: Operador extraido do valor COPAM/CERH.
- `copam_cerh_minimo`: Valor minimo extraido do campo COPAM/CERH.
- `copam_cerh_maximo`: Valor maximo extraido do campo COPAM/CERH.
- `copam_cerh_unidade`: Unidade de medida extraida do campo COPAM/CERH.
- `lq`: Texto original do LQ.
- `lq_minimo`: Valor minimo do LQ gravado como numero no Excel, com casas decimais preservadas conforme o LQ original.
- `lq_maximo`: Valor maximo do LQ gravado como numero no Excel, com casas decimais preservadas conforme o LQ original.
- `lq_unidade`: Unidade de medida do LQ.
- `referencia`: Referencia normativa/metodologica.
- `incerteza`: Texto original da incerteza.
- `incerteza_valor`: Valor da incerteza gravado como numero no Excel, com casas decimais preservadas conforme a incerteza original.
- `incerteza_unidade`: Unidade da incerteza, usualmente `%`.
- `numero_cq`: Numero de controle de qualidade.
- `duplicata`: Valor de duplicata extraido diretamente do PDF; validado como texto numerico.
- `faixa_aceitacao`: Texto original da faixa/limite de aceitacao.
- `faixa_aceitacao_operador`: Operador da faixa/limite de aceitacao.
- `faixa_aceitacao_minimo`: Valor minimo da aceitacao gravado como numero no Excel, com casas decimais preservadas conforme a faixa original.
- `faixa_aceitacao_maximo`: Valor maximo da aceitacao gravado como numero no Excel, com casas decimais preservadas conforme a faixa original.
- `faixa_aceitacao_unidade`: Unidade da faixa/limite de aceitacao.
- `variacao_percentual`: Variacao percentual gravada como numero no Excel, com casas decimais preservadas conforme o PDF.
- `quantidade_adicionada`: Quantidade adicionada gravada como numero no Excel, com casas decimais preservadas conforme o PDF.
- `recuperacao_percentual`: Recuperacao percentual gravada como numero no Excel, com casas decimais preservadas conforme o PDF.

### `sample`
Dados cadastrais, coleta e cabecalho da amostra.

- `nome_do_arquivo`: Nome do PDF de origem da extracao.
- `template_id`: Template/modelo de laudo reconhecido pela taxonomia.
- `tipo_laudo`: Tema/familia do documento identificado pela taxonomia, como `laudo_agua`, `laudo_fito` ou `laudo_sedimento`.
- `id_amostra`: Identificador da amostra.
- `tipo_amostra`: Tipo de amostra informado no cabecalho.
- `criterio_conformidade`: Criterio de conformidade textual do cabecalho da amostra.
- `data_coleta`: Data de coleta da amostra.
- `dh_coleta`: Horario de coleta da amostra.
- `data_publicacao`: Data de publicacao do laudo.
- `dh_publicacao`: Horario de publicacao do laudo.
- `data_recebimento`: Data de recebimento da amostra.
- `dh_recebimento`: Horario de recebimento da amostra.
- `observacoes`: Observacoes do cabecalho da amostra.
- `dh_inicio_atividade`: Data/hora de inicio de atividade inferida ou extraida.
- `localizacao`: Local da coleta.
- `latitude`: Latitude decimal da coleta.
- `longitude`: Longitude decimal da coleta.
- `coordenadas`: Latitude e longitude concatenadas.
- `clima_ultimas_24h`: Condicoes climaticas nas ultimas 24 horas.
- `clima`: Condicoes climaticas no momento da coleta.
- `tipo_coleta`: Tipo de coleta.
- `responsavel_amostra`: Responsavel pela amostragem.
- `planejamento_amostragem`: Codigo/plano de amostragem.
- `descricao_nao_conformidade`: Descricao de nao conformidade, quando houver.

### `client`
Dados da tabela de identificacao do cliente.

- `nome_do_arquivo`: Nome do PDF de origem da extracao.
- `template_id`: Template/modelo de laudo reconhecido pela taxonomia.
- `tipo_laudo`: Tema/familia do documento identificado pela taxonomia, como `laudo_agua`, `laudo_fito` ou `laudo_sedimento`.
- `id_amostra`: Identificador da amostra.
- `proposta_comercial`: Codigo da proposta comercial.
- `cliente`: Nome do cliente.
- `cnpj_cpf`: CNPJ ou CPF do cliente.
- `contato`: Nome do contato do cliente.
- `telefone`: Telefone do contato.
- `endereco`: Endereco do cliente, quando informado.

### `classification_audit`
Auditoria da etapa de identificacao do template. Essa aba ajuda a validar se o PDF entrou no escopo correto antes da extracao.

- `nome_do_arquivo`: Nome do PDF avaliado.
- `template_id`: Template vencedor escolhido pela taxonomia.
- `tipo_laudo`: Tema/familia associado ao template vencedor.
- `template_avaliado`: Template candidato avaliado.
- `score`: Pontuacao obtida pelo template candidato.
- `score_minimo`: Pontuacao minima exigida para aceitar o template.
- `prioridade`: Prioridade usada como desempate entre templates aceitos.
- `status`: Resultado da avaliacao, como `winner`, `candidate`, `below_score`, `missing_required` ou `blocked_by_negative`.
- `regras_encontradas`: Regras de deteccao que casaram no texto do PDF.

### `table_extraction_audit`
Auditoria generica das tabelas processadas. Essa aba ajuda a conferir se as colunas detectadas no PDF batem com o layout esperado na taxonomia.

- `nome_do_arquivo`: Nome do PDF avaliado.
- `template_id`: Template/modelo identificado.
- `tipo_laudo`: Tema/familia do documento.
- `pagina`: Pagina onde a tabela foi encontrada.
- `tabela_indice`: Ordem da tabela dentro da pagina.
- `categoria`: Bloco principal atribuido a tabela.
- `subcategoria`: Secao interna atribuida a tabela.
- `tipo_registro`: Tipo de registro usado no layout, como `AMOSTRA`, `BRANCO`, `DUPLICATA` ou `RECUPERACAO`.
- `modo_auditoria`: Indica que a checagem combina contrato esperado e descoberta de colunas.
- `cabecalho_detectado`: Cabecalho reconhecido na tabela.
- `colunas_detectadas`: Colunas lidas do cabecalho do PDF.
- `colunas_mapeadas`: Relacao entre coluna detectada e campo interno.
- `colunas_sem_mapeamento`: Colunas detectadas que ainda nao possuem regra conhecida.
- `campos_esperados`: Campos esperados conforme `table_extraction_rules`.
- `campos_obrigatorios_ausentes`: Reservado para regras obrigatorias por tabela quando forem cadastradas na taxonomia.
- `campos_opcionais_ausentes`: Campos previstos no layout que nao apareceram no cabecalho detectado.
- `usou_fallback`: Indica se a tabela foi processada sem cabecalho detectado, usando apenas o layout cadastrado.
- `status`: Resultado da auditoria da tabela, como `ok`, `ok_com_opcional_ausente`, `alerta_descoberta`, `alerta_descoberta_com_opcional_ausente` ou `fallback`.
- `observacao`: Detalhe textual sobre ausencias, colunas novas ou uso de fallback.

### `validation_errors`
Erros encontrados pela validacao final com Pydantic. Quando a extracao esta consistente, a aba e criada apenas com cabecalhos e sem linhas.

- `row_number`: Numero da linha na aba validada.
- `id_sample`: Identificador da amostra na aba `results_extract`.
- `parameter`: Parametro/analise da linha de resultado.
- `field`: Campo onde ocorreu o erro de validacao.
- `error_type`: Tipo tecnico do erro Pydantic.
- `message`: Mensagem de validacao.
- `value`: Valor que gerou o erro de validacao.

## Módulos

- `core/pipeline.py`: orquestra o fluxo completo em etapas: contexto, cabecalho, resultados, normalizacao, validacao e gravacao.
- `core/context.py`: guarda o contexto do documento processado e monta a auditoria de classificacao do template.
- `core/scope.py`: identifica se o PDF pertence a algum template cadastrado.
- `config/loader.py`: carrega o Excel de configuração `taxonomy_config_consolidada_v1.xlsx`.
- `extraction/pdf_reader.py`: extrai texto e tabelas do PDF.
- `extraction/metadata_extractor.py`: extrai metadata e abas `sample` e `client`.
- `extraction/section_classifier.py`: identifica seções, categorias, tipos e continuação de tabela entre páginas.
- `extraction/row_parser.py`: extrai dados crus de cada linha conforme layout da taxonomia.
- `formatting/common.py`: direciona a formatacao para o formatter do tema identificado.
- `formatting/laudo_agua.py`: monta o contrato tabular da aba `results_extract` para o tema agua.
- `formatting/laudo_fito.py`: ponto preparado para o contrato de saida do tema fito.
- `formatting/laudo_sedimento.py`: ponto preparado para o contrato de saida do tema sedimento.
- `formatting/output_writer.py`: grava o arquivo final respeitando as abas configuradas por template em `output_model`.
- `normalization/common.py`: aplica normalizacoes comuns sem alterar os textos originais preservados do PDF.
- `normalization/laudo_agua.py`: ponto central para normalizacoes especificas do tema agua, incluindo resultado, unidade, pH, LQ, incerteza e faixa de aceitacao.
- `normalization/laudo_fito.py`: ponto central para normalizacoes especificas do tema fito.
- `normalization/laudo_sedimento.py`: ponto central para normalizacoes especificas do tema sedimento.
- `parsing/measure_parser.py`: utilitario generico para interpretar numeros, unidades, faixas, operadores e notacao cientifica.
- `validation/schemas.py`: valida as saidas com Pydantic e gera erros de auditoria.
- `constants.py`: colunas e defaults usados quando uma regra não existe no Excel.

## Observações

O script já trata tabelas quebradas entre páginas quando o cabeçalho fica no final de uma página e os dados aparecem na próxima.

Para novos laboratórios/modelos, priorize alterar o `taxonomy_config_consolidada_v1.xlsx` antes de mexer no código.

As normalizacoes por tema devem ficar nos arquivos de `normalization/`. Elas servem para padronizar campos depois da extracao; regexes de identificacao, layout e captura devem continuar cadastradas no Excel sempre que forem regra de taxonomia.
