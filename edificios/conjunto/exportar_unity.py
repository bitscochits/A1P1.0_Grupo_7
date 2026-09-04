# -*- coding: utf-8 -*-
r"""
================================================================
 edificios/conjunto/exportar_unity.py  -  EL CONJUNTO EN EL VISOR
================================================================
 Junta data/modelo/conjunto.json con data/resultados/conjunto_<caso>.json
 y escribe data/unity/conjunto.json.

 Correr:
   python edificios/conjunto/armar.py            arma el modelo
   python comun/calcular.py conjunto             lo resuelve
   python edificios/conjunto/exportar_unity.py   lo deja listo para ver
   python comun/lanzar_unity.py app conjunto     lo abre

 ----------------------------------------------------------------
 NO RECALCULA NADA
 ----------------------------------------------------------------
 Todo lo que necesita ya esta en disco: el modelo lo armo armar.py y
 los desplazamientos los calculo comun/calcular.py. Este archivo solo
 los vuelve a pegar en la forma que espera el C#, que quiere los ux/uy/uz
 dentro de cada nodo.

 Es la ventaja de haber partido el pipeline en etapas: mirar el edificio
 no obliga a volver a resolverlo.

 ----------------------------------------------------------------
 LO QUE ESTA VISTA TODAVIA NO TIENE
 ----------------------------------------------------------------
 Los poligonos de area tributaria. Son VISTA, no estructura, asi que
 contrato.separar() los deja fuera de data/modelo/ y aca no hay de donde
 sacarlos. Para tenerlos habria que arrastrar la vista de cada cuerpo a
 traves de la union, remapeando tambien el elemento al que apunta cada
 poligono y moviendo sus vertices con el calce. Se puede, pero no hace
 falta para ver el edificio entero.
================================================================
"""
from __future__ import annotations

import io
import json
import math
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(_AQUI))
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))

import contrato                              # noqa: E402
import rutas                                 # noqa: E402

NOMBRE = 'conjunto'
CASO_POR_DEFECTO = 'G'


def completar_b_h(modelo):
    r"""
    Rellena `b` y `h` en las secciones que no los traen, deduciendolos de
    A, Iy e Iz. Devuelve cuantas se completaron.

    ----------------------------------------------------------------
    POR QUE HACE FALTA
    ----------------------------------------------------------------
    El visor dibuja una barra con su seccion real solo si la seccion
    trae `b` y `h` (Seccion.TienePerfil); si no, la pinta como una
    barrita fina. El modelo del LT2 los emite; el del edificio de
    Ingenieria no. En el conjunto eso se ve feo y confuso: media
    estructura con perfiles y la otra media con lineas.

    ----------------------------------------------------------------
    DE DONDE SALEN
    ----------------------------------------------------------------
    Para una seccion rectangular llena:

        A  = b * h          Iy = h * b^3 / 12       Iz = b * h^3 / 12

    de donde  b = sqrt(12*Iy/A)  y  h = sqrt(12*Iz/A).

    Se comprueba que el resultado cierre (b*h == A) y si no cierra la
    seccion se deja como estaba: una seccion que no es un rectangulo
    lleno --una viga L, por ejemplo-- no tiene un b x h que dibujar, y
    inventarle uno seria dibujar algo que no es.

    ----------------------------------------------------------------
    ES SOLO PARA DIBUJAR
    ----------------------------------------------------------------
    No toca A, Iy, Iz ni J: el analisis usa esos y no cambia en nada.
    Y se hace ACA, en el exportador del conjunto, no en el C#: el visor
    nunca deduce, solo dibuja lo que le mandan. Cuando el edificio de
    Ingenieria emita sus b/h desde su propio exportador, esta funcion
    deja de encontrar nada que completar y se puede borrar.
    """
    completadas = 0
    for s in modelo.get('secciones', []):
        if s.get('b', 0) > 1e-3 and s.get('h', 0) > 1e-3:
            continue
        A, Iy, Iz = s.get('A', 0), s.get('Iy', 0), s.get('Iz', 0)
        if min(A, Iy, Iz) <= 0:
            continue
        b = math.sqrt(12.0 * Iy / A)
        h = math.sqrt(12.0 * Iz / A)
        if abs(b * h - A) > 1e-6 * max(A, 1.0):
            continue                       # no es un rectangulo lleno
        s['b'], s['h'] = round(b, 4), round(h, 4)
        s['b_h_deducidos'] = True
        completadas += 1
    return completadas


def main(caso=CASO_POR_DEFECTO):
    modelo = contrato.cargar_modelo(NOMBRE)

    ruta_res = rutas.resultados(NOMBRE, caso)
    if not os.path.isfile(ruta_res):
        raise SystemExit(
            'No existe %s.\nResuelvelo primero:  python comun/calcular.py %s'
            % (os.path.relpath(ruta_res, rutas.RAIZ), NOMBRE))
    res = contrato.cargar_resultados(NOMBRE, caso)

    completo = contrato.unir(modelo, resultados=res)
    deducidas = completar_b_h(completo)
    completo['info'] = dict(completo.get('info', {}))
    completo['info'].update({
        'unidades': 'm, kN, kPa',
        'caso_precalculado': caso,
        'nota': ('Los dos cuerpos del edificio, calzados por '
                 'edificios/conjunto/calce.json. La junta de dilatacion es '
                 'LIBRE: ningun elemento la cruza, los dos cuerpos se '
                 'resuelven independientes.'),
    })

    eq = res.get('equilibrio', {})
    uz = min((n.get('uz', 0.0) for n in completo['nodos']), default=0.0)
    completo['resumen'] = {
        'n_nodos': len(completo['nodos']),
        'n_elementos': len(completo['elementos']),
        'n_diafragmas': len(completo.get('diafragmas', [])),
        'caso': caso,
        'carga_total_kN': eq.get('aplicada_kN'),
        'reaccion_kN': eq.get('reaccion_kN'),
        'uz_max_mm': round(uz * 1000, 4),
    }

    salida = rutas.asegurar(rutas.unity(NOMBRE))
    with io.open(salida, 'w', encoding='utf-8') as f:
        json.dump(completo, f, indent=1, ensure_ascii=False)

    print('  caso %s   %s' % (caso, contrato.resumen(completo)))
    if deducidas:
        print('  %d seccion(es) sin b/h: se dedujeron de A, Iy, Iz para '
              'poder dibujarlas' % deducidas)
    print('  UZ maximo: %.3f mm' % (uz * 1000))
    print('  -> %s  (%.2f MB)'
          % (os.path.relpath(salida, rutas.RAIZ), os.path.getsize(salida) / 1e6))
    print()
    print('  Para verlo:  python comun/lanzar_unity.py app %s' % NOMBRE)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else CASO_POR_DEFECTO))
