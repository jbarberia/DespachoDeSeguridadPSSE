import re
import zipfile

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
    ierr, (gen_bus,) = psspy.agenbusint(string="NUMBER")
    
    # TODO juntar genbus de a dos sin repeticion (i, j) (j, i) y crear lista generadores_participantes
    
    for gen_bus, opposing_gen_bus in generadores_participantes:
        i, j, ckt = identificador_linea
        # TODO se deberia capturar este reporte
        psspy.sensitivity_flow(
            [i,j,0,1,2],
            [0,1,0,0,0,0,1,1,opposing_gen_bus],
            [ 0.5, 0.1],
            ckt,
            ["GEN{}".format(gen_bus), ""],
            "{}.dfx".format(case)
        )
    


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

for con_id, con_isv in rslt["contingencies"]:
    psspy.getcontingencysavedcase(ZIP_FILE, con_isv)
    # assert psspy.solved() == 0 # TODO: poner un factor por caso no resuelto
    riesgo, sobrecargas = calcular_riesgo()    
    riesgo_total += riesgo
    
    lineas_sobrecargadas = [identifier for identifier, sobrecarga in sobrecargas.items() if sobrecarga > 0.0]
    for identificador_linea in lineas_sobrecargadas:
        2
        sensibilidad = calcular_sensibilidad(CASE, identificador_linea, generadores_participantes)
        
    break


# -----------------------------------------------------------------------------
#psspy.case(CASE)

#calcular_riesgo()

