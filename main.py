#!/usr/bin/env python3
"""
Script principal para o sistema de comparação de documentos jurídicos.
"""

import argparse
import sys
from pathlib import Path

from src.models import ConfiguracaoProcessamento
from src.processador import ProcessadorDocumentos
from src.utils import setup_logging

logger = setup_logging(__name__)


def main():
    """Função principal do script."""
    parser = argparse.ArgumentParser(
        description="Sistema de Comparação de Documentos Jurídicos Contratuais",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python main.py --pdf1 arquivos/doc1.pdf --pdf2 arquivos/doc2.pdf --saida resultados/
  python main.py --lote arquivos/ --saida resultados/
  python main.py --analisar arquivos/doc.pdf --saida analise/
        """
    )
    
    # Argumentos principais
    parser.add_argument(
        "--pdf1", 
        help="Caminho para o primeiro PDF"
    )
    parser.add_argument(
        "--pdf2", 
        help="Caminho para o segundo PDF"
    )
    parser.add_argument(
        "--lote", 
        help="Diretório com PDFs para processamento em lote"
    )
    parser.add_argument(
        "--analisar", 
        help="Caminho para PDF único para análise"
    )
    parser.add_argument(
        "--saida", 
        default="resultados/",
        help="Diretório de saída (padrão: resultados/)"
    )
    
    # Argumentos de configuração
    parser.add_argument(
        "--threshold", 
        type=float, 
        default=0.8,
        help="Threshold de similaridade (0.0-1.0, padrão: 0.8)"
    )
    parser.add_argument(
        "--min-segmento", 
        type=int, 
        default=10,
        help="Tamanho mínimo de segmento (padrão: 10)"
    )
    parser.add_argument(
        "--detectar-significancia", 
        action="store_true",
        default=True,
        help="Detectar significância jurídica (padrão: True)"
    )
    parser.add_argument(
        "--preservar-termos", 
        action="store_true",
        default=True,
        help="Preservar termos técnicos (padrão: True)"
    )
    
    args = parser.parse_args()
    
    # Validar argumentos
    if not any([args.pdf1, args.pdf2, args.lote, args.analisar]):
        print("❌ Erro: É necessário especificar pelo menos um modo de operação")
        print("Use --help para ver as opções disponíveis")
        sys.exit(1)
    
    # Criar configuração
    config = ConfiguracaoProcessamento(
        threshold_similaridade=args.threshold,
        tamanho_minimo_segmento=args.min_segmento,
        detectar_significancia=args.detectar_significancia,
        preservar_termos_tecnicos=args.preservar_termos
    )
    
    # Criar processador
    processador = ProcessadorDocumentos(config)
    
    try:
        if args.analisar:
            # Modo análise única
            print(f"📄 Analisando documento único: {args.analisar}")
            
            documento = processador.analisar_documento_unico(
                args.analisar, 
                args.saida
            )
            
            print(f"✅ Análise concluída com sucesso!")
            print(f"   Documento: {documento.nome_arquivo}")
            print(f"   Segmentos encontrados: {len(documento.segmentos)}")
            print(f"   Resultados salvos em: {args.saida}")
            
        elif args.lote:
            # Modo lote
            print(f"📄 Processando lote de documentos em: {args.lote}")
            
            resultados = processador.processar_lote(args.lote, args.saida)
            
            print(f"✅ Processamento de lote concluído!")
            print(f"   Comparações realizadas: {len(resultados)}")
            print(f"   Resultados salvos em: {args.saida}")
            
        elif args.pdf1 and args.pdf2:
            # Modo comparação
            print(f"📄 Comparando documentos:")
            print(f"   Documento 1: {args.pdf1}")
            print(f"   Documento 2: {args.pdf2}")
            
            resultado = processador.processar_documentos(
                args.pdf1, 
                args.pdf2, 
                args.saida
            )
            
            # Exibir estatísticas
            estatisticas = resultado.estatisticas
            total_comparacoes = estatisticas.get("total_comparacoes", 0)
            significativos = estatisticas.get("significativos", 0)
            percentual_sig = estatisticas.get("percentual_significativos", 0)
            
            print(f"✅ Comparação concluída com sucesso!")
            print(f"   Total de comparações: {total_comparacoes}")
            print(f"   Alterações significativas: {significativos} ({percentual_sig:.1f}%)")
            print(f"   Resultados salvos em: {args.saida}")
            
            # Exibir detalhes das alterações significativas
            if significativos > 0:
                alteracoes_sig = [c for c in resultado.comparacoes if c.significativo]
                print(f"\n🔍 Principais alterações significativas:")
                
                for i, comp in enumerate(alteracoes_sig[:5], 1):
                    tipo = comp.tipo_diferenca.value
                    sig = comp.significancia_juridica.value
                    detalhes = comp.detalhes or "N/A"
                    
                    print(f"   {i}. [{tipo.upper()}] {sig.upper()}: {detalhes}")
                
                if len(alteracoes_sig) > 5:
                    print(f"   ... e mais {len(alteracoes_sig) - 5} alterações")
        
    except Exception as e:
        print(f"❌ Erro durante o processamento: {str(e)}")
        logger.error(f"Erro durante o processamento: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 