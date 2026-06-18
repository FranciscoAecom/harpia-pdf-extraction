# Taxonomy Discovery

Scripts auxiliares para descobrir familias de PDFs e gerar propostas de cadastro para a taxonomia.

Eles nao substituem a curadoria: a ideia e gerar planilhas candidatas para revisao antes de copiar/promover regras para `config/taxonomy_config_v5.xlsx`.

## Fluxo

1. `01_scan_pdf_corpus.py`

   Le uma pasta de PDFs, extrai amostra de texto, caminho, nome do arquivo e tokens.

   ```powershell
   py .\tools\taxonomy_discovery\01_scan_pdf_corpus.py --input "L:\Secure_DCS\BRBLH1PINFW001\COE_Digital\others\harpia_rd"
   ```

2. `02_suggest_document_types.py`

   Le `document_types` e `document_type_detection_rules` da taxonomia oficial e classifica o tipo macro de cada PDF.

   ```powershell
   py .\tools\taxonomy_discovery\02_suggest_document_types.py --taxonomy .\config\taxonomy_config_v5.xlsx
   ```

3. `03_suggest_templates.py`

   Usa o inventario e os tipos macro para propor `templates`, `template_detection_rules` e `output_sheets`.

   ```powershell
   py .\tools\taxonomy_discovery\03_suggest_templates.py
   ```

## Saidas

Por padrao, os arquivos ficam em:

- `output/taxonomy_discovery/pdf_inventory.xlsx`
- `output/taxonomy_discovery/document_type_suggestions.xlsx`
- `output/taxonomy_discovery/template_suggestions.xlsx`

## Observacao

Os scripts sao agnosticos no sentido de nao dependerem de um PDF, pasta ou template especifico. O `02_suggest_document_types.py` nao possui regras fixas no codigo: ele apenas aplica as regras cadastradas no Excel. Ainda assim, regras novas sugeridas pelos demais scripts devem ser revisadas, porque regex fraca ou baseada somente em caminho pode identificar documentos semelhantes de forma ampla demais.
