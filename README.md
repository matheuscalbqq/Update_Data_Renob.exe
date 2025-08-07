# Data Update

Uma aplicação de desktop com interface gráfica (PySide6) para atualizar bases de dados em CSV (Sisvan e Regional), oferecendo:

- Seleção de múltiplos arquivos CSV (via navegador ou input direto)
- Backup automático com rotação (até 3 versões)
- Merge incremental (só adiciona linhas novas)
- Barra de progresso animada e cancelável
- Exibição de logs em tempo real
- Tooltip de ajuda com instruções
- Exportação opcional para diretório `public/data`
- Restauração da última versão via botão **Restaurar**

---

## 📁 Estrutura do repositório

```
├── app.py                   # Ponto de entrada da aplicação
├── gui.py                   # Janela principal (QMainWindow) e lógica de UI
├── primary_function.py      # Tratamento e merge de CSVs (hash, criação/merge)
├── storage.py               # Configuração, backups, logging, contagem de linhas
├── config.json              # Parâmetros (caminhos, colunas, diretórios)
├── assets/                  # Ícones usados na aplicação
│   ├── app.png              # Ícone principal
│   └── help-icon.png        # Ícone de ajuda
├── Update.spec              # Arquivo .spec para PyInstaller
└── README.md                # Documentação (este arquivo)
```

---

## ⚙️ Pré-requisitos

- Python 3.8+
- [PySide6](https://pypi.org/project/PySide6/)
- [pandas](https://pypi.org/project/pandas/)

```bash
python -m venv venv
# Linux/macOS
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install PySide6 pandas
```

---

## 🔧 Configuração

Edite o `config.json` (no mesmo diretório de `app.py`) para ajustar:

- **data\_dir**: pasta onde os arquivos mestres (`db_sisvan.csv`, `db_regional.csv`) vivem
- **sisvan\_path** / **regional\_path**: nomes dos CSVs mestres
- **backup\_dir**: pasta onde serão salvos os backups
- **log\_path**: CSV de histórico de merges (`timestamp, input_file, master_file, added_count, total_after`)
- **colunasSisvan** / **colunasRegional**: colunas permitidas em cada base

Exemplo mínimo:

```json
{
  "data_dir":       "Data",
  "sisvan_path":    "db_sisvan.csv",
  "regional_path":  "db_regional.csv",
  "backup_dir":     "Backup",
  "log_path":       "merge_history.csv",
  "date_format":    "%Y%m%dT%H%M%S",
  "colunasSisvan":  ["UF","municipio","ANO","SEXO", "fase_vida", …],
  "colunasRegional":["estado_abrev","regional_id", …]
}
```

---

## ▶️ Como executar

### Em modo desenvolvimento

```bash
python app.py
```

### Gerando um executável com PyInstaller

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon="assets/app.png" --add-data "assets/app.png;assets" --add-data "assets/help-icon.png;assets" --name Update app.py
# Executável gerado em dist/Update.exe
```

---

## 🖥️ Uso

1. Abra o app (ou `dist/Update.exe`).
2. Escolha **Sisvan** ou **Regional**.
3. Carregue seus arquivos `.csv` pelo botão **Browser** ou digitando caminhos separados por `;`.
4. Clique em **Iniciar**.
5. Acompanhe a barra de progresso e o painel **Detalhes**.
6. Quando concluir, confirme exportação para `public/data` (opcional).
7. Para restaurar a última versão, use **Restaurar**.

---

## 🔄 Backups e Logs

- **Backups** → pasta `Backup/`, até 3 versões por base, com timestamp no nome.
- **Logs**   → `merge_history.csv`, registra data, arquivo de entrada, master, linhas adicionadas e total após.
