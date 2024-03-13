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
    return sobrecarga, sobrecargas

print calcular_riesgo()