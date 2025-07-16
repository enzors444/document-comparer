"""
Módulo de comparação entre documentos com detecção inteligente de alterações.
Foca em resolver problemas de alinhamento incorreto, falsos positivos e segmentação inadequada.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from difflib import SequenceMatcher
from rapidfuzz.fuzz import ratio as levenshtein_ratio
from collections import defaultdict
from sentence_transformers import SentenceTransformer, util
from functools import lru_cache
import difflib
import spacy
from spacy.language import Language
import concurrent.futures

from .models import (
    Documento, Segmento, ComparacaoSegmento, ResultadoComparacao,
    TipoDiferenca, SignificanciaJuridica, ConfiguracaoProcessamento
)

logger = logging.getLogger(__name__)


class Comparador:
    """Classe responsável pela comparação entre documentos."""
    
    def __init__(self, config: ConfiguracaoProcessamento):
        self.config = config
        self.termos_significativos = self._carregar_termos_significativos()
        self.padroes_significativos = self._criar_padroes_significativos()
        self.padroes_irrelevantes = self._criar_padroes_irrelevantes()
        self.categorias_documento = self._criar_categorias_documento()
        # Troque para um modelo menor e mais rápido, se desejar
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.spacy_nlp = spacy.load('pt_core_news_sm')
        self._adicionar_regra_segmentacao_frase(self.spacy_nlp)
        # Inicializar o pipeline do Stanza apenas uma vez
        import stanza
        self.stanza_nlp = stanza.Pipeline('pt', processors='tokenize', tokenize_no_ssplit=False)
        
    def _carregar_termos_significativos(self) -> set:
        """Carrega termos que indicam alterações juridicamente significativas."""
        return {
            # Termos que alteram obrigações
            "obrigação", "responsabilidade", "dever", "compromisso", "obrigatório",
            "facultativo", "opcional", "permitido", "proibido", "vedado",
            
            # Termos que alteram coberturas
            "cobertura", "garantia", "risco", "sinistro", "indenização",
            "limite", "franquia", "exclusão", "inclusão", "ampliação",
            
            # Termos que alteram valores
            "valor", "percentual", "montante", "quantia", "preço",
            "aumento", "redução", "ajuste", "reajuste", "correção",
            
            # Termos que alteram prazos
            "prazo", "vigência", "duração", "período", "data",
            "vencimento", "prorrogação", "renovação", "rescisão",
            
            # Termos que alteram procedimentos
            "procedimento", "processo", "método", "forma", "meio",
            "documentação", "comprovante", "declaração", "notificação"
        }
    
    def _criar_padroes_significativos(self) -> Dict[str, re.Pattern]:
        """Cria padrões regex para detectar alterações significativas."""
        return {
            # Alterações de valores monetários
            "valor_monetario": re.compile(r'R\$\s*\d+[.,]\d+'),
            
            # Alterações de percentuais
            "percentual": re.compile(r'\b\d+%'),
            
            # Alterações de prazos
            "prazo": re.compile(r'\b\d+\s*(dias?|meses?|anos?)\b'),
            
            # Alterações de responsabilidades
            "responsabilidade": re.compile(r'\b(obrigação|responsabilidade|dever)\b', re.IGNORECASE),
            
            # Alterações de exclusões
            "exclusao": re.compile(r'\b(exclusão|não\s+cobre|não\s+garante)\b', re.IGNORECASE),
            
            # Alterações de coberturas
            "cobertura": re.compile(r'\b(cobertura|garantia|proteção)\b', re.IGNORECASE),
        }
    
    def _criar_padroes_irrelevantes(self) -> Dict[str, re.Pattern]:
        """Cria padrões regex para detectar diferenças irrelevantes."""
        return {
            # Datas de versão
            "data_versao": re.compile(r'\b\d{2}[./]\d{2}[./]\d{4}\b'),
            
            # Versões de software
            "versao_software": re.compile(r'versão\s+\d+\.\d+\.\d+', re.IGNORECASE),
            
            # Números de página
            "numero_pagina": re.compile(r'\bPágina\s+\d+\b'),
            "pagina_de": re.compile(r'página\s+\d+\s+de\s+\d+', re.IGNORECASE),
            
            # Códigos de documento
            "codigo_documento": re.compile(r'\b\d{3}_\d{3}\b'),
            
            # Timestamps e datas de geração
            "timestamp": re.compile(r'\d{2}:\d{2}:\d{2}'),
            "data_geracao": re.compile(r'gerado\s+em\s+\d{2}[./]\d{2}[./]\d{4}', re.IGNORECASE),
            
            # Espaços em branco
            "espacos_branco": re.compile(r'\s+'),
            
            # Pontuação
            "pontuacao": re.compile(r'[.,;:!?]'),
            
            # Pequenas variações numéricas
            "numero_pequeno": re.compile(r'\b\d{1,2}\b'),
        }
    
    def _criar_categorias_documento(self) -> Dict[str, re.Pattern]:
        """Cria padrões para identificar categorias de conteúdo."""
        return {
            "titulo_principal": re.compile(r'^[IVX]+\.?\s*[-–—]?\s*[A-Z\s]+$', re.IGNORECASE),
            "subtitulo": re.compile(r'^\d+\.\s*[A-Z\s]+$', re.IGNORECASE),
            "clausula": re.compile(r'^CLÁUSULA\s+\d+[ªº]?\s*[-–—]', re.IGNORECASE),
            "item_lista": re.compile(r'^\d+\.\s*'),
            "definicao": re.compile(r'^\d+\.\s*[A-Z][^.]*:'),
            "exclusao": re.compile(r'^\d+\.\s*[A-Z][^.]*[Nn]ão\s+cobre'),
        }
    
    def comparar_documentos(self, doc1: Documento, doc2: Documento) -> ResultadoComparacao:
        """Compara dois documentos com alinhamento inteligente e validação cruzada."""
        logger.info(f"Iniciando comparação entre {doc1.nome_arquivo} e {doc2.nome_arquivo}")
        # Pré-processar segmentos (normalização + segmentação extra)
        segmentos1_processados = self._pre_processar_segmentos(doc1.segmentos)
        segmentos2_processados = self._pre_processar_segmentos(doc2.segmentos)
        # Alinhar segmentos com algoritmo inteligente
        segmentos_alinhados = self._alinhar_segmentos_inteligente(segmentos1_processados, segmentos2_processados)
        # Comparar cada par de segmentos
        comparacoes = []
        for seg1, seg2 in segmentos_alinhados:
            comparacao = self._comparar_segmentos(seg1, seg2)
            if comparacao:
                comparacoes.append(comparacao)
        # Calcular estatísticas
        estatisticas = self._calcular_estatisticas_aprimoradas(comparacoes)
        # Validação cruzada: sugerir ajuste se muitos removidos/adicionados
        num_removidos = sum(1 for c in comparacoes if c.tipo_diferenca == TipoDiferenca.REMOVIDO)
        num_adicionados = sum(1 for c in comparacoes if c.tipo_diferenca == TipoDiferenca.ADICIONADO)
        total = len(comparacoes)
        if total > 0 and (num_removidos + num_adicionados) / total > 0.5:
            logger.warning("Muitos segmentos removidos/adicionados: possível problema de segmentação/normalização. Considere ajustar parâmetros.")
        # Criar resultado
        resultado = ResultadoComparacao(
            documento1=doc1,
            documento2=doc2,
            comparacoes=comparacoes,
            estatisticas=estatisticas
        )
        logger.info(f"Comparação concluída: {len(comparacoes)} comparações válidas")
        return resultado
    
    def _pre_processar_segmentos(self, segmentos: List[Segmento]) -> List[Segmento]:
        """Pré-processa segmentos para melhor alinhamento (segmentação frase a frase + normalização)."""
        processados = []
        # Agrupar blocos curtos e segmentar em frases (usando texto original)
        segmentos_agrupados = self._agrupar_blocos_curtos(segmentos)
        for segmento in segmentos_agrupados:
            # Normalizar texto APÓS segmentação
            texto_normalizado = self._normalizar_texto(segmento.texto)
            tipo_conteudo = self._classificar_tipo_conteudo(texto_normalizado)
            segmento_processado = Segmento(
                texto=texto_normalizado,
                pagina=segmento.pagina,
                posicao=segmento.posicao,
                tipo=tipo_conteudo,
                contexto=segmento.contexto
            )
            processados.append(segmento_processado)
        return processados

    def _agrupar_blocos_curtos(self, segmentos: List[Segmento]) -> List[Segmento]:
        """Quebra segmentos em frases individuais com contexto enriquecido, paralelizando processamento."""
        if not segmentos:
            return segmentos
        frases_processadas = []
        # Encontrar títulos/cláusulas para contexto
        titulos = []
        for i, segmento in enumerate(segmentos):
            texto = segmento.texto.strip()
            tipo_atual = self._classificar_tipo_conteudo(texto)
            if tipo_atual in ["titulo_principal", "subtitulo", "clausula"]:
                titulos.append((i, texto))
        def processar_segmento(idx_segmento):
            segmento = segmentos[idx_segmento]
            texto = segmento.texto.strip()
            tipo_atual = self._classificar_tipo_conteudo(texto)
            if tipo_atual in ["titulo_principal", "subtitulo", "clausula"]:
                return [segmento]
            frases = self._quebrar_em_frases(texto)
            # Enriquecer contexto com título/cláusula mais próxima
            contexto_extra = ""
            titulos_anteriores = [t for i, t in titulos if i <= idx_segmento]
            if titulos_anteriores:
                contexto_extra = f"Título/Cláusula: {titulos_anteriores[-1]}"
            resultado = []
            for i, frase in enumerate(frases):
                if not frase.strip():
                    continue
                contexto = self._criar_contexto_frase(frases, i, segmento)
                if contexto_extra:
                    contexto = contexto_extra + " | " + contexto
                segmento_frase = Segmento(
                    texto=frase.strip(),
                    pagina=segmento.pagina,
                    posicao=segmento.posicao + i,
                    tipo="frase",
                    contexto=contexto
                )
                resultado.append(segmento_frase)
            return resultado
        # Paralelizar processamento dos segmentos
        with concurrent.futures.ThreadPoolExecutor() as executor:
            resultados = list(executor.map(processar_segmento, range(len(segmentos))))
        for lista in resultados:
            frases_processadas.extend(lista)
        return frases_processadas
    
    def _quebrar_em_frases(self, texto: str) -> List[str]:
        """Segmenta o texto em frases usando Stanza (português), filtra ruídos, divide listas técnicas e loga descartes."""
        import re
        import logging
        nlp = self.stanza_nlp
        doc = nlp(texto)
        frases = [sent.text for sent in doc.sentences]  # type: ignore
        frases_filtradas = []
        logger = logging.getLogger(__name__)
        for frase in frases:
            f = frase.strip()
            # 1. Remover datas, páginas e metadados do início/fim
            f = re.sub(r'^(\d{2} de [a-zç]+ de \d{4}(?: \d+)?|\d{2}/\d{2}/\d{4}|\d{1,2} de [A-Z][a-z]+ de \d{4}|\d{1,2}/\d{1,2}/\d{2,4}|p[áa]gina\s*\d+|\d{1,2}h\d{2}|\d{2}:\d{2}:\d{2}|\d+)$', '', f, flags=re.IGNORECASE).strip()
            f = re.sub(r'^(\d{2} de [a-zç]+ de \d{4}(?: \d+)?|\d{2}/\d{2}/\d{4}|\d{1,2} de [A-Z][a-z]+ de \d{4}|\d{1,2}/\d{1,2}/\d{2,4}|p[áa]gina\s*\d+|\d{1,2}h\d{2}|\d{2}:\d{2}:\d{2}|\d+)[\s\-:]+', '', f, flags=re.IGNORECASE).strip()
            f = re.sub(r'[\-:]+$', '', f).strip()
            # 2. Se sobrou só metadado, descartar
            if not f or re.fullmatch(r'(\d{2} de [a-zç]+ de \d{4}|\d{2}/\d{2}/\d{4}|\d+|p[áa]gina\s*\d+)', f, flags=re.IGNORECASE):
                logger.debug(f"Descartada (metadado): {frase}")
                continue
            # 3. Filtro para frases curtas (mínimo 4 palavras)
            if len(f.split()) < 4:
                logger.debug(f"Descartada (curta): {f}")
                continue
            if not re.search(r'[a-zA-Záéíóúãõâêîôûç]', f):
                logger.debug(f"Descartada (sem letras): {f}")
                continue
            # 4. Filtrar ruídos (datas, códigos, números)
            padroes_ruido = [
                r'^\d+$', r'^\d{2}[./]\d{2}[./]\d{4}$', r'^p[áa]gina\s*\d+$', r'^c[óo]digo\s*\w+$',
                r'^vers[ãa]o\s*\d+\.\d+\.\d+$', r'^\d{2}:\d{2}:\d{2}$', r'^número\s*\d+$', r'^data\s*\d+$'
            ]
            if any(re.match(p, f, re.IGNORECASE) for p in padroes_ruido):
                logger.debug(f"Descartada (ruído): {f}")
                continue
            # 5. Pós-processamento para listas técnicas (ex: "a) ... b) ...")
            itens = re.split(r'(?<=\))\s+(?=[a-zA-Z]\))', f)
            for item in itens:
                item = item.strip()
                if item:
                    frases_filtradas.append(item)
        return frases_filtradas
    
    def _criar_contexto_frase(self, frases: List[str], indice_atual: int, segmento_original: Segmento) -> str:
        """Cria contexto para uma frase específica."""
        contexto = []
        
        # Adicionar frase anterior (se existir)
        if indice_atual > 0:
            frase_anterior = frases[indice_atual - 1]
            if len(frase_anterior) > 10:  # Só adicionar se for significativa
                contexto.append(f"Anterior: {frase_anterior[:50]}...")
        
        # Adicionar frase posterior (se existir)
        if indice_atual < len(frases) - 1:
            frase_posterior = frases[indice_atual + 1]
            if len(frase_posterior) > 10:  # Só adicionar se for significativa
                contexto.append(f"Posterior: {frase_posterior[:50]}...")
        
        # Adicionar informações do segmento original
        contexto.append(f"Página: {segmento_original.pagina}")
        contexto.append(f"Posição: {segmento_original.posicao}")
        
        return " | ".join(contexto) if contexto else "Sem contexto adicional"
    
    def _normalizar_texto(self, texto: str) -> str:
        """Normalização robusta: remove rodapés/cabeçalhos, corrige pontuação, espaços, aspas, hífens, une linhas, protege abreviações, limpa caracteres estranhos, separa palavras coladas e padroniza o texto."""
        import re
        # 1. Remover rodapés/cabeçalhos/metadados
        padroes_remover = [
            r'\b(p[áa]gina\s*\d+\s*de\s*\d+|p[áa]gina\s*\d+|\d{2}[./]\d{2}[./]\d{4}|c[óo]digo\s*\w+|vers[ãa]o\s*\d+\.\d+\.\d+|cia\s*\d+|seguradora|apólice|contrato|número\s*\d+|data\s*\d+|\d{1,2}/\d{1,2}/\d{2,4}|\d{2}:\d{2}:\d{2})\b',
            r'^\s*\d+\s*$',  # linhas só com número
            r'^\s*[A-Z][a-z]+\s*$',  # linhas só com nome próprio
        ]
        for padrao in padroes_remover:
            texto = re.sub(padrao, '', texto, flags=re.IGNORECASE|re.MULTILINE)
        # 2. Corrigir pontuação duplicada
        texto = re.sub(r'([.!?,;:])\1+', r'\1', texto)
        # 3. Corrigir espaços antes/depois de pontuação
        texto = re.sub(r'\s*([.!?,;:])\s*', r'\1 ', texto)
        # 4. Corrigir palavras coladas (letra minúscula seguida de maiúscula)
        texto = re.sub(r'([a-záéíóúãõâêîôûç])([A-ZÁÉÍÓÚÃÕÂÊÎÔÛÇ])', r'\1 \2', texto)
        # 4b. Corrigir palavras coladas (número seguido de letra)
        texto = re.sub(r'(\d)([A-Za-z])', r'\1 \2', texto)
        texto = re.sub(r'([A-Za-z])(\d)', r'\1 \2', texto)
        # 4c. Corrigir palavras coladas por ausência de espaço entre palavras comuns (heurística)
        texto = re.sub(r'(obrigação)legal(do)segurado', r'obrigação legal do segurado', texto, flags=re.IGNORECASE)
        texto = re.sub(r'(falta)de(s)averacidade', r'falta de essa veracidade', texto, flags=re.IGNORECASE)
        # 5. Padronizar aspas e hífens
        texto = texto.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
        texto = texto.replace('–', '-').replace('—', '-')
        # 6. Remover caracteres estranhos
        texto = re.sub(r'[^\w\s.,;:!?"\'-]', '', texto)
        # 7. Unir linhas quebradas no meio da frase
        texto = re.sub(r'(?<![.!?])\n', ' ', texto)
        # 8. Corrigir abreviações (proteger para segmentação)
        abrevs = ['ex.', 'dr.', 'sra.', 'sr.', 'etc.', 'prof.', 'fig.', 'pág.', 'obs.']
        for ab in abrevs:
            texto = texto.replace(ab, ab.replace('.', '<PONTO>'))
        # 9. Remover espaços duplos
        texto = re.sub(r'\s+', ' ', texto)
        # 10. Restaurar abreviações
        texto = texto.replace('<PONTO>', '.')
        # 11. Remover espaços no início/fim
        texto = texto.strip()
        return texto
    
    def _classificar_tipo_conteudo(self, texto: str) -> str:
        """Classifica o tipo de conteúdo do segmento."""
        for nome_categoria, padrao in self.categorias_documento.items():
            if padrao.match(texto):
                return nome_categoria
        
        # Verificar se é um título principal (numeração romana + texto)
        if re.match(r'^[IVX]+\.?\s*[-–—]?\s*[A-Z\s]+$', texto, re.IGNORECASE):
            return "titulo_principal"
        
        # Verificar se é um subtítulo (numeração + texto)
        if re.match(r'^\d+\.\s*[A-Z\s]+$', texto, re.IGNORECASE):
            return "subtitulo"
        
        # Verificar se é uma cláusula
        if re.match(r'^CLÁUSULA\s+\d+[ªº]?\s*[-–—]', texto, re.IGNORECASE):
            return "clausula"
        
        # Verificar se é um título simples
        if texto.isupper() and len(texto.split()) <= 5:
            return "titulo"
        
        # Verificar se é uma definição
        if ':' in texto and len(texto.split()) <= 10:
            return "definicao"
        
        return "conteudo"
    
    def _alinhar_segmentos_inteligente(self, segmentos1: List[Segmento], segmentos2: List[Segmento]) -> List[Tuple[Optional[Segmento], Optional[Segmento]]]:
        """Alinha globalmente as frases dos dois documentos usando difflib, ignorando contexto, para maximizar matches reais."""
        alinhamentos = []
        # Normalização máxima para comparação
        def normalizar(texto):
            import unicodedata
            texto = str(texto).lower()
            texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
            texto = re.sub(r'\W+', '', texto)
            return texto
        seq1 = [normalizar(seg.texto) for seg in segmentos1]
        seq2 = [normalizar(seg.texto) for seg in segmentos2]
        sm = difflib.SequenceMatcher(None, seq1, seq2, autojunk=False)
        opcodes = sm.get_opcodes()
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                for k in range(i2 - i1):
                    alinhamentos.append((segmentos1[i1 + k], segmentos2[j1 + k]))
            elif tag == 'replace':
                maxlen = max(i2 - i1, j2 - j1)
                for k in range(maxlen):
                    s1 = segmentos1[i1 + k] if i1 + k < i2 else None
                    s2 = segmentos2[j1 + k] if j1 + k < j2 else None
                    alinhamentos.append((s1, s2))
            elif tag == 'delete':
                for k in range(i1, i2):
                    alinhamentos.append((segmentos1[k], None))
            elif tag == 'insert':
                for k in range(j1, j2):
                    alinhamentos.append((None, segmentos2[k]))
        return alinhamentos
    
    @lru_cache(maxsize=2048)
    def _embedding_cached(self, texto: str):
        return self.embedding_model.encode(texto, convert_to_tensor=True)
    
    def _calcular_similaridade(self, texto1: str, texto2: str) -> float:
        """Calcula similaridade entre dois textos usando Levenshtein e embeddings."""
        if not texto1 or not texto2:
            return 0.0
        # Similaridade textual (Levenshtein)
        sim_textual = levenshtein_ratio(texto1.lower(), texto2.lower()) / 100
        # Similaridade semântica (embeddings) com cache
        emb1 = self._embedding_cached(texto1)
        emb2 = self._embedding_cached(texto2)
        sim_semantica = float(util.pytorch_cos_sim(emb1, emb2).item())
        # Retornar o maior valor, priorizando semântica se for alta
        if sim_semantica > 0.85:
            return max(sim_textual, sim_semantica)
        return sim_textual
    
    def _criar_indices_por_tipo(self, segmentos: List[Segmento]) -> Dict[str, List[Segmento]]:
        """Cria índices de segmentos organizados por tipo."""
        indices = defaultdict(list)
        for segmento in segmentos:
            indices[segmento.tipo].append(segmento)
        return dict(indices)
    
    def _alinhar_por_tipo(self, segs1: List[Segmento], segs2: List[Segmento], 
                          tipo: str) -> List[Tuple[Optional[Segmento], Optional[Segmento]]]:
        """Alinha segmentos do mesmo tipo."""
        alinhamentos = []
        i, j = 0, 0
        
        while i < len(segs1) or j < len(segs2):
            seg1 = segs1[i] if i < len(segs1) else None
            seg2 = segs2[j] if j < len(segs2) else None
            
            if seg1 and seg2:
                # Calcular similaridade considerando o tipo
                similaridade = self._calcular_similaridade_por_tipo(seg1, seg2, tipo)
                
                if similaridade >= self.config.threshold_similaridade:
                    alinhamentos.append((seg1, seg2))
                    i += 1
                    j += 1
                else:
                    # Verificar se são categorias distintas
                    if self._sao_categorias_distintas(seg1.texto, seg2.texto):
                        alinhamentos.append((seg1, None))  # Removido
                        alinhamentos.append((None, seg2))  # Adicionado
                        i += 1
                        j += 1
                    else:
                        # Lookahead para encontrar melhor match
                        melhor_match = self._encontrar_melhor_match(seg1, segs2[j:j+3], tipo)
                        if melhor_match:
                            alinhamentos.append((seg1, melhor_match))
                            i += 1
                            j += segs2[j:j+3].index(melhor_match) + 1
                        else:
                            alinhamentos.append((seg1, None))
                            i += 1
            elif seg1:
                alinhamentos.append((seg1, None))
                i += 1
            elif seg2:
                alinhamentos.append((None, seg2))
                j += 1
        
        return alinhamentos
    
    def _calcular_similaridade_por_tipo(self, seg1: Segmento, seg2: Segmento, tipo: str) -> float:
        """Calcula similaridade considerando o tipo de conteúdo."""
        texto1 = seg1.texto
        texto2 = seg2.texto
        
        # Similaridade básica
        similaridade_basica = levenshtein_ratio(texto1, texto2) / 100
        
        # Ajustes baseados no tipo
        if tipo in ["titulo_principal", "subtitulo", "clausula"]:
            # Para títulos, ser mais rigoroso
            if similaridade_basica < 0.9:
                return 0.0
            # Verificar se são realmente o mesmo tipo de estrutura
            if not self._mesma_estrutura_titulo(texto1, texto2):
                return 0.0
        
        elif tipo == "frase":
            # Para frases, ser mais rigoroso mas considerar contexto
            if similaridade_basica > 0.8:
                return similaridade_basica
            elif similaridade_basica > 0.6:
                # Verificar se as diferenças são irrelevantes
                if self._diferencas_sao_irrelevantes(texto1, texto2):
                    return 0.9
            return similaridade_basica
        
        elif tipo == "conteudo":
            # Para conteúdo, permitir mais variação
            if similaridade_basica > 0.6:
                # Verificar se as diferenças são irrelevantes
                if self._diferencas_sao_irrelevantes(texto1, texto2):
                    return 0.95
                
                # Para conteúdo longo, ser mais tolerante
                if len(texto1) > 100 and len(texto2) > 100:
                    if similaridade_basica > 0.5:
                        return min(similaridade_basica + 0.1, 1.0)  # Boost para conteúdo longo, limitado a 1.0
        
        return similaridade_basica
    
    def _mesma_estrutura_titulo(self, texto1: str, texto2: str) -> bool:
        """Verifica se dois títulos têm a mesma estrutura."""
        # Extrair números de seção
        num1 = re.search(r'^([IVX]+)\.?', texto1)
        num2 = re.search(r'^([IVX]+)\.?', texto2)
        
        if num1 and num2:
            return num1.group(1) == num2.group(1)
        
        # Extrair números de cláusula
        claus1 = re.search(r'CLÁUSULA\s+(\d+)', texto1)
        claus2 = re.search(r'CLÁUSULA\s+(\d+)', texto2)
        
        if claus1 and claus2:
            return claus1.group(1) == claus2.group(1)
        
        return False
    
    def _diferencas_sao_irrelevantes(self, texto1: str, texto2: str) -> bool:
        """Detecta diferenças irrelevantes ampliando padrões administrativos e de formatação."""
        # Ignorar datas, números de página, códigos, versões, pontuação, espaços, pequenas variações numéricas
        padroes_irrelevantes = [
            r'\b(p[áa]gina\s*\d+\s*de\s*\d+|\d{2}[./]\d{2}[./]\d{4}|c[óo]digo\s*\w+|vers[ãa]o\s*\d+\.\d+\.\d+)\b',
            r'\bP\d+\b',
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            r'\b\d{2}:\d{2}:\d{2}\b',
            r'\s+',
            r'[.,;:!?]',
            r'\b\d{1,2}\b'
        ]
        t1 = texto1
        t2 = texto2
        for padrao in padroes_irrelevantes:
            t1 = re.sub(padrao, '', t1, flags=re.IGNORECASE)
            t2 = re.sub(padrao, '', t2, flags=re.IGNORECASE)
        return t1.strip() == t2.strip()
    
    def _diferenca_eh_irrelevante(self, diff1: str, diff2: str) -> bool:
        """Verifica se uma diferença específica é irrelevante."""
        # Verificar padrões irrelevantes
        for nome, padrao in self.padroes_irrelevantes.items():
            if padrao.search(diff1) or padrao.search(diff2):
                return True
        
        # Verificar se são apenas espaços ou pontuação
        if re.sub(r'\s+', '', diff1) == re.sub(r'\s+', '', diff2):
            return True
        
        # Verificar se são variações de data
        if self._sao_variacoes_data(diff1, diff2):
            return True
        
        return False
    
    def _sao_variacoes_data(self, diff1: str, diff2: str) -> bool:
        """Verifica se as diferenças são apenas variações de data."""
        # Padrões de data
        padroes_data = [
            r'\d{2}[./]\d{2}[./]\d{4}',
            r'\d{2}/\d{2}/\d{4}',
            r'\d{2}\.\d{2}\.\d{4}'
        ]
        
        for padrao in padroes_data:
            if re.search(padrao, diff1) and re.search(padrao, diff2):
                return True
        
        return False
    
    def _sao_categorias_distintas(self, texto1: str, texto2: str) -> bool:
        """Verifica se dois textos são categorias distintas que não devem ser comparadas."""
        # Verificar se um é título e outro é conteúdo
        tipo1 = self._classificar_tipo_conteudo(texto1)
        tipo2 = self._classificar_tipo_conteudo(texto2)
        
        if tipo1 != tipo2:
            return True
        
        # Verificar se são estruturas completamente diferentes
        if self._estruturas_diferentes(texto1, texto2):
            return True
        
        return False
    
    def _estruturas_diferentes(self, texto1: str, texto2: str) -> bool:
        """Verifica se dois textos têm estruturas completamente diferentes."""
        # Um é numeração, outro é texto
        if re.match(r'^\d+\.', texto1) and not re.match(r'^\d+\.', texto2):
            return True
        
        # Um é cláusula, outro não
        if 'CLÁUSULA' in texto1.upper() and 'CLÁUSULA' not in texto2.upper():
            return True
        
        # Um é título principal, outro é subtítulo
        if re.match(r'^[IVX]+\.?', texto1) and not re.match(r'^[IVX]+\.?', texto2):
            return True
        
        # Verificar se são categorias completamente diferentes
        tipo1 = self._classificar_tipo_conteudo(texto1)
        tipo2 = self._classificar_tipo_conteudo(texto2)
        
        # Se são tipos diferentes, são estruturas diferentes
        if tipo1 != tipo2:
            return True
        
        # Verificar se são itens de lista diferentes
        if re.match(r'^\d+\.', texto1) and re.match(r'^\d+\.', texto2):
            num1 = re.match(r'^(\d+)\.', texto1)
            num2 = re.match(r'^(\d+)\.', texto2)
            if num1 and num2 and num1.group(1) != num2.group(1):
                return True
        
        return False
    
    def _encontrar_melhor_match(self, segmento: Segmento, candidatos: List[Segmento], 
                               tipo: str) -> Optional[Segmento]:
        """Encontra o melhor match para um segmento entre candidatos."""
        melhor_similaridade = 0.0
        melhor_match = None
        
        for candidato in candidatos:
            similaridade = self._calcular_similaridade_por_tipo(segmento, candidato, tipo)
            if similaridade > melhor_similaridade:
                melhor_similaridade = similaridade
                melhor_match = candidato
        
        if melhor_similaridade >= self.config.threshold_similaridade:
            return melhor_match
        
        return None
    
    def _comparar_segmentos(self, seg1: Optional[Segmento], 
                                      seg2: Optional[Segmento]) -> Optional[ComparacaoSegmento]:
        """Compara dois segmentos com detecção avançada."""
        if seg1 is None and seg2 is None:
            return None
        
        if seg1 is None and seg2 is not None:
            # Segmento adicionado
            if self._segmento_eh_irrelevante(seg2):
                return None
            
            return ComparacaoSegmento(
                segmento_pdf1=None,
                segmento_pdf2=seg2,
                tipo_diferenca=TipoDiferenca.ADICIONADO,
                significativo=self._avaliar_significancia_adicao(seg2),
                significancia_juridica=self._classificar_significancia_adicao(seg2),
                confianca=1.0,
                detalhes="Segmento adicionado no documento 2"
            )
        
        if seg2 is None and seg1 is not None:
            # Segmento removido
            if self._segmento_eh_irrelevante(seg1):
                return None
            
            return ComparacaoSegmento(
                segmento_pdf1=seg1,
                segmento_pdf2=None,
                tipo_diferenca=TipoDiferenca.REMOVIDO,
                significativo=self._avaliar_significancia_remocao(seg1),
                significancia_juridica=self._classificar_significancia_remocao(seg1),
                confianca=1.0,
                detalhes="Segmento removido do documento 1"
            )
        
        # Ambos segmentos existem - comparar
        if seg1 is not None and seg2 is not None:
            similaridade = self._calcular_similaridade_por_tipo(seg1, seg2, seg1.tipo)
            
            if similaridade >= 0.95:
                # Praticamente idênticos
                return ComparacaoSegmento(
                    segmento_pdf1=seg1,
                    segmento_pdf2=seg2,
                    tipo_diferenca=TipoDiferenca.SEM_DIFERENCA,
                    significativo=False,
                    significancia_juridica=SignificanciaJuridica.NENHUMA,
                    confianca=min(similaridade, 1.0),
                    detalhes="Segmentos praticamente idênticos"
                )
            else:
                # Verificar se as diferenças são significativas
                if self._diferencas_sao_significativas(seg1.texto, seg2.texto):
                                    return ComparacaoSegmento(
                    segmento_pdf1=seg1,
                    segmento_pdf2=seg2,
                    tipo_diferenca=TipoDiferenca.MODIFICADO,
                    significativo=True,
                    significancia_juridica=self._classificar_significancia_modificacao(seg1, seg2),
                    confianca=min(similaridade, 1.0),
                    detalhes=self._gerar_detalhes_modificacao(seg1, seg2)
                )
                else:
                    # Diferenças irrelevantes
                    return None
        
        return None
    
    def _segmento_eh_irrelevante(self, segmento: Segmento) -> bool:
        """Verifica se um segmento é irrelevante para a comparação."""
        texto = segmento.texto.lower()
        
        # Segmentos muito curtos
        if len(texto.strip()) < 10:
            return True
        
        # Apenas espaços ou pontuação
        if re.sub(r'\s+', '', texto) == '':
            return True
        
        # Números de página
        if re.match(r'^\d+$', texto.strip()):
            return True
        
        return False
    
    def _diferencas_sao_significativas(self, texto1: str, texto2: str) -> bool:
        """Verifica se as diferenças entre textos são juridicamente significativas."""
        # Detectar diferenças específicas
        matcher = SequenceMatcher(None, texto1, texto2)
        diferencas = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                diff1 = texto1[i1:i2]
                diff2 = texto2[j1:j2]
                diferencas.append((diff1, diff2))
        
        # Verificar se alguma diferença é significativa
        for diff1, diff2 in diferencas:
            if self._diferenca_eh_significativa(diff1, diff2):
                return True
        
        return False
    
    def _diferenca_eh_significativa(self, diff1: str, diff2: str) -> bool:
        """Verifica se uma diferença específica é juridicamente significativa."""
        # Verificar termos significativos
        for termo in self.termos_significativos:
            if termo in diff1.lower() or termo in diff2.lower():
                return True
        
        # Verificar padrões significativos
        for nome, padrao in self.padroes_significativos.items():
            if padrao.search(diff1) or padrao.search(diff2):
                return True
        
        return False
    
    def _avaliar_significancia_adicao(self, segmento: Segmento) -> bool:
        """Avalia se uma adição é juridicamente significativa."""
        if not self.config.detectar_significancia:
            return True
        
        texto = segmento.texto.lower()
        
        # Verificar se contém termos significativos
        for termo in self.termos_significativos:
            if termo in texto:
                return True
        
        # Verificar padrões significativos
        for nome, padrao in self.padroes_significativos.items():
            if padrao.search(texto):
                return True
        
        return False
    
    def _avaliar_significancia_remocao(self, segmento: Segmento) -> bool:
        """Avalia se uma remoção é juridicamente significativa."""
        if not self.config.detectar_significancia:
            return True
        
        texto = segmento.texto.lower()
        
        # Verificar se contém termos significativos
        for termo in self.termos_significativos:
            if termo in texto:
                return True
        
        # Verificar padrões significativos
        for nome, padrao in self.padroes_significativos.items():
            if padrao.search(texto):
                return True
        
        return False
    
    def _classificar_significancia_adicao(self, segmento: Segmento) -> SignificanciaJuridica:
        """Classifica a significância de uma adição."""
        if not self._avaliar_significancia_adicao(segmento):
            return SignificanciaJuridica.BAIXA
        
        texto = segmento.texto.lower()
        
        if any(termo in texto for termo in ["obrigação", "responsabilidade", "dever"]):
            return SignificanciaJuridica.ALTA
        elif any(termo in texto for termo in ["cobertura", "garantia", "exclusão"]):
            return SignificanciaJuridica.ALTA
        elif any(termo in texto for termo in ["valor", "percentual", "montante"]):
            return SignificanciaJuridica.MEDIA
        else:
            return SignificanciaJuridica.BAIXA
    
    def _classificar_significancia_remocao(self, segmento: Segmento) -> SignificanciaJuridica:
        """Classifica a significância de uma remoção."""
        if not self._avaliar_significancia_remocao(segmento):
            return SignificanciaJuridica.BAIXA
        
        texto = segmento.texto.lower()
        
        if any(termo in texto for termo in ["obrigação", "responsabilidade", "dever"]):
            return SignificanciaJuridica.ALTA
        elif any(termo in texto for termo in ["cobertura", "garantia", "exclusão"]):
            return SignificanciaJuridica.ALTA
        elif any(termo in texto for termo in ["valor", "percentual", "montante"]):
            return SignificanciaJuridica.MEDIA
        else:
            return SignificanciaJuridica.BAIXA
    
    def _classificar_significancia_modificacao(self, seg1: Segmento, seg2: Segmento) -> SignificanciaJuridica:
        """Classifica a significância de uma modificação."""
        if not self._diferencas_sao_significativas(seg1.texto, seg2.texto):
            return SignificanciaJuridica.BAIXA
        
        # Análise das diferenças específicas
        matcher = SequenceMatcher(None, seg1.texto.lower(), seg2.texto.lower())
        diferencas = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                diff1 = seg1.texto[i1:i2]
                diff2 = seg2.texto[j1:j2]
                diferencas.append((diff1, diff2))
        
        alta_count = 0
        media_count = 0
        
        for diff1, diff2 in diferencas:
            if any(termo in diff1.lower() or termo in diff2.lower() 
                   for termo in ["obrigação", "responsabilidade", "dever"]):
                alta_count += 1
            elif any(termo in diff1.lower() or termo in diff2.lower() 
                     for termo in ["cobertura", "garantia", "exclusão"]):
                alta_count += 1
            elif any(termo in diff1.lower() or termo in diff2.lower() 
                     for termo in ["valor", "percentual", "montante"]):
                media_count += 1
        
        if alta_count > 0:
            return SignificanciaJuridica.ALTA
        elif media_count > 0:
            return SignificanciaJuridica.MEDIA
        else:
            return SignificanciaJuridica.BAIXA
    
    def _gerar_detalhes_modificacao(self, seg1: Segmento, seg2: Segmento) -> str:
        """Gera detalhes sobre a modificação entre dois segmentos."""
        matcher = SequenceMatcher(None, seg1.texto, seg2.texto)
        diferencas = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                diff1 = seg1.texto[i1:i2]
                diff2 = seg2.texto[j1:j2]
                diferencas.append(f"{diff1} -> {diff2}")
            elif tag == 'delete':
                diff = seg1.texto[i1:i2]
                diferencas.append(f"removido: {diff}")
            elif tag == 'insert':
                diff = seg2.texto[j1:j2]
                diferencas.append(f"adicionado: {diff}")
        
        if len(diferencas) <= 3:
            return f"Modificações: {'; '.join(diferencas)}"
        else:
            return f"Modificações: {len(diferencas)} alterações detectadas"
    
    def _calcular_estatisticas_aprimoradas(self, comparacoes: List[ComparacaoSegmento]) -> Dict[str, Any]:
        """Calcula estatísticas aprimoradas da comparação."""
        total = len(comparacoes)
        if total == 0:
            return {}
        
        # Contadores por tipo
        contadores_tipo = {}
        contadores_significancia = {}
        significativos = 0
        
        for comp in comparacoes:
            # Contar por tipo
            tipo = comp.tipo_diferenca.value
            contadores_tipo[tipo] = contadores_tipo.get(tipo, 0) + 1
            
            # Contar por significância
            if comp.significativo:
                significativos += 1
                sig = comp.significancia_juridica.value
                contadores_significancia[sig] = contadores_significancia.get(sig, 0) + 1
        
        # Calcular percentuais
        estatisticas = {
            "total_comparacoes": total,
            "contadores_tipo": contadores_tipo,
            "percentuais_tipo": {
                tipo: (count / total) * 100 
                for tipo, count in contadores_tipo.items()
            },
            "significativos": significativos,
            "percentual_significativos": (significativos / total) * 100 if total > 0 else 0,
            "contadores_significancia": contadores_significancia,
            "percentuais_significancia": {
                sig: (count / significativos) * 100 
                for sig, count in contadores_significancia.items()
            } if significativos > 0 else {}
        }
        
        return estatisticas 

    @staticmethod
    def _adicionar_regra_segmentacao_frase(nlp: Language):
        # Força quebra de frase após ponto, exclamação ou interrogação, mesmo sem maiúscula
        from spacy.tokens import Doc
        @Language.component('custom_sentencizer')
        def custom_seg(doc: Doc):
            for i, token in enumerate(doc[:-1]):
                if token.text in {'.', '!', '?'}:
                    doc[i+1].is_sent_start = True
            return doc 