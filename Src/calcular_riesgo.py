import re
import zipfile
import itertools
import pandas as pd
import psse34
import psspy
import pssarrays

def crear_dfax(case):
    psspy.dfax_2(
        [1,1,1],
        "{}.sub".format(case),
        "{}.mon".format(case),
        "{}.con".format(case),
        "{}.dfx".format(case)
    )
    
def correr_accc(case):
    psspy.accc_with_dsp_3(
        0.1,
        [0,0,0,1,1,1,0,0,0,0,1],
        case,
        "{}.dfx".format(case),
        "{}.acc".format(case),
        "",
        "",
        "{}.zip".format(case)
    )
    
    contingencias_isv = extraer_mapeo_zip_accc(case)
    rslt = {
        "zipfile": "{}.zip".format(case),
        "contingencies": contingencias_isv
    }
    return rslt

def extraer_mapeo_zip_accc(case):
    # Encuentro mapeo de caso incremental para cada contingencia
    zip_file_obj = zipfile.ZipFile("{}.zip".format(case), 'r')
    name_file = zip_file_obj.read('Names.phy').decode()
    strings = re.findall(r'[^\x00-\x1F\x7F-\xFF]+', name_file)[1:]
    contingency_identificator = [
        (label, isv.strip()) for label, isv in zip(strings[::2], strings[1::2])
    ]
    return contingency_identificator

def obtener_transferencias():
    "obtiene las transferencias por las lineas" 
    ierr, (i, j) = psspy.abrnint(string=["FROMNUMBER", "TONUMBER"])
    ierr, (ckt,) = psspy.abrnchar(string=["ID"])
    ierr, (flow, rate) = psspy.abrnreal(string=["MAXMVA", "RATE"])
    
    return i, j, ckt, flow, rate

def calcular_riesgo(c=1.0):
    "devuelve el riesgo y un mapeo de sobrecargas en lineas"
    sobrecarga = 0
    sobrecargas = {}
    transferencias = obtener_transferencias()
    for i, j, ckt, flow, rate in zip(*transferencias):
        sobrecargas[i, j, ckt] = max(0, flow - rate)
        sobrecarga += max(0, flow - rate)
    riesgo = sobrecarga * c
    return riesgo, sobrecargas
    
def calcular_sensibilidad(case, identificador_linea):
    "Genera una tabla con la sensibilidad para cada generador"
    ierr, (gen_buses,) = psspy.agenbusint(string="NUMBER")
    ierr, (pmax,) = psspy.agenbusreal(string="PMAX")
    gen_buses = [bus for bus, pmax in zip(gen_buses, pmax) if pmax > 0]

    results = []
    for gen_bus in gen_buses:
        i, j, ckt = identificador_linea
        rslt = pssarrays.sensitivity_flow_to_mw(
            ibus=i, jbus=j, ckt=ckt,
            mainsys=case,
            netmod="ac",
            dfxfile="{}.dfx".format(case),
            brnflowtyp="mva",
            transfertyp="import",
            oppsystyp="subsystem",
            dispmod=1,
            oppsys="OPPOSING_GEN{}".format(gen_bus)
        )
        # cambio de extended bus a numero
        for extend_bus_name in rslt['genvalues'].keys():
            bus_num = int(extend_bus_name.strip().split(" ")[0])
            rslt['genvalues'][bus_num] = rslt['genvalues'].pop(extend_bus_name)    
        
        # genero tabla de datos
        df = pd.DataFrame(rslt['genvalues']).T
        df["gen"] = df.index        
        df["oppsys"] = gen_bus
        results.append(df)
        
    return pd.concat(results, axis=0).reset_index(drop=True)

## MAIN
CASE = "IEEE14"
SAV_FILE = "{}.sav".format(CASE)
COST_FILE = "{}.cost".format(CASE)
ZIP_FILE = "{}.zip".format(CASE)

# -----------------------------------------------------------------------------
psspy.case(SAV_FILE)    
#correr_despacho_economico(COST_FILE, cuts=[])    
crear_dfax(CASE)
rslt = correr_accc(CASE) 

# ------------------------------------------------------------------------------
riesgo_total = 0
sensibilidades = []
for con_id, con_isv in rslt["contingencies"]:
    psspy.getcontingencysavedcase(ZIP_FILE, con_isv)
    assert psspy.solved() == 0 # TODO: poner un factor por caso no resuelto
    riesgo, sobrecargas = calcular_riesgo()    
    riesgo_total += riesgo

    
    lineas_sobrecargadas = [identifier for identifier, sobrecarga in sobrecargas.items() if sobrecarga > 0.0]
    
    for identificador_linea in lineas_sobrecargadas:
        sensibilidad = calcular_sensibilidad(CASE, identificador_linea)
        sensibilidad = sensibilidad[sensibilidad.gen == sensibilidad.oppsys]
        sensibilidad['con_id'] = con_id
        sensibilidades.append(sensibilidad)
    
cuts = pd.concat(sensibilidades, axis=0).reset_index(drop=True)
# -----------------------------------------------------------------------------
#psspy.case(CASE)

#calcular_riesgo()

