# -*- coding: utf-8 -*-
r"""
================================================================
 comun/rutas.py  -  DONDE ESTA CADA COSA
================================================================
 Un solo archivo sabe como esta ordenado el repositorio. Todos los
 demas se lo preguntan a el.

 ----------------------------------------------------------------
 POR QUE EXISTE
 ----------------------------------------------------------------
 Antes cada script calculaba la raiz contando `os.path.dirname`:

     _RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

 Eso funciona hasta que el archivo cambia de carpeta -- y entonces
 apunta un nivel mas arriba o mas abajo SIN FALLAR: simplemente
 escribe el JSON en el lugar equivocado, o lee uno viejo que quedo
 en la ubicacion anterior. El sintoma aparece mucho despues, en
 Unity, como un modelo que "no se actualiza".

 Aca la raiz se busca SUBIENDO hasta encontrar la marca del
 repositorio, asi que no depende de la profundidad del que pregunta.

 ----------------------------------------------------------------
 COMO SE USA
 ----------------------------------------------------------------
 Tres lineas al principio del script, sea cual sea su carpeta:

     import os, sys
     sys.path.insert(0, os.path.join(RAIZ_CALCULADA, 'comun'))
     import rutas

 o, mas comodo, el ayudante que hace las tres de una:

     from comun.rutas import ...        # si la raiz esta en sys.path

 En la practica cada script usa `entrar()`, que sube desde su
 propia ubicacion hasta la raiz, la deja en sys.path y devuelve el
 modulo ya listo:

     import sys, os
     sys.path.insert(0, ...)  # ver la plantilla en cualquier script

 ----------------------------------------------------------------
 EL ORDEN DEL REPOSITORIO
 ----------------------------------------------------------------
     edificios/ingenieria/   el edificio de Ingenieria (planos 2017_67)
     edificios/lt2/          el LT2                    (planos 2024_22)
     edificios/conjunto/     los dos unidos por la junta de dilatacion
     comun/                  lo que comparten: contrato, solver, servidor
     benchmark/              el benchmark de la Semana 1 (validado c/SAP2000)
     data/geometria/         lo que DICE el plano
     data/modelo/            el modelo listo para calcular
     data/resultados/        lo que OpenSees calculo
     data/unity/             lo que consume el visor
================================================================
"""
from __future__ import annotations

import os
import sys

# La marca de la raiz: cualquiera de estas sirve. `.git` es la natural,
# pero un ZIP descargado de GitHub no la trae, y ahi salva el README.
MARCAS = ('.git', 'setup.ps1')


def _subir_hasta_la_raiz(desde: str) -> str:
    """Sube por el arbol de carpetas hasta encontrar la marca del repo."""
    d = os.path.dirname(os.path.abspath(desde))
    while True:
        if any(os.path.exists(os.path.join(d, m)) for m in MARCAS):
            return d
        padre = os.path.dirname(d)
        if padre == d:
            # No se encontro la marca: se cae a la ubicacion de este
            # archivo, que por construccion esta en comun/.
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        d = padre


RAIZ = _subir_hasta_la_raiz(__file__)

# --- las carpetas del pipeline ---
GEOMETRIA = os.path.join(RAIZ, 'data', 'geometria')
MODELO = os.path.join(RAIZ, 'data', 'modelo')
RESULTADOS = os.path.join(RAIZ, 'data', 'resultados')
UNITY = os.path.join(RAIZ, 'data', 'unity')

# --- las carpetas de codigo ---
COMUN = os.path.join(RAIZ, 'comun')
EDIFICIOS = os.path.join(RAIZ, 'edificios')
BENCHMARK = os.path.join(RAIZ, 'benchmark')
REPORTS = os.path.join(RAIZ, 'reports')

# --- Unity ---
UNITY_PROYECTO = os.path.join(RAIZ, 'unity')
STREAMING = os.path.join(UNITY_PROYECTO, 'Assets', 'StreamingAssets')


def edificio(nombre: str) -> str:
    """La carpeta de codigo de un edificio: 'lt2', 'ingenieria', 'conjunto'."""
    return os.path.join(EDIFICIOS, nombre)


def geometria(nombre: str) -> str:
    """data/geometria/<nombre>.json -- lo que dice el plano."""
    return os.path.join(GEOMETRIA, nombre + '.json')


def modelo(nombre: str) -> str:
    """data/modelo/<nombre>.json -- el modelo listo para calcular."""
    return os.path.join(MODELO, nombre + '.json')


def resultados(nombre: str, caso: str) -> str:
    """data/resultados/<nombre>_<caso>.json -- lo que OpenSees calculo."""
    return os.path.join(RESULTADOS, '%s_%s.json' % (nombre, caso))


def unity(nombre: str) -> str:
    """data/unity/<nombre>.json -- lo que consume el visor."""
    return os.path.join(UNITY, nombre + '.json')


def asegurar(ruta: str) -> str:
    """Crea la carpeta que contiene `ruta` si no existe. Devuelve `ruta`."""
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    return ruta


def en_sys_path(*carpetas: str) -> None:
    """Deja estas carpetas al principio de sys.path, sin repetir."""
    for c in reversed(carpetas):
        if c not in sys.path:
            sys.path.insert(0, c)


def entrar(archivo: str, *extra: str) -> None:
    """
    Prepara sys.path para un script que vive en cualquier carpeta del
    repositorio: deja `comun/` y la carpeta del propio script listas
    para importar, mas las que se pidan.

        import os, sys
        sys.path.insert(0, <ruta a comun>)
        from rutas import entrar; entrar(__file__)
    """
    en_sys_path(COMUN, os.path.dirname(os.path.abspath(archivo)), *extra)


if __name__ == '__main__':
    print('RAIZ       ', RAIZ)
    for n in ('GEOMETRIA', 'MODELO', 'RESULTADOS', 'UNITY', 'COMUN',
              'EDIFICIOS', 'BENCHMARK', 'STREAMING'):
        v = globals()[n]
        print('%-11s %s   %s' % (n, v, '' if os.path.isdir(v) else '(no existe aun)'))
