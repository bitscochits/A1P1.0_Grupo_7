# -*- coding: utf-8 -*-
r"""
================================================================
 edificios/ingenieria/enfierradura.py  -  EL FIERRO DE LAS COLUMNAS
================================================================
 El detalle de armadura que armar.py le pega a cada columna del
 modelo, en el mismo formato que usa el LT2, para que
 comun/capacidad.py no tenga que saber de que edificio viene.

 Correr solo, para ver el detalle:
   python edificios/ingenieria/enfierradura.py

 ----------------------------------------------------------------
 POR QUE ES UN DETALLE TIPICO Y NO UNA LECTURA DEL PLANO
 ----------------------------------------------------------------
 El LT2 trae sus pilares rotulados en la elevacion (`P.70x70`, con su
 estribo debajo), y edificios/lt2/planos/enfierradura.py los lee uno a
 uno. Aca no se puede hacer lo mismo: se revisaron las 38 laminas del
 proyecto 2017_67 y NO HAY CUADRO DE PILARES. El sistema resistente
 son muros, y los elementos verticales se detallan como cabezales de
 borde en las once elevaciones de eje (-300 a -310).

 La armadura longitudinal que aparece ahi es de muro:

     L:3+3f10   L:4+4f8   L:5+5f8   L:6+6f8   L:9+9f8   L:10+10f8

 que en una seccion de 0.50 x 0.50 m daria una cuantia de 0.19 % a
 0.40 %, bajo el minimo normativo de 1 %. Es armadura repartida de muro
 delgado, no una jaula de columna.

 ----------------------------------------------------------------
 DE DONDE SALE ENTONCES
 ----------------------------------------------------------------
 Del detalle tipico de pilar de la lamina 2017_67-000, "ESQUEMA
 ESTRIBOS EN VIGAS Y PILARES", cuya geometria se midio del DXF. Las
 barras estan dibujadas como donuts y su conteo da

     y = 498   5 barras          + ----- +
     y = 472   2                 |       |     16 barras
     y = 440   2                 |       |     5 por cara
     y = 409   2                 |       |     perimetral
     y = 381   5                 + ----- +

 con estribo exterior cuadrado mas un segundo estribo en rombo que
 traba las barras de media cara. En esa lamina el parametro de los
 estribos de pilar es el NUMERO, asi que ese esquema es el "2E".

 Es la misma forma que Pedro dedujo para el LT2 desde el estribo
 (cantidad 16, por_cara 5, perimetral), llegando por otro camino.

 ----------------------------------------------------------------
 LO QUE QUEDA SUPUESTO
 ----------------------------------------------------------------
 Solo el diametro longitudinal. Se adopta phi16, que es uno de los que
 el edificio usa: en las elevaciones aparecen phi16, phi18, phi22,
 phi25 y phi28. Con 16 phi16 resulta As = 32.17 cm2 y cuantia 1.29 % en
 la seccion de 0.50 x 0.50 m: sobre el minimo y en rango normal de
 columna.

 El espaciamiento de estribos, phi10 a 10 cm, es el que aparece en las
 elevaciones de eje del propio edificio (EDf10a10, Ef10a10).
================================================================
"""
from __future__ import annotations

import copy

# Detalle tipico de pilar, lamina 2017_67-000.
DIAMETRO_LONGITUDINAL_MM = 16.0        # unico dato supuesto
BARRAS_POR_CARA = 5                    # -> 16 perimetrales
DIAMETRO_ESTRIBO_MM = 10.0
SEPARACION_ESTRIBO_CM = 10.0
RECUBRIMIENTO_M = 0.05


def detalle_tipico():
    """
    El detalle, en el contrato que consume comun/capacidad.py. Las
    claves son las mismas que escribe edificios/lt2/planos/enfierradura.py
    para que desde_elemento() lea los dos edificios sin preguntar cual es.
    """
    por_cara = BARRAS_POR_CARA
    return {
        'estribo': {
            'tipo': 'E',
            'cantidad': 1,
            'diametro_mm': DIAMETRO_ESTRIBO_MM,
            'separacion_cm': SEPARACION_ESTRIBO_CM,
            'texto': 'Ef10a10 (lamina 2017_67-000, esquema 2E)',
        },
        # El rombo interior traba las cuatro barras de media cara: una
        # traba en cada direccion.
        'trabas': [{
            'tipo': 'T',
            'cantidad': 1,
            'diametro_mm': DIAMETRO_ESTRIBO_MM,
            'separacion_cm': SEPARACION_ESTRIBO_CM,
            'texto': 'estribo en rombo (2E)',
        }],
        'trabas_longitudinales': [{
            'tipo': 'TL',
            'cantidad': 1,
            'diametro_mm': DIAMETRO_ESTRIBO_MM,
            'separacion_cm': SEPARACION_ESTRIBO_CM,
            'texto': 'estribo en rombo (2E)',
        }],
        'longitudinal': {
            'cantidad': 4 * (por_cara - 1),
            'por_cara': por_cara,
            'diametro_mm': DIAMETRO_LONGITUDINAL_MM,
            'distribucion': 'perimetral',
            'origen': ('numero y disposicion medidos de la lamina '
                       '2017_67-000; diametro SUPUESTO'),
        },
        'recubrimiento_m': RECUBRIMIENTO_M,
        'acero': {
            'designacion': 'A630-420H',
            'fy_MPa': 420.0,
            'Es_MPa': 200000.0,
            'endurecimiento': 0.01,
            '_fuente': [
                'A630-420H es el acero de refuerzo estandar en Chile.',
                'El edificio no declara otro en sus laminas generales.',
            ],
        },
        'fuente': {
            'lamina': '2017_67-000',
            'elevacion': 'ESQUEMA ESTRIBOS EN VIGAS Y PILARES',
            'eje': 'detalle tipico',
        },
        '_procedencia': [
            'El proyecto 2017_67 NO tiene cuadro de pilares: se revisaron',
            'sus 38 laminas. Este es el detalle tipico de la lamina -000,',
            'medido del DXF. Solo el diametro longitudinal es supuesto.',
        ],
    }


def aplicar(modelo, detalle=None):
    """
    Le pega el detalle tipico a cada columna del modelo, en su campo
    'enfierradura'. Devuelve cuantas columnas quedaron con fierro.
    """
    detalle = detalle or detalle_tipico()
    n = 0
    for e in modelo.get('elementos', []):
        if e.get('tipo') == 'columna':
            e['enfierradura'] = copy.deepcopy(detalle)
            n += 1
    return n


if __name__ == '__main__':
    import json
    d = detalle_tipico()
    lon = d['longitudinal']
    print('DETALLE TIPICO DE PILAR, lamina 2017_67-000')
    print('  %d phi%.0f, %d por cara, %s'
          % (lon['cantidad'], lon['diametro_mm'], lon['por_cara'],
             lon['distribucion']))
    print('  estribo phi%.0f a %.0f cm, esquema 2E (exterior + rombo)'
          % (d['estribo']['diametro_mm'], d['estribo']['separacion_cm']))
    print('  recubrimiento %.2f m, acero %s'
          % (d['recubrimiento_m'], d['acero']['designacion']))
    print()
    print(json.dumps(d, indent=2, ensure_ascii=False))
