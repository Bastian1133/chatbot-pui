"""
Script de indexación — ejecución manual desde la máquina local.

Implementa el mismo algoritmo que usará más adelante el endpoint
POST /documentos cuando el admin suba PDFs desde el panel web.
La única diferencia con esa versión futura es el origen del archivo:
aquí se lee de una carpeta local, ahí vendrá de un UploadFile subido
desde el navegador. El resto del pipeline (hash, segmentación con
Gemini, chunking, embeddings, inserción, manejo de errores) es el
mismo que correrá en producción.

Uso:
    python indexador/indexar_pdf.py
"""

from pathlib import Path
import sys

# Para que Python encuentre embedder.py y database/ en la carpeta raíz
sys.path.append(str(Path(__file__).parent.parent))

from chunker import Chunker
from extractor_pdf import Extractor
from segmentador import Segmentador
from embedder import Embedder
from database.insertar_supabase import InsersorSupabase
from database.documentos_repo import DocumentosRepo


def procesar_pdf(ruta_pdf, extractor, segmentador, chunker, embedder, insersor, repo):
    nombre_archivo = ruta_pdf.name
    print(f"\n{'=' * 60}")
    print(f"Procesando: {nombre_archivo}")
    print("=" * 60)

    # 1. Extraer texto del PDF
    texto = extractor.extraer_de_archivo(str(ruta_pdf))
    print(f"  Texto extraído: {len(texto)} caracteres")

    # 2. Calcular hash sobre el TEXTO extraído (no sobre los bytes del PDF)
    hash_contenido = repo.calcular_hash(texto)

    if repo.existe_hash(hash_contenido):
        print(f"  Ya existe un documento con este contenido. Se omite.")
        return

    # 3. Crear el registro del documento (estado='pendiente')
    documento_id = repo.crear_documento(nombre_archivo, hash_contenido)
    print(f"  Documento creado — id: {documento_id}")

    try:
        # 4. Segmentación temática con Gemini
        print("  Segmentando temáticamente con Gemini...")
        bloques_texto = segmentador.segmentar(texto)
        print(f"  {len(bloques_texto)} bloques temáticos generados")

        # 5. Construir padres e hijos a partir de los bloques ya segmentados
        bloques = chunker.generar_chunks_desde_bloques(bloques_texto, nombre_archivo)

        # 6. Vectorizar todos los hijos en un solo lote
        print("  Vectorizando chunks hijos...")
        textos_hijos = [
            hijo["texto_embedding"]
            for bloque in bloques
            for hijo in bloque["hijos"]
        ]
        embeddings = embedder.vectorizar_lote(textos_hijos)
        print(f"  {len(embeddings)} embeddings generados")

        # 7. Insertar padres + hijos en Supabase
        print("  Insertando en Supabase...")
        insersor.insertar_bloques(bloques, embeddings, documento_id)

        # 8. Marcar el documento como indexado
        repo.actualizar_estado(documento_id, "indexado")
        print(f"  OK — {nombre_archivo} indexado correctamente")

    except Exception as e:
        # Si algo falla a medio camino, se borra el documento.
        # La cascada en BD limpia cualquier chunk_padre/chunk_hijo
        # que se haya alcanzado a insertar antes del fallo.
        print(f"  ERROR procesando {nombre_archivo}: {e}")
        repo.eliminar_documento(documento_id)
        print(f"  Documento revertido (rollback por cascada)")


def main():
    carpeta_documentos = Path(__file__).parent.parent / "documentos"
    pdfs = list(carpeta_documentos.glob("*.pdf"))

    if not pdfs:
        print(f"No se encontraron PDFs en {carpeta_documentos}")
        return

    extractor = Extractor()
    segmentador = Segmentador()
    chunker = Chunker()
    embedder = Embedder()
    insersor = InsersorSupabase()
    repo = DocumentosRepo()

    for ruta_pdf in pdfs:
        procesar_pdf(ruta_pdf, extractor, segmentador, chunker, embedder, insersor, repo)

    print(f"\n{'=' * 60}")
    print("Indexación completada")
    print("=" * 60)


if __name__ == "__main__":
    main()