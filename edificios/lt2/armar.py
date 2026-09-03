# -*- coding: utf-8 -*-
r"""
================================================================
 edificios/lt2/armar.py  -  ETAPA 2 DEL LT2: GEOMETRIA -> MODELO
================================================================
 Toma data/geometria/lt2.json (lo que dice el plano) y escribe
 data/modelo/lt2.json (el modelo listo para calcular).

 Correr:  python edificios/lt2/armar.py

 ----------------------------------------------------------------
 QUE PASA ACA ADENTRO
 ----------------------------------------------------------------
 Todo el trabajo pesado ya vive en los modulos del LT2; este archivo
 solo los encadena y guarda el resultado en el formato neutro:

     modelo_lt2.ModeloLT2().preparar()
        malla.py    los ejes de vigas se cortan entre si en sus
                    INTERSECCIONES, no donde el dibujante corto la
                    polilinea; los muros se enganchan con brazos rigidos
        panos.py    los panos son las CARAS del grafo plano de vigas +
                    muros + brazos, y el reparto a 45 grados se resuelve
                    recortando cada cara con semiplanos (Sutherland-
                    Hodgman), que reproduce exactamente los trapecios y
                    triangulos del laboratorio

     .ensamblar('G')   secciones, elementos, diafragmas rigidos y las
                       tres vias de carga: peso propio nodal, losa
                       distribuida por area tributaria, y el peso de
                       los muros como carga puntual

 ----------------------------------------------------------------
 POR QUE SE GUARDA EN VEZ DE CALCULARLO SIEMPRE
 ----------------------------------------------------------------
 Armar el modelo desde los planos toma bastante mas que resolverlo.
 Congelarlo en un JSON deja el analisis, las consultas y el visor
 partiendo del MISMO modelo, sin volver a leer un DXF -- y hace que
 unir este edificio con el de al lado sea leer dos archivos.

 La contra: si cambias la malla o los panos, hay que volver a correr
 este paso. Es una dependencia tipo `make`; el JSON guarda de que
 geometria salio para poder avisarte.
================================================================
"""
from __future__ import annotations

import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(_AQUI))
sys.path.insert(0, _AQUI)
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))

import contrato                              # noqa: E402
import rutas                                 # noqa: E402
import exportar_unity                        # noqa: E402

NOMBRE = 'lt2'


def main():
    print('=' * 68)
    print(' ARMAR EL LT2   geometria -> modelo')
    print('=' * 68)
    print('  entrada: %s' % os.path.relpath(rutas.geometria(NOMBRE), rutas.RAIZ))

    completo = exportar_unity.construir()
    estructura, vista = contrato.separar(completo)

    # De que geometria salio, para poder detectar despues que el modelo
    # quedo viejo respecto del plano.
    estructura.setdefault('info', {})
    estructura['info']['geometria'] = os.path.relpath(
        rutas.geometria(NOMBRE), rutas.RAIZ).replace(os.sep, '/')

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
