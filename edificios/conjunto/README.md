# El conjunto — los dos edificios unidos

Todavía no está construido. Este archivo es el diseño y los datos duros
que ya sabemos, para que quien lo escriba no tenga que redescubrirlos.

---

## Qué es el conjunto, en realidad

No es un invento de organización del repo. **Son dos etapas del mismo
edificio, separadas por una junta de dilatación.**

La prueba más fuerte la dan las cotas: los dos modelos, extraídos de
juegos de planos distintos y por dos personas distintas, coinciden.

| | Ingeniería (`2017_67`) | LT2 (`2024_22`) |
|---|---|---|
| Niveles | −7.97 · −4.01 · −0.05 · +3.91 · +7.87 · +11.83 | **los mismos**, más el −8.57 de fundación |
| Altura de piso | 3.96 m | 3.96 m |

Y en los planos del LT2 la zona del otro edificio aparece rotulada como
**"ETAPA ANTERIOR"**. La ventana de extracción del LT2 la corta
justamente ahí: `xmax = 42.75`, que es **la junta de dilatación**.

---

## Lo que falta antes de poder unirlos

### 1. Que los dos edificios emitan `data/modelo/<x>.json`

El LT2 ya lo hace: `python edificios/lt2/armar.py`.

El de Ingeniería todavía no: su modelo se arma directo en OpenSees
desde constantes de Python en `benchmark_3d.py`. Necesita un
`edificios/ingenieria/armar.py` que haga lo mismo. **No hace falta
tocar `benchmark_3d.py`**: `export_unity.construir_json()` ya devuelve
el diccionario completo con nodos, elementos, secciones, diafragmas y
casos de carga. El adaptador es del orden de 30 líneas:

```python
completo = export_unity.construir_json()
estructura, vista = contrato.separar(completo)
contrato.guardar_modelo('ingenieria', estructura)
```

### 2. El calce entre los dos sistemas de coordenadas

**Este es el único dato que falta de verdad y hay que medirlo.**

En vertical ya calzan: misma cota, mismo piso. En planta **no**, porque
cada juego de planos está dibujado en el marco de su propia lámina:

| | ejes X | ejes Y |
|---|---|---|
| Ingeniería | 8.02 … 53.02 | 47.70 … 72.75 |
| LT2 | 10.96 … 43.75 | 11.05 … 37.92 |

Los rangos se solapan en X y no tienen nada que ver en Y: son
coordenadas de página, no de terreno.

Hace falta **una transformación por edificio** (traslación, y muy
posiblemente un giro de 90°, a juzgar por cómo se invierten los
rangos), calibrada sobre algo que aparezca en los **dos** juegos de
planos. Los candidatos, en orden de confianza:

1. **La junta de dilatación.** Es el mismo plano físico en los dos.
2. Un eje que aparezca rotulado igual en ambos.
3. Una esquina de fundación que las dos láminas dibujen.

Ese calce **va declarado en un JSON de perfil**, nunca escrito en el
código — igual que la ventana y las capas del ingestor. Algo así:

```json
{
  "edificios": {
    "ingenieria": { "origen": [0, 0], "giro_grados": 0 },
    "lt2":        { "origen": [dx, dy], "giro_grados": 0 }
  },
  "junta": { "plano": "x", "coord": 42.75, "tipo": "libre" }
}
```

### 3. Decidir qué pasa en la junta

Una junta de dilatación **existe para que los dos cuerpos se muevan
independientes**. Así que lo estructuralmente correcto, por defecto, es
`"tipo": "libre"`: ningún elemento cruza, y el conjunto es dos
estructuras en un mismo archivo.

Vale la pena igual, porque:

- se ve el edificio completo en el visor;
- se comprueba que los dos cuerpos **no se solapen ni dejen un hueco**
  en la junta, que es una verificación geométrica que hoy nadie hace;
- se puede sumar el peso total y contrastarlo contra el terreno;
- deja el camino abierto para el caso sísmico, donde sí importa si los
  dos cuerpos se pueden golpear (*pounding*): con la junta libre, el
  chequeo es que la suma de derivas no supere el ancho de la junta.

---

## Cómo se va a armar (el script que falta)

`edificios/conjunto/armar.py`, y no necesita saber de planos:

```
data/modelo/ingenieria.json  ─┐
                              ├─► aplicar el calce a cada uno
data/modelo/lt2.json         ─┘   renumerar tags para que no choquen
                                  concatenar nodos, elementos, casos
                                  verificar la junta
                                  ─► data/modelo/conjunto.json
```

Y a partir de ahí **no hay nada nuevo que escribir**: la etapa de
cálculo ya sirve tal cual, porque no sabe de qué edificio viene lo que
le pasan.

```bash
python comun/calcular.py conjunto
```

---

## Lo que hay que cuidar al renumerar

Los tags no se pueden reasignar sólo en la lista de nodos y elementos.
Aparecen también en:

- `elementos[].n1`, `elementos[].n2`
- `diafragmas[].nodo_maestro` y `diafragmas[].nodos`
- `brazos_rigidos[].maestro` y `.esclavo`
- `casos_de_carga[].cargas_nodales[].nodo`
- `casos_de_carga[].cargas_distribuidas[].elemento`
- `areas_tributarias[].elemento` (esto es vista, pero si queda
  apuntando mal el visor dibuja polígonos en el edificio equivocado)

Si se olvida uno de la carga, **OpenSees no falla**: avisa por consola
y **descarta la carga**. El análisis corre con menos peso del que uno
cree y el equilibrio cierra igual, porque lo descartado nunca entró.
Por eso `contrato.validar()` revisa exactamente eso, y `armar.py` del
conjunto tiene que llamarlo antes de guardar.
