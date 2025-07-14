"""
Utilitários para o sistema de comparação de documentos jurídicos.
"""

import logging
import structlog
from typing import Dict, Any
from pathlib import Path
import json
from datetime import datetime


def setup_logging(module_name: str) -> logging.Logger:
    """Configura logging estruturado para o módulo."""
    # Configurar structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger(module_name)


def salvar_resultado_json(resultado: Dict[str, Any], caminho_saida: str) -> None:
    """Salva resultado da comparação em formato JSON."""
    try:
        with open(caminho_saida, 'w', encoding='utf-8') as arquivo:
            json.dump(resultado, arquivo, ensure_ascii=False, indent=2, default=str)
        print(f"Resultado salvo em: {caminho_saida}")
    except Exception as e:
        print(f"Erro ao salvar resultado: {e}")


def carregar_configuracao(caminho_config: str) -> Dict[str, Any]:
    """Carrega configuração de um arquivo JSON."""
    try:
        with open(caminho_config, 'r', encoding='utf-8') as arquivo:
            return json.load(arquivo)
    except FileNotFoundError:
        print(f"Arquivo de configuração não encontrado: {caminho_config}")
        return {}
    except Exception as e:
        print(f"Erro ao carregar configuração: {e}")
        return {}


def validar_arquivo_pdf(caminho_pdf: str) -> bool:
    """Valida se o arquivo é um PDF válido."""
    if not Path(caminho_pdf).exists():
        print(f"Arquivo não encontrado: {caminho_pdf}")
        return False
    
    if not caminho_pdf.lower().endswith('.pdf'):
        print(f"Arquivo não é um PDF: {caminho_pdf}")
        return False
    
    # Verificar tamanho mínimo
    tamanho = Path(caminho_pdf).stat().st_size
    if tamanho < 1024:  # Menos de 1KB
        print(f"Arquivo muito pequeno: {caminho_pdf}")
        return False
    
    return True


def formatar_tamanho_arquivo(bytes_size: int) -> str:
    """Formata tamanho de arquivo em formato legível."""
    size = float(bytes_size)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def calcular_metricas_documento(segmentos: list) -> Dict[str, Any]:
    """Calcula métricas básicas de um documento."""
    if not segmentos:
        return {}
    
    total_segmentos = len(segmentos)
    total_caracteres = sum(len(seg.texto) for seg in segmentos)
    total_palavras = sum(len(seg.texto.split()) for seg in segmentos)
    
    # Calcular estatísticas por tipo
    tipos = {}
    for seg in segmentos:
        tipo = seg.tipo
        if tipo not in tipos:
            tipos[tipo] = 0
        tipos[tipo] += 1
    
    return {
        "total_segmentos": total_segmentos,
        "total_caracteres": total_caracteres,
        "total_palavras": total_palavras,
        "media_caracteres_por_segmento": total_caracteres / total_segmentos if total_segmentos > 0 else 0,
        "media_palavras_por_segmento": total_palavras / total_segmentos if total_segmentos > 0 else 0,
        "distribuicao_tipos": tipos
    }


def gerar_relatorio_comparacao(resultado: Dict[str, Any]) -> str:
    """Gera um relatório textual da comparação."""
    if not resultado:
        return "Nenhum resultado disponível."
    
    relatorio = []
    relatorio.append("=" * 60)
    relatorio.append("RELATÓRIO DE COMPARAÇÃO DE DOCUMENTOS")
    relatorio.append("=" * 60)
    relatorio.append("")
    
    # Informações dos documentos
    doc1 = resultado.get("documento1", {})
    doc2 = resultado.get("documento2", {})
    
    relatorio.append("DOCUMENTOS COMPARADOS:")
    relatorio.append(f"  Documento 1: {doc1.get('nome_arquivo', 'N/A')}")
    relatorio.append(f"  Documento 2: {doc2.get('nome_arquivo', 'N/A')}")
    relatorio.append("")
    
    # Estatísticas
    estatisticas = resultado.get("estatisticas", {})
    if estatisticas:
        relatorio.append("ESTATÍSTICAS DA COMPARAÇÃO:")
        relatorio.append(f"  Total de comparações: {estatisticas.get('total_comparacoes', 0)}")
        relatorio.append(f"  Alterações significativas: {estatisticas.get('significativos', 0)}")
        
        percentual_sig = estatisticas.get("percentual_significativos", 0)
        relatorio.append(f"  Percentual de alterações significativas: {percentual_sig:.1f}%")
        relatorio.append("")
        
        # Detalhar por tipo
        contadores_tipo = estatisticas.get("contadores_tipo", {})
        if contadores_tipo:
            relatorio.append("DISTRIBUIÇÃO POR TIPO:")
            for tipo, count in contadores_tipo.items():
                percentual = estatisticas.get("percentuais_tipo", {}).get(tipo, 0)
                relatorio.append(f"  {tipo}: {count} ({percentual:.1f}%)")
            relatorio.append("")
    
    # Resumo das alterações significativas
    comparacoes = resultado.get("comparacoes", [])
    alteracoes_significativas = [c for c in comparacoes if c.get("significativo", False)]
    
    if alteracoes_significativas:
        relatorio.append("ALTERAÇÕES SIGNIFICATIVAS DETECTADAS:")
        for i, comp in enumerate(alteracoes_significativas[:10], 1):  # Limitar a 10
            tipo = comp.get("tipo_diferenca", "N/A")
            significancia = comp.get("significancia_juridica", "N/A")
            detalhes = comp.get("detalhes", "N/A")
            
            relatorio.append(f"  {i}. Tipo: {tipo} | Significância: {significancia}")
            relatorio.append(f"     Detalhes: {detalhes}")
            relatorio.append("")
    
    relatorio.append("=" * 60)
    relatorio.append(f"Relatório gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    return "\n".join(relatorio)


def criar_diretorio_saida(caminho_base: str) -> Path:
    """Cria diretório de saída se não existir."""
    diretorio = Path(caminho_base)
    diretorio.mkdir(parents=True, exist_ok=True)
    return diretorio 