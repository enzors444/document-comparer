"""
Módulo principal que orquestra o processamento completo de documentos.
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from dataclasses import asdict

from .models import ConfiguracaoProcessamento, Documento, ResultadoComparacao
from .extrator import ExtratorPDF
from .normalizador import NormalizadorTexto
from .comparador import Comparador
from .utils import setup_logging, salvar_resultado_json, validar_arquivo_pdf, gerar_relatorio_comparacao

logger = setup_logging(__name__)


class ProcessadorDocumentos:
    """Classe principal que orquestra todo o processamento de documentos."""
    
    def __init__(self, config: ConfiguracaoProcessamento):
        self.config = config
        self.extrator = ExtratorPDF(config)
        self.normalizador = NormalizadorTexto(config)
        self.comparador = Comparador(config)
        
    def processar_documentos(self, caminho_pdf1: str, caminho_pdf2: str, 
                           caminho_saida: Optional[str] = None) -> ResultadoComparacao:
        """Processa dois documentos PDF e retorna a comparação."""
        logger.info("Iniciando processamento de documentos")
        
        # Validar arquivos
        if not self._validar_arquivos(caminho_pdf1, caminho_pdf2):
            raise ValueError("Arquivos inválidos fornecidos")
        
        # Extrair documentos
        logger.info("Extraindo documentos...")
        doc1 = self.extrator.extrair_documento(caminho_pdf1)
        doc2 = self.extrator.extrair_documento(caminho_pdf2)
        
        # Normalizar documentos
        logger.info("Normalizando documentos...")
        doc1.segmentos = self.normalizador.normalizar_segmentos(doc1.segmentos)
        doc2.segmentos = self.normalizador.normalizar_segmentos(doc2.segmentos)
        
        # Comparar documentos
        logger.info("Comparando documentos...")
        resultado = self.comparador.comparar_documentos(doc1, doc2)
        
        # Salvar resultado se caminho fornecido
        if caminho_saida:
            self._salvar_resultados(resultado, caminho_saida)
        
        logger.info("Processamento concluído com sucesso")
        return resultado
    
    def _validar_arquivos(self, caminho_pdf1: str, caminho_pdf2: str) -> bool:
        """Valida os arquivos PDF fornecidos."""
        if not validar_arquivo_pdf(caminho_pdf1):
            logger.error(f"Arquivo 1 inválido: {caminho_pdf1}")
            return False
        
        if not validar_arquivo_pdf(caminho_pdf2):
            logger.error(f"Arquivo 2 inválido: {caminho_pdf2}")
            return False
        
        return True
    
    def _salvar_resultados(self, resultado: ResultadoComparacao, caminho_base: str):
        """Salva os resultados da comparação."""
        try:
            # Criar diretório de saída
            diretorio_saida = Path(caminho_base)
            diretorio_saida.mkdir(parents=True, exist_ok=True)
            
            # Salvar resultado JSON
            caminho_json = diretorio_saida / "resultado_comparacao.json"
            resultado_dict = asdict(resultado)
            salvar_resultado_json(resultado_dict, str(caminho_json))
            
            # Gerar e salvar relatório textual
            relatorio = gerar_relatorio_comparacao(resultado_dict)
            caminho_relatorio = diretorio_saida / "relatorio_comparacao.txt"
            with open(caminho_relatorio, 'w', encoding='utf-8') as f:
                f.write(relatorio)
            
            logger.info(f"Resultados salvos em: {diretorio_saida}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar resultados: {e}")
    
    def processar_lote(self, diretorio_entrada: str, diretorio_saida: str) -> List[ResultadoComparacao]:
        """Processa um lote de documentos em um diretório."""
        logger.info(f"Processando lote de documentos em: {diretorio_entrada}")
        
        diretorio = Path(diretorio_entrada)
        arquivos_pdf = list(diretorio.glob("*.pdf"))
        
        if len(arquivos_pdf) < 2:
            logger.error("Pelo menos 2 arquivos PDF são necessários para comparação")
            return []
        
        resultados = []
        
        # Comparar cada par de arquivos
        for i in range(len(arquivos_pdf)):
            for j in range(i + 1, len(arquivos_pdf)):
                try:
                    pdf1 = arquivos_pdf[i]
                    pdf2 = arquivos_pdf[j]
                    
                    logger.info(f"Comparando {pdf1.name} com {pdf2.name}")
                    
                    # Criar diretório específico para esta comparação
                    nome_comparacao = f"{pdf1.stem}_vs_{pdf2.stem}"
                    caminho_saida_especifico = Path(diretorio_saida) / nome_comparacao
                    
                    resultado = self.processar_documentos(
                        str(pdf1), 
                        str(pdf2), 
                        str(caminho_saida_especifico)
                    )
                    
                    resultados.append(resultado)
                    
                except Exception as e:
                    logger.error(f"Erro ao processar {pdf1.name} vs {pdf2.name}: {e}")
                    continue
        
        logger.info(f"Processamento de lote concluído: {len(resultados)} comparações realizadas")
        return resultados 