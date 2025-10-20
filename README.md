# 🚀 Processador ETL Pro com Transcrição de Mídia

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Qt](https://img.shields.io/badge/Qt-6.0%2B-orange.svg)](https://qt.io)

Uma aplicação desktop profissional para processamento ETL (Extract, Transform, Load) com funcionalidades avançadas de transcrição de áudio e vídeo.

## ✨ Características Principais

### 🔄 Processamento ETL Avançado
- **Suporte múltiplos formatos**: CSV, Excel (XLSX/XLS), JSON
- **Conversão inteligente de tipos**: Detecção automática de datas, números, textos
- **Limpeza de dados**: Normalização de texto, remoção de duplicatas
- **Análise de qualidade**: Relatórios detalhados de completude e estatísticas

### 🎤 Transcrição de Mídia
- **Áudio**: MP3, WAV, FLAC, M4A
- **Vídeo**: MP4, AVI, MOV, MKV
- **Reconhecimento de voz**: Integração com Google Speech Recognition
- **Processamento em lote**: Múltiplos arquivos simultaneamente

### 💾 Exportação Flexível
- **Excel**: Planilhas com múltiplas abas e análise
- **SQLite**: Banco de dados relacional completo
- **SQL Script**: Scripts de criação para MySQL/PostgreSQL
- **CSV/JSON**: Formatos abertos e interoperáveis

## 🛠️ Instalação Rápida

### Pré-requisitos
- Python 3.8 ou superior
- FFmpeg (para processamento de mídia)

### Instalação via pip
```bash
# Clone o repositório
git clone https://github.com/RafaCodeRJ/Processador_ETL_Pro.git
cd processador-etl-pro

# Instale as dependências
pip install -r requirements.txt

# Execute a aplicação
python src/etl_processor.py
Aplicação que transforma dados não estruturados em estruturados, agiliza o processo ETL, retirando acentuação, removendo duplicatas e criando tabelas.
