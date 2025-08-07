import shutil
import pandas as pd
from typing             import Optional
from pathlib            import Path
from primary_function   import merge_csvs, treatment, find_renob
from storage            import load_config, log_merge_file, backup, count_lines, resource_path
from PySide6.QtCore     import QPoint, Qt, QSize, QEvent, QPropertyAnimation, QThread, Signal
from PySide6.QtGui      import QIcon, QCursor
from PySide6.QtWidgets  import (
    QMainWindow,    QPushButton,    QVBoxLayout,    QHBoxLayout,
    QWidget,        QProgressBar,   QFileDialog,    QMessageBox, 
    QLineEdit,      QRadioButton,   QButtonGroup,  
    QGridLayout,    QToolButton,    QTextEdit,      QLabel
)


# recupera os caminhos para o arquivo master/pasta backup do config.json
cfg             = load_config()
SISVAN_FILE     = cfg["sisvan_path"]
REGIONAL_FILE   = cfg["regional_path"]
BACKUP_DIR      = cfg["backup_dir"]
BACKUP_DIR      .mkdir(exist_ok=True)
DATA_DIR        = cfg["data_dir"]
DATA_DIR        .mkdir(exist_ok=True)


class Worker(QThread):
    # sinais: emite um int (0–100) para progresso, e notifica fim de processamento
    progresso = Signal(int)
    finished  = Signal(bool)  # bool indica se cancelou (True) ou não (False)
    log       = Signal(str)

    def __init__(self, paths, master, backup_dir):
        super().__init__()
        self.paths      = paths
        self.master     = master
        self.backup_dir = backup_dir
        self.cancel_requested = False

        self.total          = 0
        self.added          = 0
        self.total_lines    = 0

    def run(self):
        # 1) Inicialização → 10%
        self.total = len(self.paths)
        if self.master.exists():
            self.total_lines = count_lines(self.master)
        else:
            self.total_lines = 0
        self.progresso.emit(10)

        # 2) Backup → 20%
        if self.master.exists() and not self.cancel_requested:
            self.log.emit("💾 Fazendo backup...")
            backup(self.master, self.backup_dir)
        self.progresso.emit(20)

        # 3) Processa cada CSV → de 20% a 90%
        
        for idx, file_path in enumerate(self.paths, start=1):
            if self.cancel_requested:
                break
            
            self.log.emit(f"({idx}/{self.total}) Processando: {file_path}")
            frac = (idx - 1) / self.total
            pct  = int(20 + frac*(90-20))
            self.progresso.emit(pct)

            # treatment + merge + log
            new_csv = treatment(Path(file_path), self.master)
            result = merge_csvs(pd.DataFrame(new_csv), self.master)
            log_merge_file(
                input_file   = file_path,
                master_file  = self.master,
                added_count  = result["added_count"],
                total_after  = result["total_after"]
            )
            self.added += result["added_count"]
        self.total_lines += self.added
        # 4) Final → 100%
        if not self.cancel_requested:
            self.progresso.emit(100)

        # 5) emite finished com flag se cancelou
        self.finished.emit(self.cancel_requested)



class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()                  # cria janela principal herdando QMainWindow

        self.paths = []
        self.last_backup: Path | None = None
        self.cancel_requested = False

        self._progress_anim = None

        self.setWindowTitle("Data Update")
        self.setWindowIcon(QIcon(resource_path("assets/app.png")))

        self._base_w = 700
        self._base_h = 150
        self         .setFixedSize(self._base_w, self._base_h)

        self._button_w = 75
        self._button_h = 25
        

        self.rb_op1 = QRadioButton("Sisvan Database")
        self.rb_op1.setFixedHeight(30)
        self.rb_op1.setChecked(True)

        self.rb_op2 = QRadioButton("Regional Database")
        self.rb_op2.setFixedHeight(30)

        group = QButtonGroup(self)
        group.setExclusive(True)
        for rb in (self.rb_op1,self.rb_op2):
            group.addButton(rb)
        
        self.line_edit = QLineEdit()
        self.line_edit .setFixedHeight(self._button_h - 2)
        self.line_edit.textChanged.connect(self.on_line_edit_changed)
        self.line_edit.setPlaceholderText(
            "Selecione o(s) arquivo(s) .csv ou digite o caminho aqui separados por ponto e vírgula (;)"
            )
        
        self.progress       = QProgressBar()                              # barra de progresso
        self.progress       .setFixedWidth(385)
        self.progress       .hide()
        
        self.button_help    = QToolButton()                               # botão ajuda
        self.button_help    .setIcon(QIcon(resource_path("assets/help-icon.png")))
        self.button_help    .setIconSize(QSize(25,25))                    # largura do botão ajuda
        self.button_help    .setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.button_help    .setAutoRaise(True)
        self.button_help    .setStyleSheet("border: none; background: transparent;")
        self.button_help    .clicked.connect(self.on_help_clicked)
        self.button_help    .setMouseTracking(True)

        self.help_label     = QLabel(self)
        self.help_label     .setWindowFlags(Qt.WindowType.ToolTip)
        self.help_label     .setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.help_label     .hide()
        self.help_label     .setStyleSheet(
                            """
                            background-color:white;
                            color: black;
                            border: 1px solid gray;
                            padding: 5px;
                            """
                            )
        
        self.button_help    .installEventFilter(self)
        
        self.button_select  = QPushButton("Browser")                      # botão que abre file browser
        self.button_select  .setFixedSize(self._button_w, self._button_h)
        self.button_select  .clicked.connect(self.select_files)           # Liga os eventos aos botões

        self.button_process = QPushButton("Iniciar")
        self.button_process .setFixedSize(self._button_w, self._button_h)
        self.button_process .setEnabled(False)
        self.button_process .clicked.connect(self.on_start_clicked)
        self.worker: Worker | None = None

        self.button_cancel  = QPushButton("Cancelar")
        self.button_cancel  .setFixedSize(self._button_w, self._button_h)
        self.button_cancel  .clicked.connect(self.cancel_process)
        self.button_cancel  .setEnabled(False)

        self.button_restore = QPushButton("Restaurar")
        self.button_restore .setFixedSize(self._button_w, self._button_h)
        self.button_restore .clicked.connect(self.restore_last_backup)

        self.details_button = QToolButton()
        self.details_button .setFixedSize(self._button_w, self._button_h)
        self.details_button .setText("Detalhes")
        self.details_button .setCheckable(True)
        self.details_button .setArrowType(Qt.ArrowType.RightArrow)
        self.details_button .setAutoRaise(True)
        self.details_button .setStyleSheet("border: none; background: transparent;")
        self.details_button .toggled.connect(self.on_toggle_details)
        self.details_button .setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self.details_text   = QTextEdit()
        self.details_text   .setReadOnly(True)
        self.details_text   .setStyleSheet("background-color: white;")
        self.details_text   .hide()

        for btn in (
            self.details_button,
            self.button_restore,
            self.button_process,
            self.button_cancel,
            self.button_select
        ):
            btn.setStyleSheet(
                """
                QToolButton, QPushButton {
                    padding-top: 2px;
                    padding-bottom: 4px;
                }
                """
            )

        top_layout = QHBoxLayout()                                        # Layout Horizontal para botões
        top_layout.addWidget(self.rb_op1)
        top_layout.addWidget(self.rb_op2)
        top_layout.addStretch()
        top_layout.addWidget(self.progress)
        top_layout.addStretch()
        top_layout.addWidget(self.button_help)                               

        import_layout = QHBoxLayout()
        IG_layout     = QGridLayout()
        import_layout.addLayout(IG_layout)  
        import_layout.addWidget(self.line_edit)
        import_layout.addWidget(self.button_select)

        details_layout = QVBoxLayout()
        details_layout.addWidget(self.details_button)
        details_layout.addWidget(self.details_text)


        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.button_restore)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_process)
        bottom_layout.addWidget(self.button_cancel)

        layout = QVBoxLayout()                                            #  Layout vertical
        layout.addLayout(top_layout)                                      # add: controle de topo,                              #      label status,
        layout.addLayout(import_layout)
        layout.addLayout(details_layout)
        layout.addLayout(bottom_layout)                                   #      barra de progresso.

        container = QWidget()                                             # container para encapsular tudo
        container.setLayout(layout)                                       # traz o layout pra dentro
        self.setCentralWidget(container)                                  # define como central na janela
        self.progress.setStyleSheet(
            """
                QProgressBar {
                    border: 1px solid #AAA;
                    border-radius: 5px;
                    background-color: #EEE;
                    text-align: center;
                }
                /* chunk no estado ativo */
                QProgressBar::chunk {
                    background-color: #74dba2;
                }
                /* chunk quando a janela fica inativa/desabilitada */
                QProgressBar::chunk:disabled {
                    background-color: #74dba2;
                }
            """
        )

    
    # SISVAN OU REGIONAL?
    def get_current_master(self) -> Path:
        """
        Retorna o arquivo master em uso, conforme o rádio selecionado.
        """
        if self.rb_op1.isChecked():
            return SISVAN_FILE
        else:
            return REGIONAL_FILE
        
    def on_help_clicked(self):
        """
        Mostra o balão de ajuda na posição do mouse + um offset para baixo.
        Só some quando o mouse sair do botão (capturado no eventFilter).
        """
        texto = (
                    "COMO USAR:\n"
                    "1. Selecione qual database deseja atualizar (Sisvan ou Regional).\n"
                    "2. Clique em 'Browser' e selecione CSV(s) ou escreva o(s) caminho(s) na caixa de texto.\n"
                    "3. Clique em 'Iniciar' para atualizar a database.\n"
                    "4. 'Detalhes' mostra em qual parte do processo está.\n"
                    "5. Para cancelar durante o processo, use 'Cancelar'.\n"
                    "6. Caso precise restaurar para a última versão, use 'Restaurar'.\n\n"
                    "COMO FUNCIONA?\n"
                    "1. Lê os arquivos\n"
                    "2. Os comparam com a database atual\n"
                    "3. Extrai somente as linhas que são diferentes\n"
                    "4. Faz backup da versão atual\n"
                    "5. Adiciona as novas linhas ao final da database\n"
                    "6. Atualiza o database direto no site do projeto\n"
                )
        # configura o texto e encaixa o tamanho
        self.help_label.setText(texto)
        self.help_label.adjustSize()

        # calcula posição global do canto inferior esquerdo do botão
        global_pos = QCursor.pos() + QPoint(0, 10)
        # converte para coords da MainWindow
        # move o label para aí
        self.help_label.move(global_pos)
        self.help_label.show()


    def eventFilter(self, obj, event):
        if obj is self.button_help:
            # Enquanto o tooltip estiver visível, reposiciona a cada movimento
            if event.type() == QEvent.Type.MouseMove and self.help_label.isVisible():
                # globalPosition() (QPointF) → toPoint() (QPoint)
                pos = QCursor.pos() + QPoint(0, 10)
                self.help_label.move(pos)

            # Quando o mouse sai do botão, esconde o tooltip
            elif event.type() == QEvent.Type.Leave:
                if self.help_label.isVisible():
                    self.help_label.hide()

        return super().eventFilter(obj, event)

    # controla os detalhes 
    def on_toggle_details(self, checked: bool):
        if checked:
            self.details_text.show()
            self.details_button.setArrowType(Qt.ArrowType.DownArrow)
            extra_h = self.details_text.sizeHint().height()
            self.setFixedSize(self._base_w,self._base_h + extra_h)
        else:
            self.details_text.hide()
            self.details_button.setArrowType(Qt.ArrowType.RightArrow)
            self.setFixedSize(self._base_w, self._base_h)

    def smooth_set_value(self, new_value: int, duration: int = 300):
        """
        Anima a barra de progresso de self.progress.value() até new_value em `duration` ms.
        """
        # cria o objeto de animação
        anim = QPropertyAnimation(self.progress, b"value", self)
        anim.setDuration(duration)
        anim.setStartValue(self.progress.value())
        anim.setEndValue(new_value)
        anim.start()

        # mantém referência viva
        self._progress_anim = anim
        
    # abre a seleção de arquivo (.csv)
    def select_files(self):

        paths, _ = QFileDialog.getOpenFileNames(
            self, "Carregar arquivos .CSV","","CSV Files (*.csv)"
        )
        if not paths:                                                         # Define não fazer nada se
            return                                                            # fechar a janela de seleção.
        
        self.paths  = paths
        db_name     = self.get_current_master().name

        self.details_text.clear()
        self.line_edit.setText("; ".join(paths))                              # escreve os caminhos na caixa de texto
        self.details_text.append(f"- {len(paths)} arquivo(s) selecionado(s) para {db_name}:")
        for p in paths:
            self.details_text.append(f"  • {p}")
        self.progress.setValue(0)                                             # Atualiza a barra de progresso em 10%
        self.button_process.setEnabled(True)
    
    def on_line_edit_changed(self, text: str):
        # 1) divide e limpa
        candidates = [p.strip() for p in text.split(';') if p.strip()]
        # 2) valida existência e extensão
        invalid_paths = []
        valid_paths = []
        for p in candidates:
            if Path(p).is_file() and p.lower().endswith('.csv'):
                valid_paths.append(p)
            else:
                invalid_paths.append(p)
        
        # 3) atualiza a lista de arquivos
        self.paths = valid_paths

        # 4) controla o botão Iniciar
        has_any = bool(valid_paths)
        self.button_process.setEnabled(has_any)

        self.details_text.clear()
        if valid_paths:
            self.details_text.append(f"- {len(valid_paths)} arquivo(s) detectado(s):")
            self.button_process.setEnabled(True)
            for p in valid_paths:
                self.details_text.append(f"  • {p}")
        if invalid_paths:
            self.details_text.append(f"- {len(invalid_paths)} caminho(s) inválido(s):")
            for p in invalid_paths:
                self.details_text.append(f" ❌ {p}")
        if not valid_paths and not invalid_paths:
            self.details_text.append("Nenhum caminho informado.")
                
      

    def on_start_clicked(self):
        if not self.paths:
            return
        # cria e configura o worker
        master      = self.get_current_master()
        db_name     = master.stem
        self.worker = Worker(self.paths, master, BACKUP_DIR)

        # preenche UI antes de iniciar
        self.progress.show()
        self.button_process.setEnabled(False)
        self.button_restore.setEnabled(False)
        self.button_select.setEnabled(False)
        self.rb_op1.setEnabled(False)
        self.rb_op2.setEnabled(False)
        self.button_cancel.setEnabled(True)
        self.details_text.append(f'- Atualizando: {db_name}')
        self.details_text.append(f"- Iniciando o processamento dos arquivos...")

        
        # conecta sinais
        self.worker.progresso.connect(self.smooth_set_value)
        self.worker.progresso.connect(lambda pct: self.progress.setFormat(f"{pct}%"))
        self.worker.log.connect(self.details_text.append)
        self.worker.finished.connect(self.on_worker_finished)
        # opcional: permitir cancelar
        self.worker.finished.connect(lambda _: None)  # só pra manter a referência
        # starta o thread
        self.worker.start()

    def cancel_process(self):
        """
        Marca a flag para interromper o loop de process_files.
        A restauração acontece dentro de process_files após o break.
        """
        if self.worker:
            self.worker.cancel_requested = True
        # opcional: você pode desabilitar o botão cancelar imediatamente
        self.button_cancel.setEnabled(False)
        self.progress.hide()
    
    def on_worker_finished(self, canceled: bool):
        """
        Recebe True se o usuário pediu cancelamento,
        ou False se terminou normalmente.
        """
        worker = self.worker
        assert worker is not None, "Worker deveria existir quando finished for chamado"
        if canceled:
            # restauramos o backup
            if self.worker and self.worker.master.exists():
                shutil.copy2(self.worker.master, self.worker.master)
            self.details_text.append("🚫 Processo cancelado. Backup restaurado.")
        else:
            self.details_text.append(
                f"✔️ Concluído(s) {worker.total} merge(s).\n"
                f"- {worker.added} linha(s) adicionada(s).\n"
                f"- Total final: {worker.total_lines} linha(s)."
            )
            renob_data  = find_renob("public/data")
            if renob_data is None:
                QMessageBox.warning(
                    self,
                    "Erro de localização",
                    "A pasta 'public/data' do projeto não foi encontrada."
                )
                return
            
            data_name = (
                "db_final.csv" if worker.master.stem == "db_sisvan"
                else "db_region.csv"
            )
            resposta = QMessageBox.question(
                self,
                "Exportar para o site",
                f"Deseja atualizar o arquivo '{data_name}' no projeto do site?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if resposta == QMessageBox.StandardButton.Yes:
                df_master   = pd.read_csv(worker.master)
                op_path     = renob_data / data_name
                df_master.to_csv(str(op_path), index=False)
                self.details_text.append("📂 Exportado para o projeto com sucesso!")


        # habilita/desabilita botões e oculta barra depois de um tempo
        self.button_cancel.setEnabled(False)
        self.button_restore.setEnabled(True)
        self.button_process.setEnabled(True)
        self.button_select.setEnabled(True)
        self.rb_op1.setEnabled(True)
        self.rb_op2.setEnabled(True)

    
    def restore_last_backup(self):
        """
        Busca o backup mais recente em BACKUP_DIR e restaura para MASTER_FILE.
        """
        resposta = QMessageBox.question(
            self,
            "Confirmar restauração",
            "Tem certeza que deseja restaurar a Database para a última versão?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel 
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return
        
        # Pattern de nome: master_DDMMYYYYThhmmss.csv
        master = self.get_current_master()
        pattern = f"{master.stem}_*{master.suffix}"
        backups = sorted(
            BACKUP_DIR.glob(pattern),
            key=lambda p: p.name
        )
        if not backups:
            QMessageBox.information(self, "Restaurar", "Nenhum backup encontrado.")
            return

        latest = backups[-1]
        shutil.copy2(latest, master)
        QMessageBox.information(
            self,
            "Restaurar",
            f"Backup restaurado ({master.name}): {latest.name}"
        )
        # opcional: atualizar UI
        self.progress.setValue(0)
        self.details_text.append(f"{master.name} restaurado para: {latest.name}")