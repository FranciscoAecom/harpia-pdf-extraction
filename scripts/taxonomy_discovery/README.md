# Taxonomy Discovery

Este fluxo gera insumos de curadoria, nao uma taxonomia final automaticamente.

O script `profile_pdf_corpus.py` e agnostico: ele nao sabe o que e laudo, ficha, agua, sedimento, laboratorio ou tema. Ele apenas:

- le PDFs;
- extrai texto inicial, nome do arquivo e caminho;
- cria features textuais e de caminho;
- agrupa documentos parecidos em `cluster_id`;
- aponta termos, frases e regexes candidatas por cluster.

## Uso

```powershell
py .\scripts\taxonomy_discovery\profile_pdf_corpus.py --input "L:\Secure_DCS\BRBLH1PINFW001\COE_Digital\others\harpia_rd"
```

Para uma amostra pequena:

```powershell
py .\scripts\taxonomy_discovery\profile_pdf_corpus.py --limit 50
```

## Saida

Por padrao:

```text
output/taxonomy_discovery/pdf_corpus_profile.xlsx
```

Abas geradas:

- `clusters`: grupos de PDFs parecidos, com exemplos e colunas em branco para curadoria.
- `regex_candidates`: termos/frases fortes que podem virar regras no Excel.
- `pdf_inventory`: inventario PDF a PDF, incluindo `cluster_id`.
- `summary`: status de leitura dos PDFs.

## Curadoria

Depois do profiling, uma pessoa revisa:

```text
cluster_001 -> laudo_agua
cluster_002 -> laudo_fito
cluster_003 -> ficha_subcontratacao_als
```

E decide quais candidatos entram nas abas oficiais da taxonomia:

- `document_types`
- `document_type_detection_rules`
- `templates`
- `template_detection_rules`
