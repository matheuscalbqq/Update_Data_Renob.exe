import pandas as pd
from pathlib import Path
from storage import load_config
from typing  import Optional, Callable

class UserCancelError(Exception):
    pass


#==============================================================================#
#======================= CARREGA/CRIA AS DBS ==================================#
#==============================================================================#
def load_create_master(master_path: Path) -> pd.DataFrame:
    cfg = load_config()
    if master_path.exists():
        return pd.read_csv(master_path)
    else:
        return pd.DataFrame(columns=cfg["colunasSisvan"])

#==============================================================================#
#======================= TRATAMENTO DOS DADOS =================================#
#==============================================================================#
def treatment(new_csv: Path, fase_vida: str):
    cfg = load_config()

    colunas = cfg["colunasSisvan"]

    new_df = pd.read_csv(new_csv)

    if 'eutrofia' in new_df.columns:
        new_df.rename(columns={'eutrofia': 'eutrofico'}, inplace=True)

    matching_columns = [col for col in new_df.columns if col in colunas]
    new_df = new_df[matching_columns]

    for col in colunas:
        if col not in new_df.columns:
            new_df[col] = 0
    
    new_df['fase_vida'] = fase_vida

    return new_df
    
    

#==============================================================================#
#==================== EXPORT PARA O PROJETO RENOB =============================#
#==============================================================================#

def find_renob(target: str, start: Optional[Path]=None):
    if start is None:
        start = Path.cwd()

    levels = [start] + list(start.parents)
    pattern = f"**/{target}"   # ex: "**/public/data"

    for base in levels:
        for p in base.glob(pattern):
            if p.is_dir():
                return p
    return None


#==============================================================================#
#===================== FUNÇÃO PRINCIPAL DE MERGE ==============================#
#==============================================================================#
def merge_csvs(
        new_csv: pd.DataFrame,
        master_path: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> dict:

    master_df = load_create_master(master_path)
    new_df    = new_csv.copy()

    # ===================== PRÉ-PROCESSO ESPECÍFICO (ADOLESCENTE) =====================
    if ('fase_vida' in new_df.columns) and (new_df['fase_vida'].eq('adolescente').any()):
        
        # 2) Padroniza os campos que compõem a chave (como strings)
        separador = "_"
        for coluna in ('UF', 'municipio', 'ANO', 'SEXO', 'codigo_municipio'):
            if coluna in new_df.columns:
                new_df[coluna] = new_df[coluna].astype(str).str.strip()

        # 3) Constrói a chave de agregação (independe de RACA_COR existir)
        new_df['codigo_raca'] = (
            new_df['UF'] +
            separador +
            new_df['municipio'] +
            separador +
            new_df['ANO'] +
            separador +
            new_df['SEXO'] +
            separador +
            new_df['codigo_municipio']
        )

        # 4) (Opcional, robustez) Tenta converter “medidas” que possam ter vindo como texto
        #    para numérico, sem mexer nas chaves fixas e metadados.
        colunas_chave_fixas = {
            'UF', 'municipio', 'ANO', 'SEXO', 'codigo_municipio',
            'codigo_raca', 'RACA_COR', 'fase_vida'
        }
        for c in new_df.columns:
            if c not in colunas_chave_fixas:
                # Se for texto mas parece número, vira numérico; caso contrário fica como está
                if new_df[c].dtype == object:
                    convertido = pd.to_numeric(new_df[c], errors='coerce')
                    # Se ao menos algum valor virou número, adote a coluna convertida preenchendo NaN com 0
                    if convertido.notna().any():
                        new_df[c] = convertido.fillna(0)

        # 5) Define as agregações:
        #    - 'first' para as chaves fixas (identidade da linha)
        #    - 'sum' para colunas numéricas restantes
        agregacoes: dict[str, str] = {}
        for c in ('UF', 'municipio', 'ANO', 'SEXO', 'codigo_municipio'):
            if c in new_df.columns:
                agregacoes[c] = 'first'

        for c in new_df.columns:
            if c == 'codigo_raca' or c in agregacoes:
                continue
            if pd.api.types.is_numeric_dtype(new_df[c]):
                agregacoes[c] = 'sum'
            else:
                agregacoes[c] = 'first'

        # 6) Agrega colapsando as linhas que diferem apenas por RACA_COR (ou qualquer outra
        #    coluna não-chave), somando as medidas
        df_somado = new_df.groupby('codigo_raca', as_index=False).agg(agregacoes)

        # 7) Pós-processo de tipos nas chaves numéricas que você quer como número
        if 'ANO' in df_somado.columns:
            df_somado['ANO'] = pd.to_numeric(df_somado['ANO'], errors='coerce').astype('Int64')
        if 'codigo_municipio' in df_somado.columns:
            df_somado['codigo_municipio'] = pd.to_numeric(df_somado['codigo_municipio'], errors='coerce').astype('Int64')

        # 8) Remove auxiliares (funciona mesmo se RACA_COR não existir)
        new_df = df_somado.drop(columns=['RACA_COR', 'codigo_raca'], errors='ignore')


    # ===================== ALINHAMENTO DE COLUNAS =====================
    if not master_df.empty:
        new_df = new_df.reindex(columns=master_df.columns, fill_value='')
    else:
        new_df = new_df.reindex(columns=new_df.columns, fill_value='')

    # ===================== NORMALIZAÇÃO DE TIPOS APÓS O REINDEX =====================
    # 1) converte no new_df as colunas que são numéricas no master para numérico ('' -> 0)
    colunas_numericas_master = [
        c for c in master_df.columns
        if pd.api.types.is_numeric_dtype(master_df[c]) and c not in ("ANO", "codigo_municipio")
    ]
    for c in colunas_numericas_master:
        if c in new_df.columns:
            new_df[c] = pd.to_numeric(new_df[c], errors='coerce')
            new_df[c] = new_df[c].fillna(0)

    # 2) garante strings sem NaN nos dois dataframes
    for df in (master_df, new_df):
        colunas_string = [c for c in df.columns if df[c].dtype == object]
        for c in colunas_string:
            df[c] = df[c].fillna('')

    # 3) normaliza ANO e codigo_municipio em ambos
    for df in (master_df, new_df):
        if 'ANO' in df.columns:
            df['ANO'] = pd.to_numeric(df['ANO'], errors='coerce').astype('Int64')
        if 'codigo_municipio' in df.columns:
            df['codigo_municipio'] = pd.to_numeric(df['codigo_municipio'], errors='coerce').astype('Int64')

    for df in (master_df, new_df):
        if 'ano' in df.columns:
            df['ano'] = pd.to_numeric(df['ano'], errors='coerce').astype('Int64')
       

    for df in (master_df, new_df):
        cols_obj = [c for c in df.columns if df[c].dtype == object]
        for c in cols_obj:
            df[c] = df[c].fillna('') 

    if progress_callback:
        progress_callback(10)

       
    # ===================== SELEÇÃO DE CHAVES E COLUNAS DE ATUALIZAÇÃO =====================
    lista_update_cols: list[str] = []
    lista_num_cols:   list[str] = []

    colunas_chave = [
        c for c in master_df.columns
        if (master_df[c].dtype == object) or (c in ("ANO", "codigo_municipio"))
    ]
    lista_num_cols = [
        c for c in master_df.columns
        if pd.api.types.is_numeric_dtype(master_df[c]) and c not in ("ANO", "codigo_municipio")
    ]

    # ===================== ÍNDICES PELAS CHAVES =====================
    master_indexed = master_df.set_index(colunas_chave, drop=False)
    new_indexed    = new_df.set_index(colunas_chave, drop=False)

    if progress_callback:
        progress_callback(30)

    # ===================== LINHAS NOVAS (USAR MÁSCARA, NÃO .loc[MultiIndex]) =====================
    mascara_linhas_novas = ~new_indexed.index.isin(master_indexed.index)
    added_df             = new_indexed.loc[mascara_linhas_novas].reset_index(drop=True)
    added_count          = len(added_df)

    if progress_callback:
        progress_callback(50)

    # ===================== LINHAS EM COMUM E ATUALIZAÇÕES =====================
    chaves_em_comum = master_indexed.index.intersection(new_indexed.index)
    updated_count   = 0

    
    if len(chaves_em_comum) and len(lista_num_cols):
        mascara_diferencas_numericas = (
            master_indexed.loc[chaves_em_comum, lista_num_cols] !=
            new_indexed.loc[chaves_em_comum,   lista_num_cols]
        ).any(axis=1)

        chaves_para_atualizar = mascara_diferencas_numericas[mascara_diferencas_numericas].index
        updated_count         = len(chaves_para_atualizar)

        master_indexed.loc[chaves_para_atualizar, lista_num_cols] = new_indexed.loc[chaves_para_atualizar, lista_num_cols]

    if progress_callback:
        progress_callback(75)

    # ===================== RECOMPÕE E SALVA (usar reset_index(drop=True)) =====================
    master_final = pd.concat(
        [master_indexed.reset_index(drop=True), added_df],
        ignore_index=True,
        sort=False
    )

    if progress_callback:
        progress_callback(90)

    master_final.to_csv(master_path, index=False)

    if progress_callback:
        progress_callback(100)

    return {
        "added_count": added_count,
        "updated_count": updated_count,
        "total_after": len(master_final)
    }
