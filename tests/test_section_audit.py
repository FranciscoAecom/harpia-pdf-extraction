import re
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from harpia_parser.core.context import ClassificationResult, DocumentContext
from harpia_parser.extraction.section_audit import build_section_extraction_audit


def _context() -> DocumentContext:
    classification = ClassificationResult(
        template_id="template_laudo_agua_v1",
        tipo_laudo="laudo_agua",
        id_taxonomia=1,
        nome_taxonomia="Agua Superficial",
        versao_template="1",
        scores=[],
    )
    return DocumentContext(
        pdf_path=Path("a.pdf"),
        nome_do_arquivo="a.pdf",
        template_id="template_laudo_agua_v1",
        tipo_laudo="laudo_agua",
        id_taxonomia=1,
        nome_taxonomia="Agua Superficial",
        versao_template="1",
        classification=classification,
    )


def _rules(schema: str, title: str) -> pd.DataFrame:
    return pd.DataFrame([
        {"campo": "section_start", "regex": rf"(?:^|\n)\s*{title}\s*:?"},
        {"campo": "texto", "regex": rf"(?:^|\n)\s*{title}\s*:?\s*(.*)$"},
    ])


def _config():
    return SimpleNamespace(
        df_packaging_preservatives_rules=pd.DataFrame([
            {"campo": "section_start", "regex": r"Embalagens\s+e\s+Preservantes"},
            {"campo": "table_header", "regex": r"Embalagem\s+Volume"},
        ]),
        df_notes_rules=_rules("notes", "Notas"),
        df_general_considerations_rules=_rules("general", "Consideracoes Gerais"),
        df_conformity_statement_rules=_rules("conformity", "Declaracao de Conformidade"),
        df_validation_key_rules=_rules("key", "Chave de Validacao"),
        df_revision_reason_rules=_rules("revision", "Motivo da Revisao"),
        df_section_discovery_ignore_rules=pd.DataFrame([
            {"campo": "method_reference", "regex": r"^ABNT\s+NBR$"},
        ]),
        df_metadata_text_rules=pd.DataFrame(),
        df_sample_text_rules=pd.DataFrame(),
        df_client_text_rules=pd.DataFrame(),
        df_category_type_rules=pd.DataFrame(),
        df_category_alias_rules=pd.DataFrame(),
        df_subcategory_alias_rules=pd.DataFrame(),
        df_header_alias_rules=pd.DataFrame(),
        template_rules=[{"regex": re.compile(r"Relatorio Analitico", re.IGNORECASE)}],
    )


class SectionAuditTest(unittest.TestCase):
    def test_ignored_validation_form_code_is_not_an_extraction_failure(self):
        config = _config()
        config.df_validation_key_rules = pd.concat([
            config.df_validation_key_rules,
            pd.DataFrame([{
                "campo": "audit_ignore",
                "regex": r"Chave\s+de\s+Validacao\s*:?\s*\n?\s*FO-ANL-\d+",
            }]),
        ], ignore_index=True)
        pages = [("Chave de Validacao:\nFO-ANL-162", [])]
        outputs = {
            "packaging_preservatives": pd.DataFrame(),
            "notes": pd.DataFrame(),
            "general_considerations": pd.DataFrame(),
            "conformity_statement": pd.DataFrame(),
            "validation_key": pd.DataFrame(),
            "revision_reason": pd.DataFrame(),
        }

        audit = build_section_extraction_audit(pages, _context(), config, outputs, pd.DataFrame())

        validation = audit[audit["secao"] == "validation_key"].iloc[0]
        self.assertEqual(validation["status"], "nao_aplicavel")

    def test_audits_known_and_discovered_sections_and_tables(self):
        pages = [(
            "Relatorio Analitico\nNotas:\nConteudo da nota.\nConsideracoes Gerais\nResumo Executivo\nTexto livre",
            [[['Campo', 'Valor'], ['A', 'B']]],
        )]
        outputs = {
            "packaging_preservatives": pd.DataFrame(),
            "notes": pd.DataFrame([{"texto": "Conteudo da nota."}]),
            "general_considerations": pd.DataFrame(),
            "conformity_statement": pd.DataFrame(),
            "validation_key": pd.DataFrame(),
            "revision_reason": pd.DataFrame(),
        }

        audit = build_section_extraction_audit(
            pages,
            _context(),
            _config(),
            outputs,
            pd.DataFrame(),
        )

        notes = audit[(audit["secao"] == "notes") & (audit["modo_auditoria"] == "conhecida")].iloc[0]
        general = audit[audit["secao"] == "general_considerations"].iloc[0]
        self.assertEqual(notes["status"], "ok")
        self.assertEqual(general["status"], "encontrada_sem_extracao")
        self.assertTrue(
            ((audit["titulo_detectado"] == "Resumo Executivo") & (audit["status"] == "secao_nao_mapeada")).any()
        )
        self.assertTrue((audit["status"] == "tabela_nao_mapeada").any())

    def test_discovery_ignore_rules_suppress_confirmed_false_positive(self):
        pages = [("Relatorio Analitico\nABNT NBR\nResumo Executivo", [])]
        outputs = {
            "packaging_preservatives": pd.DataFrame(), "notes": pd.DataFrame(),
            "general_considerations": pd.DataFrame(), "conformity_statement": pd.DataFrame(),
            "validation_key": pd.DataFrame(), "revision_reason": pd.DataFrame(),
        }

        audit = build_section_extraction_audit(pages, _context(), _config(), outputs, pd.DataFrame())

        discovered = set(audit.loc[audit["status"] == "secao_nao_mapeada", "titulo_detectado"])
        self.assertNotIn("ABNT NBR", discovered)
        self.assertIn("Resumo Executivo", discovered)


if __name__ == "__main__":
    unittest.main()
