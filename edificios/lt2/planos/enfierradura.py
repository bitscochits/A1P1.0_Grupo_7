# -*- coding: utf-8 -*-
r"""
================================================================
 enfierradura.py  -  EL FIERRO DE LOS PILARES, DESDE LA ELEVACION
================================================================
 Lee las laminas de elevacion y devuelve, para cada pilar y cada
 piso, el juego de estribos y trabas que el plano le pone.

 ----------------------------------------------------------------
 DONDE ESTA EL FIERRO EN ESTE JUEGO DE PLANOS
 ----------------------------------------------------------------
 No en las plantas: las 200/201/202 son armadura de LOSA y las
 101/102 son encofrado. El fierro de un pilar esta en la ELEVACION
 del eje, escrito justo debajo del rotulo de la seccion:

     P.70x70          <- el rotulo, capa RLE-TEXTOS-1
     E%%C12a10        <- estribo, capa RLA-TEXTOS-FE
     +3T%%C12a10      <- mas 3 trabas
     +3TL%%C12a10     <- mas 3 trabas longitudinales

 Cada pilar aparece en las DOS elevaciones perpendiculares que lo
 cruzan, pero detallado en UNA sola: la otra dice

     VER ELEV. EJE B

 Esa referencia cruzada es lo que evita contar dos veces. Y cierra:
 de los 80 rotulos P.70x70 del juego, 40 traen fierro y 40 remiten.

 ----------------------------------------------------------------
 LA TRAMPA: EL VECINO MAS CERCANO ES LA VIGA
 ----------------------------------------------------------------
 Alrededor del rotulo de un pilar hay llamadas de fierro que NO son
 suyas: las de las vigas que llegan al nudo, con su linea de
 referencia apuntando a la viga. Son las mas cercanas de todas.

     34ED%%C10a10  L:7+7%%C10      <- viga, no pilar

 Buscar "el texto de fierro mas cercano al rotulo" da la respuesta
 equivocada y no avisa. Lo que distingue al fierro del pilar es que
 esta DEBAJO del rotulo y dentro de su ancho: las llamadas de viga
 salen hacia el lado, fuera de la franja. Por eso la busqueda es
 direccional (solo hacia abajo, ver VENTANA_*) y no un radio.

 ----------------------------------------------------------------
 DE LA LAMINA A LA PLANTA
 ----------------------------------------------------------------
 En una elevacion la coordenada horizontal es la coordenada de
 planta del eje PERPENDICULAR, corrida por el origen de la lamina.
 El corrimiento se DERIVA de las burbujas de eje que la propia
 elevacion dibuja, no se supone:

     elevacion EJE B:  burbuja '3' en x=8.03  y el eje 3 esta en
                       11.047  ->  corrimiento 3.017 m

 Se toma la MEDIANA de todas las burbujas reconocidas. Hace falta:
 en la elevacion del eje 1 las burbujas de A', A, B y C dan 93.125
 pero las de D y D' estan dibujadas 45 cm corridas. Con la mediana
 los pilares caen igual en su sitio -- se verifico contra el modelo,
 los tres del eje 1 quedan en 22.355, 32.355 y 42.355 m.

 ----------------------------------------------------------------
 LO QUE ESTE MODULO NO PUEDE DAR
 ----------------------------------------------------------------
 El fierro LONGITUDINAL del pilar. No esta en la elevacion, ni en
 las plantas de encofrado, ni como circulos de barra en seccion
 (los unicos CIRCLE del juego son burbujas de eje), ni en las
 laminas de detalles tipicos. Lo que el plano da para un pilar es
 su juego de estribos y trabas.

 Como el longitudinal es justamente lo que manda en la capacidad a
 momento, hay que declararlo aparte, en el perfil, con su criterio
 escrito. Este modulo devuelve lo que el plano dice y nada mas; que
 el supuesto se vea como supuesto es el punto.
================================================================
"""
from __future__ import annotations

import collections
import re

import ezdxf

try:
    from . import lectura
except ImportError:                            # corriendo suelto
    import lectura                             # noqa: F401

# El nombre del XREF que trae una elevacion: 'EJE 1', "EJE A'",
# "EJE D-D'". Cada uno es un dibujo aparte con su propio origen.
ES_ELEVACION = re.compile(r'^EJE\s+\S', re.I)

# Rotulo de seccion de un pilar: 'P.70x70', 'P. 70 x 70', 'P.30x70'.
ROTULO_PILAR = re.compile(r'^P\.\s*(\d+)\s*[xX]\s*(\d+)\s*$')

# Una llamada de fierro. En AutoCAD el simbolo de diametro se
# escribe '%%C', asi que 'E%%C12a10' es "estribo fi 12 cada 10".
#
#   [+] [n] TIPO %%C diametro a separacion
#
# TIPO segun la simbologia de la lamina 000:
#   E    estribo          ED  2 estribos desplazados
#   ET   3 estribos       T   traba          TL  traba longitudinal
LLAMADA = re.compile(
    r'^\+?\s*(\d*)\s*(ED|ET|E|TL|T)\s*%%C\s*(\d+)\s*a\s*(\d+)\s*$', re.I)

# Remision al otro eje: 'VER ELEV. EJE B'
REMISION = re.compile(r'VER\s+ELEV\.?\s+EJE\s+(.+?)\s*$', re.I)

# Ventana de busqueda del fierro de un pilar, respecto de su rotulo,
# en metros. Hacia ABAJO porque el plano escribe el estribo debajo
# del rotulo, y estrecha porque las llamadas de viga salen de la
# franja del pilar.
VENTANA_ABAJO = (0.05, 0.80)    # cuanto mas abajo que el rotulo
VENTANA_LADO = 1.20             # cuanto a los lados del rotulo

# La remision ('VER ELEV. EJE B') se escribe mas abajo que el estribo
# -- 1.15 m en el eje 2 -- asi que necesita su propia ventana. Sigue
# siendo segura: entre piso y piso hay 3.96 m.
VENTANA_REMISION = 1.60

# Las tres lineas del juego de un pilar van pegadas: 0.16 a 0.19 m
# entre si. Un salto mayor significa que la siguiente llamada ya es de
# otra cosa -- el estribo de un muro vecino, por ejemplo -- aunque
# todavia caiga dentro de la ventana.
SALTO_MAXIMO = 0.35

# Cuanto puede alejarse una burbuja de eje del corrimiento mediano
# para seguir contando en el ajuste, en metros.
TOL_BURBUJA = 0.30


def eje_de(nombre_bloque):
    r"""
    Que eje dibuja este XREF.

        'EJE B'      -> 'B'
        "EJE A'"     -> "A'"     el eje auxiliar es OTRO eje
        "EJE D-D'"   -> 'D'      una sola elevacion para los dos

    El apostrofo se conserva salvo cuando viene en un par 'D-D'': ahi
    la elevacion es una y se le atribuye al eje principal.
    """
    n = re.sub(r'^EJE\s+', '', nombre_bloque.strip(), flags=re.I)
    return n.split('-')[0].strip()


def hojas_de_elevacion(ruta, perfil):
    """
    Las elevaciones de UNA lamina, cada una por separado.

    ----------------------------------------------------------------
    POR QUE NO SIRVE LEER LA LAMINA ENTERA
    ----------------------------------------------------------------
    Una lamina puede traer dos elevaciones: la 305 es 'ELEVACION EJES
    C, D-D''. Cada una es un XREF distinto, dibujado en su propio
    origen y pegado en la lamina en un sitio distinto.

    Leyendo la lamina de corrido, las burbujas de eje de las dos
    elevaciones se mezclan y el corrimiento que sale de su mediana no
    es el de ninguna de las dos: los pilares terminan a decenas de
    metros de donde estan. Y no falla, da coordenadas.

    Por eso cada XREF se lee en su propia Hoja.
    """
    doc = ezdxf.readfile(ruta)
    hojas = {}
    for e in doc.modelspace():
        if e.dxftype() != 'INSERT' or not ES_ELEVACION.match(e.dxf.name):
            continue
        try:
            hijas = list(e.virtual_entities())
        except Exception:
            continue
        h = lectura.Hoja(ruta, perfil.factor)
        lectura._recorrer(hijas, h, perfil.factor, 1)
        for att in getattr(e, 'attribs', []):
            lectura._agregar(h, att, perfil.factor)
        hojas[e.dxf.name] = h
    return hojas


def parsear_llamada(texto):
    """
    'E%%C12a10' -> {'tipo': 'E', 'cantidad': 1, 'diametro_mm': 12,
                    'separacion_cm': 10}
    Devuelve None si el texto no es una llamada de fierro.
    """
    m = LLAMADA.match(texto.strip())
    if not m:
        return None
    n, tipo, diam, sep = m.groups()
    return {
        'tipo': tipo.upper(),
        'cantidad': int(n) if n else 1,
        'diametro_mm': int(diam),
        'separacion_cm': int(sep),
        'texto': texto.strip(),
    }


def _corrimiento(hoja, perfil, grid):
    """
    Cuanto hay que sumarle a la x de esta elevacion para caer en la
    coordenada de planta. Sale de las burbujas de eje que la lamina
    dibuja; se devuelve tambien con que burbujas se calculo.
    """
    candidatos = []
    for t in hoja.textos_de(perfil, 'ejes_rotulos'):
        nombre = t.texto.strip()
        if nombre in grid:
            candidatos.append((grid[nombre] - t.x, nombre, t.x))
    if not candidatos:
        return None, []

    valores = sorted(c[0] for c in candidatos)
    mediana = valores[len(valores) // 2]
    usadas = [c for c in candidatos if abs(c[0] - mediana) <= TOL_BURBUJA]
    if not usadas:
        return mediana, []
    # Con las que sobrevivieron se recalcula, para no quedarse con el
    # valor de una sola burbuja cuando hay varias buenas.
    finos = sorted(c[0] for c in usadas)
    return finos[len(finos) // 2], [(c[1], round(c[0], 4)) for c in candidatos]


def _filas(valores, tol=0.30):
    """Agrupa coordenadas en filas; devuelve los centros ordenados."""
    filas = []
    for v in sorted(valores):
        if filas and v - filas[-1][-1] <= tol:
            filas[-1].append(v)
        else:
            filas.append([v])
    return [sum(f) / len(f) for f in filas]


def extraer(hoja, perfil, grid, niveles=None):
    """
    Lee una lamina de elevacion. Devuelve (pilares, auditoria).

    Cada pilar es un dict con su posicion en planta, el piso, la
    seccion rotulada y sus llamadas de fierro -- o, si la lamina
    remite a otra, a que eje remite.

    'niveles' es la lista de cotas del edificio, de menor a mayor.
    Si viene, cada pilar sale con la cota de su piso; si no, sale
    solo con el indice de la fila.
    """
    aud = {'archivo': hoja.archivo}

    dx, burbujas = _corrimiento(hoja, perfil, grid)
    aud['burbujas'] = burbujas
    aud['corrimiento_m'] = None if dx is None else round(dx, 4)
    if dx is None:
        aud['problema'] = ('no se reconocio ninguna burbuja de eje: sin eso '
                           'no se puede llevar la elevacion a coordenadas '
                           'de planta')
        return [], aud

    rotulos = []
    for t in hoja.textos:
        m = ROTULO_PILAR.match(t.texto.strip())
        if m:
            rotulos.append((t, int(m.group(1)), int(m.group(2))))
    aud['rotulos'] = len(rotulos)
    if not rotulos:
        return [], aud

    # Los rotulos se ordenan en filas horizontales, una por piso.
    filas = _filas([t.y for t, _b, _h in rotulos])
    aud['filas'] = len(filas)

    fierro = [t for t in hoja.textos_de(perfil, 'enfierradura')]
    aud['textos_de_fierro'] = len(fierro)

    pilares = []
    for t, b_cm, h_cm in rotulos:
        # De todas las llamadas de fierro, las que caen DEBAJO de este
        # rotulo y dentro de su franja. Ver la nota del encabezado
        # sobre por que no sirve el vecino mas cercano.
        cerca = []
        for f in fierro:
            dy = t.y - f.y
            if not (VENTANA_ABAJO[0] <= dy <= VENTANA_REMISION):
                continue
            if abs(f.x - t.x) > VENTANA_LADO:
                continue
            # Si hay otro rotulo mas cerca en horizontal, la llamada es
            # de ese otro pilar.
            otro = min(rotulos, key=lambda r: abs(r[0].x - f.x))
            if abs(otro[0].x - f.x) < abs(t.x - f.x) - 1e-9:
                continue
            cerca.append(f)
        cerca.sort(key=lambda f: -f.y)

        # La remision puede estar mas abajo que el juego de estribos.
        remite = None
        for f in cerca:
            m = REMISION.search(f.texto)
            if m:
                remite = m.group(1).strip()
                break

        # El juego del pilar es la CADENA de llamadas que arranca justo
        # debajo del rotulo. Se corta en el primer salto grande: lo que
        # viene despues ya es de otro elemento.
        llamadas, sueltos = [], []
        anterior = t.y
        for f in cerca:
            if t.y - f.y > VENTANA_ABAJO[1]:
                break
            if anterior - f.y > SALTO_MAXIMO:
                break
            c = parsear_llamada(f.texto)
            if c:
                llamadas.append(c)
                anterior = f.y
            elif REMISION.search(f.texto):
                continue
            else:
                sueltos.append(f.texto.strip())

        fila = min(range(len(filas)), key=lambda i: abs(filas[i] - t.y))
        pilares.append({
            'x_planta': round(t.x + dx, 4),
            'piso': fila,
            'cota': (round(niveles[fila], 4)
                     if niveles and fila < len(niveles) else None),
            'seccion_cm': [b_cm, h_cm],
            'rotulo': t.texto.strip(),
            'llamadas': llamadas,
            'remite_a': remite,
            'no_reconocido': sueltos,
        })

    con = sum(1 for p in pilares if p['llamadas'])
    aud['con_fierro'] = con
    aud['remiten'] = sum(1 for p in pilares if p['remite_a'] and not p['llamadas'])
    aud['sin_nada'] = sum(1 for p in pilares
                          if not p['llamadas'] and not p['remite_a'])
    return pilares, aud


def esquemas(pilares):
    """Cuantos pilares comparten cada juego de llamadas."""
    c = collections.Counter()
    for p in pilares:
        if not p['llamadas']:
            continue
        c[' '.join(l['texto'] for l in p['llamadas'])] += 1
    return c


def a_json(pilares):
    """Solo los que traen fierro, listos para el JSON de geometria."""
    return [p for p in pilares if p['llamadas']]
