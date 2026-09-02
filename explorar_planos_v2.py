#!/usr/bin/env python3
"""
Explora los DXF de C:\\planos_v2 SIN asumir nada del modelo anterior.

Primer paso de rehacer el modelo desde cero: saber que trae cada
lamina, que capas usa y que rotulos tiene, antes de extraer geometria.

Uso:  python explorar_planos_v2.py
"""

import logging
import os
import re
import sys
from collections import Counter

# ezdxf avisa por cada ACDB_BLOCKREPRESENTATION_DATA que no sabe copiar.
# En estas laminas son miles y tapan toda la salida util; no afectan a
# la geometria que nos interesa.
logging.getLogger('ezdxf').setLevel(logging.ERROR)

try:
    import ezdxf
except ImportError:
    sys.exit("Falta ezdxf.  pip install ezdxf")

DIR = r"C:\planos_v2"


def texto_de(e):
    """Texto plano de un TEXT o MTEXT, sin los codigos de formato."""
    try:
        if e.dxftype() == 'MTEXT':
            t = e.plain_text()
        else:
            t = e.dxf.text
    except Exception:
        return ""
    return re.sub(r"\s+", " ", t).strip()


def explorar(ruta):
    doc = ezdxf.readfile(ruta)
    msp = doc.modelspace()

    capas = Counter()
    tipos = Counter()
    for e in msp:
        tipos[e.dxftype()] += 1
        capas[e.dxf.layer] += 1

    # Los titulos y cotas viven en textos. Se juntan los del modelspace
    # y los que estan dentro de bloques (INSERT), porque casi todo el
    # dibujo esta bloqueado.
    textos = []
    for e in msp:
        if e.dxftype() in ('TEXT', 'MTEXT'):
            t = texto_de(e)
            if t:
                textos.append((e.dxf.layer, t))
        elif e.dxftype() == 'INSERT':
            try:
                for sub in e.virtual_entities():
                    if sub.dxftype() in ('TEXT', 'MTEXT'):
                        t = texto_de(sub)
                        if t:
                            textos.append((sub.dxf.layer, t))
            except Exception:
                pass

    return doc, capas, tipos, textos


def main():
    hojas = sorted(f for f in os.listdir(DIR) if f.lower().endswith('.dxf'))
    if not hojas:
        sys.exit(f"No hay DXF en {DIR}")

    # Palabras que delatan de que es una lamina y a que nivel va.
    CLAVE = re.compile(
        r"planta|elevacion|elevación|corte|cielo|fundacion|fundación|"
        r"subterr|piso|nivel|escala|N\.?\s*[+-]?\s*\d+[.,]\d+",
        re.IGNORECASE)

    for h in hojas:
        ruta = os.path.join(DIR, h)
        print("=" * 70)
        print(f"  {h}")
        print("=" * 70)
        try:
            doc, capas, tipos, textos = explorar(ruta)
        except Exception as ex:
            print(f"  no se pudo leer: {ex}")
            continue

        print(f"  unidades (INSUNITS): {doc.header.get('$INSUNITS')}  "
              f"(1=pulg, 2=pies, 4=mm, 5=cm, 6=m)")
        print(f"  entidades: {sum(tipos.values())}")

        print("  capas con mas entidades:")
        for c, n in capas.most_common(12):
            print(f"      {n:7d}  {c}")

        # Titulos: textos que suenan a rotulo de planta/elevacion.
        vistos = set()
        rotulos = []
        for capa, t in textos:
            if CLAVE.search(t) and len(t) < 120:
                k = t.upper()
                if k not in vistos:
                    vistos.add(k)
                    rotulos.append((capa, t))
        print(f"  rotulos que parecen titulos o cotas ({len(rotulos)}):")
        for capa, t in rotulos[:40]:
            print(f"      [{capa}] {t}")
        print()


if __name__ == '__main__':
    main()
