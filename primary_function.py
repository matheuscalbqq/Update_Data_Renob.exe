import pandas as pd
import hashlib
from pathlib import Path
from storage import load_config
from typing  import Optional

#==============================================================================#
#======================= HASH PARA COMPARAÇÂO =================================#
#==============================================================================#
def hash_line(line: str) -> str:
    return hashlib.sha256(line.encode('utf-8')).hexdigest()

#==============================================================================#
#======================= CARREGA/CRIA AS DBS ==================================#
#==============================================================================#
def load_create_master(master_path: Path) -> pd.DataFrame:
    cfg = load_config()
    if master_path.exists():
        return pd.read_csv(master_path)
    elif 'sisvan' in master_path.stem:
        return pd.DataFrame(columns=cfg["colunasSisvan"])
    else: 
        return pd.DataFrame(columns=cfg["colunasRegional"])

#==============================================================================#
#======================= TRATAMENTO DOS DADOS =================================#
#==============================================================================#
def treatment(new_csv: Path, master_csv: Path):
    cfg = load_config()
    
    if 'sisvan' in master_csv.stem:
        colunas = cfg["colunasSisvan"]

        new_df = pd.read_csv(new_csv)

        matching_columns = [col for col in new_df.columns if col in colunas]
        new_df = new_df[matching_columns]

        for col in colunas:
            if col not in new_df.columns:
                new_df[col] = 0
        
        if 'adolescente' in new_csv.stem:
            new_df['fase_vida'] = 'adolescente'
        elif 'adulto' in new_csv.stem:
            new_df['fase_vida'] = 'adulto'
        elif 'idosos' in new_csv.stem:
            new_df['fase_vida'] = 'idoso'
        else:
            new_df['fase_vida'] = 'desconhecido'

        return new_df
    
    elif 'regional' in master_csv.stem:
        colunas = cfg["colunasRegional"]

        new_df = pd.read_csv(new_csv)

        matching_columns = [col for col in new_df.columns if col in colunas]
        new_df = new_df[matching_columns]

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
def merge_csvs(new_csv: pd.DataFrame, master_path:Path) -> dict:
    data_path   = "public/data"
    renob_data  = find_renob(data_path)
    master_df   = load_create_master(master_path)         # carrega o Master.csv
    new_df      = new_csv                                 # Leitura do arquivo .csv selecionado
    
    if Path(master_path).stem == 'db_sisvan': 
            data_name   = "db_final" 
    else:   data_name   = "db_region"

    #cria conjuntos de hashes para comparação (linha inteira como string)
    existing_hashes = set()
    if not master_df.empty:
        existing_hashes = set(
            master_df.apply(
                lambda row: hash_line(','.join(map(str,row.tolist()))),axis=1
            )
        )
    
    #itera sobre cada linha de new_df: string única -> hash -> compara 
    added = []
    for _, row in new_df.iterrows():
        line_str = ','.join(map(str,row.tolist()))
        h = hash_line(line_str)
        if h not in existing_hashes:                    # se não existe, adicona a added e ao set de hashes
            added.append(row)
            existing_hashes.add(h)
    
    #criar DataFrame com as novas linhas (se existirem)
    if added:
        added_df = pd.DataFrame(added)
        if master_df.empty:
            updated = added_df
        else:
            updated = pd.concat([master_df,added_df], ignore_index=True)
        updated.to_csv(master_path, index=False)
        # updated.to_csv(f'{renob_data}/{data_name}.csv', index=False) # comentando para teste
    else:
        updated = master_df
    return{                                             # retorna dicionario com resumo do resultado 
        "added_count": len(added),                      # do processo: quantas linhas adicionadas e 
        "total_after": len(updated)                     # o novo total de linhas
    }