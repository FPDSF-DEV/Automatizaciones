# -*- coding: utf-8 -*-
"""
Normalizacion de nombres de contratistas OPS.

El problema en los reportes del hospital:
  - la misma persona aparece con variantes ortograficas (RUBY/RUBI, VELOSA/VELOZA)
  - a veces el nombre viene truncado (le falta un apellido)
  - la caja varia (MAYUSCULAS, minusculas, Mixta)
  - a veces escriben primero los apellidos y luego los nombres

La cedula es el identificador confiable, asi que se agrupa por cedula y se elige
un nombre canonico por grupo. El orden nombres/apellidos se decide con un lexico
de nombres de pila reforzado con evidencia estadistica del propio corpus.
"""
import re
import unicodedata
from collections import Counter, defaultdict

# Particulas que pertenecen al apellido que las sigue.
PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "DA", "DI", "VAN", "VON", "SAN", "SANTA"}

# Marcas de razon social. Ojo: la columna clase_persona no sirve para esto,
# porque describe el vehiculo de contratacion (sindicato, cooperativa) mientras
# que nombres_apellidos sigue trayendo a la persona que presta el servicio.
MARCAS_EMPRESA = {
    "SAS", "S A S", "LTDA", "SA", "EU", "ESE", "IPS", "EPS", "UT", "SCA",
    "SINDICATO", "COOPERATIVA", "PRECOOPERATIVA", "FUNDACION", "ASOCIACION",
    "CORPORACION", "EMPRESA", "COMPANIA", "SOCIEDAD", "GREMIO", "UNION",
    "TEMPORAL", "CONSORCIO", "AGREMIACION", "SERVICIOS", "SOLUCIONES",
}

# Nombres de pila frecuentes en Colombia. Semilla del lexico; el corpus lo amplia.
NOMBRES_PILA = set("""
MARIA JOSE JUAN LUIS CARLOS JORGE ANA LUZ ANDRES DIEGO JAVIER FERNANDO MIGUEL
ANGEL RAFAEL PEDRO PABLO SANDRA PAOLA ANDREA CLAUDIA DIANA MONICA PATRICIA
ADRIANA CAROLINA CATALINA DANIELA JOHANA JOHANNA YOHANA YOHANNA LEIDY LEIDI
LEIDA LEYDA LIZETH LISETH YESICA JESSICA YURI YURANI ANGELICA ALEJANDRA
NATALIA VIVIANA LORENA MILENA MARCELA GLORIA MARTHA MARTA ROSA ELENA ISABEL
ELIZABETH ELISABETH BEATRIZ CONSUELO ESPERANZA MERCEDES CRISTINA CECILIA
TERESA CARMEN DOLORES VICTORIA ALBA AMPARO NUBIA NELLY OLGA STELLA YOLANDA
EDGAR EDWIN OSCAR OMAR NELSON WILSON WILLIAM JAIRO JAIME GERMAN GUSTAVO
HERNAN HUGO IVAN JULIAN JULIO LEONARDO MANUEL MAURICIO RICARDO ROBERTO
SERGIO VICTOR ALVARO ARMANDO ALBERTO ALEXANDER ANTONIO ARTURO CAMILO CESAR
CRISTIAN DANIEL DAVID DIDIER EDUARDO ENRIQUE ESTEBAN FABIAN FELIPE FRANCISCO
GABRIEL GIOVANNI HAROLD HECTOR HENRY JEFFERSON JHON JOHN JONATHAN JOAQUIN
JULIANA KATHERINE KATERINE CATHERINE KAREN LADY LILIANA LINA LUISA MAGDA
MAYERLY MELISSA MIREYA NANCY NIDIA NORMA PAULA RUBY RUBI SARA SHIRLEY SILVIA
SONIA TATIANA VALENTINA VANESSA WENDY XIMENA YAMILE YENNY ZULMA ARLETH ARLET
ARLYN ARLIN HERMEDIS HERMEDYS SANTIAGO SEBASTIAN NICOLAS SAMUEL MATEO EMILIO
IGNACIO LORENZO MARLENY MARLENE MARISOL MARIBEL MAGNOLIA LUCIA LUZMILA
JAKELINE JACQUELINE YURLEY YULIETH YULI DEISY DEYSI DAISY MAIRA MAYRA
FLOR AIDA ALICIA AURA BLANCA CIELO DORA EDITH ELSA EMMA GINA GLADYS GRACIELA
HILDA INES IRMA JUDITH JULIETH LEONOR LILIA LUCERO MAGALY MARGARITA MIRIAM
MYRIAM NATHALY NATALY NOHORA PIEDAD RUTH SOFIA SUSANA VERONICA VIRGINIA
ABEL ADOLFO AGUSTIN ALEX ALFONSO ALFREDO AMANDA ANIBAL BENJAMIN BERNARDO
BRAYAN BRIAN DARIO DEIVY DILAN DUVAN EDISON EDUAR EFRAIN ELIAS
EMERSON ERIKA ERIK ESNEIDER FABIO FELIX FERNEY FIDEL FRANKLIN FREDY FREDDY
GERARDO GILBERTO GIOVANY GONZALO GUILLERMO HAROL HELBERT HERIBERTO HERNANDO
HORACIO HUMBERTO ISRAEL JADER JAIDER JEISON JEYSON JESUS JIMMY JOAN JOEL
JOSUE JUANITA KEVIN LEANDRO LEONEL LUCAS MARCO MARIO MARLON MARTIN MAXIMO
MOISES NESTOR NOEL NORBERTO ORLANDO OVIDIO RAMIRO RAMON RAUL RENE REINALDO
REY RODRIGO ROLANDO RUBEN SALOMON SAUL SIMON TOMAS URIEL VLADIMIR WALTER
WILMAR WILMER YEISON YESID ZAMIR IVONNE YVONNE IVON ANGIE ANYI YINA PAHOLA
CONSTANZA GIULIANA KEYLA ELSY EDILBERTO YANET YANETH SAHILY ZAILY KELLYS KELYS
KAROL NORALBA DORALY EDID STEFY STEPFANY YINET YINETH JHOJAN ESTIVEN ESTEFANIA
MAYERLI MAYERLY ZULEIMA ZULEIMY YULIANA YULIED DARLING DARLIN LUDY LUDIVIA
NEYLA NEIDY NEYDA MILADY MILEDY DEYANIRA DEYSSI ANDERSON ANDERSSON YAMID
JHONATAN JHOAN JHOJANNY BLADIMIR CARLINA CARLOTA CARMENZA CLEMENCIA CLARITZA
DAIRO DAGOBERTO DEIBY DERLY DERLIS DOLLY DUBERNEY ELKIN ELIECER EDUARDA
FANNY FLORALBA GENITH GLEIDY HEIDY IDALY ILIANA INGRID ISABELLA JANETH
JAZMIN JENNIFER JENNY JOHNNY JOSEFA LEONARDA LIBIA LILIBETH LORENZA LUDIVIA
MAGALI MAILEN MARELVIS MARIELA MARINA MARLEN MAURA MERCY MILDRED MIRIAN
NEIFY NELCY NEYLA NOHELIA NUBIA OFELIA OLIVA OMAIRA PASTORA PETRONA RAQUEL
ROCIO ROSALBA ROSMERY SANDRITA SILVANA SLENDY SOLANYI SORAYA SULEIMA TERESITA
TULIA URSULA VILMA VIVIAN WENDI YADIRA YAMILET YANIRA YARLEDY YENIFER YESENIA
YOLIMA YUDY YULEIMY YURANY ZORAIDA ZORAYA ELMIR SUGEYDY
""".split())

# Apellidos frecuentes en Colombia. Contrapeso de la lista anterior: un token
# aqui empuja hacia 'apellido' aunque aparezca en primera posicion.
APELLIDOS_COMUNES = set("""
RODRIGUEZ GOMEZ GONZALEZ GONZALES MARTINEZ MARTINES LOPEZ GARCIA PEREZ SANCHEZ
RAMIREZ TORRES FLOREZ FLORES RIVERA GUTIERREZ DIAZ HERNANDEZ MORENO MUÑOZ
MUNOZ ROJAS JIMENEZ SUAREZ RUIZ ALVAREZ ROMERO VARGAS CASTRO ORTIZ MORALES
DELGADO CASTILLO SILVA NUÑEZ NUNEZ MEDINA CORTES GUERRERO CARDENAS REYES
HERRERA AGUILAR MEJIA MENDOZA VELASQUEZ SALAZAR ARIAS PARRA OSORIO QUINTERO
MONTOYA RESTREPO ZAPATA GIRALDO ARANGO OCHOA BEDOYA VALENCIA HOYOS BETANCUR
CARDONA GALLEGO GRISALES LONDOÑO LONDONO ORTEGA PINEDA BOLAÑOS BOLANOS NARVAEZ
CHAVEZ CHAVES SOLARTE ERAZO BURBANO PANTOJA CAICEDO MOSQUERA RIASCOS ANGULO
VALDERRAMA CUERVO BELTRAN NIÑO NINO SIERRA PACHON FORERO CAMARGO BAUTISTA
MALAGON SANABRIA TRUJILLO PERDOMO POLANIA CHARRY CUELLAR CABRERA OLAYA LOSADA
FALLA MANRIQUE MOTTA VELOSA VELOZA CAVIEDES FONSECA CAMPOS TOLEDO VEGA
CABALLERO ZAMBRANO LIZ LIS RAMOS SASTOQUE FONTALVO ARTUNDUAGA QUINTANA
BARRERA BARRERO BARREIRA CARRIAZO FIGUEROA MOLANO CASTAÑO CASTANO GUAUÑA
MONTEALEGRE IMBACHI CUCHUMBE CAQUIMBO CARDOSO GRAFFE VICTORIA BOTELLO MAZA
CALDERON BRAVO MIRANDA ROMO REALES SAAVEDRA LASSO VANEGAS TIERRADENTRO MURCIA
NEIRA BORRERO MAZABEL VILLEGAS BURGOS AVILEZ CHAPARRO QUESADA ORDOÑEZ ORDONEZ
PEÑA PENA RIAÑO RIANO SEPULVEDA ACOSTA AVILA BARRIOS BENAVIDES BLANCO BUITRAGO
CANO CARRILLO CESPEDES CIFUENTES CONTRERAS CORDOBA CORREA CRUZ DUARTE DUQUE
ESCOBAR ESPINOSA ESTRADA FRANCO FUENTES GALINDO GALVIS GARZON GIL GUZMAN
IBARRA LARA LEON LOZANO LUNA MARIN MARQUEZ MATEUS MELO MENDEZ MONTAÑA MONTANA
MORA NAVARRO NAVAS NOVOA OSPINA OTALORA PALACIOS PARDO PAREDES PATIÑO PATINO
PENAGOS PINILLA PINTO PINZON PRADA PRIETO PULIDO QUIROGA RANGEL REY RINCON
RIOS RIVAS ROA ROBLES ROLDAN ROSAS RUBIO SAENZ SALAS SANTANA SANTOS SEGURA
SOLER SOTO TAPIERO TOVAR URREGO USECHE VALBUENA VALLEJO VASQUEZ VELANDIA
VELASCO VERA VIDAL VILLAMIL VILLANUEVA VILLAREAL ZULUAGA
""".split())


def quitar_tildes(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    )


def limpiar(texto):
    """Mayusculas sin tildes (pero conservando la Ñ), sin puntuacion."""
    if texto is None:
        return ""
    t = str(texto).upper().replace("Ñ", "\x01")   # la Ñ no es una N con tilde
    t = quitar_tildes(t)
    t = re.sub(r"[^A-Z0-9 \x01]", " ", t).replace("\x01", "Ñ")
    return re.sub(r" +", " ", t).strip()


def tokenizar(nombre):
    """Divide en tokens uniendo las particulas al apellido que las sigue."""
    crudos = limpiar(nombre).split()
    tokens, pendiente = [], []
    for tok in crudos:
        if tok in PARTICULAS:
            pendiente.append(tok)
        else:
            tokens.append(" ".join(pendiente + [tok]))
            pendiente = []
    if pendiente:
        tokens.append(" ".join(pendiente))
    return tokens


def construir_lexico(nombres):
    """
    Devuelve (pila, apellidos) para clasificar tokens.

    Deliberadamente NO aprende del orden en que vienen los nombres: esa senial
    es circular, porque es justo el orden que se quiere averiguar, y se derrumba
    si el archivo entero llega con los apellidos adelante. Se usan los lexicos
    fijos, que son invariantes a la posicion; los tokens desconocidos quedan
    neutros y no arrastran la decision.
    """
    del nombres                              # firma estable para quien la llame
    return set(NOMBRES_PILA), set(APELLIDOS_COMUNES) - NOMBRES_PILA


def es_pila(tok, pila, apellidos):
    """1.0 si es nombre de pila, 0.0 si es apellido, 0.5 si no hay evidencia."""
    if tok in pila and tok not in apellidos:
        return 1.0
    if tok in apellidos and tok not in pila:
        return 0.0
    return 0.5


def ordenar_nombre(nombre, pila, apellidos):
    """
    Devuelve (nombre_ordenado, se_invirtio).

    La senial fuerte es 'parece nombre de pila': los nombres de pila son un
    conjunto cerrado y muy repetido, mientras que los apellidos son diversos y
    casi siempre desconocidos. Asi que se compara cuanto se parece a nombre de
    pila la mitad inicial frente a la final, y solo se reordena cuando la final
    gana con holgura.
    """
    toks = tokenizar(nombre)
    n = len(toks)
    if n < 3:
        return " ".join(toks), False

    corte = n // 2                           # con 3 tokens: 1 al frente, 2 atras
    cabeza, cola = toks[:corte], toks[corte:]
    pila_cabeza = sum(es_pila(t, pila, apellidos) for t in cabeza) / len(cabeza)
    pila_cola = sum(es_pila(t, pila, apellidos) for t in cola) / len(cola)

    if pila_cola - pila_cabeza >= 0.5:
        return " ".join(cola + cabeza), True
    return " ".join(toks), False


def limpiar_display(texto):
    """
    Como limpiar(), pero CONSERVANDO las tildes. limpiar() las quita porque su
    trabajo es comparar ('MARIA' y 'MARÍA' deben coincidir); esta version es la
    que se muestra, y ahi la tilde si importa.
    """
    if texto is None:
        return ""
    t = str(texto).upper()
    t = re.sub(r"[^0-9A-ZÁÉÍÓÚÜÑ ]", " ", t)
    return re.sub(r" +", " ", t).strip()


def tokenizar_display(nombre):
    """tokenizar() sobre el texto con tildes; las particulas se cotejan sin."""
    crudos = limpiar_display(nombre).split()
    tokens, pendiente = [], []
    for tok in crudos:
        if quitar_tildes(tok) in PARTICULAS:
            pendiente.append(tok)
        else:
            tokens.append(" ".join(pendiente + [tok]))
            pendiente = []
    if pendiente:
        tokens.append(" ".join(pendiente))
    return tokens


def ordenar_nombre_display(nombre, pila, apellidos):
    """
    Como ordenar_nombre(), pero decide con los tokens sin tildes y devuelve los
    tokens con tildes: la decision necesita comparar, la salida necesita leerse.
    """
    toks = tokenizar(nombre)
    vis = tokenizar_display(nombre)
    if len(vis) != len(toks):        # desajuste raro: mejor no arriesgar la salida
        vis = toks
    n = len(toks)
    if n < 3:
        return " ".join(vis), False

    corte = n // 2
    cabeza, cola = toks[:corte], toks[corte:]
    pila_cabeza = sum(es_pila(t, pila, apellidos) for t in cabeza) / len(cabeza)
    pila_cola = sum(es_pila(t, pila, apellidos) for t in cola) / len(cola)

    if pila_cola - pila_cabeza >= 0.5:
        return " ".join(vis[corte:] + vis[:corte]), True
    return " ".join(vis), False


def capitalizar(nombre):
    """MARIA DEL CARMEN -> Maria del Carmen (particulas y conjunciones abajo)."""
    minusculas = PARTICULAS | {"Y", "E", "EN"}
    palabras = nombre.split()
    return " ".join(
        p.lower() if (p in minusculas and i > 0) else p.capitalize()
        for i, p in enumerate(palabras)
    )


def _tildes(texto):
    """Cuantas letras acentuadas tiene; desempata a favor de la mejor escrita."""
    return sum(1 for c in str(texto) if quitar_tildes(c) != c)


def _token_parecido(tok, referencia):
    """
    True si 'tok' es alguna palabra de 'referencia' escrita con una errata.

    Cubre los dos descuidos de digitacion frecuentes en estos reportes:
      - una letra cambiada o perdida: HERNA ~ HERNAN
      - un espacio que falta:         ARIELZAPATA = ARIEL + ZAPATA
    """
    if tok in referencia:
        return True
    if len(tok) >= 5 and any(len(r) >= 5 and distancia_edicion(tok, r, 1) <= 1
                             for r in referencia):
        return True
    # palabra pegada: RODRIGUEZTRUJILLO contiene RODRIGUEZ y TRUJILLO
    return any(len(r) >= 5 and r in tok for r in referencia)


def separar_familia(variantes):
    """
    Parte las grafias de una cedula en (familia, ajenas).

    familia -> la misma persona escrita de varias formas
    ajenas  -> OTRA persona a la que le digitaron esta cedula

    Se arranca de la grafia dominante -quien aparece 28 veces es el dueño de la
    cedula, no quien aparece una vez con un nombre mas largo- y la familia se
    hace crecer por pasadas: cada grafia que se suma aporta sus palabras, asi
    'ARIEL ZAPATA' alcanza a 'ARIELZAPATA QUIMBAYO' a traves de
    'ARIEL ZAPATA QUIMBAYO'. Comparar solo contra la dominante dejaba fuera esa
    cadena y partia a la persona en dos.
    """
    dominante = max(variantes.items(), key=lambda kv: (kv[1], len(tokenizar(kv[0]))))[0]
    familia = {dominante: variantes[dominante]}
    referencia = set(tokenizar(dominante))

    crecio = True
    while crecio:
        crecio = False
        for v, n in variantes.items():
            if v in familia:
                continue
            toks = set(tokenizar(v))
            if any(_token_parecido(t, referencia) for t in toks) or \
               any(_token_parecido(r, toks) for r in referencia):
                familia[v] = n
                referencia |= toks
                crecio = True

    ajenas = {v: n for v, n in variantes.items() if v not in familia}
    return familia, ajenas


def agrupar_por_parecido(variantes):
    """
    Agrupa grafias que comparten alguna palabra. Sirve para repartir las
    'ajenas' de una cedula entre las distintas personas que haya ahi metidas.
    """
    grupos = []
    for v in sorted(variantes, key=lambda x: -variantes[x]):
        toks = set(tokenizar(v))
        for g in grupos:
            if toks & g["tokens"]:
                g["variantes"][v] = variantes[v]
                g["tokens"] |= toks
                break
        else:
            grupos.append({"tokens": toks, "variantes": {v: variantes[v]}})
    return [Counter(g["variantes"]) for g in grupos]


def elegir_canonico(variantes):
    """
    variantes: Counter {nombre_crudo: frecuencia}.

    Manda la FRECUENCIA, y solo entre las grafias de esa misma persona se
    prefiere la mas completa: asi 'ZULMA VANEGAS' (5 veces) sigue cediendo ante
    'ZULMA CLARITZA VANEGAS MEDINA' (2 veces), que era el proposito original.

    Antes se ordenaba por numero de palabras ANTES que por frecuencia, y un
    nombre ajeno de 4 palabras digitado una sola vez le ganaba a la grafia
    correcta repetida 28 veces: 71 contratos quedaban a nombre de otra persona.
    """
    familia, _ = separar_familia(variantes)
    return max(
        familia.items(),
        key=lambda kv: (len(tokenizar(kv[0])), kv[1], _tildes(kv[0]), -len(kv[0])),
    )[0]


def distancia_edicion(a, b, tope=2):
    """
    Distancia de Levenshtein con corte temprano: solo interesa saber si es <=
    tope, asi que en cuanto se pasa se abandona el calculo.
    """
    if abs(len(a) - len(b)) > tope:
        return tope + 1
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1,
                              previa[j - 1] + (ca != cb)))
        if min(actual) > tope:
            return tope + 1
        previa = actual
    return previa[-1]


def es_razon_social(nombre):
    """True si el texto parece una entidad y no una persona."""
    tokens = set(limpiar(nombre).split())
    return bool(tokens & MARCAS_EMPRESA) or len(tokens) > 6


DISTANCIA_CEDULA = 2    # una errata de digitacion: digito de mas, de menos o cambiado


def _canonizar(variantes, pila, apellidos):
    """Nombre para mostrar a partir de las grafias de una identidad."""
    crudo = elegir_canonico(variantes)
    if es_razon_social(crudo):
        return capitalizar(limpiar_display(crudo)), False
    ordenado, giro = ordenar_nombre_display(crudo, pila, apellidos)
    return capitalizar(ordenado), giro


def normalizar(registros, campo_nombre="nombres_apellidos",
               campo_id="numero_cedula"):
    """
    registros: lista de dicts (o DataFrame.to_dict('records')).

    Devuelve (ids, nombres, reporte, resumen). 'ids' y 'nombres' van alineados
    con registros, una entrada por fila.

    La identidad de una persona ya NO es la cedula tal como quedo digitada,
    porque los datos traen los dos errores opuestos:

      - la misma persona con dos cedulas (una con errata) queda partida en dos
        -> se fusionan las identidades con el mismo nombre cuyas cedulas estan
           a distancia de edicion <= DISTANCIA_CEDULA
      - dos personas bajo una misma cedula quedan fundidas en una
        -> las filas cuyo nombre no comparte ninguna palabra con la grafia
           dominante pasan a una identidad aparte, '<cedula>-b2'

    Ninguna de las dos cosas altera totales de dinero ni de contratos: cambian
    a quien se le atribuyen, que es lo que alimenta el ranking de retencion.
    """
    nombres_crudos = [str(r.get(campo_nombre, "")).strip() for r in registros]
    docs = [re.sub(r"\D", "", str(r.get(campo_id, ""))) for r in registros]
    pila, apellidos = construir_lexico(
        [n for n in nombres_crudos if not es_razon_social(n)])

    por_doc = defaultdict(Counter)
    for doc, nombre in zip(docs, nombres_crudos):
        por_doc[doc][nombre] += 1

    # --- 1. Separar las cedulas que cargan a mas de una persona --------------
    id_de = {}                      # (doc, grafia) -> identidad
    variantes_de = defaultdict(Counter)
    separadas = []
    for doc, variantes in por_doc.items():
        familia, ajenas = separar_familia(variantes)
        for v, n in familia.items():
            id_de[(doc, v)] = doc
            variantes_de[doc][v] += n
        for i, grupo in enumerate(agrupar_por_parecido(ajenas), start=2):
            sub = f"{doc}-b{i}"
            for v, n in grupo.items():
                id_de[(doc, v)] = sub
                variantes_de[sub][v] += n
            separadas.append({
                "documento": doc,
                "identidad_nueva": sub,
                "grafias_separadas": " | ".join(sorted(grupo)),
                "contratos": int(sum(grupo.values())),
                "se_queda_con_la_cedula": elegir_canonico(variantes),
            })

    # --- 2. Nombre canonico de cada identidad -------------------------------
    canonico, invertidos = {}, 0
    for ident, variantes in variantes_de.items():
        canonico[ident], giro = _canonizar(variantes, pila, apellidos)
        invertidos += giro

    # --- 3. Fusionar las cedulas con errata ---------------------------------
    # Mismo nombre + cedulas casi iguales = la misma persona digitada dos veces.
    padre = {i: i for i in variantes_de}

    def raiz(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    por_nombre = defaultdict(list)
    for ident, nom in canonico.items():
        por_nombre[limpiar(nom)].append(ident)

    fusiones, homonimos = [], []
    for nom, idents in por_nombre.items():
        if len(idents) < 2:
            continue
        for i, a in enumerate(idents):
            for b in idents[i + 1:]:
                ced_a, ced_b = a.split("-")[0], b.split("-")[0]
                d = distancia_edicion(ced_a, ced_b, DISTANCIA_CEDULA)
                if d <= DISTANCIA_CEDULA and ced_a != ced_b:
                    padre[raiz(a)] = raiz(b)
                    fusiones.append({
                        "nombre": canonico[a],
                        "cedula_a": ced_a,
                        "cedula_b": ced_b,
                        "distancia": d,
                        "contratos_a": int(sum(variantes_de[a].values())),
                        "contratos_b": int(sum(variantes_de[b].values())),
                    })
                elif ced_a != ced_b:
                    homonimos.append({
                        "nombre": canonico[a],
                        "cedula_a": ced_a,
                        "cedula_b": ced_b,
                        "distancia": "> %d" % DISTANCIA_CEDULA,
                        "contratos_a": int(sum(variantes_de[a].values())),
                        "contratos_b": int(sum(variantes_de[b].values())),
                    })

    # La identidad que conserva mas contratos representa al grupo fusionado.
    grupos = defaultdict(list)
    for ident in variantes_de:
        grupos[raiz(ident)].append(ident)

    final_de, canonico_final = {}, {}
    for miembros in grupos.values():
        jefe = max(miembros, key=lambda i: (sum(variantes_de[i].values()), i))
        juntas = Counter()
        for m in miembros:
            juntas.update(variantes_de[m])
            final_de[m] = jefe
        canonico_final[jefe], _ = _canonizar(juntas, pila, apellidos)

    # --- 4. Resultado por fila ----------------------------------------------
    ids, nombres = [], []
    for doc, nombre in zip(docs, nombres_crudos):
        ident = final_de[id_de[(doc, nombre)]]
        ids.append(ident)
        nombres.append(canonico_final[ident])

    # --- 5. Auditoria --------------------------------------------------------
    reporte = []
    for doc, variantes in por_doc.items():
        if len(variantes) < 2:
            continue
        _, ajenas = separar_familia(variantes)
        reporte.append({
            "documento": doc,
            "nombre_normalizado": canonico_final[final_de[id_de[(doc, elegir_canonico(variantes))]]],
            "n_variantes": len(variantes),
            "revisar": "SI" if ajenas else "",
            "variantes_sospechosas": " | ".join(sorted(ajenas)),
            "variantes_originales": " | ".join(sorted(variantes)),
        })
    reporte.sort(key=lambda f: (f["revisar"] != "SI", -f["n_variantes"]))

    resumen = {
        "invertidos": invertidos,
        "fusiones": fusiones,
        "separadas": separadas,
        "homonimos": homonimos,
        "identidades": len(canonico_final),
        "cedulas": len(por_doc),
    }
    return ids, nombres, reporte, resumen
