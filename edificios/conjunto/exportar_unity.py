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
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(_AQUI))
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))

import contrato                              # noqa: E402
import rutas                                 # noqa: E402

NOMBRE = 'conjunto'
CASO_POR_DEFECTO = 'G'


def main(caso=CASO_POR_DEFECTO):
    modelo = contrato.cargar_modelo(NOMBRE)

    ruta_res = rutas.resultados(NOMBRE, caso)
    if not os.path.isfile(ruta_res):
        raise SystemExit(
            'No existe %s.\nResuelvelo primero:  python comun/calcular.py %s'
            % (os.path.relpath(ruta_res, rutas.RAIZ), NOMBRE))
    res = contrato.cargar_resultados(NOMBRE, caso)

    completo = contrato.unir(modelo, resultados=res)
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
    print('  UZ maximo: %.3f mm' % (uz * 1000))
    print('  -> %s  (%.2f MB)'
          % (os.path.relpath(salida, rutas.RAIZ), os.path.getsize(salida) / 1e6))
    print()
    print('  Para verlo:  python comun/lanzar_unity.py app %s' % NOMBRE)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else CASO_POR_DEFECTO))
