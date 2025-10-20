# Guia de Contribuição

Obrigado por considerar contribuir com o Processador ETL Pro!

## Como Contribuir

### Reportando Bugs
1. Use o template de issue
2. Descreva o comportamento esperado vs atual
3. Inclua steps para reproduzir
4. Adicione screenshots se aplicável

### Sugerindo Melhorias
1. Explique a funcionalidade desejada
2. Descreva o caso de uso
3. Cite exemplos similares se existirem

### Submetendo Pull Requests
1. Fork o repositório
2. Crie uma branch descritiva
3. Siga as convenções de código
4. Adicione testes quando possível
5. Atualize a documentação

## Convenções de Código

### Python
- Use Black para formatação
- Siga PEP 8
- Documente funções com docstrings

### Commits
- Use mensagens descritivas em português ou inglês 
- Formato: `tipo(escopo): descrição`

### Testes
- Cubra novas funcionalidades
- Mantenha cobertura acima de 80%

## Desenvolvimento

### Configuração do Ambiente
```bash
git clone https://github.com/seu-usuario/processador-etl-pro.git
cd processador-etl-pro
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
pip install -r requirements.txt