"""Comprobacion simple de la transferencia de carga Q."""

import json
import re
from pathlib import Path


# La raiz permite ejecutar el script desde cualquier carpeta.
RAIZ = Path(__file__).resolve().parents[1]

# Leemos q_Q directamente desde el modelo estructural.
codigo = (RAIZ / "edificios/ingenieria/benchmark_3d.py").read_text()
q_Q = float(re.search(r"\bw_live_val\s*=\s*([-+0-9.eE]+)", codigo).group(1))

with (RAIZ / "data/modelo/ingenieria.json").open(encoding="utf-8") as archivo:
    modelo = json.load(archivo)

vigas = [
    elemento
    for elemento in modelo["elementos"]
    if elemento["tipo"].startswith("viga") and elemento["area_tributaria"] > 0
]
suma_areas = sum(viga["area_tributaria"] for viga in vigas)
Q_transferida = q_Q * suma_areas

with (RAIZ / "data/resultados/ingenieria_Q.json").open(encoding="utf-8") as archivo:
    resultados = json.load(archivo)

suma_reacciones = sum(reaccion["fz"] for reaccion in resultados["reacciones"])
error_absoluto = abs(Q_transferida - suma_reacciones)
error_relativo = error_absoluto / abs(Q_transferida)

print(f"q_Q: {q_Q:.4f} kN/m2")
print(f"Numero de vigas: {len(vigas)}")
print(f"Suma de areas tributarias: {suma_areas:.4f} m2")
print(f"Q transferida: {Q_transferida:.4f} kN")
print(f"Suma de reacciones verticales: {suma_reacciones:.4f} kN")
print(f"Error absoluto: {error_absoluto:.6f} kN")
print(f"Error relativo: {error_relativo * 100:.6f} %")
print("Resultado: OK" if error_relativo < 0.0001 else "Resultado: REVISAR")
