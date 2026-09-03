# -*- coding: utf-8 -*-
r"""
================================================================
 comun/contrato.py  -  EL FORMATO NEUTRO DEL MODELO
================================================================
 Define que es un "modelo" para este proyecto, independiente del
 edificio que sea y de que planos haya salido.

 ----------------------------------------------------------------
 LAS TRES ETAPAS
 ----------------------------------------------------------------
     planos DXF
        |  ingesta                    (propia de cada edificio)
        v
     data/geometria/<edificio>.json   lo que DICE el plano
        |  armado                     (propia de cada edificio)
        v
     data/modelo/<edificio>.json      <-- ESTE ARCHIVO lo define
        |  calculo                    (comun/calcular.py, uno solo)
        v
     data/resultados/<edificio>_<caso>.json
        |  vista
        v
     data/unity/<edificio>.json       lo que dibuja el visor

 ----------------------------------------------------------------
 POR QUE LA ETAPA DEL MEDIO ES LA IMPORTANTE
 ----------------------------------------------------------------
 En data/modelo/ un edificio ya no es "planos 2024_22" ni "eje A'":
 es una lista de nodos y elementos en coordenadas absolutas. A ese
 nivel los dos edificios del grupo hablan el mismo idioma, y unirlos
 deja de ser fusionar dos programas y pasa a ser un script que:

     1. aplica el calce entre los dos sistemas de coordenadas
     2. renumera los tags para que no choquen
     3. decide que pasa en la junta de dilatacion

 Y la etapa de calculo corre sobre el conjunto SIN CAMBIAR UNA LINEA,
 porque no sabe de que edificio viene lo que le pasaron.

 ----------------------------------------------------------------
 QUE ES ESTRUCTURA Y QUE ES DIBUJO
 ----------------------------------------------------------------
 La regla: si sacarlo cambia el resultado del analisis, es
 estructura. Si solo cambia como se ve, es vista.

     estructura   secciones, nodos, elementos, diafragmas,
                  brazos rigidos, casos de carga, material
     vista        areas tributarias (los poligonos), el resumen,
                  y los ux/uy/uz precalculados de cada nodo

 Los poligonos tributarios son vista aunque de ellos SALGA la carga:
 lo que entra al analisis es la carga distribuida ya calculada, no el
 poligono. El poligono viaja para poder mirarlo en Unity y para que
 las verificaciones puedan contrastar w*L contra q*A.
================================================================
"""
from __future__ import annotations

import io
import json
import os

import rutas

# Las claves que definen la estructura. Lo que no este aca es vista.
CLAVES_ESTRUCTURA = (
    'info',
    'material',
    'secciones',
    'nodos',
    'elementos',
    'diafragmas',
    'brazos_rigidos',
    'casos_de_carga',
)

# Campos de un nodo que son resultado, no dato: se van a la vista.
CAMPOS_RESULTADO_NODO = ('ux', 'uy', 'uz')

# Lo minimo que tiene que traer un modelo para poder resolverse.
OBLIGATORIAS = ('secciones', 'nodos', 'elementos')


# ============================================================
# SEPARAR Y UNIR
# ============================================================
def separar(completo: dict) -> tuple[dict, dict]:
    """
    Parte un diccionario completo en (estructura, vista).

    El diccionario completo es el que arma cada edificio y el que
    consume Unity. La estructura es lo que se guarda en data/modelo/ y
    lo unico que necesita el solver.
    """
    estructura = {}
    for k in CLAVES_ESTRUCTURA:
        if k in completo:
            estructura[k] = completo[k]

    # Los nodos van sin sus desplazamientos: esos son resultado.
    if 'nodos' in estructura:
        estructura['nodos'] = [
            {k: v for k, v in n.items() if k not in CAMPOS_RESULTADO_NODO}
            for n in estructura['nodos']
        ]

    vista = {k: v for k, v in completo.items() if k not in CLAVES_ESTRUCTURA}
    return estructura, vista


def unir(estructura: dict, vista: dict = None,
         resultados: dict = None) -> dict:
    """
    Rehace el diccionario completo. Si vienen resultados, sus
    desplazamientos se vuelven a pegar en cada nodo, que es como los
    espera el visor.
    """
    completo = dict(estructura)
    if vista:
        completo.update(vista)

    if resultados:
        desp = {int(d['id']): d for d in resultados.get('desplazamientos', [])}
        nodos = []
        for n in completo.get('nodos', []):
            n = dict(n)
            d = desp.get(int(n['id']))
            if d:
                n['ux'], n['uy'], n['uz'] = d['ux'], d['uy'], d['uz']
            nodos.append(n)
        completo['nodos'] = nodos
    return completo


# ============================================================
# VALIDAR
# ============================================================
def validar(modelo: dict) -> list[str]:
    """
    Revisa que el modelo se pueda resolver. Devuelve la lista de
    problemas; vacia si esta sano.

    Lo que se revisa es lo que rompe EN SILENCIO:

      - Un elemento que apunta a un nodo que no existe: OpenSees tira
        un error claro, ese no es el problema.
      - Una CARGA que apunta a un elemento que ya no existe: OpenSees
        avisa por consola y DESCARTA la carga. El analisis "funciona"
        con menos peso del que uno cree y el equilibrio cierra igual,
        porque la carga descartada nunca entro. Ese si hay que cazarlo.
      - Un diafragma cuyos nodos no estan todos a la misma cota.
      - Un nodo maestro de diafragma sin sus GDL fuera del plano
        fijados: el piso se puede ir de viaje.
    """
    problemas = []

    for k in OBLIGATORIAS:
        if k not in modelo:
            problemas.append('falta la clave obligatoria %r' % k)
    if problemas:
        return problemas

    nodos = {int(n['id']): n for n in modelo['nodos']}
    elementos = {int(e['id']): e for e in modelo['elementos']}
    secciones = {s['nombre'] for s in modelo['secciones']}

    for e in modelo['elementos']:
        for extremo in ('n1', 'n2'):
            if int(e[extremo]) not in nodos:
                problemas.append('el elemento %s apunta al nodo %s, que no existe'
                                 % (e['id'], e[extremo]))
        if e.get('seccion') and e['seccion'] not in secciones:
            problemas.append('el elemento %s usa la seccion %r, que no esta declarada'
                             % (e['id'], e['seccion']))

    for caso in modelo.get('casos_de_carga', []):
        n = caso.get('nombre', '?')
        for c in caso.get('cargas_nodales', []):
            if int(c['nodo']) not in nodos:
                problemas.append('caso %s: carga sobre el nodo %s, que no existe '
                                 '(OpenSees la descartaria en silencio)'
                                 % (n, c['nodo']))
        for c in caso.get('cargas_distribuidas', []):
            if int(c['elemento']) not in elementos:
                problemas.append('caso %s: carga distribuida sobre el elemento %s, '
                                 'que no existe (OpenSees la descartaria en '
                                 'silencio)' % (n, c['elemento']))

    for d in modelo.get('diafragmas', []):
        maestro = int(d['nodo_maestro'])
        if maestro not in nodos:
            problemas.append('diafragma con maestro %s, que no existe' % maestro)
            continue
        z = nodos[maestro].get('z')
        for s in d.get('nodos', []):
            if int(s) not in nodos:
                problemas.append('diafragma %s: el esclavo %s no existe' % (maestro, s))
            elif abs(nodos[int(s)].get('z', z) - z) > 1e-6:
                problemas.append('diafragma %s: el esclavo %s esta a otra cota '
                                 '(%.4f vs %.4f)'
                                 % (maestro, s, nodos[int(s)]['z'], z))

    for b in modelo.get('brazos_rigidos', []):
        for extremo in ('maestro', 'esclavo'):
            if int(b[extremo]) not in nodos:
                problemas.append('brazo rigido: el nodo %s no existe' % b[extremo])

    return problemas


# ============================================================
# LEER Y ESCRIBIR
# ============================================================
def guardar_modelo(nombre: str, estructura: dict) -> str:
    """Escribe data/modelo/<nombre>.json. Devuelve la ruta."""
    ruta = rutas.asegurar(rutas.modelo(nombre))
    with io.open(ruta, 'w', encoding='utf-8') as f:
        json.dump(estructura, f, indent=1, ensure_ascii=False)
    return ruta


def cargar_modelo(nombre: str) -> dict:
    """Lee data/modelo/<nombre>.json."""
    ruta = rutas.modelo(nombre)
    if not os.path.isfile(ruta):
        raise FileNotFoundError(
            'no existe %s.\nArmalo primero: python edificios/%s/armar.py'
            % (ruta, nombre))
    with io.open(ruta, encoding='utf-8') as f:
        return json.load(f)


def guardar_resultados(nombre: str, caso: str, res: dict) -> str:
    """Escribe data/resultados/<nombre>_<caso>.json. Devuelve la ruta."""
    ruta = rutas.asegurar(rutas.resultados(nombre, caso))
    with io.open(ruta, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    return ruta


def cargar_resultados(nombre: str, caso: str) -> dict:
    """Lee data/resultados/<nombre>_<caso>.json."""
    ruta = rutas.resultados(nombre, caso)
    with io.open(ruta, encoding='utf-8') as f:
        return json.load(f)


def resumen(modelo: dict) -> str:
    """Una linea con el tamano del modelo, para los mensajes."""
    tipos = {}
    for e in modelo.get('elementos', []):
        tipos[e.get('tipo', '?')] = tipos.get(e.get('tipo', '?'), 0) + 1
    detalle = ', '.join('%d %s' % (v, k) for k, v in sorted(tipos.items()))
    return ('%d nodos, %d elementos (%s), %d secciones, %d diafragmas, %d caso(s)'
            % (len(modelo.get('nodos', [])), len(modelo.get('elementos', [])),
               detalle, len(modelo.get('secciones', [])),
               len(modelo.get('diafragmas', [])),
               len(modelo.get('casos_de_carga', []))))
