import pandas as pd

from ..constants import RESULTS_EXTRACT_COLUMNS, TIPO_LABELS


def format_results_extract(df: pd.DataFrame, config, context=None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=RESULTS_EXTRACT_COLUMNS)

    out = pd.DataFrame({
        "nome_do_arquivo": df["nome_do_arquivo"],
        "template_id": df["template_id"],
        "tipo_laudo": df["tipo_laudo"],
        "id_sample": df["id_amostra"],
        "tipo": df["tipo_registro"].map(TIPO_LABELS).fillna(df["tipo_registro"]),
        "categoria": df["categoria"],
        "subcategoria": df["subcategoria"],
        "parameter": df["parametro"],
        "resultado": df["resultado"],
        "resultado_tratado": df["resultado_tratado"],
        "qualificador": df["qualificador_resultado"],
        "unidade": df["unidade_resultado"],
        "local": df["local"].fillna("laboratorio"),
        "data_inicio": df["data_inicio"],
        "conama": df.get("conama"),
        "conama_operador": None,
        "conama_minimo": None,
        "conama_maximo": None,
        "conama_unidade": None,
        "copam_cerh": df.get("copam_cerh"),
        "copam_cerh_operador": None,
        "copam_cerh_minimo": None,
        "copam_cerh_maximo": None,
        "copam_cerh_unidade": None,
        "ld": df["ld"],
        "ld_minimo": None,
        "ld_maximo": None,
        "ld_unidade": None,
        "lq": df["lq"],
        "lq_minimo": None,
        "lq_maximo": None,
        "lq_unidade": None,
        "referencia": df["referencia"],
        "incerteza": df["incerteza"],
        "incerteza_valor": None,
        "incerteza_unidade": None,
        "numero_cq": df["numero_cq"],
        "duplicata": df["duplicata"],
        "faixa_aceitacao": df["faixa_aceitacao"],
        "faixa_aceitacao_operador": None,
        "faixa_aceitacao_minimo": None,
        "faixa_aceitacao_maximo": None,
        "faixa_aceitacao_unidade": None,
        "variacao_percentual": df["variacao_percentual"],
        "quantidade_adicionada": df["quantidade_adicionada"],
        "recuperacao_percentual": df["recuperacao_percentual"],
    })
    return out[RESULTS_EXTRACT_COLUMNS]
