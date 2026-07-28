import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv(Path(__file__).parent.parent / "keys.env")


PROMPT_SEGMENTACION = """
Vas a dividir el siguiente documento en bloques temáticos independientes.

Reglas estrictas:
1. Copia el texto EXACTO, sin resumir, reescribir ni corregir nada.
2. Una pregunta con su respuesta completa (incluyendo listas o viñetas
   que pertenezcan a esa respuesta) es UN SOLO bloque, sepáralas en
   bloque siempre.
3. Un procedimiento de pasos numerados en secuencia (ej. "Flujo paso a
   paso: 1... 2... 3...") es UN SOLO bloque, nunca lo separes por número.
4. Una lista de aclaraciones numeradas donde cada número trata un tema
   distinto e independiente SÍ debe separarse, un bloque por número.
5. Ignora encabezados de sección en mayúsculas que no tengan contenido
   propio (ej. "3. CAMPOS Y CATÁLOGOS") — únelos al primer bloque real
   que les sigue.
6. Ignora encabezados o pies de página repetidos (nombre de la
   dependencia, número de página, etc.) si aparecen intercalados en el
   texto; no forman parte de ningún bloque.
7. Si y solo si detectas un enlace o URL que quedó dividido por un salto de
   línea del PDF (por ejemplo, terminando una línea a mitad de la URL, con
   o sin guion, y continuando en la línea siguiente), reconstrúyelo como una
   sola cadena continua, sin espacios ni saltos de línea internos.
   - Si el corte ocurre justo después de un guion "-", mantén el guion pegado
     al carácter siguiente (no le agregues ni le quites ningún espacio):
     "...Nc7am7Q-\\nt056Kqxx..." debe quedar como "...Nc7am7Q-t056Kqxx...".
   - No agregues, quites ni "corrijas" ningún otro carácter de la URL más
     allá de eliminar el salto de línea que la partió.
   Esta es la única excepción a la regla 1 (copiar el texto exacto): para
   todo lo demás en el documento, sigue aplicando la regla 1 sin cambios.
8. Si una parte del texto conforma ya sea una portada o índice de contenidos,
   ignóralo y no lo incluyas en ningún bloque.

Separa cada bloque final con la línea exacta: ===BLOQUE===
No agregues numeración, títulos ni comentarios propios, solo el texto
del documento ya segmentado.

DOCUMENTO:
{texto}
"""


class Segmentador:

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Falta GEMINI_API_KEY en el archivo keys.env")

        self.modelo = ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite-preview",
            temperature=0,  # consistencia, no creatividad, para esta tarea
            max_tokens=8192,
            google_api_key=api_key,
        )

    def segmentar(self, texto: str) -> list:
        """Envía el texto completo de un documento a Gemini y devuelve
        la lista de bloques temáticos ya separados."""
        prompt = PROMPT_SEGMENTACION.format(texto=texto)
        respuesta = self.modelo.invoke(prompt)

        contenido = respuesta.content
        if isinstance(contenido, list):
            contenido = "".join(
                bloque.get("text", "") if isinstance(bloque, dict) else str(bloque)
                for bloque in contenido
            )

        bloques = [
            b.strip()
            for b in contenido.split("===BLOQUE===")
            if b.strip()
        ]
        return bloques