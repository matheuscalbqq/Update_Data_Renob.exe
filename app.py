from gui                import MainWindow
from PySide6.QtWidgets  import QApplication, QStyleFactory
import sys

if __name__ == "__main__":                  # Garante que só roda quando script for executado diretamente
    app     = QApplication(sys.argv)        # Instancia a aplicação Qt
   # 1) Force um style Fusion que respeite paletas
    app.setStyle(QStyleFactory.create("Fusion"))

    window  = MainWindow()                  # Cria janela principal
    window  .show()                         # Torna visível
    sys     .exit(app.exec())               # Loop para deixar janela aberta até fechar com sys.exit