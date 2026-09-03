#!/usr/bin/env python3
"""
Verifica el modelo del edificio contra los planos DXF.

Responde dos preguntas que quedaron abiertas en la Semana 2:

  1. Los ejes Y 46.92 y 65.22 "no existen en los planos".
     SI existen. Son los ejes 3' y 1b. Lo que pasa es que su GLOBO
     (el circulito con la etiqueta, en el margen de la lamina) esta
     corrido respecto de la linea del eje, y unido a ella por un
     QUIEBRE. Leer la altura del globo da la coordenada equivocada.
     Los valores reales son 47.701 y 64.651.

  2. "Se asume que los muros suben por los 8 pisos".
     No suben. Y ademas el edificio no tiene 8 pisos: tiene 5, de
     3.96 m cada uno. Sobre el nivel +-0.00 solo queda el nucleo de
     escalera/ascensor: 13.1 m de los 168.3 m que usa el modelo.

Los planos estan fuera del repo (.gitignore, 113 MB de DWG). Se
convierten a DXF con accoreconsole.exe de AutoCAD, a una ruta SIN
espacios ni tildes, y se leen con ezdxf.

    Unidades del DXF: CENTIMETROS. Aca todo se pasa a metros.

Uso:
    python verificar_planos.py [carpeta_dxf]
"""

import math
import os
import sys
import collections

try:
    import ezdxf
except ImportError:
    print("Falta ezdxf.  pip install ezdxf")
    sys.exit(1)


RUTA_DXF = sys.argv[1] if len(sys.argv) > 1 else r"C:\dxf_planos"

# La lamina de fundaciones es el sistema de referencia: sus ejes
# coinciden al centimetro con los del modelo.
REF_X, REF_Y = 8.021, 47.951      # cruce eje E x eje 3

# Cada planta se identifica por su datum (cruce eje E x eje 3) y por
# la banda en Y que ocupa dentro de la lamina, porque una lamina trae
# hasta DOS plantas, cada una insertada en un origen distinto.
#
# (lamina, nombre, X del eje E, Y del eje 3, banda Y min, banda Y max, cota losa)
PLANTAS = [
    ('2017_67-100', 'Fundaciones',    8.021, 47.951, -1e9, 1e9,  -7.97),
    ('2017_67-101', 'Cielo 1o subt', 10.613, 55.501,   51, 1e9,  -4.01),
    ('2017_67-101', 'Cielo piso 1o', 10.613, 19.430, -1e9,  51,  -0.05),
    ('2017_67-102', 'Cielo piso 2o',  8.932, 62.699,   50, 1e9,   3.91),
    ('2017_67-102', 'Cielo piso 3o',  5.350, 26.453, -1e9,  50,   7.87),
    ('2017_67-103', 'Cielo piso 4o',  4.903, 46.642, -1e9, 1e9,  11.83),
]


# ---------------------------------------------------------------------
# lectura del DXF
# ---------------------------------------------------------------------
def leer_lamina(ruta):
    """
    Devuelve globos de eje, etiquetas, lineas de eje y lineas de muro,
    todo en metros. Explota los INSERT porque casi todo el dibujo vive
    dentro de bloques.
    """
    doc = ezdxf.readfile(ruta)
    d = dict(globos=[], etiquetas=[], ejes=[], muros=[])

    def recorrer(contenedor, prof=0):
        for e in contenedor:
            t = e.dxftype()
            capa = e.dxf.layer
            try:
                if t == 'CIRCLE' and capa.endswith('RLE-EJE'):
                    c = e.dxf.center
                    d['globos'].append((c.x / 100.0, c.y / 100.0))
                elif t in ('TEXT', 'MTEXT', 'ATTRIB') and capa.endswith('RLE-EJE'):
                    txt = e.plain_text() if hasattr(e, 'plain_text') else e.dxf.text
                    txt = ' '.join(txt.split())
                    if txt:
                        p = e.dxf.insert
                        d['etiquetas'].append((txt, p.x / 100.0, p.y / 100.0))
                elif t == 'LINE' and capa.endswith('RLE-EJES'):
                    a, b = e.dxf.start, e.dxf.end
                    d['ejes'].append((a.x / 100.0, a.y / 100.0,
                                      b.x / 100.0, b.y / 100.0))
                elif capa.endswith('RLE-MURO'):
                    if t == 'LINE':
                        a, b = e.dxf.start, e.dxf.end
                        d['muros'].append((a.x / 100.0, a.y / 100.0,
                                           b.x / 100.0, b.y / 100.0))
                    elif t == 'LWPOLYLINE':
                        p = [(x / 100.0, y / 100.0) for x, y in e.get_points('xy')]
                        if e.closed and len(p) > 2:
                            p = p + [p[0]]
                        for i in range(len(p) - 1):
                            d['muros'].append((p[i][0], p[i][1],
                                               p[i + 1][0], p[i + 1][1]))
            except Exception:
                pass
            if t == 'INSERT' and prof < 3:
                try:
                    recorrer(e.virtual_entities(), prof + 1)
                except Exception:
                    pass

    recorrer(doc.modelspace())
    return d


# ---------------------------------------------------------------------
# ejes: seguir el quiebre entre el globo y la linea
# ---------------------------------------------------------------------
def nombrar_globos(d):
    """Cada etiqueta se asigna al globo mas cercano (a menos de 1 m)."""
    out = {}
    for txt, tx, ty in d['etiquetas']:
        if not d['globos']:
            continue
        g = min(d['globos'], key=lambda c: math.hypot(c[0] - tx, c[1] - ty))
        if math.hypot(g[0] - tx, g[1] - ty) < 1.0:
            out[g] = txt
    return out


def eje_real(globo, lineas):
    """
    Coordenada Y del eje al que pertenece este globo horizontal.

    Del globo sale un tramo horizontal. Si es largo, el globo esta
    sobre su propio eje. Si es corto (menos de 5 m) hay QUIEBRE: en su
    extremo arranca un tramo vertical que baja o sube hasta la linea
    larga, y esa es la coordenada buena.
    """
    y_globo, x_globo = globo[1], globo[0]

    tramo = None
    for x1, y1, x2, y2 in lineas:
        if abs(y1 - y_globo) < 0.02 and abs(y2 - y_globo) < 0.02:
            if min(abs(x1 - x_globo), abs(x2 - x_globo)) < 1.0:
                largo = abs(x1 - x2)
                if tramo is None or largo > tramo[0]:
                    lejos = max(x1, x2) if (x1 > x_globo or x2 > x_globo) else min(x1, x2)
                    tramo = (largo, lejos)
    if tramo is None:
        return None, 'sin tramo'
    if tramo[0] > 5.0:
        return y_globo, 'directo'

    for x1, y1, x2, y2 in lineas:
        if abs(x1 - x2) < 0.02 and abs(x1 - tramo[1]) < 0.05:
            if abs(y1 - y_globo) < 0.05:
                return y2, 'quiebre'
            if abs(y2 - y_globo) < 0.05:
                return y1, 'quiebre'
    return None, 'quiebre sin destino'


def ejes_y(ruta):
    """{nombre del eje: (Y del globo, Y real, como se leyo)}"""
    d = leer_lamina(ruta)
    nombres = nombrar_globos(d)
    xs = [g[0] for g in d['globos']]
    if not xs:
        return {}
    xmin, xmax = min(xs), max(xs)
    out = {}
    for g, nom in nombres.items():
        if abs(g[0] - xmin) > 0.5 and abs(g[0] - xmax) > 0.5:
            continue                      # no esta en el margen: es un eje X
        y, como = eje_real(g, d['ejes'])
        if y is None:
            continue
        # el borde izquierdo manda; el derecho solo si falta
        if nom not in out or abs(g[0] - xmin) < 0.5:
            out[nom] = (g[1], y, como)
    return out


# ---------------------------------------------------------------------
# muros
# ---------------------------------------------------------------------
def corridas(segmentos, tol=0.03, hueco=0.35, minimo=0.80):
    """
    Agrupa los segmentos ortogonales en corridas de muro: misma
    direccion, misma coordenada fija, intervalos fusionados.
    Devuelve {('X'|'Y', coordenada): [(desde, hasta), ...]}
    """
    ejes = collections.defaultdict(list)
    for x1, y1, x2, y2 in segmentos:
        dx, dy = x2 - x1, y2 - y1
        if abs(dy) < tol and abs(dx) > 0.20:
            ejes[('X', round((y1 + y2) / 2, 2))].append((min(x1, x2), max(x1, x2)))
        elif abs(dx) < tol and abs(dy) > 0.20:
            ejes[('Y', round((x1 + x2) / 2, 2))].append((min(y1, y2), max(y1, y2)))

    out = {}
    for k, iv in ejes.items():
        iv.sort()
        fus = [list(iv[0])]
        for a, b in iv[1:]:
            if a <= fus[-1][1] + hueco:
                fus[-1][1] = max(fus[-1][1], b)
            else:
                fus.append([a, b])
        buenas = [tuple(f) for f in fus if f[1] - f[0] >= minimo]
        if buenas:
            out[k] = buenas
    return out


def muros_por_planta():
    """{nombre de planta: corridas de muro en el sistema de fundaciones}"""
    cache, out = {}, {}
    for lam, nombre, xE, y3, ymin, ymax, _cota in PLANTAS:
        ruta = os.path.join(RUTA_DXF, lam + '.dxf')
        if ruta not in cache:
            cache[ruta] = leer_lamina(ruta)['muros']
        dx, dy = REF_X - xE, REF_Y - y3
        segs = [(x1 + dx, y1 + dy, x2 + dx, y2 + dy)
                for x1, y1, x2, y2 in cache[ruta]
                if ymin <= (y1 + y2) / 2 <= ymax]
        out[nombre] = corridas(segs)
    return out


def cubrimiento(c, direccion, coord, a, b, espesor):
    """Fraccion del tramo [a,b] cubierta por una cara de muro en ese eje."""
    mejor = 0.0
    for (d, cc), ivs in c.items():
        if d != direccion or abs(cc - coord) > espesor / 2 + 0.12:
            continue
        for u, v in ivs:
            mejor = max(mejor, max(0.0, min(b, v) - max(a, u)))
    return mejor / (b - a)


# ---------------------------------------------------------------------
def main():
    if not os.path.isdir(RUTA_DXF):
        print(f"No encuentro {RUTA_DXF}.")
        print("Los planos van fuera del repo; convierte los DWG a DXF con")
        print("accoreconsole.exe a una ruta sin espacios ni tildes.")
        return 0

    fallos = []

    # -- 1. ejes -------------------------------------------------------
    print("=" * 68)
    print("1. EJES Y  (lamina 2017_67-100, fundaciones)")
    print("=" * 68)
    ruta100 = os.path.join(RUTA_DXF, '2017_67-100.dxf')
    if not os.path.exists(ruta100):
        print(f"  falta {ruta100}")
        return 0
    ejes = ejes_y(ruta100)
    print(f"  {'eje':6s} {'globo':>9s} {'eje real':>9s}   lectura")
    for nom, (yg, yr, como) in sorted(ejes.items(), key=lambda kv: kv[1][1]):
        marca = "" if como == 'directo' else "   <-- el globo enganna"
        print(f"  {nom:6s} {yg:9.3f} {yr:9.3f}   {como}{marca}")

    # benchmark_3d no tiene guarda __main__: importarlo corre el modelo
    # entero. Nos interesan solo Y_axes y MUROS, asi que le tapamos la
    # salida mientras se importa.
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        import benchmark_3d as m

    reales = sorted(yr for _, yr, _ in ejes.values())
    print("\n  ejes del modelo contra el plano:")
    for y in m.Y_axes:
        cerca = min(reales, key=lambda r: abs(r - y))
        d = abs(cerca - y)
        ok = d <= 0.01
        nom = [n for n, v in ejes.items() if abs(v[1] - cerca) < 1e-6][0]
        print(f"    modelo {y:7.2f}  ->  eje {nom:5s} {cerca:7.3f}   "
              f"dif {d*1000:5.1f} mm  {'OK' if ok else 'NO CALZA'}")
        if not ok:
            fallos.append(f"el eje Y={y} del modelo no calza con ningun eje del plano")

    # -- 2. muros ------------------------------------------------------
    print("\n" + "=" * 68)
    print("2. MUROS, PLANTA POR PLANTA")
    print("=" * 68)
    faltan = [p[0] for p in PLANTAS
              if not os.path.exists(os.path.join(RUTA_DXF, p[0] + '.dxf'))]
    if faltan:
        print(f"  faltan laminas: {sorted(set(faltan))}")
        return 1 if fallos else 0

    porplanta = muros_por_planta()
    nombres = [p[1] for p in PLANTAS]
    corto = {n: n.replace('Cielo ', '').replace('Fundaciones', 'Fundac.')
             for n in nombres}
    cotas = {p[1]: p[6] for p in PLANTAS}

    print(f"  {'muro del modelo':34s}" + "".join(f"{corto[n]:>11s}" for n in nombres))
    print("  " + "-" * (34 + 11 * len(nombres)))
    largos = {n: 0.0 for n in nombres}
    # El piso i del modelo va del nivel i-1 al i, y lo corona la planta
    # de cielo correspondiente. La planta de fundaciones no es un piso.
    PISO_DE_PLANTA = {'Cielo 1o subt': 1, 'Cielo piso 1o': 2,
                      'Cielo piso 2o': 3, 'Cielo piso 3o': 4,
                      'Cielo piso 4o': 5}
    for direccion, coord, a, b, esp, pisos in m.MUROS:
        fila = ""
        segun_plano = set()
        for n in nombres:
            f = cubrimiento(porplanta[n], direccion, coord, a, b, esp)
            largos[n] += f * (b - a)
            fila += f"{'-':>11s}" if f < 0.05 else f"{f*100:9.0f}% "
            if f >= 0.5 and n in PISO_DE_PLANTA:
                segun_plano.add(PISO_DE_PLANTA[n])
        et = f"{direccion} {coord:6.2f} {a:6.2f}->{b:6.2f} e={esp:.2f}"
        declarado = set(pisos)
        marca = "" if declarado == segun_plano else "   <-- NO CALZA"
        if declarado != segun_plano:
            fallos.append(f"muro {et}: el modelo declara los pisos "
                          f"{sorted(declarado)} y el plano muestra "
                          f"{sorted(segun_plano)}")
        print(f"  {et:34s}{fila}{marca}")
    print("  " + "-" * (34 + 11 * len(nombres)))

    total = sum(b - a for _, _, a, b, _, _ in m.MUROS)
    print(f"  {'largo de muro presente (m)':34s}"
          + "".join(f"{largos[n]:10.1f} " for n in nombres))
    print(f"  {'porcentaje de los 168.3 m':34s}"
          + "".join(f"{largos[n]/total*100:9.0f}% " for n in nombres))
    print(f"  {'cota de la losa (m)':34s}"
          + "".join(f"{cotas[n]:+10.2f} " for n in nombres))

    # El supuesto que hay que desmentir: muros iguales en los 8 pisos.
    sobre_suelo = ['Cielo piso 2o', 'Cielo piso 3o', 'Cielo piso 4o']
    frac = max(largos[n] for n in sobre_suelo) / total
    print(f"\n  Sobre el nivel +-0.00 solo sobrevive el nucleo: "
          f"{largos[sobre_suelo[0]]:.1f} m de {total:.1f} m ({frac*100:.0f}%).")
    if frac > 0.5:
        fallos.append("los muros sobre el suelo deberian ser una fraccion pequenna")

    # Los tres pisos altos tienen que traer exactamente el mismo nucleo.
    iguales = len({round(largos[n], 2) for n in sobre_suelo}) == 1
    print(f"  Los pisos 2o, 3o y 4o traen el mismo nucleo: "
          f"{'si' if iguales else 'NO'}")
    if not iguales:
        fallos.append("los pisos altos no traen el mismo nucleo")

    # Y el modelo tiene que estar puesto a esa misma altura.
    esperado = [0.0, 3.96, 7.92, 11.88, 15.84, 19.80]
    if [round(h, 2) for h in m.heights] != esperado:
        fallos.append(f"heights deberia ser {esperado} y es {m.heights}")
    else:
        print(f"  El modelo tiene los 5 pisos de 3.96 m, techo en "
              f"{m.COTA_BASE + m.heights[-1]:+.2f} m: si")

    print("\n" + "=" * 68)
    if fallos:
        print("  FALLOS:")
        for f in fallos:
            print(f"    - {f}")
    else:
        print("  TODO CALZA CON LOS PLANOS")
    print("=" * 68)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
