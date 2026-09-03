#!/usr/bin/env python3
"""
Sondea que tipo de entidad hay en las capas estructurales, y con que
tamanos, para saber COMO leerlas antes de escribir el extractor.

Tambien estima las unidades del dibujo: los DXF vienen con
INSUNITS = 0 (sin unidades declaradas), asi que hay que deducirlas de
las dimensiones reales.
"""

import logging
import os
import re
import sys
from collections import Counter, defaultdict

logging.getLogger('ezdxf').setLevel(logging.ERROR)
import ezdxf

DIR = r"C:\planos_v2"

# Capas que suenan a estructura. Se sondean todas las que existan.
INTERES = ['RLE-EJE', 'RLE-EJES', 'RLE-MURO', 'RLE-PILAR', 'RLE-VIGA',
           'RLE-LOSA', 'RLA-LOSAS', 'RLE-FUNDACION', 'RLE-NIVELES',
           'RLE-VANOS', 'RLE-SOLID']


def aplanar(msp):
    """
    Devuelve (entidad, capa) de todo el dibujo, explotando los INSERT.
    Casi todo vive dentro de bloques: sin virtual_entities() no se ve
    practicamente nada de la geometria.
    """
    for e in msp:
        if e.dxftype() == 'INSERT':
            try:
                for sub in e.virtual_entities():
                    yield sub, sub.dxf.layer
            except Exception:
                pass
        else:
            yield e, e.dxf.layer


def bbox_de(e):
    """Caja envolvente aproximada de una entidad, o None."""
    t = e.dxftype()
    try:
        if t == 'LINE':
            a, b = e.dxf.start, e.dxf.end
            return (min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y))
        if t in ('LWPOLYLINE', 'POLYLINE'):
            pts = [(p[0], p[1]) for p in e.get_points()] if t == 'LWPOLYLINE' \
                  else [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            if not pts:
                return None
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))
        if t == 'CIRCLE':
            c, r = e.dxf.center, e.dxf.radius
            return (c.x - r, c.y - r, c.x + r, c.y + r)
        if t in ('TEXT', 'MTEXT'):
            p = e.dxf.insert
            return (p.x, p.y, p.x, p.y)
        if t == 'SOLID':
            pts = [e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx2, e.dxf.vtx3]
            xs = [p.x for p in pts]
            ys = [p.y for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))
    except Exception:
        return None
    return None


def main():
    hojas = sys.argv[1:] or ['2017_67-100', '2017_67-101',
                             '2017_67-102', '2017_67-103']
    for h in hojas:
        ruta = os.path.join(DIR, h + '.dxf')
        if not os.path.exists(ruta):
            print(f"  falta {ruta}")
            continue
        print("=" * 70)
        print(f"  {h}")
        print("=" * 70)
        doc = ezdxf.readfile(ruta)
        msp = doc.modelspace()

        porcapa = defaultdict(Counter)
        cajas = defaultdict(list)
        for e, capa in aplanar(msp):
            if capa in INTERES:
                porcapa[capa][e.dxftype()] += 1
                b = bbox_de(e)
                if b:
                    cajas[capa].append(b)

        for capa in INTERES:
            if capa not in porcapa:
                continue
            tipos = ", ".join(f"{t}:{n}" for t, n in
                              porcapa[capa].most_common())
            print(f"  {capa:16s} {tipos}")
            bs = cajas[capa]
            if bs:
                anchos = sorted(b[2] - b[0] for b in bs)
                altos = sorted(b[3] - b[1] for b in bs)
                # Extension total: dice la escala del dibujo.
                print(f"      extension X: {min(b[0] for b in bs):10.1f} .. "
                      f"{max(b[2] for b in bs):10.1f}")
                print(f"      extension Y: {min(b[1] for b in bs):10.1f} .. "
                      f"{max(b[3] for b in bs):10.1f}")
                med = len(anchos) // 2
                print(f"      ancho mediano {anchos[med]:8.2f}   "
                      f"alto mediano {altos[med]:8.2f}")
        print()


if __name__ == '__main__':
    main()
