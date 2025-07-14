"""
Módulo de normalização de texto com preservação de termos técnicos jurídicos.
"""

import re
import logging
from typing import List, Set, Dict, Any
from unicodedata import normalize

from .models import Segmento, ConfiguracaoProcessamento
from .utils import setup_logging

logger = setup_logging(__name__)


class NormalizadorTexto:
    """Classe responsável pela normalização de texto preservando valor jurídico."""
    
    def __init__(self, config: ConfiguracaoProcessamento):
        self.config = config
        self.termos_tecnicos = self._carregar_termos_tecnicos()
        self.padroes_preservacao = self._criar_padroes_preservacao()
        
    def _carregar_termos_tecnicos(self) -> Set[str]:
        """Carrega lista de termos técnicos para preservação."""
        return {
            # Termos de seguros
            "cobertura", "garantia", "sinistro", "indenização", "prêmio", "apólice",
            "segurado", "seguradora", "corretor", "beneficiário", "risco", "exclusão",
            "franquia", "limite", "vigência", "rescisão", "renovação", "endosso",
            "perícia", "avaliação", "liquidação", "pagamento", "reembolso",
            
            # Termos jurídicos
            "cláusula", "parágrafo", "inciso", "alínea", "artigo", "lei", "decreto",
            "contrato", "obrigação", "responsabilidade", "indenização", "compensação",
            "exclusão", "limitação", "renúncia", "arbitragem", "jurisdição", "foro",
            "competência", "aplicável", "vigente", "revogado", "suspenso",
            
            # Expressões específicas
            "condições gerais", "condições especiais", "cláusulas contratuais",
            "objeto do seguro", "riscos cobertos", "riscos excluídos",
            "obrigações do segurado", "obrigações da seguradora",
            "procedimento de sinistro", "pagamento de indenização",
            "limite de garantia", "franquia obrigatória", "período de vigência",
            "denúncia de contrato", "resolução contratual"
        }
    
    def _criar_padroes_preservacao(self) -> Dict[str, re.Pattern]:
        """Cria padrões regex para preservação de elementos específicos."""
        return {
            # Preservar numerações de cláusulas
            "clausula": re.compile(r'CLÁUSULA\s+\d+[ªº]?\s*[-–—]\s*', re.IGNORECASE),
            
            # Preservar numerações romanas
            "romanos": re.compile(r'\b[IVX]+\.\s+'),
            
            # Preservar numerações arábicas
            "arabicos": re.compile(r'\b\d+\.\s+'),
            
            # Preservar letras de alíneas
            "letras": re.compile(r'\b[a-z]\)\s+'),
            
            # Preservar maiúsculas de subseções
            "maiusculas": re.compile(r'\b[A-Z]\.\s+'),
            
            # Preservar percentuais
            "percentuais": re.compile(r'\b\d+%'),
            
            # Preservar valores monetários
            "monetarios": re.compile(r'R\$\s*\d+[.,]\d+'),
            
            # Preservar datas
            "datas": re.compile(r'\d{1,2}/\d{1,2}/\d{4}'),
            
            # Preservar CPF/CNPJ
            "documentos": re.compile(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}'),
        }
    
    def normalizar_segmentos(self, segmentos: List[Segmento]) -> List[Segmento]:
        """Normaliza uma lista de segmentos."""
        logger.info(f"Iniciando normalização de {len(segmentos)} segmentos")
        
        segmentos_normalizados = []
        
        for segmento in segmentos:
            texto_normalizado = self.normalizar_texto(segmento.texto)
            
            # Criar novo segmento com texto normalizado
            segmento_normalizado = Segmento(
                texto=texto_normalizado,
                pagina=segmento.pagina,
                posicao=segmento.posicao,
                tipo=segmento.tipo,
                contexto=segmento.contexto
            )
            
            segmentos_normalizados.append(segmento_normalizado)
        
        logger.info(f"Normalização concluída: {len(segmentos_normalizados)} segmentos processados")
        return segmentos_normalizados
    
    def normalizar_texto(self, texto: str) -> str:
        """Normaliza um texto preservando elementos importantes, removendo ruídos administrativos e títulos genéricos/rodapés de seguradoras."""
        if not texto:
            return texto
        # Normalizar unicode
        texto = normalize('NFKC', texto)
        # Corrigir hifenização e palavras quebradas por OCR
        texto = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', texto)
        texto = re.sub(r'(\w)[ \t]*\n[ \t]*([a-z])', r'\1 \2', texto)
        # Remover caracteres estranhos
        texto = re.sub(r'[^\w\s.,;:!?()\[\]{}"\'-]', '', texto)
        # Corrigir caracteres repetidos
        texto = re.sub(r'(\w)\1{2,}', r'\1', texto)
        # Remover expressões administrativas genéricas e rodapés/cabeçalhos de seguradoras
        texto = re.sub(r'\b(p[áa]gina\s*\d+\s*de\s*\d+|\d{2}[./]\d{2}[./]\d{4}|c[óo]digo\s*\w+|vers[ãa]o\s*\d+\.\d+\.\d+|cia\s*\d+\s*vers[ãa]o\s*\d+\s*de\s*\w+\s*de\s*\d{4}|tokio marine seguradora s|porto seguro|sul américa|bradesco seguros|itau seguros|allianz|zurich|mapfre|condições gerais|condições especiais|cláusulas contratuais|objeto do seguro|riscos cobertos|riscos excluídos|obrigações do segurado|obrigações da seguradora|procedimento de sinistro|pagamento de indenização|importante|atenção|nota|observação|aviso|dica|lembrete|alerta|cuidado|informação|resumo|exemplo|definição|glossário|anexo|apêndice|índice|sumário|introdução|conclusão|referência|bibliografia|autor|data|versão|empresa|companhia|seguradora)\b', '', texto, flags=re.IGNORECASE)
        # Preservar elementos importantes antes da limpeza
        elementos_preservados = self._preservar_elementos(texto)
        # Aplicar limpezas básicas
        texto = self._limpar_espacos(texto)
        texto = self._corrigir_hifenacao(texto)
        texto = self._corrigir_pontuacao(texto)
        texto = self._corrigir_quebras_linha(texto)
        # Restaurar elementos preservados
        texto = self._restaurar_elementos(texto, elementos_preservados)
        # Preservar termos técnicos
        texto = self._preservar_termos_tecnicos(texto)
        return texto.strip()
    
    def _preservar_elementos(self, texto: str) -> Dict[str, str]:
        """Preserva elementos importantes antes da limpeza."""
        elementos = {}
        
        for nome, padrao in self.padroes_preservacao.items():
            matches = padrao.findall(texto)
            for i, match in enumerate(matches):
                placeholder = f"__{nome.upper()}_{i}__"
                elementos[placeholder] = match
                texto = texto.replace(match, placeholder)
        
        return elementos
    
    def _restaurar_elementos(self, texto: str, elementos: Dict[str, str]) -> str:
        """Restaura elementos preservados após a limpeza."""
        for placeholder, elemento in elementos.items():
            texto = texto.replace(placeholder, elemento)
        
        return texto
    
    def _limpar_espacos(self, texto: str) -> str:
        """Remove espaços duplicados e normaliza espaçamento."""
        if not self.config.remover_espacos_duplicados:
            return texto
        
        # Remover espaços múltiplos
        texto = re.sub(r'\s+', ' ', texto)
        
        # Remover espaços no início e fim
        texto = texto.strip()
        
        # Normalizar espaços ao redor de pontuação
        texto = re.sub(r'\s*([.,;:!?])\s*', r'\1 ', texto)
        
        return texto
    
    def _corrigir_hifenacao(self, texto: str) -> str:
        """Corrige hifenização incorreta."""
        if not self.config.corrigir_hifenacao:
            return texto
        
        # Padrões comuns de hifenização incorreta
        correcoes = {
            r'(\w+)-\s*(\w+)': r'\1\2',  # Palavras quebradas
            r'(\w+)\s*-\s*(\w+)': r'\1-\2',  # Hífens mal espaçados
        }
        
        for padrao, substituicao in correcoes.items():
            texto = re.sub(padrao, substituicao, texto)
        
        return texto
    
    def _corrigir_pontuacao(self, texto: str) -> str:
        """Corrige problemas de pontuação."""
        # Remover pontuação duplicada
        texto = re.sub(r'([.,;:!?])\1+', r'\1', texto)
        
        # Corrigir espaços antes de pontuação
        texto = re.sub(r'\s+([.,;:!?])', r'\1', texto)
        
        # Corrigir múltiplos pontos
        texto = re.sub(r'\.{2,}', '...', texto)
        
        return texto
    
    def _corrigir_quebras_linha(self, texto: str) -> str:
        """Corrige quebras de linha incorretas."""
        if not self.config.detectar_quebras_linha:
            return texto
        
        # Detectar quebras de linha no meio de frases
        # Padrão: palavra seguida de quebra de linha seguida de palavra minúscula
        texto = re.sub(r'(\w+)\s*\n\s*([a-z])', r'\1 \2', texto)
        
        # Detectar quebras de linha antes de pontuação
        texto = re.sub(r'\s*\n\s*([.,;:!?])', r'\1', texto)
        
        # Normalizar quebras de linha múltiplas
        texto = re.sub(r'\n\s*\n+', '\n\n', texto)
        
        return texto
    
    def _preservar_termos_tecnicos(self, texto: str) -> str:
        """Preserva termos técnicos durante a normalização."""
        if not self.config.preservar_termos_tecnicos:
            return texto
        
        # Para cada termo técnico, garantir que não seja alterado
        for termo in self.termos_tecnicos:
            # Criar padrão que preserva o termo exato
            padrao = re.compile(rf'\b{re.escape(termo)}\b', re.IGNORECASE)
            
            def preservar_termo(match):
                return match.group(0)  # Retorna o termo exato como encontrado
            
            texto = padrao.sub(preservar_termo, texto)
        
        return texto
    
    def detectar_anomalias(self, texto: str) -> List[Dict[str, Any]]:
        """Detecta anomalias no texto que podem indicar problemas de OCR."""
        anomalias = []
        
        # Detectar caracteres estranhos
        caracteres_estranhos = re.findall(r'[^\w\s\.,;:!?()\[\]{}"\'-]', texto)
        if caracteres_estranhos:
            anomalias.append({
                "tipo": "caracteres_estranhos",
                "descricao": f"Caracteres não reconhecidos: {set(caracteres_estranhos)}",
                "severidade": "media"
            })
        
        # Detectar palavras com caracteres repetidos
        palavras_repetidas = re.findall(r'\b(\w*(\w)\2{2,}\w*)\b', texto)
        if palavras_repetidas:
            anomalias.append({
                "tipo": "caracteres_repetidos",
                "descricao": f"Palavras com caracteres repetidos: {[p[0] for p in palavras_repetidas[:5]]}",
                "severidade": "baixa"
            })
        
        # Detectar frases muito longas
        frases = re.split(r'[.!?]', texto)
        frases_longas = [f.strip() for f in frases if len(f.strip()) > 200]
        if frases_longas:
            anomalias.append({
                "tipo": "frases_longas",
                "descricao": f"Frases muito longas detectadas: {len(frases_longas)}",
                "severidade": "baixa"
            })
        
        return anomalias
    
    def validar_normalizacao(self, texto_original: str, texto_normalizado: str) -> Dict[str, Any]:
        """Valida se a normalização preservou o conteúdo importante e estrutura."""
        validacao = {
            "preservou_estrutura": True,
            "preservou_termos_tecnicos": True,
            "anomalias": [],
            "score_preservacao": 1.0
        }
        # Verificar se termos técnicos foram preservados
        termos_originais = self._extrair_termos_tecnicos(texto_original)
        termos_normalizados = self._extrair_termos_tecnicos(texto_normalizado)
        if termos_originais != termos_normalizados:
            validacao["preservou_termos_tecnicos"] = False
            validacao["anomalias"].append("Termos técnicos alterados durante normalização")
        # Verificar se estrutura foi preservada
        estrutura_original = self._extrair_estrutura(texto_original)
        estrutura_normalizada = self._extrair_estrutura(texto_normalizado)
        if estrutura_original != estrutura_normalizada:
            validacao["preservou_estrutura"] = False
            validacao["anomalias"].append("Estrutura do documento alterada")
        # Calcular score de preservação
        score = self._calcular_score_preservacao(texto_original, texto_normalizado)
        validacao["score_preservacao"] = score
        # Alertar se score for baixo
        if score < 0.85:
            validacao["anomalias"].append("Score de preservação baixo: possível perda de conteúdo relevante")
        return validacao
    
    def _extrair_termos_tecnicos(self, texto: str) -> Set[str]:
        """Extrai termos técnicos de um texto."""
        termos_encontrados = set()
        texto_lower = texto.lower()
        
        for termo in self.termos_tecnicos:
            if termo.lower() in texto_lower:
                # Encontrar a forma exata como aparece no texto
                padrao = re.compile(rf'\b{re.escape(termo)}\b', re.IGNORECASE)
                matches = padrao.findall(texto)
                termos_encontrados.update(matches)
        
        return termos_encontrados
    
    def _extrair_estrutura(self, texto: str) -> Dict[str, int]:
        """Extrai elementos estruturais do texto."""
        estrutura = {
            "clausulas": len(re.findall(r'CLÁUSULA\s+\d+', texto, re.IGNORECASE)),
            "paragrafos": len(re.findall(r'§\s*\d+', texto)),
            "incisos": len(re.findall(r'\b[IVX]+\.\s+', texto)),
            "alíneas": len(re.findall(r'\b[a-z]\)\s+', texto)),
        }
        return estrutura
    
    def _calcular_score_preservacao(self, texto_original: str, texto_normalizado: str) -> float:
        """Calcula um score de preservação do conteúdo."""
        # Implementação simplificada - em produção seria mais sofisticada
        palavras_originais = set(re.findall(r'\b\w+\b', texto_original.lower()))
        palavras_normalizadas = set(re.findall(r'\b\w+\b', texto_normalizado.lower()))
        
        if not palavras_originais:
            return 1.0
        
        palavras_preservadas = palavras_originais.intersection(palavras_normalizadas)
        score = len(palavras_preservadas) / len(palavras_originais)
        
        return min(score, 1.0) 