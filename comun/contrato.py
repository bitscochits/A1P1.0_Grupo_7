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

 La EXCEPCION es el area: el poligono se queda en la vista, pero su
 area se sella dentro del elemento, en 'area_tributaria'. Es el dato
 del que salio la carga, y sin el la verificacion de conservacion
 tendria que abrir la carpeta de Unity para correr. Ver
 sellar_areas_tributarias(), mas abajo.
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

# El area de losa que le llega a un elemento. El POLIGONO es vista; este
# escalar viaja con el elemento (ver sellar_areas_tributarias).
CAMPO_AREA = 'area_tributaria'

# Bandera OPCIONAL de un caso de carga: dice si sus cargas distribuidas
# ya traen sumado el peso propio de cada barra.
#
#     G   suele traerlo:  w = A_seccion * gamma  +  q * A_trib / L
#     Q   nunca:          w = q * A_trib / L
#
# Sin esta bandera no hay forma de separar las dos partes mirando el
# JSON, y cualquier verificacion que quiera sacar la presion de la losa
# a partir de la carga aplicada tiene que ADIVINARLO. Un caso que no la
# declara no es invalido -- se infiere, y quien infiera deberia decir
# que lo hizo.
CAMPO_PESO_PROPIO = 'incluye_peso_propio'

# Cuanto pueden discrepar el area declarada por un edificio y la que
# suman sus propios poligonos, en m2. Los dos vienen redondeados a 4 y 6
# decimales, asi que 1e-3 m2 -- 10 cm2 -- es holgado para el redondeo y
# fino para cualquier error de reparto real.
TOL_AREA_M2 = 1e-3


# ============================================================
# EL AREA TRIBUTARIA, QUE ES DATO Y NO DIBUJO
# ============================================================
def areas_por_elemento(vista: dict) -> dict:
    """
    Cuanta losa le llega a cada elemento, en m2, sacado de los
    poligonos tributarios de la vista.

    Los dos edificios escriben los poligonos distinto:

        LT2          UNA entrada por elemento, con sus poligonos
                     concatenados y una lista 'tamanos'
        Ingenieria   UNA ENTRADA POR POLIGONO, asi que un elemento
                     que toma un trapecio de un pano y un triangulo
                     del otro aparece dos veces

    En los dos casos el area del elemento es la SUMA de lo que traen
    sus entradas, asi que sumar sirve para ambos sin preguntar de que
    edificio viene.
    """
    por_elemento = {}
    for a in (vista or {}).get('areas_tributarias', []) or []:
        try:
            tag = int(a['elemento'])
        except (KeyError, TypeError, ValueError):
            continue
        por_elemento[tag] = por_elemento.get(tag, 0.0) + float(a.get('area', 0.0))
    return por_elemento


def sellar_areas_tributarias(estructura: dict, vista: dict) -> list:
    """
    Deja el area tributaria de cada elemento DENTRO del elemento, en
    'area_tributaria'. Devuelve la lista de desacuerdos; vacia si el
    modelo y su dibujo dicen lo mismo.

    El poligono es vista: sacarlo no cambia el analisis. El AREA no: es
    el dato del que salio la carga y lo que permite verificar la
    conservacion sum(carga) = q*A sin abrir la carpeta de Unity. Los dos
    edificios la exponian por puertas distintas; ahora se pregunta igual
    en los dos, e.get('area_tributaria').

    No pisa un valor que el edificio ya haya puesto: si el elemento trae
    el campo se respeta y solo se COMPARA, para que no contradiga en
    silencio a su propio dibujo.
    """
    por_elemento = areas_por_elemento(vista)
    if not por_elemento:
        return []

    desacuerdos, en_el_modelo = [], set()
    for e in estructura.get('elementos', []):
        tag = int(e['id'])
        en_el_modelo.add(tag)
        del_dibujo = por_elemento.get(tag)
        if del_dibujo is None:
            continue
        if CAMPO_AREA in e:
            propia = float(e[CAMPO_AREA] or 0.0)
            if abs(propia - del_dibujo) > TOL_AREA_M2:
                desacuerdos.append(
                    'el elemento %d declara %.4f m2 de area tributaria, pero '
                    'sus poligonos suman %.4f m2'
                    % (tag, propia, del_dibujo))
            continue
        e[CAMPO_AREA] = round(del_dibujo, 6)

    # Un poligono sobre un elemento que ya no existe es el mismo error
    # que una carga huerfana, y se ve igual de poco: el visor lo dibuja
    # colgado de la nada.
    huerfanos = sorted(set(por_elemento) - en_el_modelo)
    for tag in huerfanos[:5]:
        desacuerdos.append(
            'hay poligonos tributarios sobre el elemento %d, que no esta en '
            'el modelo' % tag)
    if len(huerfanos) > 5:
        desacuerdos.append('... y %d elemento(s) mas con poligonos huerfanos'
                           % (len(huerfanos) - 5))
    return desacuerdos


# ============================================================
# LOS POLIGONOS TRIBUTARIOS, EN LA FORMA QUE LEE EL C#
# ============================================================
def normalizar_poligono(a):
    r"""
    Deja un poligono tributario como lo entiende ModeloEstructural.cs:

        vertices: [{x, y}, ...]   +   tamanos: [n1, n2, ...]

    Los dos edificios lo escribian distinto -- el LT2 ya asi, el de
    Ingenieria como vx: [...], vy: [...] -- y JsonUtility solo lee la
    primera forma, sin avisar: el poligono simplemente no se dibuja.
    'tamanos' importa porque una viga toma un TRAPECIO de un pano y un
    TRIANGULO del otro; sin la lista, el visor parte los 7 vertices por
    la mitad y dibuja lineas que no existen.

    Devuelve None si el poligono no tiene ni tres vertices.
    """
    if a.get('vertices'):
        return dict(a)
    vx, vy = a.get('vx') or [], a.get('vy') or []
    if len(vx) < 3 or len(vx) != len(vy):
        return None
    b = {k: v for k, v in a.items() if k not in ('vx', 'vy')}
    b['vertices'] = [{'x': x, 'y': y} for x, y in zip(vx, vy)]
    b['tamanos'] = [len(vx)]
    b['n_poligonos'] = 1
    return b


def normalizar_poligonos(lista):
    """Todos los poligonos de una vista, descartando los invalidos."""
    return [p for p in (normalizar_poligono(a) for a in lista or []) if p]


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

    # El area tributaria cruza la frontera: el poligono se queda en la
    # vista, el escalar viaja con el elemento. Va aca y no en el armar.py
    # de cada edificio para que ninguno se pueda olvidar.
    sellar_areas_tributarias(estructura, vista)

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
