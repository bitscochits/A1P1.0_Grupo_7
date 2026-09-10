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
 LAS AREAS TRIBUTARIAS TAMBIEN VIAJAN
 ----------------------------------------------------------------
 Son VISTA, no estructura, asi que contrato.separar() las deja fuera de
 data/modelo/. Se leen de data/unity/<edificio>.json y se les aplica el
 MISMO calce y el MISMO corrimiento de tags que a los nodos y elementos.
 Sin eso los poligonos del LT2 quedarian a 35 m de su edificio, y cada
 uno apuntando a la viga equivocada del otro cuerpo.
================================================================
"""
from __future__ import annotations

import collections
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

sys.path.insert(0, _AQUI)
import armar                                 # noqa: E402

NOMBRE = 'conjunto'
CASO_POR_DEFECTO = 'G'
CALCE = os.path.join(_AQUI, 'calce.json')


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


def tributarias_del_conjunto():
    r"""
    Los poligonos tributarios de los dos cuerpos, ya calzados y
    renumerados. Devuelve (lista, cuantos aporto cada uno).

    ----------------------------------------------------------------
    DE DONDE SALEN
    ----------------------------------------------------------------
    De data/unity/<edificio>.json, no de data/modelo/. Son VISTA: no
    entran al analisis --- lo que se resuelve es la carga distribuida ya
    calculada --- asi que contrato.separar() los deja fuera del modelo.
    Viajan igual porque son lo que permite mirar en Unity de donde sale
    la carga de cada viga, y comprobar a ojo que w*L = q*A.

    ----------------------------------------------------------------
    HAY QUE MOVERLOS CON EL EDIFICIO
    ----------------------------------------------------------------
    Un poligono trae coordenadas absolutas de planta y una cota. Si se
    copian tal cual, los del LT2 quedan a 35 m de su edificio y a 8 m de
    altura del piso que cargan: se dibujan flotando en el aire, al lado.
    Se les aplica el MISMO calce que a los nodos, y el mismo corrimiento
    de tags que a los elementos --- si no, cada poligono apunta a la
    viga equivocada del otro cuerpo.
    """
    with io.open(CALCE, encoding='utf-8') as f:
        calce = json.load(f)

    salida, cuantos = [], {}
    for i, (nombre, cfg) in enumerate(calce['edificios'].items()):
        base = (i + 1) * armar.PASO_DE_TAG
        dx = float(cfg.get('dx', 0.0))
        dy = float(cfg.get('dy', 0.0))
        dz = float(cfg.get('dz', 0.0))

        ruta = rutas.unity(cfg.get('archivo', nombre))
        if not os.path.isfile(ruta):
            cuantos[nombre] = 0
            continue
        with io.open(ruta, encoding='utf-8') as f:
            vista = json.load(f)

        suyos = contrato.normalizar_poligonos(vista.get('areas_tributarias'))

        n = 0
        for a in suyos:
            a = dict(a)
            a['elemento'] = int(a['elemento']) + base
            a['z'] = round(float(a.get('z', 0.0)) + dz, 4)
            a['vertices'] = [{'x': round(v['x'] + dx, 4),
                              'y': round(v['y'] + dy, 4)}
                             for v in a['vertices']]
            salida.append(a)
            n += 1
        cuantos[nombre] = n
    return salida, cuantos


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
    contrato.sellar_ejes_locales(completo)
    completo['areas_tributarias'], por_cuerpo = tributarias_del_conjunto()
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
    print('  %d poligonos tributarios: %s'
          % (len(completo['areas_tributarias']),
             ', '.join('%s %d' % kv for kv in sorted(por_cuerpo.items()))))
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
