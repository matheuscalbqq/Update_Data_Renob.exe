# Atualizador SISVAN (CSV → Base Mestre)

> Aplicativo desktop para **atualizar a base SISVAN** a partir de arquivos `.csv`. 

![Plataforma](https://img.shields.io/badge/plataforma-Windows-blue) 
![Empacotamento](https://img.shields.io/badge/build-PyInstaller-informational) 
![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen)

---

## ✳️ Sumário
- [Visão Geral](#visão-geral)
- [Como Funciona](#como-funciona)
- [Formato do CSV (Esquema)](#formato-do-csv-esquema)
- [Regras de Mesclagem](#regras-de-mesclagem)
- [Como Usar (GUI)](#como-usar-gui)
- [Backups e Log de Auditoria](#backups-e-log-de-auditoria)
- [Estrutura do Repositório](#estrutura-do-repositorio)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Configuração (`config.json`)](#configuração-configjson)
- [Dúvidas Comuns](#dúvidas-comuns)
- [Build a partir do código-fonte](#build-a-partir-do-código-fonte)
- [Changelog](#changelog)

---

## 🏠 Visão Geral

Este app lê um ou mais **CSVs do SISVAN** e os **mescla** à base mestre (`Data/db_sisvan.csv`), mantendo histórico via **backup** e **log**.  
O processo é **acréscimo/atualização**: nada é apagado automaticamente.

Principais pontos:
- **Validação** de colunas e tipos básicos.
- **Backup** automático do mestre antes de qualquer alteração.
- **Mescla determinística** por chave composta (ver [Regras de Mesclagem](#regras-de-mesclagem)).
- **Log de auditoria** com totais de linhas inseridas/atualizadas e arquivos processados.

---

## 📁 Estrutura do Projeto

```

├─ assets/                # Ícones usados na aplicação
│  ├─ app.png             # Ícone principal
│  └─ help-icon.png       # Ícone de ajuda
├─ build/                 
│  └─ Update/             # Diversos arquivos utilizado para a build
├─ dist/                   
│  └─ Update.exe          # Aplicação
├─ old_version/ 
│  └─ Update-v1.exe       # Versão anterior com atualização da base Regional
├─ app.py                 # Ponto de entrada da aplicação
├─ config.json            # Parâmetros (caminhos, colunas, diretórios)
├─ gui.py                 # Janela principal (QMainWindow) e lógica de UI
├─ INSTRUCOES.txt         # Instruções de uso e formatação de entrada para o usuário
├─ primary_function.py    # Tratamento e merge de CSVs (hash, criação/merge)
├─ README.md              # Documentação (este arquivo)
├─ storage.py             # Configuração, backups, logging, contagem de linhas
└─ Update.spec            # Arquivo .spec para PyInstaller

```

---

## 📁 Estrutura do Projeto

```
.
├─ Update.exe
├─ config.json
├─ Data/
│  └─ db_sisvan.csv
└─ Backup/
   ├─ db_sisvan_YYYYMMDDThhmmss.csv
   └─ merge_history.csv
```

> A pasta/nomes podem ser ajustados via [`config.json`](#configuração-configjson).

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


## 🖥️ Como Funciona

1. Você seleciona um ou mais `.csv` (GUI → **Browser**).
2. O app valida o **cabeçalho** e o **tipo** das colunas.
3. É gerado um **backup** do mestre atual em `Backup/` (com timestamp).
4. As linhas do(s) CSV(s) são mescladas à base:
   - **Novas chaves** → linhas **inseridas**;
   - **Chaves existentes** → **somente colunas numéricas** são **atualizadas** com valores válidos do CSV.
5. O app grava um registro em `Backup/merge_history.csv`.

---

## 📃 Formato do CSV (Esquema)

**Colunas obrigatórias** (nomes exatos):
- **Dimensões/identificação**
  - `UF` (string, 2 letras, ex.: `MG`)
  - `codigo_municipio` (código IBGE de 7 dígitos, ex.: `3170206`)
  - `municipio` (nome do município)
  - `SEXO` (ex.: `M`, `F` — manter padrão da base)
  - `ANO` (inteiro, ex.: `2024`)
  - `fase_vida` (string; manter o mesmo padrão da base)

- **Métricas numéricas**
  - `baixo_peso`, `eutrofico`, `sobrepeso`,
  - `obesidade_G_1`, `obesidade_G_2`, `obesidade_G_3`,
  - `magreza_acentuada`, `magreza`,
  - `obesidade`, `obesidade_grave`,
  - `total`

**Recomendações e regras**:
- **Separador**: vírgula (`,`); **Codificação**: UTF‑8.
- **Numéricos** com **ponto** como separador decimal (`.`).
- `codigo_municipio`: 7 dígitos **sem máscara**.
- `UF`: `AA` (sempre 2 letras maiúsculas).
- `ANO`: 2000–2050 (faixa padrão de validação).

**Exemplo (cabeçalho + linha):**
```
UF,codigo_municipio,municipio,baixo_peso,eutrofico,sobrepeso,obesidade_G_1,obesidade_G_2,obesidade_G_3,magreza_acentuada,magreza,obesidade,obesidade_grave,total,SEXO,ANO,fase_vida
MG,3170206,Viçosa,12,345,67,23,4,1,3,10,28,2,495,M,2024,Adolescente
```

---

## ➕ Regras de Mesclagem

A **chave** de correspondência é a combinação de **todas as colunas textuais** (ex.: `UF`, `municipio`, `SEXO`, `fase_vida`) **+** `ANO` **+** `codigo_municipio`.

- Se a **chave existe** no mestre → **atualiza somente colunas numéricas** quando o CSV trouxer **valor válido** (não vazio/nulo).  
- Se a **chave não existe** → **insere** a linha completa.
- **Duplicatas** dentro do mesmo CSV: a **última ocorrência prevalece**.
- Linhas que não aparecem nos CSVs importados **não são removidas** do mestre.

---

## 🖥️ Como Usar (GUI)

1. Execute `Update.exe`.
2. Clique em **Browser** e selecione um ou mais `.csv`.
3. Clique em **Iniciar** para processar.  
4. Acompanhe o progresso pelo painel **Detalhes**.
5. Verifique os resultados:
   - Mestre atualizado: `Data/db_sisvan.csv`
   - Backups: `Backup/db_sisvan_YYYYMMDDThhmmss.csv`
   - Log: `Backup/merge_history.csv`

> Em caso de inconsistências, restaure o último backup (copiando de `Backup/...` para `Data/db_sisvan.csv`).

---

## 🔄 Backups e Log de Auditoria

- **Backup** automático do mestre (CSV) é criado **antes** de cada mesclagem:
  - `Backup/db_sisvan_YYYYMMDDThhmmss.csv`
- **Log** de auditoria em `Backup/merge_history.csv` com:
  - Timestamp da execução
  - CSVs processados
  - Linhas **inseridas** e **atualizadas**
  - Tamanho final da base mestre

---

## 🔧 Configuração (`config.json`)

Exemplo:

```json
{
  "data_dir": "Data",
  "sisvan_path": "db_sisvan.csv",
  "backup_dir": "Backup",
  "log_path": "merge_history.csv",
  "date_format": "%d%m%YT%H%M%S",
  "max_rows_in_memory": 1000000,
  "colunasSisvan": [
    "UF", "codigo_municipio", "municipio", "baixo_peso",
    "eutrofico", "sobrepeso", "obesidade_G_1", "obesidade_G_2",
    "obesidade_G_3", "magreza_acentuada", "magreza", "obesidade",
    "obesidade_grave", "total", "SEXO", "ANO", "fase_vida"
  ]
}
```

- `data_dir`: pasta onde fica o mestre.
- `sisvan_path`: nome do arquivo mestre dentro de `data_dir`.
- `backup_dir`: pasta de backups/logs.
- `log_path`: nome do arquivo de log de auditoria.
- `date_format`: formato do timestamp nos backups.
- `max_rows_in_memory`: limite para operações em memória.
- `colunasSisvan`: nomes/ordem esperados na base.

---

## ❓ Dúvidas Comuns

**“Coluna X não encontrada”**  
Verifique o **nome exato** no cabeçalho. Sensível à presença/ausência de acentos/underscores.

**“Números com vírgula”**  
Use **ponto** como separador decimal ou padronize antes de importar.

**“Arquivo em uso” (erro de acesso)**  
Feche o CSV no Excel/Google Sheets antes de rodar o app.

**“Caracteres estranhos”**  
Salve o CSV em **UTF‑8**.

**“Não atualizou”**  
Cheque a **chave** (texto + `ANO` + `codigo_municipio`) e o `merge_history.csv`.

---

## ▶️ Build

> Opcional. Usuários finais podem usar diretamente o `.exe`.

1. Em modo de desenvolvimento:
    ```bash
    python app.py
    ```
2. Gerar o binário com **PyInstaller**:
  ```bash
  pip install pyinstaller
  pyinstaller --onefile --windowed --icon="assets/app.png" --add-data "assets/app.png;assets" --add-data "assets/help-icon.png;assets" --name Update app.py
  # Executável gerado em dist/Update.exe
  ```
3. Gerar o binário com **PyInstaller** usando `Update.spec`:
   ```bash
   pyinstaller Update.spec
   ```
4. Saída em `dist/`.

