import re


class Chunker:

    def _dividir_en_oraciones(self, texto_bloque: str) -> list:
        """Divide un bloque (ya segmentado temáticamente) en oraciones,
        que serán los hijos de ese bloque."""
        fragmentos = []
        lineas = [l.strip() for l in texto_bloque.split("\n") if l.strip()]

        for linea in lineas:
            oraciones = re.split(r'(?<=[.!?])\s+', linea)
            for oracion in oraciones:
                oracion = oracion.strip()
                if oracion:
                    fragmentos.append(oracion)

        return fragmentos

    def generar_chunks_desde_bloques(self, bloques: list, fuente: str) -> list:
        """
        Recibe los bloques YA segmentados temáticamente (por el Segmentador
        con Gemini) y construye la estructura padre-hijo.

        A diferencia del esquema anterior (un padre por PDF completo),
        aquí cada bloque temático es su propio padre, con sus propios
        hijos (oraciones/líneas de ESE bloque, no del documento entero).
        Esto evita que el contexto que recibe el modelo mezcle temas
        no relacionados, y evita que listas o procedimientos de varios
        pasos pierdan elementos por baja similitud individual.
        """
        resultado = []
        for bloque in bloques:
            padre = {
                "contexto_completo": bloque.strip(),
                "fuente": fuente
            }

            fragmentos = self._dividir_en_oraciones(bloque)
            hijos = [{"texto_embedding": frag} for frag in fragmentos]

            resultado.append({
                "padre": padre,
                "hijos": hijos
            })

        return resultado