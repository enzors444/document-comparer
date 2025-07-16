from flask import Flask, request, jsonify, send_file
from pathlib import Path
import shutil
import uuid
import os
import json
from dataclasses import asdict
import logging
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

from src.processador import ProcessadorDocumentos
from src.models import ConfiguracaoProcessamento

UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("resultados/api")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
RESULTS_DIR.mkdir(exist_ok=True, parents=True)

app = Flask(__name__)
CORS(app)

@app.route("/api/comparar", methods=["POST"])
def comparar():
    logger.info("Recebida requisição para /api/comparar")
    pdf1 = request.files.get('pdf1')
    pdf2 = request.files.get('pdf2')
    logger.info(f"Arquivos recebidos: pdf1={getattr(pdf1, 'filename', None)}, pdf2={getattr(pdf2, 'filename', None)}")
    if not pdf1 or not pdf2:
        logger.warning("Um ou ambos os arquivos PDF não foram enviados para /api/comparar")
        return jsonify({"error": "Ambos os arquivos PDF são obrigatórios"}), 400
    threshold = float(request.form.get('threshold_similaridade', 0.75))
    min_segmento = int(request.form.get('min_segmento', 10))
    try:
        path1 = UPLOAD_DIR / f"{uuid.uuid4()}_{pdf1.filename}"
        path2 = UPLOAD_DIR / f"{uuid.uuid4()}_{pdf2.filename}"
        pdf1.save(path1)
        pdf2.save(path2)
        logger.info(f"Arquivos salvos em: {path1}, {path2}")
        config = ConfiguracaoProcessamento(threshold_similaridade=threshold, tamanho_minimo_segmento=min_segmento)
        processador = ProcessadorDocumentos(config)
        resultado = processador.processar_documentos(str(path1), str(path2))
        # Gerar id da comparação
        result_id = str(uuid.uuid4())
        logger.info(f"Comparação realizada com sucesso | id={result_id}")
        # Salvar resultado em arquivo (opcional, se já não salva)
        result_path = RESULTS_DIR / f"{result_id}.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(asdict(resultado), f, ensure_ascii=False, indent=2, default=str)
        # Retornar id e resultado
        return jsonify({"id": result_id, **asdict(resultado)})
    except Exception as e:
        logger.exception("Erro ao comparar PDFs")
        return jsonify({"error": str(e)}), 500

@app.route("/api/resultado/<result_id>", methods=["GET"])
def get_resultado(result_id):
    result_path = RESULTS_DIR / f"{result_id}.json"
    if not result_path.exists():
        return jsonify({"error": "Resultado não encontrado"}), 404
    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/api/filtrar-alterados/<result_id>", methods=["GET"])
def filtrar_alterados(result_id):
    result_path = RESULTS_DIR / f"{result_id}.json"
    if not result_path.exists():
        return jsonify({"error": "Resultado não encontrado"}), 404
    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    alterados = [c for c in data.get("comparacoes", []) if c.get("tipo_diferenca") in ["removido", "adicionado", "modificado"]]
    return {"id": result_id, "alterados": alterados}