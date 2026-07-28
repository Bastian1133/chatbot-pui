from pathlib import Path
from pypdf import PdfReader
import re
import textwrap

class Extractor:    
    def extraer_desde_carpeta(self, ruta_carpeta: str) -> dict:
        carpeta = Path(ruta_carpeta)
        resultados = {}
        pdfs = list(carpeta.glob("*.pdf"))
        
        if not pdfs:
            print(f"No se encontraron PDFs en {ruta_carpeta}")
            return resultados
        
        for pdf in pdfs:
            print(f"Extrayendo: {pdf.name}")
            try:
                texto = self.__extraer_texto(str(pdf))
                resultados[pdf.name] = texto
                print(f"  OK — {len(texto)} caracteres extraídos")
            except Exception as e:
                print(f"  ERROR en {pdf.name}: {e}")
        
        return resultados
    
    def __extraer_texto(self, ruta_pdf: str) -> str:
        reader = PdfReader(ruta_pdf)
        texto_completo = ""
        for pagina in reader.pages:
            texto = pagina.extract_text()
            if texto:
                texto_completo += texto + "\n"
        return self.__limpiar_texto(texto_completo)
    
    def __limpiar_texto(self, texto: str) -> str:
        texto = textwrap.dedent(texto)
        # Eliminar espacios al final de cada línea ANTES de evaluar puntuación
        texto = re.sub(r' +\n', '\n', texto)
        texto = re.sub(r'\n(?![•\n\-\d]|[A-ZÁÉÍÓÚÑ¿¡])', ' ', texto)
        texto = re.sub(r'(?<![.?!:])\n(?=[A-ZÁÉÍÓÚÑ])', ' ', texto)
        texto = re.sub(r'\n{3,}', '\n\n', texto)
        texto = re.sub(r' {2,}', ' ', texto)
        texto = re.sub(r'(\s{3,})(-\s)', r'\n\2', texto)
        texto = re.sub(r'\s+([,.])', r'\1', texto)
        texto = texto.strip()
        return texto    
    
    