# ============================================================================
# Processador ETL Pro com Transcrição de Mídia
# ============================================================================

"""
Processador ETL Pro - Versão Completa (Qt6)
Com transcrição de áudio/vídeo e melhor tratamento de tipos de dados

Autor: Rafael Coriolano Siqueira
Data: 2025
Licença: MIT

INSTALAÇÃO DE DEPENDÊNCIAS:
pip install pandas openpyxl PyQt6 numpy speechrecognition pydub moviepy

OBSERVAÇÕES:
- Para transcrição de áudio, é necessário ter o ffmpeg instalado no sistema
- A transcrição usa o reconhecimento de voz do Google (requer internet)
- Para uso offline de transcrição, seria necessário integrar um modelo local como Vosk
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json
import sqlite3
from datetime import datetime
import unicodedata
import re
import tempfile
import os

# Importações para transcrição de mídia
try:
    import speech_recognition as sr
    from pydub import AudioSegment
    from moviepy.video.io.VideoFileClip import VideoFileClip
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    TRANSCRICAO_DISPONIVEL = True
except ImportError:
    TRANSCRICAO_DISPONIVEL = False

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QListWidget, QTextEdit,
                             QFileDialog, QProgressBar, QTabWidget, QCheckBox,
                             QComboBox, QGroupBox, QMessageBox, QApplication,
                             QLineEdit, QSpinBox, QDoubleSpinBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSplitter, QFormLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QIcon, QPixmap

# ============================================================================
# CLASSE ETL PROCESSOR - MELHORADA
# ============================================================================


class ETLProcessor:
    """Processador ETL principal com tratamento melhorado de tipos de dados"""

    def __init__(self):
        self.dataframes = {}
        self.metadata = {
            "processamento_inicio": None,
            "processamento_fim": None,
            "arquivos_processados": [],
            "registros_totais": 0,
            "colunas_totais": 0,
            "duplicatas_removidas": 0,
            "arquivos_transcritos": []
        }

    def normalizar_texto(self, texto: str) -> str:
        """Normaliza texto removendo acentos e caracteres especiais"""
        if pd.isna(texto) or not isinstance(texto, str):
            return texto

        texto_nfd = unicodedata.normalize('NFD', texto)
        texto_sem_acento = ''.join(
            char for char in texto_nfd if unicodedata.category(char) != 'Mn')

        return texto_sem_acento.strip()

    def detectar_e_converter_tipo_coluna(self, serie: pd.Series) -> Tuple[pd.Series, str]:
        """Detecta e converte o tipo de dados de uma coluna"""
        # Tentativa de conversão para data
        if serie.dtype == 'object':
            # Tenta converter para datetime
            try:
                serie_datetime = pd.to_datetime(serie, errors='coerce')
                if not serie_datetime.isna().all():
                    # Verifica se há pelo menos 30% de valores de data válidos
                    percentual_validos = (
                        1 - serie_datetime.isna().sum() / len(serie)) * 100
                    if percentual_validos >= 30:
                        return serie_datetime, "data"
            except:
                pass

            # Tenta converter para numérico
            try:
                serie_numerica = pd.to_numeric(serie, errors='coerce')
                if not serie_numerica.isna().all():
                    # Verifica se há pelo menos 50% de valores numéricos válidos
                    percentual_validos = (
                        1 - serie_numerica.isna().sum() / len(serie)) * 100
                    if percentual_validos >= 50:
                        # Decide entre inteiro e decimal
                        if (serie_numerica % 1 == 0).all():
                            return serie_numerica.astype('Int64'), "inteiro"
                        else:
                            return serie_numerica.astype(float), "decimal"
            except:
                pass

        # Mantém como texto se não for possível converter
        return serie.astype(str), "texto"

    def processar_transcricao_midia(self, caminho: Path) -> Dict[str, Any]:
        """Processa arquivos de áudio/vídeo e extrai texto transcrito"""
        if not TRANSCRICAO_DISPONIVEL:
            raise Exception(
                "Bibliotecas de transcrição não disponíveis. Instale speechrecognition, pydub e moviepy.")

        try:
            recognizer = sr.Recognizer()
            texto_transcrito = ""

            # Extrai áudio do arquivo
            if caminho.suffix.lower() in ['.mp3', '.wav', '.flac', '.m4a']:
                # É arquivo de áudio
                audio = AudioSegment.from_file(str(caminho))
            elif caminho.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']:
                # É arquivo de vídeo - extrai áudio
                video = VideoFileClip(str(caminho))
                temp_audio = tempfile.NamedTemporaryFile(
                    delete=False, suffix='.wav')
                video.audio.write_audiofile(
                    temp_audio.name, logger=None)
                audio = AudioSegment.from_file(temp_audio.name)
                temp_audio.close()
                os.unlink(temp_audio.name)
            else:
                raise ValueError(
                    f"Formato de mídia não suportado: {caminho.suffix}")

            # Converte para formato WAV para processamento
            temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            audio.export(temp_wav.name, format='wav')

            # Carrega o áudio para reconhecimento
            with sr.AudioFile(temp_wav.name) as source:
                audio_data = recognizer.record(source)

            # Tenta transcrever usando Google Speech Recognition
            try:
                texto_transcrito = recognizer.recognize_google(
                    audio_data, language='pt-BR')
            except sr.UnknownValueError:
                texto_transcrito = "Não foi possível entender o áudio"
            except sr.RequestError as e:
                texto_transcrito = f"Erro no serviço de reconhecimento: {e}"

            # Limpa arquivos temporários
            temp_wav.close()
            os.unlink(temp_wav.name)

            resultado = {
                "arquivo": caminho.name,
                "caminho_completo": str(caminho),
                "texto_transcrito": texto_transcrito,
                "tamanho_arquivo": caminho.stat().st_size,
                "data_processamento": datetime.now().isoformat()
            }

            self.metadata["arquivos_transcritos"].append(caminho.name)
            return resultado

        except Exception as e:
            raise Exception(
                f"Erro ao processar mídia {caminho.name}: {str(e)}")

    def carregar_csv(self, caminho: Path, normalizar: bool = True) -> pd.DataFrame:
        """Carrega arquivo CSV com tratamento de erros e conversão de tipos"""
        try:
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            df = None

            for encoding in encodings:
                try:
                    df = pd.read_csv(caminho, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if df is None:
                raise ValueError(
                    f"Não foi possível ler o arquivo {caminho.name}")

            # Aplica conversão de tipos de colunas
            for coluna in df.columns:
                df[coluna], tipo_detectado = self.detectar_e_converter_tipo_coluna(
                    df[coluna])
                # Log da conversão (poderia ser armazenado em metadados)

            df['arquivo_origem'] = caminho.name

            if normalizar:
                for col in df.select_dtypes(include=['object']).columns:
                    if col != 'arquivo_origem':
                        df[col] = df[col].apply(self.normalizar_texto)

            duplicatas_antes = len(df)
            df = df.drop_duplicates()
            duplicatas_removidas = duplicatas_antes - len(df)

            self.metadata["duplicatas_removidas"] += duplicatas_removidas
            self.metadata["arquivos_processados"].append(caminho.name)

            return df

        except Exception as e:
            raise Exception(f"Erro ao carregar {caminho.name}: {str(e)}")

    def carregar_excel(self, caminho: Path, normalizar: bool = True) -> Dict[str, pd.DataFrame]:
        """Carrega arquivo Excel com múltiplas abas e conversão de tipos"""
        try:
            excel_file = pd.ExcelFile(caminho)
            dfs = {}

            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)

                # Aplica conversão de tipos de colunas
                for coluna in df.columns:
                    df[coluna], tipo_detectado = self.detectar_e_converter_tipo_coluna(
                        df[coluna])

                df['arquivo_origem'] = f"{caminho.name}:{sheet_name}"

                if normalizar:
                    for col in df.select_dtypes(include=['object']).columns:
                        if col != 'arquivo_origem':
                            df[col] = df[col].apply(self.normalizar_texto)

                duplicatas_antes = len(df)
                df = df.drop_duplicates()
                self.metadata["duplicatas_removidas"] += duplicatas_antes - \
                    len(df)

                dfs[sheet_name] = df

            self.metadata["arquivos_processados"].append(caminho.name)
            return dfs

        except Exception as e:
            raise Exception(f"Erro ao carregar Excel {caminho.name}: {str(e)}")

    def carregar_json(self, caminho: Path) -> pd.DataFrame:
        """Carrega arquivo JSON com conversão de tipos"""
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            else:
                raise ValueError("Formato JSON não suportado")

            # Aplica conversão de tipos de colunas
            for coluna in df.columns:
                df[coluna], tipo_detectado = self.detectar_e_converter_tipo_coluna(
                    df[coluna])

            df['arquivo_origem'] = caminho.name
            self.metadata["arquivos_processados"].append(caminho.name)

            return df

        except Exception as e:
            raise Exception(f"Erro ao carregar JSON {caminho.name}: {str(e)}")

    def analisar_qualidade(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analisa qualidade dos dados com informações de tipos"""
        analise = {
            "total_registros": len(df),
            "total_colunas": len(df.columns),
            "colunas": {}
        }

        for col in df.columns:
            tipo_detectado = "texto"
            if pd.api.types.is_numeric_dtype(df[col]):
                tipo_detectado = "decimal" if df[col].dtype == float else "inteiro"
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                tipo_detectado = "data"

            analise["colunas"][col] = {
                "tipo": str(df[col].dtype),
                "tipo_detectado": tipo_detectado,
                "valores_nulos": int(df[col].isna().sum()),
                "valores_unicos": int(df[col].nunique()),
                "completude": float(round((1 - df[col].isna().sum() / len(df)) * 100, 2))
            }

            if pd.api.types.is_numeric_dtype(df[col]):
                analise["colunas"][col].update({
                    "minimo": float(df[col].min()) if not df[col].isna().all() else None,
                    "maximo": float(df[col].max()) if not df[col].isna().all() else None,
                    "media": float(df[col].mean()) if not df[col].isna().all() else None,
                    "mediana": float(df[col].median()) if not df[col].isna().all() else None
                })
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                analise["colunas"][col].update({
                    "data_minima": df[col].min().isoformat() if not df[col].isna().all() else None,
                    "data_maxima": df[col].max().isoformat() if not df[col].isna().all() else None
                })

        return analise

    def exportar_excel(self, caminho: Path, incluir_analise: bool = True):
        """Exporta dados para Excel com múltiplas abas"""
        with pd.ExcelWriter(caminho, engine='openpyxl') as writer:
            for nome, df in self.dataframes.items():
                df.to_excel(writer, sheet_name=nome[:31], index=False)

            if incluir_analise:
                analises = []
                for nome, df in self.dataframes.items():
                    analise = self.analisar_qualidade(df)
                    for col, stats in analise["colunas"].items():
                        analises.append({
                            "Tabela": nome,
                            "Coluna": col,
                            **stats
                        })

                if analises:
                    df_analise = pd.DataFrame(analises)
                    df_analise.to_excel(
                        writer, sheet_name="Analise_Qualidade", index=False)

            df_meta = pd.DataFrame([self.metadata])
            df_meta.to_excel(writer, sheet_name="Metadados", index=False)

    def exportar_sqlite(self, caminho: Path):
        """Exporta dados para SQLite"""
        conn = sqlite3.connect(caminho)

        for nome, df in self.dataframes.items():
            df.to_sql(nome, conn, if_exists='replace', index=False)

        df_meta = pd.DataFrame([self.metadata])
        df_meta.to_sql('_metadados', conn, if_exists='replace', index=False)

        conn.close()

    def exportar_sql_script(self, caminho: Path, dialeto: str = 'mysql'):
        """Exporta script SQL para criação de tabelas"""
        with open(caminho, 'w', encoding='utf-8') as f:
            f.write(f"-- Script SQL gerado em {datetime.now()}\n")
            f.write(f"-- Dialeto: {dialeto}\n\n")

            for nome, df in self.dataframes.items():
                f.write(f"-- Tabela: {nome}\n")
                f.write(f"DROP TABLE IF EXISTS {nome};\n")
                f.write(f"CREATE TABLE {nome} (\n")

                colunas = []
                for col in df.columns:
                    tipo_sql = self._mapear_tipo_sql(df[col].dtype, dialeto)
                    colunas.append(f"    {col} {tipo_sql}")

                f.write(",\n".join(colunas))
                f.write("\n);\n\n")

    def _mapear_tipo_sql(self, dtype, dialeto: str) -> str:
        """Mapeia tipos pandas para SQL"""
        if pd.api.types.is_integer_dtype(dtype):
            return "INTEGER"
        elif pd.api.types.is_float_dtype(dtype):
            return "DECIMAL(10,2)"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            return "DATETIME" if dialeto == 'mysql' else "TIMESTAMP"
        else:
            return "VARCHAR(255)"

# ============================================================================
# THREADS DE PROCESSAMENTO
# ============================================================================


class ProcessadorThread(QThread):
    """Thread para processamento ETL em background"""
    progresso = pyqtSignal(int, str)
    concluido = pyqtSignal(dict)
    erro = pyqtSignal(str)

    def __init__(self, arquivos, opcoes):
        super().__init__()
        self.arquivos = arquivos
        self.opcoes = opcoes
        self.processor = ETLProcessor()

    def run(self):
        try:
            total = len(self.arquivos)

            for i, arquivo in enumerate(self.arquivos):
                self.progresso.emit(int((i / total) * 100),
                                    f"Processando {arquivo.name}...")

                if arquivo.suffix.lower() == '.csv':
                    df = self.processor.carregar_csv(
                        arquivo, self.opcoes['normalizar'])
                    self.processor.dataframes[arquivo.stem] = df

                elif arquivo.suffix.lower() in ['.xlsx', '.xls']:
                    dfs = self.processor.carregar_excel(
                        arquivo, self.opcoes['normalizar'])
                    self.processor.dataframes.update(dfs)

                elif arquivo.suffix.lower() == '.json':
                    df = self.processor.carregar_json(arquivo)
                    self.processor.dataframes[arquivo.stem] = df

            self.progresso.emit(100, "Processamento concluído!")
            self.concluido.emit(self.processor.metadata)

        except Exception as e:
            self.erro.emit(str(e))


class TranscricaoThread(QThread):
    """Thread para processamento de transcrição em background"""
    progresso = pyqtSignal(int, str)
    concluido = pyqtSignal(list)
    erro = pyqtSignal(str)

    def __init__(self, arquivos):
        super().__init__()
        self.arquivos = arquivos
        self.processor = ETLProcessor()
        self.resultados = []

    def run(self):
        try:
            total = len(self.arquivos)

            for i, arquivo in enumerate(self.arquivos):
                self.progresso.emit(int((i / total) * 100),
                                    f"Transcrevendo {arquivo.name}...")

                resultado = self.processor.processar_transcricao_midia(arquivo)
                self.resultados.append(resultado)

            self.progresso.emit(100, "Transcrição concluída!")
            self.concluido.emit(self.resultados)

        except Exception as e:
            self.erro.emit(str(e))

# ============================================================================
# JANELA PRINCIPAL - EXPANDIDA
# ============================================================================


class MainWindow(QMainWindow):
    """Janela principal da aplicação com funcionalidades expandidas"""

    def __init__(self):
        super().__init__()
        self.arquivos = []
        self.arquivos_midia = []
        self.processor = None
        self.resultados_transcricao = []
        self.init_ui()

    def init_ui(self):
        """Inicializa interface"""
        self.setWindowTitle("Processador ETL Pro - v2.0 com Transcrição")
        self.setGeometry(100, 100, 1400, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        titulo = QLabel("🚀 Processador ETL Profissional com Transcrição")
        titulo.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titulo)

        tabs = QTabWidget()
        tabs.addTab(self.criar_aba_importacao(), "📁 Importação")
        tabs.addTab(self.criar_aba_processamento(), "⚙️ Processamento")
        tabs.addTab(self.criar_aba_transcricao(), "🎤 Transcrição")
        tabs.addTab(self.criar_aba_exportacao(), "💾 Exportação")
        tabs.addTab(self.criar_aba_logs(), "📊 Logs")
        layout.addWidget(tabs)

        self.statusBar().showMessage("Pronto")
        self.aplicar_estilo()

    def criar_aba_importacao(self):
        """Cria aba de importação"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Seção arquivos de dados
        grupo_dados = QGroupBox("Arquivos de Dados (CSV, Excel, JSON)")
        layout_dados = QVBoxLayout()

        btn_layout = QHBoxLayout()
        btn_adicionar = QPushButton("➕ Adicionar Arquivos de Dados")
        btn_adicionar.clicked.connect(self.adicionar_arquivos)
        btn_limpar = QPushButton("🗑️ Limpar Lista")
        btn_limpar.clicked.connect(self.limpar_arquivos)
        btn_layout.addWidget(btn_adicionar)
        btn_layout.addWidget(btn_limpar)
        layout_dados.addLayout(btn_layout)

        self.lista_arquivos = QListWidget()
        layout_dados.addWidget(QLabel("Arquivos de dados selecionados:"))
        layout_dados.addWidget(self.lista_arquivos)

        grupo_dados.setLayout(layout_dados)
        layout.addWidget(grupo_dados)

        # Seção arquivos de mídia
        grupo_midia = QGroupBox("Arquivos de Mídia (Áudio/Video)")
        layout_midia = QVBoxLayout()

        btn_layout_midia = QHBoxLayout()
        btn_adicionar_midia = QPushButton("🎵 Adicionar Arquivos de Mídia")
        btn_adicionar_midia.clicked.connect(self.adicionar_arquivos_midia)
        btn_limpar_midia = QPushButton("🗑️ Limpar Lista de Mídia")
        btn_limpar_midia.clicked.connect(self.limpar_arquivos_midia)
        btn_layout_midia.addWidget(btn_adicionar_midia)
        btn_layout_midia.addWidget(btn_limpar_midia)
        layout_midia.addLayout(btn_layout_midia)

        self.lista_arquivos_midia = QListWidget()
        layout_midia.addWidget(QLabel("Arquivos de mídia selecionados:"))
        layout_midia.addWidget(self.lista_arquivos_midia)

        grupo_midia.setLayout(layout_midia)
        layout.addWidget(grupo_midia)

        layout.addStretch()
        return widget

    def criar_aba_processamento(self):
        """Cria aba de processamento"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        grupo_opcoes = QGroupBox("Opções de Processamento")
        opcoes_layout = QVBoxLayout()

        self.check_normalizar = QCheckBox("Normalizar texto (remover acentos)")
        self.check_normalizar.setChecked(True)
        opcoes_layout.addWidget(self.check_normalizar)

        self.check_duplicatas = QCheckBox("Remover duplicatas")
        self.check_duplicatas.setChecked(True)
        opcoes_layout.addWidget(self.check_duplicatas)

        self.check_converter_tipos = QCheckBox(
            "Converter tipos automaticamente")
        self.check_converter_tipos.setChecked(True)
        opcoes_layout.addWidget(self.check_converter_tipos)

        grupo_opcoes.setLayout(opcoes_layout)
        layout.addWidget(grupo_opcoes)

        self.btn_processar = QPushButton("▶️ Iniciar Processamento ETL")
        self.btn_processar.clicked.connect(self.processar_arquivos)
        self.btn_processar.setMinimumHeight(50)
        layout.addWidget(self.btn_processar)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.label_status = QLabel("Aguardando...")
        layout.addWidget(self.label_status)

        layout.addStretch()
        return widget

    def criar_aba_transcricao(self):
        """Cria aba de transcrição de mídia"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        if not TRANSCRICAO_DISPONIVEL:
            layout.addWidget(
                QLabel("⚠️ Funcionalidade de transcrição não disponível."))
            layout.addWidget(
                QLabel("Instale: pip install speechrecognition pydub moviepy"))
            return widget

        layout.addWidget(QLabel("Arquivos de mídia para transcrição:"))
        self.lista_transcricao = QListWidget()
        layout.addWidget(self.lista_transcricao)

        self.btn_transcrever = QPushButton("🎤 Transcrever Áudio/Video")
        self.btn_transcrever.clicked.connect(self.transcrever_midia)
        layout.addWidget(self.btn_transcrever)

        self.progress_bar_transcricao = QProgressBar()
        layout.addWidget(self.progress_bar_transcricao)

        self.label_status_transcricao = QLabel(
            "Aguardando arquivos de mídia...")
        layout.addWidget(self.label_status_transcricao)

        # Área de visualização dos resultados
        layout.addWidget(QLabel("Resultados da Transcrição:"))
        self.tabela_resultados = QTableWidget()
        self.tabela_resultados.setColumnCount(3)
        self.tabela_resultados.setHorizontalHeaderLabels(
            ["Arquivo", "Tamanho", "Texto Transcrito"])
        self.tabela_resultados.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tabela_resultados)

        return widget

    def criar_aba_exportacao(self):
        """Cria aba de exportação"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Exportação de dados ETL
        grupo_etl = QGroupBox("Exportação de Dados ETL")
        layout_etl = QVBoxLayout()

        layout_etl.addWidget(QLabel("Formato de saída para dados:"))
        self.combo_formato = QComboBox()
        self.combo_formato.addItems([
            "Excel (.xlsx)",
            "SQLite (.db)",
            "SQL Script (.sql)",
            "CSV (múltiplos)",
            "JSON"
        ])
        layout_etl.addWidget(self.combo_formato)

        btn_exportar = QPushButton("💾 Exportar Dados ETL")
        btn_exportar.clicked.connect(self.exportar_dados)
        layout_etl.addWidget(btn_exportar)

        grupo_etl.setLayout(layout_etl)
        layout.addWidget(grupo_etl)

        # Exportação de transcrições
        grupo_transcricao = QGroupBox("Exportação de Transcrições")
        layout_transcricao = QVBoxLayout()

        layout_transcricao.addWidget(
            QLabel("Formato de saída para transcrições:"))
        self.combo_formato_transcricao = QComboBox()
        self.combo_formato_transcricao.addItems([
            "Texto (.txt)",
            "JSON (.json)",
            "Excel (.xlsx)",
            "CSV (.csv)"
        ])
        layout_transcricao.addWidget(self.combo_formato_transcricao)

        btn_exportar_transcricao = QPushButton("📝 Exportar Transcrições")
        btn_exportar_transcricao.clicked.connect(self.exportar_transcricoes)
        layout_transcricao.addWidget(btn_exportar_transcricao)

        grupo_transcricao.setLayout(layout_transcricao)
        layout.addWidget(grupo_transcricao)

        layout.addStretch()
        return widget

    def criar_aba_logs(self):
        """Cria aba de logs"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.text_logs = QTextEdit()
        self.text_logs.setReadOnly(True)
        layout.addWidget(self.text_logs)

        btn_limpar_logs = QPushButton("🧹 Limpar Logs")
        btn_limpar_logs.clicked.connect(self.limpar_logs)
        layout.addWidget(btn_limpar_logs)

        return widget

    def adicionar_arquivos(self):
        """Adiciona arquivos de dados à lista"""
        arquivos, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar Arquivos de Dados",
            "",
            "Todos os Arquivos (*.csv *.xlsx *.xls *.json);;CSV (*.csv);;Excel (*.xlsx *.xls);;JSON (*.json)"
        )

        for arquivo in arquivos:
            path = Path(arquivo)
            if path not in self.arquivos:
                self.arquivos.append(path)
                self.lista_arquivos.addItem(path.name)

        self.log(f"✓ {len(arquivos)} arquivo(s) de dados adicionado(s)")

    def adicionar_arquivos_midia(self):
        """Adiciona arquivos de mídia à lista"""
        arquivos, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar Arquivos de Mídia",
            "",
            "Arquivos de Mídia (*.mp3 *.wav *.flac *.m4a *.mp4 *.avi *.mov *.mkv);;Áudio (*.mp3 *.wav *.flac *.m4a);;Vídeo (*.mp4 *.avi *.mov *.mkv)"
        )

        for arquivo in arquivos:
            path = Path(arquivo)
            if path not in self.arquivos_midia:
                self.arquivos_midia.append(path)
                self.lista_arquivos_midia.addItem(path.name)
                self.lista_transcricao.addItem(path.name)

        self.log(f"✓ {len(arquivos)} arquivo(s) de mídia adicionado(s)")

    def limpar_arquivos(self):
        """Limpa lista de arquivos de dados"""
        self.arquivos.clear()
        self.lista_arquivos.clear()
        self.log("Lista de arquivos de dados limpa")

    def limpar_arquivos_midia(self):
        """Limpa lista de arquivos de mídia"""
        self.arquivos_midia.clear()
        self.lista_arquivos_midia.clear()
        self.lista_transcricao.clear()
        self.log("Lista de arquivos de mídia limpa")

    def processar_arquivos(self):
        """Processa arquivos de dados selecionados"""
        if not self.arquivos:
            QMessageBox.warning(
                self, "Aviso", "Nenhum arquivo de dados selecionado!")
            return

        opcoes = {
            'normalizar': self.check_normalizar.isChecked(),
            'remover_duplicatas': self.check_duplicatas.isChecked(),
            'converter_tipos': self.check_converter_tipos.isChecked()
        }

        self.btn_processar.setEnabled(False)
        self.thread = ProcessadorThread(self.arquivos, opcoes)
        self.thread.progresso.connect(self.atualizar_progresso)
        self.thread.concluido.connect(self.processamento_concluido)
        self.thread.erro.connect(self.processamento_erro)
        self.thread.start()

    def transcrever_midia(self):
        """Processa arquivos de mídia para transcrição"""
        if not self.arquivos_midia:
            QMessageBox.warning(
                self, "Aviso", "Nenhum arquivo de mídia selecionado!")
            return

        if not TRANSCRICAO_DISPONIVEL:
            QMessageBox.warning(
                self, "Aviso", "Bibliotecas de transcrição não disponíveis!")
            return

        self.btn_transcrever.setEnabled(False)
        self.thread_transcricao = TranscricaoThread(self.arquivos_midia)
        self.thread_transcricao.progresso.connect(
            self.atualizar_progresso_transcricao)
        self.thread_transcricao.concluido.connect(self.transcricao_concluida)
        self.thread_transcricao.erro.connect(self.transcricao_erro)
        self.thread_transcricao.start()

    def atualizar_progresso(self, valor, mensagem):
        """Atualiza barra de progresso do ETL"""
        self.progress_bar.setValue(valor)
        self.label_status.setText(mensagem)
        self.log(mensagem)

    def atualizar_progresso_transcricao(self, valor, mensagem):
        """Atualiza barra de progresso da transcrição"""
        self.progress_bar_transcricao.setValue(valor)
        self.label_status_transcricao.setText(mensagem)
        self.log(mensagem)

    def processamento_concluido(self, metadata):
        """Callback quando processamento ETL termina"""
        self.processor = self.thread.processor
        self.btn_processar.setEnabled(True)

        msg = f"""✅ Processamento ETL concluído!

📊 Estatísticas:
- Arquivos processados: {len(metadata['arquivos_processados'])}
- Duplicatas removidas: {metadata['duplicatas_removidas']}
- Tabelas geradas: {len(self.processor.dataframes)}
        """

        self.log(msg)
        QMessageBox.information(self, "Sucesso", msg)

    def transcricao_concluida(self, resultados):
        """Callback quando transcrição termina"""
        self.resultados_transcricao = resultados
        self.btn_transcrever.setEnabled(True)

        # Atualiza tabela de resultados
        self.tabela_resultados.setRowCount(len(resultados))
        for i, resultado in enumerate(resultados):
            self.tabela_resultados.setItem(
                i, 0, QTableWidgetItem(resultado['arquivo']))
            self.tabela_resultados.setItem(
                i, 1, QTableWidgetItem(str(resultado['tamanho_arquivo'])))
            self.tabela_resultados.setItem(
                i, 2, QTableWidgetItem(resultado['texto_transcrito']))

        msg = f"✅ Transcrição concluída! {len(resultados)} arquivo(s) processado(s)"
        self.log(msg)
        QMessageBox.information(self, "Sucesso", msg)

    def processamento_erro(self, erro):
        """Callback quando ocorre erro no ETL"""
        self.btn_processar.setEnabled(True)
        self.log(f"❌ Erro no ETL: {erro}")
        QMessageBox.critical(
            self, "Erro", f"Erro no processamento ETL:\n{erro}")

    def transcricao_erro(self, erro):
        """Callback quando ocorre erro na transcrição"""
        self.btn_transcrever.setEnabled(True)
        self.log(f"❌ Erro na transcrição: {erro}")
        QMessageBox.critical(self, "Erro", f"Erro na transcrição:\n{erro}")

    def exportar_dados(self):
        """Exporta dados processados do ETL"""
        if not self.processor or not self.processor.dataframes:
            QMessageBox.warning(
                self, "Aviso", "Nenhum dado para exportar! Processe os arquivos primeiro.")
            return

        formato = self.combo_formato.currentText()

        if "Excel" in formato:
            caminho, _ = QFileDialog.getSaveFileName(
                self, "Salvar Excel", "", "Excel (*.xlsx)")
            if caminho:
                self.processor.exportar_excel(Path(caminho))
                self.log(f"✓ Dados exportados para {caminho}")
                QMessageBox.information(
                    self, "Sucesso", f"Dados exportados para:\n{caminho}")

        elif "SQLite" in formato:
            caminho, _ = QFileDialog.getSaveFileName(
                self, "Salvar SQLite", "", "SQLite (*.db)")
            if caminho:
                self.processor.exportar_sqlite(Path(caminho))
                self.log(f"✓ Dados exportados para {caminho}")
                QMessageBox.information(
                    self, "Sucesso", f"Banco de dados criado em:\n{caminho}")

        elif "SQL Script" in formato:
            caminho, _ = QFileDialog.getSaveFileName(
                self, "Salvar SQL", "", "SQL (*.sql)")
            if caminho:
                self.processor.exportar_sql_script(Path(caminho))
                self.log(f"✓ Script SQL exportado para {caminho}")
                QMessageBox.information(
                    self, "Sucesso", f"Script SQL criado em:\n{caminho}")

    def exportar_transcricoes(self):
        """Exporta resultados das transcrições"""
        if not self.resultados_transcricao:
            QMessageBox.warning(
                self, "Aviso", "Nenhuma transcrição para exportar!")
            return

        formato = self.combo_formato_transcricao.currentText()

        if "Texto" in formato:
            caminho, _ = QFileDialog.getSaveFileName(
                self, "Salvar Texto", "", "Texto (*.txt)")
            if caminho:
                with open(caminho, 'w', encoding='utf-8') as f:
                    for resultado in self.resultados_transcricao:
                        f.write(f"Arquivo: {resultado['arquivo']}\n")
                        f.write(
                            f"Tamanho: {resultado['tamanho_arquivo']} bytes\n")
                        f.write(
                            f"Transcrição: {resultado['texto_transcrito']}\n")
                        f.write("-" * 50 + "\n")
                self.log(f"✓ Transcrições exportadas para {caminho}")

        elif "JSON" in formato:
            caminho, _ = QFileDialog.getSaveFileName(
                self, "Salvar JSON", "", "JSON (*.json)")
            if caminho:
                with open(caminho, 'w', encoding='utf-8') as f:
                    json.dump(self.resultados_transcricao, f,
                              ensure_ascii=False, indent=2)
                self.log(f"✓ Transcrições exportadas para {caminho}")

        elif "Excel" in formato:
            caminho, _ = QFileDialog.getSaveFileName(
                self, "Salvar Excel", "", "Excel (*.xlsx)")
            if caminho:
                df = pd.DataFrame(self.resultados_transcricao)
                df.to_excel(caminho, index=False)
                self.log(f"✓ Transcrições exportadas para {caminho}")

        elif "CSV" in formato:
            caminho, _ = QFileDialog.getSaveFileName(
                self, "Salvar CSV", "", "CSV (*.csv)")
            if caminho:
                df = pd.DataFrame(self.resultados_transcricao)
                df.to_csv(caminho, index=False, encoding='utf-8')
                self.log(f"✓ Transcrições exportadas para {caminho}")

    def log(self, mensagem):
        """Adiciona mensagem ao log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_logs.append(f"[{timestamp}] {mensagem}")
        self.statusBar().showMessage(mensagem)

    def limpar_logs(self):
        """Limpa os logs"""
        self.text_logs.clear()
        self.log("Logs limpos")

    def aplicar_estilo(self):
        """Aplica estilo CSS"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #2196F3;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #2196F3;
            }
            QProgressBar {
                border: 2px solid #2196F3;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
            }
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
            QTabWidget::pane {
                border: 1px solid #C2C7CB;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #E1E1E1;
                border: 1px solid #C4C4C3;
                padding: 8px 20px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #2196F3;
                color: white;
            }
        """)

# ============================================================================
# MAIN
# ============================================================================


def main():
    """Função principal da aplicação"""
    app = QApplication(sys.argv)
    app.setApplicationName("Processador ETL Pro")
    app.setOrganizationName("ETL Solutions")
    app.setApplicationVersion("2.0.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

