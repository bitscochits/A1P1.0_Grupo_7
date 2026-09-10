# -*- coding: utf-8 -*-
r"""
================================================================
 edificios/ingenieria/enfierradura_muros.py  -  EL FIERRO DE LOS MUROS
================================================================
 El armado que armar.py le pega a cada muro del modelo, en el mismo
 contrato que escribe edificios/lt2/planos/enfierradura.py, para que
 comun/capacidad.py lea los dos edificios sin preguntar cual es.

 Correr solo, para ver lo que se adopta y de donde sale:
   python edificios/ingenieria/enfierradura_muros.py

 ----------------------------------------------------------------
 DE DONDE SALE
 ----------------------------------------------------------------
 El sistema resistente de este edificio son MUROS, y el proyecto
 2017_67 los detalla en sus once elevaciones de eje, laminas -300 a
 -310. De ahi salen 66 bloques de muro -- con espesor, malla vertical
 y malla horizontal en sus atributos -- y 211 llamadas de fierro de
 punta del tipo 'L:3+3%%C10'.

 Todo eso esta en perfiles/muros_2017_67.json, que separa lo LEIDO
 (el inventario, bloque por bloque) de lo ADOPTADO (que malla se le
 pega a cada espesor), con el respaldo escrito al lado.

 ----------------------------------------------------------------
 POR QUE POR ESPESOR Y NO MURO POR MURO
 ----------------------------------------------------------------
 La elevacion da el fierro por tramo de eje. Llevarlo a cada muro del
 modelo pide el calce geometrico elevacion -> planta, y este proyecto
 tiene once laminas con ejes secundarios (1A, 1b, Eb, Ec, Ga, H1, H2,
 IA, IB, J) que el modelo no conoce. Se asigna por ESPESOR, que es el
 dato que si comparten el plano y el modelo.

 Y calza mejor de lo que uno esperaria: los cuatro espesores del
 modelo -- 15, 20, 25 y 30 cm -- son exactamente los cuatro que traen
 los bloques, y en dos el conteo coincide (15 cm: 4 muros y 4 bloques;
 25 cm: 10 y 10). En 25 cm la malla vertical ademas es la MISMA en los
 diez bloques, asi que ahi no hay nada que elegir: es la del plano.

 ----------------------------------------------------------------
 LO QUE QUEDA SUPUESTO
 ----------------------------------------------------------------
 - En 20 y 30 cm la malla no es unica: se toma la mas repetida y el
   JSON anota cuantas la respaldan y cuales son las otras.
 - La POSICION de las barras de punta. El plano dice cuantas son, no
   en que muro del modelo. Se ponen en las dos puntas, escalonadas
   hacia adentro cada PASO_PUNTA, que es como se arma un machon.
 - El hormigon del muro corre SIN confinar en comun/capacidad.py: el
   alma no lleva estribos. Queda del lado seguro.
================================================================
"""
from __future__ import annotations

import io
import json
import os

_AQUI = os.path.dirname(os.path.abspath(__file__))
PERFIL = os.path.join(_AQUI, 'perfiles', 'muros_2017_67.json')

# Las barras de punta no van todas en el mismo punto: se escalonan
# hacia adentro, que es como queda un machon y ademas no le regala
# brazo de palanca a la seccion.
PASO_PUNTA = 0.10       # m


def cargar_perfil(ruta=PERFIL):
    with io.open(ruta, encoding='utf-8') as f:
        return json.load(f)


def _malla(texto):
    """'8a16' -> fi 8 cada 16 cm."""
    if not texto:
        return None
    d, _a, s = texto.partition('a')
    return {'diametro_mm': float(d), 'separacion_cm': float(s),
            'texto': texto}


def _barras_de_punta(largo_m, perfil):
    """
    Las de las dos puntas. 'L:3+3%%C10' son tres barras fi10 POR CARA,
    o sea seis en cada punta: en el contrato van como una cantidad por
    posicion, y comun/capacidad.py las reparte entre las dos cortinas.
    """
    b = perfil['barras_de_punta']
    d = float(b['diametro_mm'])
    rec = float(perfil.get('recubrimiento_m', 0.03))
    borde = largo_m / 2.0 - rec - d / 2000.0

    salida = []
    for signo in (-1.0, 1.0):
        for k in range(int(b['por_cara'])):
            s = signo * max(borde - k * PASO_PUNTA, 0.0)
            salida.append({'s': round(s, 4), 'cantidad': 2,
                           'diametro_mm': d, 'texto': b['texto']})
    return salida


def detalle_de(espesor_m, largo_m, perfil=None):
    """El armado de un muro de ese espesor, en el contrato del LT2."""
    perfil = perfil or cargar_perfil()
    clave = str(int(round(espesor_m * 100)))
    tipico = perfil['tipico_por_espesor'].get(clave)
    if not tipico:
        raise SystemExit(
            'no hay malla declarada para un muro de %s cm.\n'
            'Los espesores que traen las elevaciones son: %s.\n'
            'Se declara en %s.'
            % (clave, ', '.join(sorted(perfil['tipico_por_espesor'],
                                       key=int)),
               os.path.relpath(PERFIL, os.path.dirname(_AQUI))))

    return {
        'tipo': 'muro',
        'armado': 'malla',
        'espesor_m': round(espesor_m, 4),
        'largo_m': round(largo_m, 4),
        'malla_vertical': _malla(tipico['malla_vertical']),
        'malla_horizontal': _malla(tipico['malla_horizontal']),
        'capas': int(perfil.get('capas', 2)),
        'barras_de_borde': _barras_de_punta(largo_m, perfil),
        'acero': perfil.get('acero'),
        'recubrimiento_m': perfil.get('recubrimiento_m', 0.03),
        'fuente': {
            'lamina': perfil['fuente']['laminas'],
            'elevacion': 'elevaciones de eje del proyecto 2017_67',
            'eje': 'tipico por espesor',
            'texto': 'e=%s D.M. V=%s H=%s' % (clave, tipico['malla_vertical'],
                                              tipico['malla_horizontal']),
            'respaldo': tipico['respaldo_vertical'],
        },
    }


def medidas(modelo, e):
    """(espesor, largo) del muro, del elemento o de su seccion."""
    secciones = {s['nombre']: s for s in modelo.get('secciones', [])}
    s = secciones.get(e.get('seccion')) or {}
    esp = float(e.get('espesor') or s.get('espesor') or 0.0)
    largo = float(e.get('largo') or s.get('largo') or 0.0)
    return esp, largo


def aplicar(modelo, perfil=None):
    """
    Le pega su armado a cada muro del modelo. Devuelve cuantos
    quedaron con fierro.
    """
    perfil = perfil or cargar_perfil()
    n = 0
    for e in modelo.get('elementos', []):
        if e.get('tipo') != 'muro':
            continue
        esp, largo = medidas(modelo, e)
        if esp <= 0 or largo <= 0:
            raise SystemExit('el muro %s no declara espesor y largo'
                             % e.get('id'))
        e['enfierradura'] = detalle_de(esp, largo, perfil)
        n += 1
    return n


if __name__ == '__main__':
    p = cargar_perfil()
    f = p['fuente']
    print('=' * 70)
    print('  EL FIERRO DE LOS MUROS   proyecto %s' % f['proyecto'])
    print('=' * 70)
    print('  %s' % f['laminas'])
    print('  %d bloques de muro y %d llamadas de punta'
          % (f['bloques_de_muro'], f['llamadas_de_punta']))
    print()
    print('  %-8s %-8s %-10s %-18s %s'
          % ('espesor', 'vertical', 'horizontal', 'respaldo', 'otras del plano'))
    for clave in sorted(p['tipico_por_espesor'], key=int):
        t = p['tipico_por_espesor'][clave]
        print('  %5s cm %-8s %-10s %-18s %s'
              % (clave, t['malla_vertical'], t['malla_horizontal'],
                 t['respaldo_vertical'],
                 ', '.join(t['otras_verticales']) or '-'))
    print()
    b = p['barras_de_punta']
    print('  barras de punta   %s = %d fi%g por cara, en las dos puntas'
          % (b['texto'], b['por_cara'], b['diametro_mm']))
    for linea in b['_de_donde']:
        print('    %s' % linea)
