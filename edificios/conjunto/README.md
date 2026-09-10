# El conjunto — los dos cuerpos unidos

Los dos modelos describen **el mismo edificio en dos etapas**: comparten
las seis cotas de piso (−7.97 a +11.83, 3.96 m entre niveles) y los
ejes numerados 1, 2 y 3, y los separa una junta de dilatación justo
después de la caja de ascensores del LT2. Cada plano refiere el otro
cuerpo como "etapa anterior" / "etapa nueva".

```
python edificios\conjunto\armar.py           une data/modelo/lt2 + ingenieria
python comun\calcular.py conjunto            resuelve G, Q, EX, EY
python edificios\conjunto\exportar_unity.py  data/unity/conjunto.json
python edificios\conjunto\verificar_conjunto.py
python comun\lanzar_unity.py app conjunto --pantalla-completa
```

## `calce.json` — la transformación entre los dos planos

Cada juego de planos está dibujado en su propio marco. `calce.json`
declara, por cuerpo, `dx`, `dy`, `dz` y el giro, **con cómo se midió
cada uno**:

| | valor | de dónde sale |
|---|---|---|
| `dy` | 36.904 | medido sobre los ejes 1, 2 y 3, que ambos planos comparten; los tres dan lo mismo a cuatro decimales |
| `dz` | −7.97 | Ingeniería está en alturas relativas, el LT2 en cotas reales |
| `dx` | −35.082 | **derivado** de las caras: cara este del LT2 + junta declarada = cara oeste de Ingeniería |
| junta | 0.05 m, libre | supuesto; `armar.py` mide la separación real y avisa si no es la declarada |

`dx` depende del modelo del otro cuerpo y ya cambió dos veces; no hace
falta acordarse porque `armar.py` mide las caras en cada corrida.

## Qué hace `armar.py`

1. Lee los dos `data/modelo/`, aplica el calce y renumera nodos,
   elementos y secciones con un corrimiento por cuerpo, tocando los
   siete sitios donde vive un tag.
2. **Sella `E` y `G` en cada sección** con el hormigón de su propio
   cuerpo. El contrato tiene un solo `material`; sin esto el LT2
   (G35) corría con los 28 MPa del otro, un 10.6 % más blando, y el
   equilibrio cerraba igual.
3. **Mide** que las caras queden a la junta declarada, que los cuerpos
   no se solapen y que compartan las cotas de piso.
4. La junta es **libre**: ningún elemento la cruza; los dos cuerpos se
   resuelven independientes dentro del mismo modelo.

## El invariante que lo vigila

Con la junta libre, cada cuerpo dentro del conjunto tiene que dar
**exactamente** lo mismo que resuelto solo. `verificar_conjunto.py` lo
compara GDL por GDL: el LT2 da 0.00e+00 en los cuatro casos; Ingeniería
queda dentro del redondeo del servidor (7e-8 m sobre 33 mm, con el 84 %
de los GDL exactos). Es la verificación que el equilibrio no puede
hacer, y la que atrapó el error del módulo elástico.

## Números

558 nodos, 937 elementos, 10 diafragmas, 47 secciones.
G = 84 801.2 kN = 34 148.98 (LT2) + 50 652.2 (Ingeniería).
Separación cara a cara 0.050 m. 705 polígonos tributarios.
