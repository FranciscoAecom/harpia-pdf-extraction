import pandas as pd

from ..constants import RESULTS_EXTRACT_COLUMNS, TIPO_LABELS


def format_results_extract(df: pd.DataFrame, config, context=None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=RESULTS_EXTRACT_COLUMNS)

    out = pd.DataFrame({
        "nome_do_arquivo": df["nome_do_arquivo"],
        "id_taxonomia": df["id_taxonomia"],
        "nome_taxonomia": df["nome_taxonomia"],
        "id_amostra": df["id_amostra"],
        "tipo": df["tipo_registro"].map(TIPO_LABELS).fillna(df["tipo_registro"]),
        "categoria": df["categoria"],
        "subcategoria": df["subcategoria"],
        "parameter": df["parametro"],
        "resultado": df["resultado"],
        "acm_resultado_tratado": df["resultado_tratado"],
        "acm_qualificador": df["qualificador_resultado"],
        "acm_unidade": df["unidade_resultado"],
        "local": df["local"].fillna("laboratorio"),
        "data_inicio": df["data_inicio"],
        "conama": df.get("conama"),
        "acm_conama_operador": None,
        "acm_conama_minimo": None,
        "acm_conama_maximo": None,
        "acm_conama_unidade": None,
        "copam_cerh": df.get("copam_cerh"),
        "acm_copam_cerh_operador": None,
        "acm_copam_cerh_minimo": None,
        "acm_copam_cerh_maximo": None,
        "acm_copam_cerh_unidade": None,
        "ld": df["ld"],
        "acm_ld_minimo": None,
        "acm_ld_maximo": None,
        "acm_ld_unidade": None,
        "lq": df["lq"],
        "acm_lq_minimo": None,
        "acm_lq_maximo": None,
        "acm_lq_unidade": None,
        "referencia": df["referencia"],
        "incerteza": df["incerteza"],
        "acm_incerteza_valor": None,
        "acm_incerteza_unidade": None,
        "numero_cq": df["numero_cq"],
        "duplicata": df["duplicata"],
        "faixa_aceitacao": df["faixa_aceitacao"],
        "acm_faixa_aceitacao_operador": None,
        "acm_faixa_aceitacao_minimo": None,
        "acm_faixa_aceitacao_maximo": None,
        "acm_faixa_aceitacao_unidade": None,
        "variacao_percentual": df["variacao_percentual"],
        "quantidade_adicionada": df["quantidade_adicionada"],
        "recuperacao_percentual": df["recuperacao_percentual"],
    })
    return out[RESULTS_EXTRACT_COLUMNS]
