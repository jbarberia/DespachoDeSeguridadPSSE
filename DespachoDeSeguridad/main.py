import os
import psse34
import psspy
import pandas as pd
psspy.psseinit()


from DespachoDeSeguridad.functions import crear_dfax, correr_accc, calcular_riesgo
from DespachoDeSeguridad.sensitivity_reports import get_sensitivities

# Set names and PATH
CASE = "IEEE14"
FOLDER = "Caso IEEE14"
os.chdir(f"{FOLDER}")

# Read case
ierr = psspy.case(CASE + ".sav")
assert ierr == 0

# Economic Dispatch
# despacho_economico(CASE + ".cost", cuts=[])

# Generate DFAX and ACCC
crear_dfax(CASE)
rslt = correr_accc(CASE)

# Calcular sobrecargas
riesgo_total = 0
sensibilidades = []
for con_id, con_isv in rslt["contingencies"]:   
    psspy.getcontingencysavedcase(CASE + ".zip", "InitCase")
    psspy.getcontingencysavedcase(CASE + ".zip", con_isv)
    # assert psspy.solved() == 0
    if not psspy.solved() == 0:
        continue
    riesgo, sobrecargas = calcular_riesgo()    
    riesgo_total += riesgo
    
    lineas_sobrecargadas = [identifier for identifier, sobrecarga in sobrecargas.items() if sobrecarga > 0.0]
    sensitivities = get_sensitivities(CASE, con_id.strip())
    sensitivities = sensitivities.set_index(["BUSI", "BUSJ", "CKT"])
    sensitivities = sensitivities.loc[lineas_sobrecargadas]

    if not sensitivities.empty():
        # TODO armar cortes
        cuts = pd.concat(sensibilidades, axis=0).reset_index(drop=True)


