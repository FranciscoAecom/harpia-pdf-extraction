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
|-- run_batch.py
|-- run_pipeline.py
|-- README.md
|-- config/
|   `-- taxonomy.xlsx
|-- data/
|   `-- input/
|      `-- *.pdf
|-- output/
|   `-- <tipo_laudo>/
|      `-- extracted_data.xlsx
`-- src/
   `-- harpia_parser/
      |-- constants.py
      |-- utils.py
      |-- config/
      |   |-- common.py
      |   |-- loader.py
      |   |-- mapper.py
      |   |-- reader.py
      |   `-- validators.py
      |-- core/
      |   |-- context.py
      |   |-- pipeline.py
      |   `-- scope.py
      |-- extraction/
      |   |-- pdf_reader.py
      |   |-- metadata_extractor.py
      |   |-- section_classifier.py
      |   `-- row_parser.py
      |-- formatting/
      |   |-- common.py
      |   |-- laudo_agua.py
      |   |-- laudo_fito.py
      |   |-- laudo_sedimento.py
      |   `-- output_writer.py
      |-- normalization/
      |   |-- common.py
      |   |-- laudo_agua.py
      |   |-- laudo_fito.py
      |   `-- laudo_sedimento.py
      |-- parsing/
      |   `-- measure_parser.py
      `-- validation/
         `-- schemas.py
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

As regras ficam em `config/taxonomy.xlsx`. A taxonomy oficial usa 5 abas relacionais: cadastro do item de taxonomia, templates, regras do template, schemas de saida e campos de cada schema.

Depois que o template do PDF e identificado, o parser filtra as regras relacionais pelo template cadastrado. O arquivo atual esta preenchido para agua; novos temas devem ser cadastrados nessa mesma estrutura antes de entrarem no escopo de extracao.

Campos booleanos da taxonomy, como `ativo`, podem usar os valores padronizados do modelo (`Verdadeiro`/`Falso`). Campos de nulidade em `item_schema.nulo` usam `sim` ou `nao`.

### Abas da Taxonomy

- `item_taxonomia`: Cadastro do tema ou item de taxonomia, como agua superficial.
- `template`: Cadastro dos templates associados ao item de taxonomia, incluindo regex geral e status ativo.
- `item_template`: Regras do template. Contem regexes textuais, regras de identificacao, layouts de tabela, aliases de cabecalho, secoes e continuacoes.
- `schema`: Cadastro das abas/tabelas de saida esperadas.
- `item_schema`: Campos de cada aba de saida, com tipo esperado e regra de nulidade.

### Campos das Abas de Configuracao

Template cadastrado atualmente: `laudo_agua`.

#### `item_taxonomia`
Registro do tema ou item de taxonomia.

- `id`: Identificador interno do item.
- `id_taxonomia`: Identificador agrupador da taxonomia.
- `nome`: Nome do item de taxonomia, como `Agua Superficial`.

#### `template`
Registro dos templates/modelos de documento reconhecidos pela taxonomia.

- `id`: Identificador interno do template.
- `id_item_taxonomia`: Vinculo com `item_taxonomia.id`.
- `regex`: Regex geral do template.
- `ativo`: Indica se o template esta ativo.

#### `item_template`
Regras associadas a cada template. Essa aba concentra as regras que antes ficavam espalhadas por abas especificas.

- `id`: Identificador interno da regra.
- `id_template`: Vinculo com `template.id`.
- `schema`: Grupo da regra, como `template_required`, `metadata`, `sample`, `client`, `layout`, `header_alias`, `category_type`, `category_alias`, `subcategory_alias` ou `continuation`.
- `campo`: Campo de destino ou valor semantico da regra.
- `regex`: Regex usada pela regra. Em regras de layout sem regex, fica como `Nao se aplica`.
- `coluna_origem`: Posicao da coluna no layout ou atributos complementares no formato `chave=valor; chave=valor`.
- `tipo_registro`: Tipo de registro/tabela, como `Amostra`, `Branco`, `Duplicata` ou `Recuperacao`.

#### `schema`
Cadastro das abas/tabelas de saida.

- `id`: Identificador interno do schema.
- `id_item_taxonomia`: Vinculo com `item_taxonomia.id`.
- `nome`: Nome da aba/tabela, como `results_extract`, `sample`, `client`, `table_extraction_audit`, `classification_audit` ou `validation_errors`.
- `is_serial`: Indica se a aba possui varias linhas por documento.

#### `item_schema`
Campos de cada aba/tabela de saida.

- `id`: Identificador interno do campo.
- `id_schema`: Vinculo com `schema.id`.
- `schema`: Nome da aba/tabela de saida.
- `campo`: Nome da coluna de saida.
- `tipo`: Tipo esperado do dado na validacao.
- `nulo`: Indica se o campo permite nulo (`sim` ou `nao`).

## Saidas

O arquivo de extracao padrao e separado por tema em `output/<tipo_laudo>/extracted_data.xlsx`. As abas criadas sao definidas em `schema` e seus campos em `item_schema`. No estado atual, o template de agua gera `results_extract`, `sample`, `client`, `packaging_preservatives`, `notes`, `general_considerations`, `conformity_statement`, `validation_key`, `table_extraction_audit`, `classification_audit` e `validation_errors`.

## Auditorias

As auditorias sao abas de controle criadas junto com os dados extraidos. Elas nao corrigem nem alteram valores do PDF; servem para indicar se o documento foi classificado corretamente, se as tabelas foram lidas com o layout esperado e se a saida final respeita o contrato definido.

### Fluxo de auditoria

- `classification_audit`: verifica qual taxonomia/template o PDF acionou antes da extracao. Use essa aba para confirmar se o documento entrou no escopo correto.
- `table_extraction_audit`: verifica cada tabela encontrada, comparando cabecalhos detectados, campos mapeados e campos esperados pela taxonomia.
- `validation_errors`: valida a saida final com Pydantic. Hoje cobre `results_extract`, `sample`, `client` e `packaging_preservatives`. Use essa aba para encontrar campos obrigatorios vazios, tipos invalidos, datas/horarios invalidos, colunas ausentes ou colunas inesperadas.

### Como interpretar

- `classification_audit.status = winner`: template escolhido para extrair o PDF.
- `classification_audit.status = candidate`: template que atingiu o score minimo, mas nao foi o vencedor.
- `classification_audit.status = below_minimum`: regras positivas encontradas, mas score insuficiente para aceitar o template.
- `classification_audit.status = required_missing`: regra obrigatoria do template nao foi encontrada.
- `classification_audit.status = negative_matched`: regra negativa encontrada; o template foi bloqueado.
- `table_extraction_audit.status = ok`: cabecalho detectado e campos mapeados conforme esperado.
- `table_extraction_audit.status = ok_com_opcional_ausente`: a tabela foi extraida, mas algum campo esperado pela taxonomia nao apareceu no cabecalho. Normalmente exige revisao se o campo deveria existir naquele tipo de tabela.
- `table_extraction_audit.status = alerta_descoberta`: o PDF trouxe coluna detectada sem mapeamento na taxonomia. Pode indicar coluna nova que precisa ser cadastrada.
- `table_extraction_audit.status = alerta_descoberta_com_opcional_ausente`: existe coluna nova sem mapeamento e tambem campo esperado ausente. Esse status merece revisao prioritaria.
- `table_extraction_audit.status = fallback_cabecalho_texto_layout_confiavel`: o cabecalho nao veio na malha da tabela, mas apareceu no texto da pagina e o layout cadastrado ficou consistente.
- `table_extraction_audit.status = fallback_cabecalho_texto_layout_incompleto`: o cabecalho apareceu no texto da pagina, mas o layout nao ficou totalmente consistente. Revisar a taxonomia antes de confiar cegamente.
- `table_extraction_audit.status = fallback_layout_confiavel`: o cabecalho nao foi detectado, mas a estrutura da tabela bateu com o layout cadastrado.
- `table_extraction_audit.status = fallback`: a tabela foi processada usando apenas o layout cadastrado, sem cabecalho detectado e sem evidencia forte de confianca. Esse e o principal status para revisao manual.
- `validation_errors` sem linhas: a saida validada esta consistente com o contrato atual.
- `validation_errors` com linhas: ha erro de contrato na aba indicada em `sheet`; o valor original deve ser preservado, e o erro deve ser usado para corrigir taxonomia, extracao ou regra de validacao.

### Status observados na extracao atual

Na execucao atual dos laudos de agua, os status observados em `table_extraction_audit` foram:

- `ok`: tabela com cabecalho detectado e campos mapeados.
- `ok_com_opcional_ausente`: tabela extraida, mas com campo previsto no layout que nao apareceu no cabecalho detectado.
- `fallback_cabecalho_texto_layout_incompleto`: cabecalho encontrado no texto da pagina, mas layout ainda incompleto.
- `fallback_cabecalho_texto_layout_confiavel`: cabecalho encontrado no texto da pagina e layout consistente.
- `fallback_layout_confiavel`: sem cabecalho detectado, mas estrutura compativel com o layout.
- `fallback`: sem cabecalho detectado e sem evidencia forte de confianca.

Os status `alerta_descoberta` e `alerta_descoberta_com_opcional_ausente` continuam previstos no motor, mas nao apareceram na ultima execucao analisada. Eles surgem quando uma tabela traz coluna detectada sem mapeamento na taxonomia.

### `results_extract`
Resultados analiticos e QA/QC extraidos do PDF.

- `nome_do_arquivo`: Nome do PDF de origem da extracao.
- `id_taxonomia`: Identificador da taxonomia reconhecida, conforme `item_taxonomia.id_taxonomia`.
- `nome_taxonomia`: Nome da taxonomia reconhecida, conforme `item_taxonomia.nome`.
- `id_amostra`: Identificador da amostra na aba `results_extract`.
- `tipo`: Natureza do registro/tabela extraida: Amostra, Branco, Duplicata ou Recuperacao.
- `categoria`: Bloco principal do PDF, como `Resultados Analíticos`, `Controle de Qualidade` ou `Provedores Externos`.
- `subcategoria`: Secao interna do bloco principal, preservando o nome cadastrado/original do PDF, como `Metais` ou `Recuperação - Especiação`.
- `parameter`: Parametro/analise da linha de resultado.
- `resultado`: Resultado textual preservado como aparece no PDF.
- `acm_resultado_tratado`: Resultado convertido para numero no Excel, com casas decimais preservadas e notacao cientifica exibida como decimal normal.
- `acm_qualificador`: Qualificador do resultado, como `<` ou `>`.
- `acm_unidade`: Unidade de medida do resultado.
- `local`: Local da medicao/analise, como campo ou laboratorio.
- `data_inicio`: Data de inicio da analise.
- `conama`: Valor extraido da coluna normativa CONAMA, quando esse cabecalho existir na tabela.
- `acm_conama_operador`: Operador extraido do valor CONAMA.
- `acm_conama_minimo`: Valor minimo extraido do campo CONAMA.
- `acm_conama_maximo`: Valor maximo extraido do campo CONAMA.
- `acm_conama_unidade`: Unidade de medida extraida do campo CONAMA.
- `copam_cerh`: Valor extraido da coluna normativa COPAM/CERH, quando esse cabecalho existir na tabela.
- `acm_copam_cerh_operador`: Operador extraido do valor COPAM/CERH.
- `acm_copam_cerh_minimo`: Valor minimo extraido do campo COPAM/CERH.
- `acm_copam_cerh_maximo`: Valor maximo extraido do campo COPAM/CERH.
- `acm_copam_cerh_unidade`: Unidade de medida extraida do campo COPAM/CERH.
- `lq`: Texto original do LQ.
- `acm_lq_minimo`: Valor minimo do LQ gravado como numero no Excel, com casas decimais preservadas conforme o LQ original.
- `acm_lq_maximo`: Valor maximo do LQ gravado como numero no Excel, com casas decimais preservadas conforme o LQ original.
- `acm_lq_unidade`: Unidade de medida do LQ.
- `referencia`: Referencia normativa/metodologica.
- `incerteza`: Texto original da incerteza.
- `acm_incerteza_valor`: Valor da incerteza gravado como numero no Excel, com casas decimais preservadas conforme a incerteza original.
- `acm_incerteza_unidade`: Unidade da incerteza, usualmente `%`.
- `numero_cq`: Numero de controle de qualidade.
- `duplicata`: Valor de duplicata extraido diretamente do PDF; validado como texto numerico.
- `faixa_aceitacao`: Texto original da faixa/limite de aceitacao.
- `acm_faixa_aceitacao_operador`: Operador da faixa/limite de aceitacao.
- `acm_faixa_aceitacao_minimo`: Valor minimo da aceitacao gravado como numero no Excel, com casas decimais preservadas conforme a faixa original.
- `acm_faixa_aceitacao_maximo`: Valor maximo da aceitacao gravado como numero no Excel, com casas decimais preservadas conforme a faixa original.
- `acm_faixa_aceitacao_unidade`: Unidade da faixa/limite de aceitacao.
- `variacao_percentual`: Variacao percentual gravada como numero no Excel, com casas decimais preservadas conforme o PDF.
- `quantidade_adicionada`: Quantidade adicionada gravada como numero no Excel, com casas decimais preservadas conforme o PDF.
- `recuperacao_percentual`: Recuperacao percentual gravada como numero no Excel, com casas decimais preservadas conforme o PDF.

### `sample`
Dados cadastrais, coleta e cabecalho da amostra.

- `nome_do_arquivo`: Nome do PDF de origem da extracao.
- `id_taxonomia`: Identificador da taxonomia reconhecida, conforme `item_taxonomia.id_taxonomia`.
- `nome_taxonomia`: Nome da taxonomia reconhecida, conforme `item_taxonomia.nome`.
- `id_amostra`: Identificador da amostra.
- `identificacao_amostra`: Identificacao textual da linha `Informacoes da Amostra - No:`, como `68659-1/2024.0 - ECR 01R - P50`.
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
- `id_taxonomia`: Identificador da taxonomia reconhecida, conforme `item_taxonomia.id_taxonomia`.
- `nome_taxonomia`: Nome da taxonomia reconhecida, conforme `item_taxonomia.nome`.
- `id_amostra`: Identificador da amostra.
- `proposta_comercial`: Codigo da proposta comercial.
- `cliente`: Nome do cliente.
- `cnpj_cpf`: CNPJ ou CPF do cliente.
- `contato`: Nome do contato do cliente.
- `telefone`: Telefone do contato.
- `endereco`: Endereco do cliente, quando informado.

### `packaging_preservatives`
Dados do quadro de embalagens e preservantes.

- `nome_do_arquivo`: Nome do PDF de origem da extracao.
- `id_taxonomia`: Identificador da taxonomia reconhecida.
- `nome_taxonomia`: Nome da taxonomia reconhecida.
- `id_amostra`: Identificador da amostra associada ao quadro.
- `identificacao_amostra`: Texto da identificacao da amostra no quadro.
- `embalagem`: Tipo de embalagem.
- `volume`: Volume informado.
- `preservacao`: Preservacao informada.
- `metodos`: Metodo(s) associado(s) ao item.

### `notes`
Textos extraidos da secao `Notas` do PDF.

- `nome_do_arquivo`: Nome do PDF de origem da extracao.
- `id_taxonomia`: Identificador da taxonomia reconhecida.
- `nome_taxonomia`: Nome da taxonomia reconhecida.
- `id_amostra`: Identificador da amostra.
- `pagina`: Pagina onde o texto foi encontrado.
- `texto`: Conteudo textual da secao.

### `general_considerations`
Textos extraidos da secao `Consideracoes Gerais` do PDF.

- `nome_do_arquivo`: Nome do PDF de origem da extracao.
- `id_taxonomia`: Identificador da taxonomia reconhecida.
- `nome_taxonomia`: Nome da taxonomia reconhecida.
- `id_amostra`: Identificador da amostra.
- `pagina`: Pagina onde o texto foi encontrado.
- `texto`: Conteudo textual da secao.

### `conformity_statement`
Textos extraidos da secao `Declaracao de Conformidade` do PDF.

- `nome_do_arquivo`: Nome do PDF de origem da extracao.
- `id_taxonomia`: Identificador da taxonomia reconhecida.
- `nome_taxonomia`: Nome da taxonomia reconhecida.
- `id_amostra`: Identificador da amostra.
- `pagina`: Pagina onde o texto foi encontrado.
- `texto`: Conteudo textual da declaracao.

### `validation_key`
Chave de validacao do laudo, quando informada no PDF.

- `nome_do_arquivo`: Nome do PDF de origem da extracao.
- `id_taxonomia`: Identificador da taxonomia reconhecida.
- `nome_taxonomia`: Nome da taxonomia reconhecida.
- `id_amostra`: Identificador da amostra.
- `pagina`: Primeira pagina onde a chave foi encontrada.
- `chave_validacao`: Chave de validacao extraida.

### `classification_audit`
Auditoria da etapa de identificacao do template. Essa aba ajuda a validar se o PDF entrou no escopo correto antes da extracao.

- `nome_do_arquivo`: Nome do PDF avaliado.
- `id_taxonomia`: Identificador da taxonomia reconhecida pelo template vencedor.
- `nome_taxonomia`: Nome da taxonomia reconhecida pelo template vencedor.
- `template_avaliado`: Template candidato avaliado.
- `score`: Pontuacao obtida pelo template candidato.
- `score_minimo`: Pontuacao minima exigida para aceitar o template.
- `prioridade`: Prioridade usada como desempate entre templates aceitos.
- `status`: Resultado da avaliacao, como `winner`, `candidate`, `below_minimum`, `required_missing` ou `negative_matched`.
- `regras_encontradas`: Regras de deteccao que casaram no texto do PDF.

### `table_extraction_audit`
Auditoria generica das tabelas processadas. Essa aba ajuda a conferir se as colunas detectadas no PDF batem com o layout esperado na taxonomia.

- `nome_do_arquivo`: Nome do PDF avaliado.
- `id_taxonomia`: Identificador da taxonomia reconhecida.
- `nome_taxonomia`: Nome da taxonomia reconhecida.
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
- `campos_esperados`: Campos esperados conforme as regras `layout` cadastradas em `item_template`.
- `campos_obrigatorios_ausentes`: Reservado para regras obrigatorias por tabela quando forem cadastradas na taxonomia.
- `campos_opcionais_ausentes`: Campos previstos no layout que nao apareceram no cabecalho detectado.
- `usou_fallback`: Indica se a tabela foi processada sem cabecalho detectado, usando apenas o layout cadastrado.
- `status`: Resultado da auditoria da tabela. Pode indicar leitura direta por cabecalho (`ok`, `ok_com_opcional_ausente`), descoberta de coluna nova (`alerta_descoberta`, `alerta_descoberta_com_opcional_ausente`) ou uso de fallback (`fallback_cabecalho_texto_layout_confiavel`, `fallback_cabecalho_texto_layout_incompleto`, `fallback_layout_confiavel`, `fallback`).
- `observacao`: Detalhe textual sobre ausencias, colunas novas ou uso de fallback.

### `validation_errors`
Erros encontrados pela validacao final com Pydantic nas abas de saida validadas: `results_extract`, `sample`, `client` e `packaging_preservatives`. Quando a extracao esta consistente, a aba e criada apenas com cabecalhos e sem linhas.

- `sheet`: Aba validada onde o erro ocorreu.
- `row_number`: Numero da linha na aba validada.
- `id_amostra`: Identificador da amostra, quando aplicavel.
- `parameter`: Parametro/analise da linha de resultado ou metodo da linha de embalagem/preservante, quando aplicavel.
- `field`: Campo onde ocorreu o erro de validacao.
- `error_type`: Tipo tecnico do erro Pydantic.
- `message`: Mensagem de validacao.
- `value`: Valor que gerou o erro de validacao.

## Módulos

- `core/pipeline.py`: orquestra o fluxo completo em etapas: contexto, cabecalho, resultados, normalizacao, validacao e gravacao.
- `core/context.py`: guarda o contexto do documento processado e monta a auditoria de classificacao do template.
- `core/scope.py`: identifica se o PDF pertence a algum template cadastrado.
- `config/loader.py`: orquestra leitura, validacao, mapeamento e montagem da configuracao em memoria.
- `config/reader.py`: le as 5 abas oficiais do Excel `taxonomy.xlsx`.
- `config/mapper.py`: transforma o modelo relacional da taxonomia nos DataFrames usados pelo motor de extracao.
- `config/validators.py`: valida estrutura, chaves relacionais, regexes, layouts e contratos de saida da taxonomia.
- `config/common.py`: funcoes comuns para normalizar marcadores, booleanos e atributos da taxonomia.
- `extraction/pdf_reader.py`: extrai texto e tabelas do PDF.
- `extraction/metadata_extractor.py`: extrai metadata e abas `sample` e `client`.
- `extraction/section_classifier.py`: identifica seções, categorias, tipos e continuação de tabela entre páginas.
- `extraction/row_parser.py`: extrai dados crus de cada linha conforme layout da taxonomia.
- `formatting/common.py`: direciona a formatacao para o formatter do tema identificado.
- `formatting/laudo_agua.py`: monta o contrato tabular da aba `results_extract` para o tema agua.
- `formatting/laudo_fito.py`: ponto preparado para o contrato de saida do tema fito.
- `formatting/laudo_sedimento.py`: ponto preparado para o contrato de saida do tema sedimento.
- `formatting/output_writer.py`: grava o arquivo final respeitando as abas configuradas pela taxonomia.
- `normalization/common.py`: aplica normalizacoes comuns sem alterar os textos originais preservados do PDF.
- `normalization/laudo_agua.py`: ponto central para normalizacoes especificas do tema agua, incluindo resultado, unidade, pH, LQ, incerteza e faixa de aceitacao.
- `normalization/laudo_fito.py`: ponto central para normalizacoes especificas do tema fito.
- `normalization/laudo_sedimento.py`: ponto central para normalizacoes especificas do tema sedimento.
- `parsing/measure_parser.py`: utilitario generico para interpretar numeros, unidades, faixas, operadores e notacao cientifica.
- `validation/schemas.py`: valida as saidas com Pydantic e gera erros de auditoria.
- `constants.py`: colunas e defaults usados quando uma regra não existe no Excel.

## Observações

O script já trata tabelas quebradas entre páginas quando o cabeçalho fica no final de uma página e os dados aparecem na próxima.

Para novos laboratorios/modelos, priorize alterar o `taxonomy.xlsx` antes de mexer no codigo.

As normalizacoes por tema devem ficar nos arquivos de `normalization/`. Elas servem para padronizar campos depois da extracao; regexes de identificacao, layout e captura devem continuar cadastradas no Excel sempre que forem regra de taxonomia.
