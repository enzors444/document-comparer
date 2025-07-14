# Sistema de Comparação de Documentos Jurídicos Contratuais

Sistema robusto e escalável para extração, normalização e comparação de documentos jurídicos contratuais, especialmente Condições Gerais de Seguros.

## 🎯 Objetivos

- **Extração estruturada** de conteúdo de PDFs com preservação de formatação
- **Normalização precisa** do texto sem perder valor jurídico
- **Segmentação inteligente** frase a frase com contexto completo
- **Comparação entre versões** com identificação de alterações significativas
- **Detecção de significância jurídica** das modificações

## 🏗️ Arquitetura

O sistema segue princípios SOLID e clean code, com módulos especializados:

```
src/
├── models.py          # Modelos de dados (Pydantic)
├── extrator.py        # Extração de PDFs
├── normalizador.py    # Normalização de texto
├── comparador.py      # Comparação entre documentos
├── processador.py     # Orquestração do processo
└── utils.py          # Utilitários e logging
```

## 📋 Funcionalidades

### 🔍 Extração
- Preserva parágrafos, títulos, alíneas e formatações
- Detecta e reconstrói texto fragmentado
- Identifica estrutura de cláusulas e seções
- Extrai metadados automáticos

### 🧼 Normalização
- Corrige hifens e quebras de palavras
- Remove espaços extras e erros de OCR
- Preserva termos técnicos e expressões jurídicas
- Mantém pontuação e estrutura original

### ✂️ Segmentação
- Divide conteúdo em unidades lógicas
- Mantém contexto mínimo necessário
- Agrupa por cláusulas e dependências
- Evita frases soltas ou incompletas

### 🔁 Comparação
- Classifica diferenças: sem_diferenca, modificado, adicionado, removido
- Avalia significância jurídica das alterações
- Gera estatísticas detalhadas
- Produz relatórios estruturados

## 🚀 Instalação

1. **Clone o repositório:**
```bash
git clone <repository-url>
cd comparer
```

2. **Instale as dependências:**
```bash
pip install -r requirements.txt
```

3. **Verifique a instalação:**
```bash
python main.py --help
```

## 📖 Uso

### Comparação de Dois Documentos

```bash
python main.py \
  --pdf1 arquivos/condicoes_gerais_000_005_06112024_16052025.pdf \
  --pdf2 arquivos/CG_07.06.2025.pdf \
  --saida resultados/comparacao/
```

### Processamento em Lote

```bash
python main.py \
  --lote arquivos/ \
  --saida resultados/lote/
```

### Análise de Documento Único

```bash
python main.py \
  --analisar arquivos/condicoes_gerais_000_005_06112024_16052025.pdf \
  --saida analise/documento/
```

### Configurações Avançadas

```bash
python main.py \
  --pdf1 doc1.pdf --pdf2 doc2.pdf \
  --threshold 0.85 \
  --min-segmento 15 \
  --detectar-significancia \
  --preservar-termos \
  --saida resultados/
```

## 📊 Saídas

### Estrutura de Resultados

```
resultados/
├── resultado_comparacao.json    # Dados estruturados
├── relatorio_comparacao.txt     # Relatório textual
└── logs/                       # Logs detalhados
```

### Formato JSON de Saída

```json
{
  "documento1": {
    "nome_arquivo": "condicoes_gerais_000_005_06112024_16052025.pdf",
    "seguradora": "Detectada automaticamente",
    "ramo_seguro": "Automóvel",
    "segmentos": [...]
  },
  "documento2": {...},
  "comparacoes": [
    {
      "segmento_pdf1": {...},
      "segmento_pdf2": {...},
      "tipo_diferenca": "modificado",
      "significativo": true,
      "significancia_juridica": "alta",
      "confianca": 0.85,
      "detalhes": "Modificações: cobertura -> garantia"
    }
  ],
  "estatisticas": {
    "total_comparacoes": 150,
    "significativos": 12,
    "percentual_significativos": 8.0,
    "contadores_tipo": {...},
    "percentuais_tipo": {...}
  }
}
```

## ⚙️ Configurações

### Parâmetros Principais

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `threshold_similaridade` | 0.8 | Threshold para considerar segmentos similares |
| `tamanho_minimo_segmento` | 10 | Tamanho mínimo de caracteres por segmento |
| `detectar_significancia` | True | Detectar significância jurídica |
| `preservar_termos_tecnicos` | True | Preservar termos técnicos na normalização |

### Termos Técnicos Preservados

O sistema preserva automaticamente termos como:
- **Seguros**: cobertura, garantia, sinistro, indenização, prêmio, apólice
- **Jurídicos**: cláusula, parágrafo, obrigação, responsabilidade, exclusão
- **Expressões**: condições gerais, objeto do seguro, riscos cobertos

## 🔧 Desenvolvimento

### Estrutura do Projeto

```
comparer/
├── src/                    # Código fonte
│   ├── __init__.py
│   ├── models.py
│   ├── extrator.py
│   ├── normalizador.py
│   ├── comparador.py
│   ├── processador.py
│   └── utils.py
├── arquivos/              # Documentos de exemplo
├── resultados/            # Saídas geradas
├── main.py               # Script principal
├── requirements.txt      # Dependências
└── README.md            # Documentação
```

### Executando Testes

```bash
# Instalar dependências de desenvolvimento
pip install pytest pytest-cov

# Executar testes
pytest tests/ -v --cov=src
```

### Formatação de Código

```bash
# Instalar ferramentas de desenvolvimento
pip install black flake8 mypy

# Formatar código
black src/ main.py

# Verificar estilo
flake8 src/ main.py

# Verificar tipos
mypy src/ main.py
```

## 📈 Métricas e Logs

### Logs Estruturados

O sistema utiliza `structlog` para logs estruturados em JSON:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info",
  "logger": "src.processador",
  "event": "Iniciando processamento de documentos",
  "pdf1": "doc1.pdf",
  "pdf2": "doc2.pdf"
}
```

### Métricas de Performance

- Tempo de processamento por documento
- Número de segmentos extraídos
- Taxa de similaridade média
- Percentual de alterações significativas

## 🎯 Casos de Uso

### 1. Comparação de Versões
Comparar versões diferentes do mesmo documento para identificar mudanças:

```bash
python main.py \
  --pdf1 versao_2024.pdf \
  --pdf2 versao_2025.pdf \
  --saida comparacao_versoes/
```

### 2. Análise de Conformidade
Verificar se documentos seguem padrões específicos:

```bash
python main.py \
  --analisar documento.pdf \
  --saida analise_conformidade/
```

### 3. Processamento em Lote
Analisar múltiplos documentos de uma seguradora:

```bash
python main.py \
  --lote documentos_seguradora/ \
  --saida analise_lote/
```

## 🔍 Detecção de Significância

O sistema classifica alterações em três níveis:

### 🔴 Alta Significância
- Alterações em obrigações e responsabilidades
- Modificações em coberturas e exclusões
- Mudanças em valores monetários e percentuais

### 🟡 Média Significância
- Alterações em procedimentos
- Modificações em prazos e vigência
- Mudanças em documentação necessária

### 🟢 Baixa Significância
- Correções ortográficas
- Reformulações sem mudança de sentido
- Ajustes de formatação

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para detalhes.

## 📞 Suporte

Para dúvidas ou suporte:
- Abra uma issue no GitHub
- Consulte a documentação
- Entre em contato com a equipe de desenvolvimento

---

**Desenvolvido com ❤️ para análise jurídica precisa e eficiente.** 