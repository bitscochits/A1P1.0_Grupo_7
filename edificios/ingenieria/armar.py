# -*- coding: utf-8 -*-
r"""
================================================================
 edificios/ingenieria/armar.py  -  GEOMETRIA -> MODELO
================================================================
 Escribe data/modelo/ingenieria.json: la etapa del medio del
 pipeline, la que deja el edificio en el idioma comun.

 Correr:

   python edificios/ingenieria/armar.py
   python comun/calcular.py ingenieria        <- despues

 ----------------------------------------------------------------
 POR QUE ESTE ARCHIVO ES TAN CORTO
 ----------------------------------------------------------------
 Porque no arma nada: benchmark_3d.py ya construye el modelo en
 OpenSees y export_unity.construir_json() ya devuelve el diccionario
 completo. Aca solo se separa la parte de ESTRUCTURA (nodos,
 elementos, secciones, cargas) de la de VISTA (poligonos tributarios,
 deformada precalculada) y se guarda la primera.

 O sea que la fuente de la geometria sigue siendo benchmark_3d.py,
 que es donde estan los ejes leidos de los planos. Este archivo es el
 adaptador al contrato comun, no una segunda definicion del edificio.

 ----------------------------------------------------------------
 OJO: IMPORTAR benchmark_3d CORRE EL ANALISIS COMPLETO
 ----------------------------------------------------------------
 No tiene guarda __main__: al importarlo resuelve los cuatro casos,
 verifica equilibrio y hace el round-trip por el servidor. Es lento
 pero es deliberado -- no se puede exportar un modelo sin haber
 corrido el analisis que lo respalda.
================================================================
"""

import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(_AQUI))
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))
sys.path.insert(0, _AQUI)

import contrato          # noqa: E402
import rutas             # noqa: E402

NOMBRE = 'ingenieria'


def main():
    print()
    print('=' * 64)
    print('  ARMAR EL MODELO DEL EDIFICIO DE INGENIERIA')
    print('=' * 64)
    print()
    print('  Corriendo benchmark_3d.py (4 casos + equilibrio +')
    print('  round-trip por el servidor). Toma un rato.')
    print()

    import export_unity   # noqa: E402
    completo = export_unity.construir_json()

    estructura, vista = contrato.separar(completo)

    # De donde salio, para poder detectar despues que el modelo quedo
    # viejo respecto de la fuente.
    estructura.setdefault('info', {})
    estructura['info']['geometria'] = 'edificios/ingenieria/benchmark_3d.py'

    problemas = contrato.validar(estructura)
    if problemas:
        print('\n  El modelo tiene %d problema(s):' % len(problemas))
        for p in problemas[:10]:
            print('    - %s' % p)
        return 1

    ruta = contrato.guardar_modelo(NOMBRE, estructura)

    print()
    print('  %s' % contrato.resumen(estructura))
    print('  validado: sin cargas huerfanas, sin nodos inexistentes,')
    print('            diafragmas con todos sus nodos a la misma cota')
    print('  -> %s  (%.2f MB)'
          % (os.path.relpath(ruta, rutas.RAIZ), os.path.getsize(ruta) / 1e6))
    print()
    print('  Sigue:  python comun/calcular.py %s' % NOMBRE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
