"""La enfierradura de las columnas del Edificio de Ingenieria.

POR QUE ES UN DETALLE TIPICO Y NO UNA LECTURA DEL PLANO
------------------------------------------------------
El LT2 trae sus pilares rotulados en la elevacion (`P.70x70`, con su
estribo debajo), y `edificios/lt2/planos/enfierradura.py` los lee uno a
uno. Aca no se puede hacer lo mismo: se revisaron las 38 laminas del
proyecto 2017_67 y **no hay cuadro de pilares**. El sistema resistente
son muros, y los elementos verticales se detallan como cabezales de
borde en las once elevaciones de eje (-300 a -310).

La armadura longitudinal que aparece ahi es de muro:

    L:3+3f10   L:4+4f8   L:5+5f8   L:6+6f8   L:9+9f8   L:10+10f8

que en una seccion de 0.50 x 0.50 m daria una cuantia de 0.19 % a
0.40 %, bajo el minimo normativo de 1 %. Es armadura repartida de muro
delgado, no una jaula de columna.

DE DONDE SALE ENTONCES
----------------------
Del detalle tipico de pilar de la lamina 2017_67-000, "ESQUEMA ESTRIBOS
EN VIGAS Y PILARES", cuya geometria se midio directamente del DXF: las
barras estan dibujadas como donuts y su conteo da

    y = 498   5 barras          + ----- +
    y = 472   2                 |       |     16 barras
    y = 440   2                 |       |     5 por cara
    y = 409   2                 |       |     perimetral
    y = 381   5                 + ----- +

con estribo exterior cuadrado mas un segundo estribo en rombo que traba
las barras de media cara. En esa lamina el parametro de los estribos de
pilar es el NUMERO, asi que ese esquema es el "2E".

Es la misma forma que Pedro dedujo para el LT2 desde el estribo
(`cantidad 16, por_cara 5, perimetral`), llegando por otro camino.

LO QUE QUEDA SUPUESTO
---------------------
Solo el diametro longitudinal. Se adopta phi16, que es uno de los que el
edificio usa: en las elevaciones aparecen phi16, phi18, phi22, phi25 y
phi28. Con 16 phi16 resulta As = 32.17 cm2 y cuantia 1.29 % en la
seccion de 0.50 x 0.50 m, sobre el minimo y en rango normal de columna.

El espaciamiento de estribos, phi10 a 10 cm, es el que aparece en las
elevaciones de eje del propio edificio (`EDf10a10`, `Ef10a10`).

Uso:
    python edificios/ingenieria/enfierradura.py        # parchea el JSON
"""

import json
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELO = os.path.join(_RAIZ, "data", "modelo", "ingenieria.json")

# Detalle tipico de pilar, lamina 2017_67-000.
DIAMETRO_LONGITUDINAL_MM = 16.0        # unico dato supuesto
BARRAS_POR_CARA = 5                    # -> 16 perimetrales
DIAMETRO_ESTRIBO_MM = 10.0
SEPARACION_ESTRIBO_CM = 10.0
RECUBRIMIENTO_M = 0.05


def detalle_tipico():
    """El mismo contrato que usa edificios/lt2, para que
    comun/capacidad.py no tenga que distinguir de que edificio viene."""
    por_cara = BARRAS_POR_CARA
    return {
        "estribo": {
            "tipo": "E",
            "cantidad": 1,
            "diametro_mm": DIAMETRO_ESTRIBO_MM,
            "separacion_cm": SEPARACION_ESTRIBO_CM,
            "texto": "Ef10a10 (lamina 2017_67-000, esquema 2E)",
        },
        # El rombo interior traba las cuatro barras de media cara: una
        # traba en cada direccion.
        "trabas": [{
            "tipo": "T",
            "cantidad": 1,
            "diametro_mm": DIAMETRO_ESTRIBO_MM,
            "separacion_cm": SEPARACION_ESTRIBO_CM,
            "texto": "estribo en rombo (2E)",
        }],
        "trabas_longitudinales": [{
            "tipo": "TL",
            "cantidad": 1,
            "diametro_mm": DIAMETRO_ESTRIBO_MM,
            "separacion_cm": SEPARACION_ESTRIBO_CM,
            "texto": "estribo en rombo (2E)",
        }],
        "longitudinal": {
            "cantidad": 4 * (por_cara - 1),
            "por_cara": por_cara,
            "diametro_mm": DIAMETRO_LONGITUDINAL_MM,
            "distribucion": "perimetral",
            "origen": ("numero y disposicion medidos de la lamina "
                       "2017_67-000; diametro SUPUESTO"),
        },
        "recubrimiento_m": RECUBRIMIENTO_M,
        "acero": {
            "designacion": "A630-420H",
            "fy_MPa": 420.0,
            "Es_MPa": 200000.0,
            "endurecimiento": 0.01,
            "_fuente": [
                "A630-420H es el acero de refuerzo estandar en Chile.",
                "El edificio no declara otro en sus laminas generales.",
            ],
        },
        "_procedencia": [
            "El proyecto 2017_67 NO tiene cuadro de pilares: se revisaron",
            "sus 38 laminas. Este es el detalle tipico de la lamina -000,",
            "medido del DXF. Solo el diametro longitudinal es supuesto.",
        ],
    }


def aplicar(modelo, detalle=None):
    """Le pega el detalle tipico a cada columna. Devuelve cuantas."""
    detalle = detalle or detalle_tipico()
    n = 0
    for e in modelo.get("elementos", []):
        if e.get("tipo") == "columna":
            e["enfierradura"] = json.loads(json.dumps(detalle))
            n += 1
    return n


def main():
    with open(MODELO, encoding="utf-8") as f:
        modelo = json.load(f)

    n = aplicar(modelo)
    if not n:
        raise SystemExit("no encontre columnas en el modelo")

    with open(MODELO, "w", encoding="utf-8") as f:
        json.dump(modelo, f, indent=2, ensure_ascii=False)

    d = detalle_tipico()
    lon = d["longitudinal"]
    print(f"{n} columnas con enfierradura del detalle tipico")
    print(f"  {lon['cantidad']} phi{lon['diametro_mm']:.0f}, "
          f"{lon['por_cara']} por cara, {lon['distribucion']}")
    print(f"  estribo phi{d['estribo']['diametro_mm']:.0f} a "
          f"{d['estribo']['separacion_cm']:.0f} cm, esquema 2E")
    print(f"  escrito en {MODELO}")


if __name__ == "__main__":
    sys.exit(main())
