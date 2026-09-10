# -*- coding: utf-8 -*-
r"""
================================================================
 comun/verificar_todo.py  -  TODA LA SUITE, DE UNA
================================================================
 Corre cada verificacion y cada test del repo y dice cual paso.

 Correr:
   python comun/verificar_todo.py            todo
   python comun/verificar_todo.py --rapido   sin los que tardan mas de un minuto
   python comun/verificar_todo.py --solo sismo combinar

 Es el comando para antes de un commit y para el dia de la
 demostracion. Si aca sale todo en OK, el repo esta como se entrega.

 Cada entrada es un script que ya existe y que se puede correr solo:
 este archivo no verifica nada por su cuenta, solo los llama en orden
 y resume. Asi la lista de abajo es tambien el indice de que se
 comprueba y donde.
================================================================
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
import rutas                                 # noqa: E402

# (etiqueta, [argumentos], es lento)
SUITE = [
    # --- el modelo de cada edificio, contra si mismo y contra el plano
    ('planos LT2',            ['edificios/lt2/tests/test_planos.py'], False),
    ('modelo LT2',            ['edificios/lt2/verificar_lt2.py'], True),
    ('planos Ingenieria',     ['edificios/ingenieria/verificar_planos.py'], False),
    ('conjunto = cuerpos',    ['edificios/conjunto/verificar_conjunto.py'], False),
    # --- lo que cruza los edificios
    ('losa aplicada = dibujada', ['comun/verificar_tributarias.py'], False),
    ('sismo lt2',             ['comun/sismo.py', 'lt2'], False),
    ('sismo ingenieria',      ['comun/sismo.py', 'ingenieria'], False),
    ('sismo conjunto',        ['comun/sismo.py', 'conjunto'], False),
    ('superposicion lt2',     ['comun/combinar.py', 'lt2'], False),
    ('superposicion ingenieria', ['comun/combinar.py', 'ingenieria'], False),
    ('superposicion conjunto', ['comun/combinar.py', 'conjunto'], True),
    # --- el contrato con Unity y el servidor
    ('contrato Unity lt2',    ['comun/test_contrato_unity.py', 'lt2'], False),
    ('contrato Unity ingenieria', ['comun/test_contrato_unity.py', 'ingenieria'], False),
    ('contrato Unity conjunto', ['comun/test_contrato_unity.py', 'conjunto'], False),
    ('round-trip Ingenieria', ['edificios/ingenieria/tests/test_contrato_unity.py'], False),
    ('servidor',              ['test_servidor.py'], False),
    ('reanalisis',            ['edificios/lt2/tests/test_reanalisis.py'], False),
    # --- semana 3
    ('parametros',            ['semana03/parametros.py'], False),
    ('lab semana 3 ingenieria', ['semana03/lab_semana03.py'], False),
    ('lab semana 3 lt2',      ['semana03/lab_semana03.py', 'lt2'], False),
    ('capacidad ingenieria',  ['comun/capacidad.py', 'ingenieria', '18', '--pm'], False),
    ('capacidad lt2',         ['comun/capacidad.py', 'lt2', '1', '--pm'], False),
    ('RC a mano lt2',         ['semana03/verificar_rc.py', 'lt2'], True),
    ('demanda/capacidad lt2', ['semana03/demanda_capacidad.py', 'lt2', '--todas'], False),
    ('demanda/capacidad ingenieria',
                              ['semana03/demanda_capacidad.py', 'ingenieria', '--todas'], False),
    ('anexo Unity semana 3',  ['semana03/exportar_unity.py'], False),
]


def correr(args):
    t0 = time.time()
    r = subprocess.run([sys.executable] + [os.path.join(rutas.RAIZ, args[0])]
                       + args[1:], cwd=rutas.RAIZ, capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    return r.returncode == 0, time.time() - t0, (r.stdout + r.stderr)


def main(argv):
    rapido = '--rapido' in argv
    solo = None
    if '--solo' in argv:
        solo = [a.lower() for a in argv[argv.index('--solo') + 1:]
                if not a.startswith('--')]

    print('=' * 70)
    print('  SUITE COMPLETA   (%s)' % rutas.RAIZ)
    print('=' * 70)
    fallaron, n = [], 0
    for etiqueta, args, lento in SUITE:
        if rapido and lento:
            continue
        if solo and not any(s in (etiqueta + ' ' + args[0]).lower() for s in solo):
            continue
        n += 1
        ok, dt, salida = correr(args)
        print('  %-30s %-4s %5.1fs   %s'
              % (etiqueta, 'OK' if ok else 'FALLA', dt, ' '.join(args)))
        if not ok:
            fallaron.append((etiqueta, args, salida))

    print('=' * 70)
    if fallaron:
        print('  FALLARON %d de %d' % (len(fallaron), n))
        for etiqueta, args, salida in fallaron:
            print()
            print('--- %s   (%s)' % (etiqueta, ' '.join(args)))
            print('\n'.join('    ' + l for l in salida.strip().splitlines()[-12:]))
        return 1
    print('  %d de %d EN OK' % (n, n))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
