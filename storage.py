import json, os, sys, datetime, shutil
from pathlib import Path

def resource_path(relative_path: str) -> str:
    """
    Retorna o caminho absoluto para um recurso,
    seja em modo dev (pasta ao lado) ou em --onefile (extraído em _MEIPASS).
    """
    # Pega dinamicamente, sem gerar warning de atributo inexistente:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base_path = meipass
    else:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)

# Faz a conexão do config.json com os códigos py
def load_config(config_file: str = "config.json") -> dict:
    """
    Lê o arquivo JSON e converte strings de caminho em Path.
    Retorna um dicionário com todas as configurações.
    """
    if getattr(sys, "frozen", False):                   # Determina o "app_dir", onde está o .exe
         app_dir = Path(sys.executable).parent          # Empacotado com --onefile, o .exe é "frozen"
    else:
         app_dir = Path(__file__).parent                # Em desenvolvimento, usa o diretório do próprio script
        
    cfg_path = app_dir / config_file
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # Normaliza caminhos
    cfg["data_dir"]         = app_dir           / cfg["data_dir"]
    cfg["backup_dir"]       = app_dir           / cfg["backup_dir"]
    cfg["sisvan_path"]      = cfg["data_dir"]   / cfg["sisvan_path"]
    cfg["regional_path"]    = cfg["data_dir"]   / cfg["regional_path"]
    cfg["log_path"]         = cfg["backup_dir"] / cfg["log_path"]
    return cfg

cfg = load_config()

def count_lines(path:Path, has_header:bool=True) -> int :
            """
            Conta o número de linhas de um arquivo de texto.
            Se `has_header` for True, subtrai 1 para não contar a linha de cabeçalho.
            """
            with path.open("r", encoding="utf-8") as f:
                total = sum(1 for _ in f)
            return total - 1 if has_header else total

#=====================================================================================#
#================================= BACKUP SECTION ====================================#
#=====================================================================================#
def rotate_backup(original:Path, backup_dir:Path, keep: int=3, suffix: str = ".csv"):
    """
    Garante que não haja mais de `keep` arquivos de backup para o mesmo original.
    - original: Path do arquivo que estamos versionando (ex: master.csv)
    - backup_dir: Path da pasta de backups
    - keep: número máximo de arquivos a manter
    - suffix: extensão dos backups (padrão '.csv')
    """
    stem = original.stem
    # Padrão de nome: {stem}_{timestamp}{suffix}, ex: master_20250805T152300.csv
    pattern = f"{stem}_*{suffix}"
    backups = sorted(backup_dir.glob(pattern),key=lambda p: p.name)      # ordena alfabeticamente, e timestamps ISO sortam cronologicamente
        

    # Se já há >= keep cópias, remove as mais antigas até sobrar (keep-1)
    while len(backups) >= keep:
        oldest = backups.pop(0)     # retira e obtém o primeiro (mais antigo)
        try:
             oldest.unlink()
        except Exception as e:
             print(f"Falha ao remover backup antigo {oldest}: {e}")

def backup(original:Path, backup_dir: Path, date_format: str = "%d%m%Y-%H%M%S"):
    """
    Gera um backup do `original` em `backup_dir`, mantendo o histórico limitado por rotate_backups.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    # faz a rotação antes de criar o novo
    rotate_backup(original, backup_dir, keep=3, suffix=original.suffix)

    # cria nome com timestamp
    ts = datetime.datetime.now().strftime(date_format)
    backup_name = backup_dir / f"{original.stem}_{ts}{original.suffix}"

    # copia
    shutil.copy2(original, backup_name)
    return backup_name


#=====================================================================================#
#=================================== LOG SECTION =====================================#
#=====================================================================================#


LOG_FILE = cfg["log_path"]

# verificação da existência do arquivo de log / criação
def init_log():
    """
    Se o arquivo não existir, cria-o com cabeçalho.
    """

    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("timestamp, input_file, master_file, added_count, total_after\n")

# Adiciona linha do processo atual com timestamp e valores do resumo
def log_merge_file(input_file:str, master_file:str, added_count:int, total_after:int):
        """
        Grava uma linha no CSV de histórico
        """
        init_log()
        timestamp = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        line = f'{timestamp},"{input_file}","{master_file}", {added_count}, {total_after}\n'
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
