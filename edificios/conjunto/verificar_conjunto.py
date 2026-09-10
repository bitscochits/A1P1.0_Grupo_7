# -*- coding: utf-8 -*-
r"""
================================================================
 verificar_conjunto.py  -  LA JUNTA ES LIBRE, Y SE TIENE QUE NOTAR
================================================================
 Correr:  python edificios/conjunto/verificar_conjunto.py

 EL INVARIANTE. Ningun elemento cruza la junta, asi que cada cuerpo
 dentro del conjunto tiene que responder EXACTAMENTE igual que
 resuelto solo: hasta el redondeo del servidor. Cualquier cosa que
 cambie la rigidez de un cuerpo al unirlo -- seccion mal copiada,
 apoyo perdido, nodo fusionado, modulo elastico ajeno -- aparece aca
 y en ningun otro lado.

 POR QUE NO LO CAZA EL EQUILIBRIO. El contrato tiene UN material por
 modelo; el conjunto se quedaba con el del primer cuerpo y el LT2
 (G35) corria con 28 MPa: sqrt(28/35) = 0.894, desplazamientos 1.118x
 en los cinco pisos, y el corte basal cerrando igual. La carga que
 baja es la misma; cambia cuanto se deforma para bajarla. Resuelto
 sellando E y G por seccion; este archivo impide que vuelva.
================================================================
"""
from __future__ import annotations

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
CASOS = ('G', 'Q', 'EX', 'EY')
GDL = ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')

# ----------------------------------------------------------------
# CUANTO PUEDEN DIFERIR DOS CORRIDAS QUE DEBERIAN SER IGUALES
# ----------------------------------------------------------------
# Dos cosas separan al conjunto de sus cuerpos sueltos aunque el
# modelo sea el mismo:
#
#   1. el servidor devuelve los desplazamientos redondeados a 8
#      decimales -> piso absoluto de 1e-8 m;
#   2. el sistema es mas grande y se resuelve con otro ordenamiento
#      de ecuaciones, asi que el redondeo de punto flotante se
#      acumula distinto.
#
# Lo segundo NO es despreciable en este modelo: los brazos rigidos
# tienen secciones x100 y los tubos metalicos su propio E, y eso
# empeora el condicionamiento. Medido sobre el edificio de
# Ingenieria, la diferencia ESCALA CON LA MAGNITUD:
#
#     magnitud del GDL        diferencia maxima
#     menor que 1e-6          0.00e+00  (326 GDL, todos exactos)
#     1e-6 a 1e-4             1.00e-08
#     1e-4 a 1e-3             2.00e-08
#     mayor que 1e-3          7.00e-08
#
# con el 84% de los 1956 GDL en cero exacto. Esa es la firma del
# redondeo. Un error de MODELADO se ve al reves: da una RAZON casi
# constante entre las dos corridas, y toca por igual a los valores
# grandes y a los chicos -- que es exactamente como se vio el 1.1180
# del modulo elastico.
#
# Por eso la tolerancia es relativa a la magnitud del caso y no un
# absoluto: con 1e-5 el desacuerdo observado pasa con holgura de 4.7
# veces, y el error del modulo elastico -- que daba 3.7e-3 m en el
# techo -- habria fallado por cuatro ordenes de magnitud.
TOL_M = 1.5e-8
TOL_RELATIVA = 1.0e-5


def cuerpos_del_conjunto():
    """{nombre: corrimiento de tags} segun como los unio armar.py."""
    calce = armar.leer_calce() if hasattr(armar, 'leer_calce') else None
    if calce is None:
        import io
        import json
        with io.open(os.path.join(_AQUI, 'calce.json'), encoding='utf-8') as f:
            calce = json.load(f)
    return {nombre: (i + 1) * armar.PASO_DE_TAG
            for i, nombre in enumerate(calce['edificios'])}


def comparar(nombre_cuerpo, base, caso):
    """
    Los desplazamientos de un cuerpo dentro del conjunto contra los
    del mismo edificio resuelto solo. Devuelve (n, peor, donde).
    """
    solo = contrato.cargar_resultados(nombre_cuerpo, caso)
    junto = contrato.cargar_resultados(NOMBRE, caso)
    a = {int(d['id']): d for d in solo.get('desplazamientos', [])}
    b = {int(d['id']): d for d in junto.get('desplazamientos', [])}

    n, peor, donde, escala, exactos = 0, 0.0, None, 0.0, 0
    for tag, da in a.items():
        db = b.get(tag + base)
        if db is None:
            continue
        for k in GDL:
            n += 1
            y = float(db.get(k, 0.0))
            d = abs(float(da.get(k, 0.0)) - y)
            escala = max(escala, abs(y))
            if d == 0.0:
                exactos += 1
            if d > peor:
                peor, donde = d, (tag, k)
    limite = max(TOL_M, TOL_RELATIVA * escala)
    return n, peor, donde, limite, exactos


def main():
    print('=' * 70)
    print('  EL CONJUNTO CONTRA SUS DOS CUERPOS POR SEPARADO')
    print('=' * 70)

    modelo = contrato.cargar_modelo(NOMBRE)
    declarados = modelo.get('info', {}).get('cuerpos') or []
    bases = cuerpos_del_conjunto()
    print('  cuerpos: %s' % ', '.join(declarados))
    print('  la junta es libre, asi que cada uno tiene que dar lo MISMO')
    print('  que resuelto solo, no algo parecido.')

    fallos = []
    for cuerpo in declarados:
        base = bases.get(cuerpo)
        if base is None:
            fallos.append('no se sabe el corrimiento de tags de %s' % cuerpo)
            continue
        print()
        print('  %s   (tags +%d)' % (cuerpo, base))
        for caso in CASOS:
            if not (os.path.isfile(rutas.resultados(cuerpo, caso))
                    and os.path.isfile(rutas.resultados(NOMBRE, caso))):
                print('    %-3s  faltan resultados' % caso)
                continue
            n, peor, donde, limite, exactos = comparar(cuerpo, base, caso)
            ok = peor <= limite
            print('    %-3s  %5d GDL   %4d exactos (%.0f %%)   peor %.2e m   '
                  'limite %.2e   %s%s'
                  % (caso, n, exactos, 100.0 * exactos / max(n, 1), peor,
                     limite, 'ok' if ok else 'NO COINCIDE',
                     '' if ok else '   (nodo %s, %s)' % donde))
            if not ok:
                fallos.append('%s en %s: %.3e m de diferencia'
                              % (cuerpo, caso, peor))

    print()
    print('=' * 70)
    if fallos:
        print('  %d PROBLEMA(S)' % len(fallos))
        for f in fallos:
            print('    - %s' % f)
        print()
        print('  Un cuerpo que dentro del conjunto no se comporta como solo')
        print('  significa que la union le cambio algo: rigidez, apoyos o')
        print('  conectividad. El equilibrio NO lo detecta.')
        print('=' * 70)
        return 1
    print('  CADA CUERPO SE COMPORTA DENTRO DEL CONJUNTO EXACTAMENTE COMO')
    print('  RESUELTO POR SU CUENTA')
    print('=' * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
