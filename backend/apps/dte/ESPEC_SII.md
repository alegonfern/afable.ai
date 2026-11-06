# Especificación técnica: facturador electrónico propio en Python (Chile, SII)

Versión del documento: 2026-10-26. Alcance: DTE 33, 34, 52, 56 y 61, con envío al SII, intercambio entre contribuyentes y certificación.

## 0. Convenciones y fuentes

Cada afirmación lleva una etiqueta de fuente:

- **[OF:xxx]**: fuente oficial del SII que se leyó para escribir este documento. Abreviaturas:
  - `AUT`: autenticacion.txt, Manual Desarrollador Autenticación Automática v1.9, 2007.
  - `UPL`: envio.txt, Manual Envío Automático (Upload) v1.5, 2003.
  - `EUP`: estado_envio.txt, Consulta Estado de Upload v1.10, 2004.
  - `EDTE`: estado_dte.txt, Consulta Estado DTE v1.10, 2010.
  - `INST`: instructivo_emision.txt, Instructivo Técnico de Emisión, 15/10/2009.
  - `CERT`: manual_certificacion.txt, Manual Ambiente de Certificación, 02/02/2009.
  - `SET`: inst_set_pruebas.txt.
  - `MUES`: manual_muestras_impresas.txt v3.0, dic-2013.
  - `MOD`: modelo_operacion.txt, 2003.
  - `FDTE`: Formato DTE v2.2 del 2019-07-10, descargado a `online/fm_formato_dte.pdf`.
  - `FIC`: Formato Mensaje de Respuesta a DTE v1.0, `online/fm_formato_ic.pdf`.
  - `F19983`: Formato Recibo Ley 19.983, `online/fm_desc_19983.pdf`.
  - `IECV`: Formato Información Electrónica de Compras y Ventas v2.2, 2011, `online/formato_iecv.pdf`.
  - `WSRC`: Web Service Registro Aceptación/Reclamo v1.2, 2017, `online/ws_reclamo_v12.pdf`.
  - `XSD`: esquemas vigentes descargados el 2026-10-26 desde `https://www.sii.cl/factura_electronica/factura_mercado/schema_*.zip` y guardados en `online/fm_schema_*`. `DTE_v10.xsd` vigente tiene fecha 06/02/2026.
  - `WSDL`: los WSDL en vivo de palena/ws1, consultados el 2026-10-26.
- **[NV]**: no verificado con fuente oficial. Viene de conocimiento general o de práctica de la comunidad (LibreDTE, foros). Hay que validarlo en maullin antes de confiar en ello.

**Esquemas.** El zip local `schemas/` es de 2011. El vigente (`online/fm_schema_dte`) agrega, respecto del de 2011:
- en `IdDoc`: `TpoTranCompra`, `TpoTranVenta` (ambos después de `MntBruto`) y `TipoFactEsp` (al final);
- en `Emisor`: `RUTProveedor` y `RznSocProveedor`;
- en `Receptor/Extranjero`: `TipoDocID`;
- en `Transporte`: `PatenteCarro`;
- en `Aduana`: `FchSalida`, `HraSalida` y `FchLlegada`;
- `GeoRefEmision` y `ManejoMadera` (entre `Referencia` y `Comisiones`);
- `ImptoReten/MontoImp` pasa de `MntImpType` (entero positivo) a `ValorType` (entero con signo).

**Usar siempre el XSD vigente.**

---

## 1. Autenticación automática (semilla y token)

### 1.1 Endpoints [OF:AUT][OF:WSDL]

| Ambiente | Semilla (CrSeed) | Token (GetTokenFromSeed) |
|---|---|---|
| Certificación | `https://maullin.sii.cl/DTEWS/CrSeed.jws` (`?WSDL`) | `https://maullin.sii.cl/DTEWS/GetTokenFromSeed.jws` |
| Producción | `https://palena.sii.cl/DTEWS/CrSeed.jws` | `https://palena.sii.cl/DTEWS/GetTokenFromSeed.jws` |

- Los servicios son SOAP 1.1, RPC/encoded (Apache Axis), con `soapAction=""`.
- El manual muestra `targetNamespace` igual a la URL del `.jws`. **El WSDL en vivo declara `targetNamespace="http://DefaultNamespace"`** [OF:WSDL]. Axis suele aceptar ambos [NV]. Recomendación: usar el namespace del WSDL en vivo, o generar el cliente con zeep desde el WSDL.
- Operaciones vigentes según el WSDL en vivo:
  - CrSeed: `getSeed`, `getState`, `getVersionMayor`, `getVersionMenor` y `getVersionPatch`.
  - GetTokenFromSeed: `getToken(pszXml: string)` y las mismas `getState`/`getVersion*`.

### 1.2 getSeed [OF:AUT]

Request (no tiene parámetros):

```xml
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body><m:getSeed xmlns:m="https://palena.sii.cl/DTEWS/CrSeed.jws"/></SOAP-ENV:Body>
</SOAP-ENV:Envelope>
```

- La respuesta llega en `getSeedReturn`, un string que contiene un XML escapado (`&lt;...`). Hay que des-escaparlo y parsearlo:

```xml
<SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema">
  <SII:RESP_HDR><ESTADO>00</ESTADO></SII:RESP_HDR>
  <SII:RESP_BODY><SEMILLA>000002360958</SEMILLA></SII:RESP_BODY>
</SII:RESPUESTA>
```

- Estados: `00` = OK; `-1` = error (no se registró línea en el archivo de configuración); `-2` = "ERROR RETORNO" o "NO PUEDO CREAR O ACT. TOKEN".
- Un ejemplo del manual usa `<SEED>` en vez de `<SEMILLA>`. Conviene que el parser acepte ambos.
- **La semilla dura 2 minutos** [OF:AUT].

### 1.3 Semilla firmada (formato exacto) [OF:AUT cap. 8]

Hay que armar el documento siguiente. La semilla va tal cual se recibió, con sus ceros a la izquierda.

```xml
<?xml version="1.0"?>
<getToken>
  <item>
    <Semilla>000002248802</Semilla>
  </item>
  <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
    <SignedInfo>
      <CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
      <SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
      <Reference URI="">
        <Transforms>
          <Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
        </Transforms>
        <DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
        <DigestValue>...</DigestValue>
      </Reference>
    </SignedInfo>
    <SignatureValue>...</SignatureValue>
    <KeyInfo>
      <KeyValue><RSAKeyValue><Modulus>...</Modulus><Exponent>AQAB</Exponent></RSAKeyValue></KeyValue>
      <X509Data><X509Certificate>...</X509Certificate></X509Data>
    </KeyInfo>
  </Signature>
</getToken>
```

- La firma es enveloped sobre todo el documento: `Reference URI=""` con el transform `enveloped-signature`.
- Los algoritmos son C14N inclusivo 2001, RSA-SHA1 y SHA1.
- `KeyInfo` debe llevar `KeyValue/RSAKeyValue` **y** `X509Data/X509Certificate`.
- El certificado debe ser personal, emitido por una entidad acreditada. Su RUT debe tener habilitada en sii.cl la autenticación con certificado digital (error `-07`/`-3` si no lo está).
- El documento firmado completo, desde `<?xml version="1.0"?>`, se pasa como string en `pszXml`, escapado en el SOAP (`<` → `&lt;`).

### 1.4 getToken [OF:AUT]

```xml
<SOAP-ENV:Body>
  <m:getToken xmlns:m="https://palena.sii.cl/DTEWS/GetTokenFromSeed.jws">
    <pszXml xsi:type="xsd:string">&lt;?xml version="1.0"?&gt;&lt;getToken&gt;...</pszXml>
  </m:getToken>
</SOAP-ENV:Body>
```

Respuesta, después de des-escapar `getTokenReturn`:

```xml
<SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema">
  <SII:RESP_HDR><ESTADO>00</ESTADO><GLOSA>Token Creado</GLOSA></SII:RESP_HDR>
  <SII:RESP_BODY><TOKEN>XAuSbYXiNhIk</TOKEN></SII:RESP_BODY>
</SII:RESPUESTA>
```

Estados de GetTokenFromSeed:

| Estado | Significado |
|---|---|
| `00` | Token creado |
| `01` | XML inválido (IOException) |
| `02` | XML inválido (SAXException) |
| `03` | XML inválido (ParserConfigurationException) |
| `04` | No existe el elemento `Signature` |
| `05` | Firma inválida |
| `06` | No existe el elemento `Semilla` |
| `07` | MessageException |
| `08` | Error de retorno: "TIME-OUT DEL SEED", "NO Existe SEED", "PARAMETROS INCORRECTOS", etc. |
| `09` | MessageException |
| `10` | Error retorno datos |
| `11` | No existe el elemento `Certificate` |
| `12` | MessageException |
| `21` | Firma inválida: la llave pública no coincide con el certificado |
| `-3` | Error en autenticación |
| `-07` | Error en validación del RUT: el usuario no está registrado con la opción de autenticación por certificado |

### 1.5 Uso y vigencia del token

- **Upload:** el token viaja en el header HTTP `Cookie: TOKEN=<valor>` [OF:UPL].
- **QueryEstUp y QueryEstDte:** el token es un parámetro del cuerpo SOAP (`Token`) [OF:EUP][OF:EDTE].
- **WS de Reclamo (ws1/ws2):** ni la documentación ni el WSDL dicen cómo se pasa el token. La práctica es enviar el header `Cookie: TOKEN=<valor>` [NV]. La respuesta trae `rutToken` [OF:WSDL].
- Errores de token en los WS de consulta [OF:EUP][OF:EDTE]:
  - `001`: cookie o token inactivo;
  - `002`: token inactivo;
  - `003`: token no existe.
- **Vigencia del token:** los manuales oficiales no la indican. En la práctica caduca después de un tiempo sin uso (alrededor de 1 hora) [NV]. Diseño recomendado: cachear el token, renovarlo al recibir `001`/`002`/`003`, STATUS `5` o el HTML de login, y nunca reutilizarlo entre ambientes. El token de maullin no sirve en palena.
- El token es por persona (RUT del certificado), no por empresa. Esa persona debe tener en el SII los perfiles de la empresa ("Enviar Doctos", etc.) [OF:CERT 2.1].

---

## 2. Envío (upload) de EnvioDTE

### 2.1 Endpoint [OF:UPL]

- `POST https://maullin.sii.cl/cgi_dte/UPL/DTEUpload` (certificación) o `https://palena.sii.cl/cgi_dte/UPL/DTEUpload` (producción).
- Verificado el 2026-10-26: ambos endpoints responden; un GET devuelve "ERROR 501".
- No es un web service. Emula un formulario de navegador `multipart/form-data` (RFC 1867) [OF:CERT 4].

### 2.2 Headers requeridos [OF:UPL fig. 2.3]

```
POST /cgi_dte/UPL/DTEUpload HTTP/1.0
Accept: image/gif, image/x-xbitmap, image/jpeg, image/pjpeg, application/vnd.ms-powerpoint, application/ms-excel, application/msword, */*
Referer: <URL cualquiera, p.ej. https://miempresa.cl/envio>
Accept-Language: es-cl
Content-Type: multipart/form-data; boundary=<boundary>
Accept-Encoding: gzip, deflate
User-Agent: Mozilla/4.0 (compatible; PROG 1.0; Windows NT 5.0; YComp 5.0.2.4)
Host: maullin.sii.cl
Content-Length: <largo del cuerpo, sin headers>
Connection: Keep-Alive
Cache-Control: no-cache
Cookie: TOKEN=<token>
```

- **El token `PROG 1.0` dentro del User-Agent es lo que hace que la respuesta llegue en XML.** Sin él, el SII responde HTML [OF:UPL v1.2].
- El manual escribe `multipart/form-data: boundary=`, con dos puntos. Usar la forma estándar `; boundary=`, que es la que generan requests y httpx [NV: funciona en práctica].
- `Content-Length` no incluye los headers. Los saltos de línea son CRLF.

### 2.3 Campos multipart exactos, en este orden [OF:UPL anexo 3]

| name | contenido |
|---|---|
| `rutSender` | cuerpo del RUT de quien envía (el titular del certificado/token), sin DV |
| `dvSender` | DV de quien envía |
| `rutCompany` | cuerpo del RUT de la empresa emisora |
| `dvCompany` | DV de la empresa |
| `archivo` | `filename="EnvioXXX.xml"`, `Content-Type: text/xml`; contenido: el EnvioDTE (o libro) firmado, en bytes ISO-8859-1 sin re-codificar |

Boundary [OF:UPL anexo 4]: en el cuerpo cada separador es `--<boundary>` y el cierre es `--<boundary>--`. Requests lo hace bien automáticamente.

### 2.4 Respuesta [OF:UPL]

```xml
<?xml version="1.0"?>
<RECEPCIONDTE>
  <RUTSENDER>1-9</RUTSENDER><RUTCOMPANY>3-5</RUTCOMPANY>
  <FILE>EnvioEjemplo.xml</FILE><TIMESTAMP>2002-11-25 18:51:44</TIMESTAMP>
  <STATUS>0</STATUS><TRACKID>39</TRACKID>
</RECEPCIONDTE>
```

| STATUS | Significado |
|---|---|
| 0 | Upload OK. **Solo con 0 viene `TRACKID`** |
| 1 | El sender no tiene permiso para enviar |
| 2 | Error en tamaño del archivo (muy grande o muy chico) |
| 3 | Archivo cortado (tamaño distinto del parámetro size) |
| 5 | No está autenticado (token inválido o vencido) |
| 6 | Empresa no autorizada a enviar archivos |
| 7 | Esquema inválido. Trae `<DETAIL><ERROR>...</ERROR></DETAIL>` |
| 8 | Firma del documento |
| 9 | Sistema bloqueado |
| otro | Error interno |

- `TRACKID` es el identificador del envío. Se usa en QueryEstUp. Es numérico, de hasta 10 dígitos según el manual, pero hay que guardarlo como string o entero de 64 bits [NV: hoy los trackid superan 10 dígitos].
- STATUS 0 solo significa que el archivo se recibió. El resultado de la validación se consulta después (sección 3) y también llega por correo al "mail de contacto SII" [OF:CERT 2.4].
- El correo del SII sigue el esquema `RESULTADO_ENVIO` de `online/fm_schema_resp/RespSII_v10.xsd`: `IDENTIFICACION` (RUTEMISOR, RUTENVIA, TRACKID, TMSTRECEPCION, ESTADO), `ESTADISTICA/SUBTOTAL` (TIPODOC, INFORMADO, ACEPTA, RECHAZO, REPARO), `ERRORENVIO/DETERRENVIO` y `REVISIONENVIO/REVISIONDTE` (FOLIO, TIPODTE, ESTADO, DETALLE) [OF:XSD].

### 2.5 Límites [OF:INST A.3.3.4]

- Un EnvioDTE admite máximo **2.000 documentos**.
- Un IECV admite máximo 30.000 líneas de detalle.
- Hay que transmitir cada DTE al SII antes de entregarlo o trasladar los bienes. Sin transporte, dentro de 12 horas [OF:MOD 2003; NV si sigue vigente igual].

---

## 3. Consultas de estado

### 3.1 QueryEstUp: estado de un envío [OF:EUP][OF:WSDL]

- WSDL: `https://{maullin|palena}.sii.cl/DTEWS/QueryEstUp.jws?WSDL`.
- Método: `getEstUp(RutCompania, DvCompania, TrackId, Token)`. Todos los parámetros son `xsd:string`.
- **Rareza:** el ejemplo SOAP del manual usa los elementos `<Rut>`, `<Dv>`, `<TrackId>` y `<Token>`, pero el WSDL (manual y en vivo) los llama `RutCompania` y `DvCompania`. En RPC/encoded se procesan por posición [NV]. Usar los nombres del WSDL.
- La respuesta (`getEstUpReturn`) es un XML escapado:

```xml
<SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema">
  <SII:RESP_HDR><TRACKID>251</TRACKID><ESTADO>EPR</ESTADO><GLOSA>Envio Procesado</GLOSA>
    <NUM_ATENCION>532 ( 2004/06/14 16:44:20)</NUM_ATENCION></SII:RESP_HDR>
  <SII:RESP_BODY><TIPO_DOCTO>33</TIPO_DOCTO><INFORMADOS>1</INFORMADOS><ACEPTADOS>1</ACEPTADOS>
    <RECHAZADOS>0</RECHAZADOS><REPAROS>0</REPAROS></SII:RESP_BODY>
</SII:RESPUESTA>
```

Estados del envío:

| ESTADO | Significado | ¿Final? |
|---|---|---|
| `RSC` | Rechazado por error en schema | final, rechazo |
| `SOK` | Schema validado | intermedio |
| `CRT` | Carátula OK | intermedio |
| `RCT` | Rechazado por error en carátula | final, rechazo |
| `RFR` | Rechazado por error en firma | final, rechazo |
| `FOK` | Firma de envío validada | intermedio |
| `PDR` | Envío en proceso | intermedio |
| `EPR` | Envío procesado. Revisar el RESP_BODY por tipo de documento | final |
| `RPR`, `RLV`, `RPT`, etc. | No están en el manual 2004. En la práctica `RPR` = "Aceptado con reparos" [NV] | final [NV] |

- En `EPR`, el `RESP_BODY` se repite por tipo de documento [NV en cuanto a la repetición]: `TIPO_DOCTO`, `INFORMADOS`, `ACEPTADOS`, `RECHAZADOS` y `REPAROS`.
- Errores de consulta: `ESTADO` -1 a -14 (lista en [OF:EUP 3.5.3]), más `ERR_CODE`, `SQL_CODE`, `SRV_CODE` y los errores de token `001`/`002`/`003`.
- Política: consultar periódicamente mientras el estado no sea final. El SII no permite uso masivo [OF:INST anexo 5]. Usar backoff y no consultar de forma agresiva.

### 3.2 QueryEstDte: estado de un DTE [OF:EDTE][OF:WSDL]

- WSDL: `https://{maullin|palena}.sii.cl/DTEWS/QueryEstDte.jws?WSDL`.
- Método `getEstDte`. Parámetros, en este orden y todos string:
  1. `RutConsultante` y `DvConsultante`: RUT del usuario autenticado (el titular del token).
  2. `RutCompania` y `DvCompania`: emisor.
  3. `RutReceptor` y `DvReceptor`.
  4. `TipoDte`.
  5. `FolioDte`.
  6. `FechaEmisionDte`: **formato `DDMMAAAA`**. Es distinto del `AAAA-MM-DD` del XML.
  7. `MontoDte`: monto total.
  8. `Token`.
- Respuesta: `ESTADO`, `GLOSA` (en algunos ejemplos aparece como `GLOSA_ESTADO`), `ERR_CODE`, `GLOSA_ERR` y `NUM_ATENCION`.

| ESTADO | ERR_CODE | Significado |
|---|---|---|
| DOK | 0 | Recibido por el SII; los datos coinciden |
| DNK | 1 | Recibido, pero los datos NO coinciden |
| FAU | 3 | No recibido por el SII |
| FNA | 4 | No autorizado |
| FAN | 5 | Anulado |
| EMP | 6 | Empresa no autorizada a emitir DTE |
| TMD | 10 | Existe ND que modifica texto |
| TMC | 11 | Existe NC que modifica texto |
| MMD | 12 | Existe ND que modifica montos |
| MMC | 13 | Existe NC que modifica montos (antes `NNC`) |
| AND | 14 | Existe ND que anula |
| ANC | 15 | Existe NC que anula |

Otros errores: `-1` a `-4` y los de token `001`/`002`/`003`.

---

## 4. Estructura del DTE (33, 34, 52, 56, 61)

### 4.1 Envoltorio y encoding

- El archivo se escribe en **ISO-8859-1**. La línea 1 debe ser `<?xml version="1.0" encoding="ISO-8859-1"?>`.
- La línea 2 debe ser el elemento raíz con `xmlns="http://www.sii.cl/SiiDte"`, `xmlns:xsi` y `xsi:schemaLocation="http://www.sii.cl/SiiDte EnvioDTE_v10.xsd"`. **El SII valida estas dos primeras líneas** [OF:INST A.3.1].
- Hay que poner salto de línea después de cada tag. **No enviar el XML en una sola línea** [OF:INST A.3.1].
- Base64 (firmas, certificados): máximo 76 caracteres por línea [OF:INST A.2.4, A.3.1].
- Hay que escapar `& < > " '` con las entidades XML. Acentos y ñ van en ISO-8859-1. Un carácter fuera de ISO-8859-1 produce rechazo por schema ("Invalid Character") [OF:INST A.2.4].

Estructura:

```xml
<DTE version="1.0">
  <Documento ID="F123T33">   <!-- ID único; p.ej. "F"+folio+"T"+tipo [OF:INST A.3.4] -->
    <Encabezado> IdDoc, Emisor, [RUTMandante], Receptor, [RUTSolicita], [Transporte], Totales, [OtraMoneda] </Encabezado>
    <Detalle>…</Detalle>            <!-- 1..60 -->
    <SubTotInfo>…</SubTotInfo>      <!-- 0..20, solo informativo -->
    <DscRcgGlobal>…</DscRcgGlobal>  <!-- 0..20 -->
    <Referencia>…</Referencia>      <!-- 0..40 -->
    <GeoRefEmision/> <ManejoMadera/> <!-- nuevos, opcionales -->
    <Comisiones>…</Comisiones>      <!-- 0..20; no aplica a 33/34/52 -->
    <TED version="1.0">…</TED>
    <TmstFirma>2026-10-26T10:15:00</TmstFirma>
  </Documento>
  <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">…</Signature>
</DTE>
```

- **El orden de los elementos es estricto (`xs:sequence`)**. Hay que respetar el orden del XSD.
- `DTE/@version` es fijo, `1.0`.

### 4.2 Encabezado: obligatorios por tipo [OF:FDTE][OF:XSD]

Leyenda: 1 = obligatorio, 2 = condicional, 3 = opcional, 0 = no corresponde. Un `*` en la columna "Rechazo" significa que, si el campo falta, el DTE se rechaza.

**IdDoc**

| Campo (tag) | Tipo y largo | 33 | 34 | 52 | 56 | 61 | Rechazo |
|---|---|---|---|---|---|---|---|
| `TipoDTE` | 33/34/46/52/56/61 en el XSD (no admite 43, 110-112) | 1 | 1 | 1 | 1 | 1 | * |
| `Folio` | entero de hasta 10 dígitos, dentro del rango del CAF | 1 | 1 | 1 | 1 | 1 | * |
| `FchEmis` | AAAA-MM-DD | 1 | 1 | 1 | 1 | 1 | * |
| `IndNoRebaja` | 1 = NC sin derecho a rebajar débito | 0 | 0 | 0 | 0 | 2 | |
| `TipoDespacho` | 1, 2 o 3 | 2 | 2 | 2 | 0 | 0 | |
| `IndTraslado` | 1-9 (ver 4.7) | 0 | 0 | **1** | 0 | 0 | |
| `TpoImpresion` | N/T | 0 | 0 | 2 | 0 | 0 | |
| `IndServicio` | 1, 2 o 3 | 2 | 2 | 0 | 2 | 2 | |
| `MntBruto` | 1 = montos brutos en el detalle | 2 | 2 | 0 | 2 | 2 | |
| `TpoTranCompra` | 1-7 | 3 | 3 | 3 | 0 | 0 | |
| `TpoTranVenta` | 1-4; si se omite se asume 1 | 3 | 3 | 3 | 3 | 0 | |
| `FmaPago` | 1 = contado, 2 = crédito, 3 = sin costo | 2 (obligatorio en uso; si falta se asume 2) | 2 (ídem) | 3 | 2 | 2 | |
| `FchVenc` | AAAA-MM-DD | 2 | 2 | 0 | 3 | 3 | |

Además son opcionales: `MntCancel`, `SaldoInsol`, `MntPagos` (0..30 con `FchPago`, `MntPago`, `GlosaPagos`), `PeriodoDesde`/`PeriodoHasta`, `MedioPago` (CH, CF, LT, EF, PE, TC, OT), `TermPago*` y `TipoFactEsp` (factura turista).

**Emisor**

| Campo | Largo | Obligatoriedad |
|---|---|---|
| `RUTEmisor` | patrón `[0-9]+-([0-9]\|K)` (K mayúscula, sin puntos, máximo 10) | 1 * |
| `RznSoc` | 100 | 1 |
| `GiroEmis` | 80 | 1 |
| `Telefono` | 0..2, 20 cada uno | opcional |
| `CorreoEmisor` | 80 | opcional |
| `Acteco` | 1..4 códigos de 6 dígitos registrados en el SII | 1 |
| `GuiaExport` | | solo guías de exportación |
| `Sucursal` | 20 | opcional |
| `CdgSIISucur` | código de sucursal SII, 9 dígitos | 2: obligatorio si se emite desde una sucursal registrada |
| `DirOrigen` | 70 en el XSD (60 en FDTE) | 1 en 33/34/52; 3 en 56/61 |
| `CmnaOrigen` | 20 | igual que `DirOrigen` |
| `CiudadOrigen` | 20 | 3 |
| `CdgVendedor` | 60 | opcional |
| `IdAdicEmisor` | | opcional |

**Receptor**

| Campo | Largo | Obligatoriedad |
|---|---|---|
| `RUTRecep` | | 1 * |
| `CdgIntRecep` | 20 | opcional |
| `RznSocRecep` | 100 | 1 |
| `Extranjero` | | opcional |
| `GiroRecep` | 40 | 1 en 33/34/52; 3 en 56/61 |
| `Contacto` | 80 | opcional |
| `CorreoRecep` | | opcional |
| `DirRecep` | 70 | 1 en 33/34/52; 3 en 56/61 |
| `CmnaRecep` | 20 | 1 en 33/34/52; 3 en 56/61 |
| `CiudadRecep` | 20 | 3 |
| `DirPostal`, `CmnaPostal`, `CiudadPostal` | | 3 |

**RUTSolicita**: 2 en 33/34/56/61. Es obligatorio en ventas a público cuando el solicitante es distinto del receptor.

**Transporte** (2 en 33/34/52):
- `Patente`, `RUTTrans`, `Chofer/RUTChofer` + `NombreChofer`, `DirDest` y `CiudadDest`.
- `CmnaDest` es **1 en la guía 52**.
- La subárea `Aduana` es solo para exportación.

**Totales**

| Campo | 33 | 34 | 52 | 56 | 61 | Regla |
|---|---|---|---|---|---|---|
| `MntNeto` | 2 | 0 | 3 | 2 | 2 | Σ `MontoItem` afectos − descuentos globales + recargos globales asignados a afectos. Si `MntBruto`=1, se divide por (1+tasa) |
| `MntExe` | 2 | **1** | 3 | 2 | 2 | Σ ítems exentos (`IndExe`=1) ± descuentos/recargos globales con `IndExeDR`=1 |
| `TasaIVA` | 2 | 0 | 3 | 2 | 2 | 3 enteros y 2 decimales; hoy `19` |
| `IVA` | 2 | 0 | 3 | 2 | 2 | `MntNeto` × `TasaIVA` / 100 |
| `ImptoReten` (0..20: `TipoImp`, `TasaImp`, `MontoImp`) | 2 | 2 | 3 | 2 | 2 | tasa × Σ líneas con ese `CodImpAdic` |
| `MntTotal` | 1 * | 1 * | 1 * | 1 * | 1 * | `MntNeto` + `MntExe` + `IVA` + impuestos adicionales + … − `CredEC` − retenciones, etc. |

En 34 no van `MntNeto`, `IVA` ni `TasaIVA`. En la 52, si es "no venta", los totales pueden ser 0.

### 4.3 Detalle (1..60) [OF:FDTE B][OF:XSD]

**Máximo 60 líneas**: es `maxOccurs=60` en el XSD vigente 2026 y lo exige FDTE.

Orden de los campos en la secuencia:
1. `NroLinDet` (1..60, obligatorio).
2. `CdgItem` (0..5: `TpoCodigo` ≤10, por ejemplo "INT1"/"EAN13"; `VlrCodigo` ≤35).
3. `IndExe`: 1 = exento, 2 = no facturable, 3 = garantía de envases, 4 = ítem no venta, 5 = ítem a rebajar (guías), 6 = no facturable negativo.
4. `Retenedor`.
5. `NmbItem` (≤80, obligatorio *).
6. `DscItem` (≤1000).
7. `QtyRef`, `UnmdRef`, `PrcRef`.
8. `QtyItem`: 12 enteros y 6 decimales; mínimo 0.000001. **1 en la guía 52.**
9. `Subcantidad`.
10. `FchElabor`, `FchVencim`.
11. `UnmdItem` (≤4).
12. `PrcItem`: 12 enteros y 6 decimales; mínimo 0.000001, así que **no admite 0**.
13. `OtrMnda`.
14. `DescuentoPct`, `DescuentoMonto`.
15. `SubDscto` (0..5).
16. `RecargoPct`, `RecargoMonto`.
17. `SubRecargo` (0..5).
18. `CodImpAdic` (0..2).
19. `MontoItem` (obligatorio *).

**Regla de cálculo:** `MontoItem` = `PrcItem` × `QtyItem` − `DescuentoMonto` + `RecargoMonto`.
- En la 34 o con `IndExe`=1 es el valor exento; en los demás casos es el neto.
- Debe ser 0 cuando `IndExe` es 4 o 5, y en una NC "fe de erratas" (`CodRef`=2).
- Puede ser 0 en una guía no venta.

**Descuentos:** si hay `DescuentoPct`, debe ir también `DescuentoMonto` [OF:FDTE][OF:MUES].

### 4.4 DscRcgGlobal (0..20) [OF:FDTE D][OF:XSD]

Campos: `NroLinDR`, `TpoMov` (D/R), `GlosaDR` (≤45), `TpoValor` (`%` o `$`), `ValorDR` (16 enteros y 2 decimales), `ValorDROtrMnda` e `IndExeDR` (1 = afecta solo exentos, 2 = solo no facturables; si se omite, afecta solo afectos).

- Si un descuento afecta a afectos y a exentos, se escriben **líneas separadas**.
- Si hay ítems con distintos códigos de impuesto adicional, `TpoValor` debe ser `%`.
- No corresponde en la guía 52 según la tabla de zonas (obligatoriedad 0) [OF:FDTE 2.1].

### 4.5 Referencia (0..40) [OF:FDTE E][OF:XSD]

Campos: `NroLinRef` (1..40), `TpoDocRef` (≤3: código numérico de documento o un texto como "SET"), `IndGlobal` (1), `FolioRef` (≤18, alfanumérico; 0 solo si `IndGlobal`=1), `RUTOtr`, `FchRef` (obligatorio), `CodRef` (1 = anula, 2 = corrige texto, 3 = corrige montos) y `RazonRef` (≤90).

- **56 y 61: la referencia es obligatoria (1) y `CodRef` es obligatorio.**
- Los casos `CodRef` 1 y 2 (y la ND que anula una NC) deben tener **una única** referencia.
- En la 52, la referencia es condicional (por ejemplo, la orden de compra 801).
- **Rareza del SII en certificación:** la primera referencia de cada DTE del set debe ser `TpoDocRef`=`SET` con `RazonRef`=`CASO nnnnn-n`. Las demás referencias van desde la línea 2 [OF:SET I.6].
- NC por corrección de texto: el detalle dice "Donde dice … debe decir …" y los montos van en 0 [OF:MUES][OF:FDTE].

### 4.6 Redondeo [NV]

Los documentos oficiales no traen una regla de redondeo explícita. Lo que el SII valida es:
- consistencia `MontoItem` ≈ precio × cantidad − descuento + recargo;
- `IVA` ≈ `MntNeto` × tasa;
- `MntTotal` = suma de sus componentes.

Según FDTE 2.2, un error de contenido no rechaza el DTE en producción, pero **en certificación el set debe quedar sin rechazos ni reparos** [OF:CERT 6.1]. Por eso:
- Montos en pesos: enteros, redondeo aritmético de 0,5 hacia arriba (ROUND_HALF_UP), sobre el valor exacto calculado con `Decimal` [NV].
- `MontoItem`: redondear cada línea.
- `IVA`: redondear `MntNeto` × 0,19 una sola vez sobre el neto total, no por línea.
- Descuentos porcentuales: monto = redondear(base × pct / 100).
- Decimales en `QtyItem` y `PrcItem`: solo los significativos, con punto decimal y sin separador de miles [OF:FDTE 2.2].

### 4.7 Particularidades por tipo

- **33 (factura afecta):** si todos los ítems son `IndExe`=1, el documento debe ser una 34 [OF:FDTE].
- **34 (factura exenta):** solo `MntExe` y `MntTotal`. En el impreso no se muestran IVA ni Neto [OF:MUES].
- **52 (guía):**
  - `IndTraslado` es obligatorio: 1 venta, 2 venta por efectuar, 3 consignación, 4 entrega gratuita, 5 traslado interno, 6 otros traslados no venta, 7 devolución, 8 traslado para exportación, 9 venta para exportación.
  - En traslado interno, el receptor es igual al emisor.
  - En no venta no hay copia cedible [OF:MUES].
- **56 y 61 (notas):** referencia obligatoria al documento que modifican. Una ND que anula una NC usa `CodRef`=1.

---

## 5. Timbre electrónico (TED) y CAF

### 5.1 Archivo CAF (autorización de folios) [OF:INST anexo 1][OF:CERT]

El CAF se descarga del sitio del SII (maullin en certificación) al solicitar folios ("Solicitud de Timbraje Electrónico"). Estructura:

```xml
<AUTORIZACION>
  <CAF version="1.0">
    <DA>
      <RE>97975000-5</RE><RS>RUT DE PRUEBA</RS><TD>33</TD>
      <RNG><D>1</D><H>200</H></RNG>
      <FA>2003-09-04</FA>
      <RSAPK><M>0a4O6Kbx…BhZw==</M><E>Aw==</E></RSAPK>
      <IDK>100</IDK>
    </DA>
    <FRMA algoritmo="SHA1withRSA">g1AQX0sy…</FRMA>
  </CAF>
  <RSASK>-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----</RSASK>
  <RSAPUBK>-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----</RSAPUBK>
</AUTORIZACION>
```

- `DA` contiene:
  - `RE`: RUT del emisor.
  - `RS`: razón social, máximo 40.
  - `TD`: tipo de DTE.
  - `RNG/D` y `RNG/H`: rango de folios.
  - `FA`: fecha de autorización.
  - `RSAPK/M` y `RSAPK/E`: llave pública, como base64 de enteros big-endian sin signo.
  - `IDK`: identificador de la llave del SII que firma el CAF. **En los ejemplos de certificación `IDK`=100** [OF:CERT ejemplo]. En producción es otro valor [NV: típicamente 300].
- `FRMA`: firma SHA1withRSA del SII sobre `DA`.
- `RSASK`: llave privada de timbraje en PEM PKCS#1. `RSAPUBK`: la misma llave pública, en PEM.
- Las llaves de CAF son RSA de 512 bits con exponente 3 (`E`=`Aw==`) [OF:CERT ejemplo; NV si siempre es así].
- **El nodo `<CAF>` se copia sin ninguna modificación** dentro del TED. Cualquier cambio (espacios dentro de base64, atributos reordenados, encoding) hace que falle la verificación [OF:INST A.1.3, A.2.4].
- Cada CAF tiene su propio par de llaves. Hay que guardar el XML original completo, controlar el acceso a `RSASK` y validar `FRMA` y el par de llaves al cargarlo [OF:INST 1.4].

### 5.2 TED [OF:INST anexo 2][OF:XSD]

```xml
<TED version="1.0">
  <DD>
    <RE>97975000-5</RE><TD>33</TD><F>27</F><FE>2003-09-08</FE>
    <RR>8414240-9</RR><RSR>JORGE GONZALEZ LTDA</RSR><MNT>502946</MNT>
    <IT1>Cajon AFECTO</IT1>
    <CAF version="1.0">…copia exacta…</CAF>
    <TSTED>2003-09-08T12:28:31</TSTED>
  </DD>
  <FRMT algoritmo="SHA1withRSA">pqjXHHQL…Imw==</FRMT>
</TED>
```

Campos de `DD` (en este orden):
- `RE`: RUT del emisor.
- `TD`: tipo de DTE.
- `F`: folio.
- `FE`: `FchEmis`.
- `RR`: RUT del receptor.
- `RSR`: razón social del receptor, de 1 a 40 caracteres. **Truncar a 40.**
- `MNT`: `MntTotal`, entero.
- `IT1`: `NmbItem` de la línea 1, de 1 a 40 caracteres. **Truncar a 40.**
- `CAF`.
- `TSTED`: momento de generación, `AAAA-MM-DDTHH:MI:SS`.

Los valores del TED deben coincidir con los del Encabezado y el Detalle [OF:INST A.2.4].

**Firma `FRMT`** [OF:INST A.2.4][OF:CERT 3.2, 5.2]:
- RSA PKCS#1 v1.5 con SHA-1 ("SHA1withRSA"), usando la llave privada `RSASK` del CAF. **No es XMLDSig.**
- El mensaje firmado son los bytes ISO-8859-1 del elemento `<DD>…</DD>` **aplanado**:
  - se eliminan los saltos de línea, espacios y tabs *entre* tags;
  - no se toca el contenido de los nodos texto;
  - se eliminan las declaraciones de namespace;
  - se mantienen las entidades (`&amp;`) tal como quedan en el XML;
  - los atributos van con comillas dobles (`<CAF version="1.0">`, `<FRMA algoritmo="SHA1withRSA">`).
- Ejemplo oficial del string firmado [OF:CERT 5.2]:

```
<DD><RE>97975000-5</RE><TD>33</TD><F>27</F><FE>2003-09-08</FE><RR>8414240-9</RR><RSR>JORGE GONZALEZ LTDA</RSR><MNT>502946</MNT><IT1>Cajon AFECTO</IT1><CAF version="1.0"><DA><RE>97975000-5</RE><RS>RUT DE PRUEBA</RS><TD>33</TD><RNG><D>1</D><H>200</H></RNG><FA>2003-09-04</FA><RSAPK><M>0a4O6K…BhZw==</M><E>Aw==</E></RSAPK><IDK>100</IDK></DA><FRMA algoritmo="SHA1withRSA">g1AQX0…lDQ==</FRMA></CAF><TSTED>2003-09-08T12:28:31</TSTED></DD>
```

  `manual_certificacion.txt` sección 5.2 trae la llave privada PEM y el resultado esperado (`pqjXHHQL…Imw==`). **Usar este caso como test unitario de la firma del TED.** El 2026-10-26 se reprodujo este caso con `openssl dgst -sha1 -sign` sobre ese string exacto en ISO-8859-1 y el resultado fue **idéntico** al FRMT oficial. Eso confirma la regla de aplanado y el algoritmo.
- Al copiar el CAF dentro del TED, `xmlns` hereda `http://www.sii.cl/SiiDte`. Para firmar se **omite** esa referencia de namespace [OF:INST A.2.4]. Ojo con el string que devuelve lxml (`tostring` agrega `xmlns`): se debe serializar a mano.
- `FRMT` va en base64. Los caracteres de `RSR` e `IT1` deben ser ISO-8859-1; las librerías no deben convertirlos a UTF-8 [OF:INST A.2.4].

### 5.3 PDF417 [OF:INST A.2.5][OF:MUES 1.5]

- **Contenido:** el XML del `<TED>…</TED>` [OF:INST A.2.2]. El manual no especifica si va aplanado. En la práctica se codifica el TED sin saltos ni indentación, en ISO-8859-1 [NV].
- **Modo de codificación:** Byte Compaction Mode (binario).
- **ECL:** nivel 5.
- **No usar** "Truncated" PDF417.
- **X-dim:** como mínimo 6,7 mils (≈0,17 mm). **Y-dim** = 3 × X (proporción 3:1).
- **Quiet zone:** al menos 0,25" en cada lado.
- **Impresión:** 300 DPI o más, en negro.
- **Tamaño impreso:** se recomienda como máximo 3 × 9 cm [OF:INST]. El manual de muestras pide **mínimo 2 × 5 cm y máximo 4 × 9 cm**, ubicado en la parte inferior y a al menos 2 cm del borde izquierdo [OF:MUES].
- En PDF, el timbre debe ser una imagen PNG incrustada. Si se dibuja con vectores, rasterizar a 600 DPI o más [OF:MUES].
- **Columnas y filas:** no hay valor oficial. Valores usados en la práctica: alrededor de 12 a 15 columnas de datos, en función del tamaño [NV].

---

## 6. Firma XMLDSig del Documento y del SetDTE

### 6.1 Perfil restringido del SII (`xmldsignature_v10.xsd`) [OF:XSD][OF:INST A.3.3.1]

- `CanonicalizationMethod`: **fijo** `http://www.w3.org/TR/2001/REC-xml-c14n-20010315`, es decir, C14N inclusivo sin comentarios.
- `SignatureMethod`: `rsa-sha1` (o `dsa-sha1`). **No admite SHA-256.**
- `DigestMethod`: **fijo** `http://www.w3.org/2000/09/xmldsig#sha1`.
- Hay **una sola** `Reference`, con `URI` obligatorio.
- `Transforms` es opcional y admite como máximo **un** `Transform`. Los ejemplos oficiales usan un transform C14N; el instructivo lo omite. Ambas formas son válidas.
- `KeyInfo` es **obligatorio** y debe contener, en este orden, `KeyValue` (`RSAKeyValue`: `Modulus` + `Exponent`) y luego `X509Data` con exactamente un `X509Certificate`. No se permiten `X509IssuerSerial`, `KeyName` ni otros elementos.
- No se permiten prefijos `ds:` adicionales ni atributos `Id` extra. Lo seguro es `<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">` [NV en cuanto a prefijos; el ejemplo oficial usa namespace por defecto].

### 6.2 Firma del DTE [OF:CERT 5.1][OF:INST A.3.4]

- La `Reference` es `URI="#<ID de Documento>"`, por ejemplo `#F27T33`.
- La `Signature` va como hermano siguiente de `Documento`, dentro de `DTE`.
- Antes de firmar, el `Documento` debe tener el `TED` y el `TmstFirma`.
- Firma la persona con perfil "Firmar Doctos". El certificado debe estar vigente y no revocado [OF:CERT 2.1][OF:FDTE I].

### 6.3 Firma del EnvioDTE [OF:CERT 5.1][OF:XSD]

- La `Reference` es `URI="#SetDoc"`, el ID de `SetDTE`.
- La `Signature` es el último hijo de `EnvioDTE`, después de `</SetDTE>`.
- Firma una persona con perfil "Enviar Doctos". Su RUT va en `RutEnvia` y en `rutSender`.

### 6.4 Problemas comunes

1. **Namespaces heredados (crítico) [NV, comportamiento estándar de C14N]:**
   - C14N inclusivo de un subárbol incluye todos los namespaces en alcance. Si `Documento` se firma con un `DTE` aislado (que solo declara `xmlns`) y luego se inserta en un `EnvioDTE` que también declara `xmlns:xsi`, el C14N del `Documento` cambia y el digest deja de calzar.
   - **Recomendación:** firmar cada `Documento` *dentro del árbol final* del `EnvioDTE` (mismos ancestros y mismas declaraciones), o bien no declarar en el raíz namespaces que no estén en el DTE firmado.
   - Validar la firma localmente con xmlsec sobre el archivo final, antes de enviarlo.
2. **No re-formatear después de firmar:** C14N preserva los espacios en blanco del contenido. Cualquier cambio de indentación, saltos de línea o encoding posterior invalida el digest.
3. **Encoding:** C14N produce UTF-8 aunque el archivo esté en ISO-8859-1, y así debe calcularse el digest. Escribir el archivo como ISO-8859-1 y no convertir entidades. El TED es la excepción: se firma sobre bytes ISO-8859-1 (sección 5.2).
4. **Base64:** escribir `SignatureValue`, `Modulus` y `X509Certificate` en líneas de 76 caracteres [OF:INST]. Esos nodos van fuera de `SignedInfo`, así que no afectan la firma.
5. **Atributo ID:** la librería debe saber que `ID` (en mayúsculas) es de tipo ID para resolver `#F…`. En lxml/xmlsec hay que registrarlo con `xmlsec.tree.add_ids(node, ["ID"])`.
6. **Errores de firma en el SII:** `STATUS 8` en el upload; `RFR` en QueryEstUp (firma del envío); reparos o rechazos por documento si la firma del DTE o el TED es inválida.

---

## 7. EnvioDTE y Carátula [OF:XSD][OF:CERT][OF:SET]

```xml
<?xml version="1.0" encoding="ISO-8859-1"?>
<EnvioDTE xmlns="http://www.sii.cl/SiiDte" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.sii.cl/SiiDte EnvioDTE_v10.xsd" version="1.0">
<SetDTE ID="SetDoc">
 <Caratula version="1.0">
  <RutEmisor>97975000-5</RutEmisor>
  <RutEnvia>7880442-4</RutEnvia>
  <RutReceptor>60803000-K</RutReceptor>
  <FchResol>2003-09-02</FchResol>
  <NroResol>0</NroResol>
  <TmstFirmaEnv>2003-09-08T12:31:59</TmstFirmaEnv>
  <SubTotDTE><TpoDTE>33</TpoDTE><NroDTE>1</NroDTE></SubTotDTE>
 </Caratula>
 <DTE version="1.0">…</DTE>
</SetDTE>
<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">…</Signature>
</EnvioDTE>
```

- `RutEmisor`: la empresa.
- `RutEnvia`: la persona que firma el envío (titular del certificado).
- `RutReceptor`: **`60803000-K` (el SII) cuando el envío va al SII**. En el intercambio va el RUT del receptor comercial [OF:SET II].
- `FchResol` y `NroResol`: fecha y número de la resolución que autoriza al emisor.
  - En **certificación**: **`NroResol`=0** y `FchResol` es la fecha publicada en "datos de su empresa" del ambiente de certificación [OF:CERT 5.1][OF:SET II].
  - En producción: los datos de autorización que publica el SII para la empresa [NV: desde la Res. Ex. 80/2014 la autorización es un registro; tomar fecha y número desde "Consultar empresas autorizadas" en palena].
- `TmstFirmaEnv`: xs:dateTime `AAAA-MM-DDTHH:MI:SS`. El instructivo lo llama `TmsFirmaEnv` y dice formato AAAAMMDDHHMMSS: **eso es un error**. Manda el XSD.
- `SubTotDTE` (1..20): el elemento es **`TpoDTE`**, no `TipoDTE` como dice el instructivo. `NroDTE` debe cuadrar con la cantidad real de DTE de cada tipo.
- `SetDTE/@ID` es libre. "SetDoc" es la convención.
- En los envíos del set de certificación van todos los documentos del set, **en el mismo orden en que se entregaron** [OF:SET II].

---

## 8. Intercambio entre contribuyentes

### 8.1 Canal [OF:INST anexo 4][OF:MOD]

- Todo emisor electrónico está obligado a recibir DTE.
- El medio mínimo es el correo electrónico MIME con **un único archivo adjunto XML** por mensaje. La casilla de intercambio está registrada en el SII y se consulta en "Consulta entre Contribuyentes Autorizados".
- Al receptor se le envía el **mismo EnvioDTE** que al SII, salvo que la carátula lleva el `RutReceptor` comercial. En la práctica se genera un EnvioDTE por receptor [NV en cuanto a separar].

### 8.2 Respuesta de intercambio [OF:FIC][OF:XSD fm_schema_ic/RespuestaEnvioDTE_v10.xsd]

- **Rareza:** el archivo se llama `RespuestaEnvioDTE_v10.xsd` y el instructivo dice `<RespuestaEnvioDTE>`, pero **el elemento raíz real es `<RespuestaDTE>`**.
- Un mensaje se usa **excluyentemente** para un acuse de recibo (`RecepcionEnvio`) o para un resultado comercial (`ResultadoDTE`), nunca ambos.
- La firma es XMLDSig sobre `Resultado` (`URI="#<ID>"`).

```xml
<RespuestaDTE xmlns="http://www.sii.cl/SiiDte" xmlns:xsi="..." xsi:schemaLocation="http://www.sii.cl/SiiDte RespuestaEnvioDTE_v10.xsd" version="1.0">
 <Resultado ID="R001">
  <Caratula version="1.0">
   <RutResponde>receptor</RutResponde><RutRecibe>emisor</RutRecibe>
   <IdRespuesta>1</IdRespuesta><NroDetalles>1</NroDetalles>
   <NmbContacto/>?<FonoContacto/>?<MailContacto/>?
   <TmstFirmaResp>2026-10-26T10:00:00</TmstFirmaResp>
  </Caratula>
  <!-- opción A: acuse de recibo del envío -->
  <RecepcionEnvio>
   <NmbEnvio>archivo.xml</NmbEnvio><FchRecep>2026-10-26T09:59:00</FchRecep>
   <CodEnvio>1</CodEnvio><EnvioDTEID>SetDoc</EnvioDTEID><Digest>…DigestValue del envío…</Digest>
   <RutEmisor>…</RutEmisor><RutReceptor>…</RutReceptor>
   <EstadoRecepEnv>0</EstadoRecepEnv><RecepEnvGlosa>Envio Recibido Conforme</RecepEnvGlosa>
   <NroDTE>1</NroDTE>
   <RecepcionDTE><TipoDTE/><Folio/><FchEmis/><RUTEmisor/><RUTRecep/><MntTotal/>
     <EstadoRecepDTE>0</EstadoRecepDTE><RecepDTEGlosa>DTE Recibido OK</RecepDTEGlosa></RecepcionDTE>
  </RecepcionEnvio>
  <!-- opción B: resultado comercial -->
  <ResultadoDTE><TipoDTE/><Folio/><FchEmis/><RUTEmisor/><RUTRecep/><MntTotal/><CodEnvio/>
   <EstadoDTE>0</EstadoDTE><EstadoDTEGlosa>ACEPTADO OK</EstadoDTEGlosa><CodRchDsc>-1</CodRchDsc>?</ResultadoDTE>
 </Resultado>
 <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">…</Signature>
</RespuestaDTE>
```

- `EstadoRecepEnv`:
  - 0 = recibido conforme;
  - 1 = error de schema;
  - 2 = error de firma;
  - 3 = RUT receptor no corresponde;
  - 90 = archivo repetido;
  - 91 = archivo ilegible;
  - 99 = otros.
- `EstadoRecepDTE`:
  - 0 = OK;
  - 1 = error de firma;
  - 2 = error en RUT emisor;
  - 3 = error en RUT receptor;
  - 4 = repetido;
  - 99 = otros.
- `EstadoDTE`: 0 = aceptado OK, 1 = aceptado con discrepancia, 2 = rechazado. Para un rechazo según la Ley 19.983, la glosa debe decirlo expresamente y citar la ley [OF:FIC].
- `CodRchDsc` es de tipo **`negativeInteger`** en el XSD: solo admite valores negativos.

### 8.3 EnvioRecibos: Ley 19.983 [OF:F19983][OF:XSD fm_schema19983]

```xml
<EnvioRecibos xmlns="http://www.sii.cl/SiiDte" version="1.0">
 <SetRecibos ID="SetRec">
  <Caratula version="1.0"><RutResponde/><RutRecibe/><NmbContacto/>?<FonoContacto/>?<MailContacto/>?<TmstFirmaEnv/></Caratula>
  <Recibo version="1.0">
   <DocumentoRecibo ID="R33F27">
    <TipoDoc>33</TipoDoc><Folio>27</Folio><FchEmis/><RUTEmisor/><RUTRecep/><MntTotal/>
    <Recinto>Bodega central</Recinto><RutFirma>11111111-1</RutFirma>
    <Declaracion>El acuse de recibo que se declara en este acto, de acuerdo a lo dispuesto en la letra b) del Art. 4°, y la letra c) del Art. 5° de la Ley 19.983, acredita que la entrega de mercaderías o servicio(s) prestado(s) ha(n) sido recibido(s).</Declaracion>
    <TmstFirmaRecibo/>
   </DocumentoRecibo>
   <Signature>…URI="#R33F27"…</Signature>
  </Recibo>
 </SetRecibos>
 <Signature>…URI="#SetRec"…</Signature>
</EnvioRecibos>
```

- **Hay doble firma:** una por cada `Recibo` (sobre `DocumentoRecibo`) y otra sobre `SetRecibos`.
- Aplica a los DTE 33, 34, 43, 46 y 52.
- El texto de `Declaracion` es literal (máximo 256 caracteres).

### 8.4 Plazos y registro en el SII [OF:WSRC]

- Ley 20.956: el receptor tiene **8 días corridos** desde la recepción del DTE en el SII para reclamar. Pasado ese plazo se presume el acuse de recibo y la factura queda cedible.
- El registro oficial de aceptación o reclamo ya no es el XML de intercambio: es el **Registro de Aceptación/Reclamo del SII**, que se usa por web o por este WS:
  - WSDL de certificación: `https://ws2.sii.cl/WSREGISTRORECLAMODTECERT/registroreclamodteservice?wsdl`
  - WSDL de producción: `https://ws1.sii.cl/WSREGISTRORECLAMODTE/registroreclamodteservice?wsdl`
  - Namespace: `http://ws.registroreclamodte.diii.sdi.sii.cl` [OF:WSDL]. Requiere autenticación con certificado (token de la sección 1).

Métodos (todos los parámetros son string):

| Método | Parámetros | Uso |
|---|---|---|
| `ingresarAceptacionReclamoDoc` | `rutEmisor` (sin DV), `dvEmisor` (K mayúscula), `tipoDoc` (33, 34, 43), `folio`, `accionDoc` | Acciones: `ACD` acepta contenido; `RCD` reclama contenido; `ERM` otorga recibo de mercaderías/servicios; `RFP` reclamo por falta parcial; `RFT` reclamo por falta total |
| `listarEventosHistDoc` | `rutEmisor`, `dvEmisor`, `tipoDoc`, `folio` | Historial de eventos. Incluye `NCA`/`ENC` (NC recibidas) |
| `consultarDocDteCedible` | ídem | Códigos 20-25 (cedible o no) |
| `consultarFechaRecepcionSii` | ídem | Fecha y hora de recepción en el SII (string) |

- La respuesta es `respuestaTo` con `codResp` (int), `descResp`, `listaEventosDoc[]` (`codEvento`, `descEvento`, `rutResponsable`, `dvResponsable`, `fechaEvento`) y `rutToken`.
- `codResp`:

| Código | Significado |
|---|---|
| 0 | OK |
| 1 | RUT emisor erróneo |
| 2 | Folio erróneo |
| 3 | Tipo de documento no corresponde |
| 4 | Acción inválida |
| 5 | Ya reclamado |
| 6 | No se puede dar ERM a un documento reclamado |
| 7 | Evento ya registrado |
| 8 | Pasaron los 8 días |
| 9 | Sin registros |
| 10 | DTE anterior al 14-01-2017 |
| 11 | No se puede reclamar un documento aceptado |
| 12 | No se puede aceptar un documento reclamado |
| 13 | No se puede reclamar con ERM previo |
| 14 / 17 | Acción solo para receptor (o emisor) |
| 15 | Lista de eventos |
| 16 | Sin eventos |
| 18 | No recibido |
| 19 | Reclamo de mercaderías ya realizado |
| -1 | Error interno: reintentar |

- Reglas de transición: un reclamo bloquea `ACD` y `ERM`. `ACD` o `ERM` bloquean reclamos. `ACD` y `ERM` se pueden combinar.
- El WS solo opera sobre 33, 34 y 43. **No aplica a 52, 56 ni 61.**

---

## 9. Proceso de certificación

### 9.1 Pasos [OF:CERT 6][OF:sii.cl proceso_certificacion.htm]

1. Postulación (representante legal, con certificado).
2. Set de pruebas.
3. Simulación.
4. Intercambio de información.
5. Muestras de impresión.
6. Declaración de cumplimiento de requisitos.
7. Registro como emisor electrónico (Res. Ex. SII N°80/2014; emisión válida desde el período de la declaración).

El SII elimina del ambiente de certificación a los contribuyentes sin actividad en 6 meses.

### 9.2 Preparación [OF:CERT 1-2][OF:MOD]

- **Postulación:** en sii.cl, la hace el representante legal con certificado digital. Se registra el usuario administrador y los correos: el contacto SII (recibe los resultados de los envíos) y la casilla de intercambio.
- **Ambiente:** `https://maullin.sii.cl/cvc/dte/certificacion_dte.html`.
- **Perfiles de usuario** (en "Mantención de Usuarios Autorizados"): Administrador, Solicitar Folio, Anular Folio, Firmar Doctos y Enviar Doctos. **El administrador no tiene por defecto los perfiles de folios ni de envío: debe asignárselos.**
- **Datos del emisor para la certificación:** `https://maullin.sii.cl/cvc_cgi/dte/pe_construccion_dte` [OF:MUES 1.2].
- **CAF de certificación:** se pide en maullin, en "Solicitud de Timbraje Electrónico", por tipo de documento. Solo sirve en maullin. Si un documento del set se acepta con reparos, se reenvía **con otro folio** (de lo contrario se rechaza por folio duplicado) [OF:SET II].

### 9.3 Set de pruebas [OF:SET][OF:CERT 6.1]

- Se descarga en maullin ("Generación Nuevo Set de Pruebas"). Es único por postulante y depende del giro y de los documentos a certificar.
- El SII evalúa contra el **último set descargado**. Plazo: **2 meses** desde la descarga.
- El archivo es un texto por "SET" con casos numerados (por ejemplo `CASO 4256-1`). Cada caso indica el tipo de documento, los ítems (glosa exacta con acentos), cantidades, precios, descuentos y, en las NC/ND, el caso que referencian [OF:SET; formato exacto NV].
- **Reglas de construcción** [OF:SET I]:
  - un DTE por caso;
  - folio autorizado;
  - un RUT receptor distinto y existente en cada factura;
  - fecha del día;
  - glosa del ítem **exactamente** como en el set, sin agregar ítems y en el orden indicado;
  - cantidad y precio unitario indicados;
  - en una NC por devolución, el precio es el de la factura original;
  - en una NC por diferencia de precio, la diferencia se aplica a todas las unidades del ítem;
  - IVA vigente;
  - en todos los documentos, primera referencia `SET` / `CASO n-n`.
- **Sets típicos** [NV: según la práctica]:
  - "SET BÁSICO": facturas afectas con descuento por ítem y descuento global, ítems exentos, NC que corrige giro (`CodRef` 2), NC por devolución (`CodRef` 3), NC que anula (`CodRef` 1) y ND que anula una NC;
  - "SET GUÍA DE DESPACHO": traslado interno, venta con transporte por emisor y por cliente;
  - "SET FACTURA EXENTA" con sus NC/ND;
  - "SET LIBRO DE VENTAS", "SET LIBRO DE COMPRAS" y "SET LIBRO DE GUÍAS".
- **Envío:** un EnvioDTE con todos los documentos del set y en el mismo orden, con `RutReceptor` 60803000-K y `NroResol` 0. Se itera hasta lograr EPR sin rechazos ni reparos, y luego se declara el avance indicando trackid y fecha [OF:CERT 6.1].

### 9.4 Simulación [OF:CERT 6.2]

- Un envío **sin rechazos ni reparos** con documentos representativos de la operación real de los últimos 2 meses: máximo 100 y mínimo 10.
- Las referencias "SET" no aplican [NV].
- Después se declara el avance.

### 9.5 Intercambio [OF:CERT 6.3]

- El SII envía DTE a la casilla registrada. El postulante responde con:
  1. el acuse de recibo (`RespuestaDTE` con `RecepcionEnvio`);
  2. el recibo de mercaderías (`EnvioRecibos`);
  3. el resultado comercial (`RespuestaDTE` con `ResultadoDTE`).
- Según el manual de 2009, las respuestas se envían a `SII_dte_intercambio@sii.cl`.
- Hoy el set de intercambio se descarga y las respuestas se suben en la opción web de intercambio de maullin [NV: así funciona en la práctica; verificar en el menú vigente]. Las respuestas deben usar `RutResponde` = empresa postulante y `RutRecibe` = emisor del set.

### 9.6 Muestras impresas [OF:MUES][OF:CERT 6.4]

- **Qué se envía:** PDF de todos los documentos del set, más un documento de cada tipo de la simulación (el manual de 2009 decía 10 de la simulación), incluidas las copias cedibles.
- **Archivos:** un documento por archivo y por página; cada archivo de máximo 500 KB (ideal unos 100 KB). Por correo, máximo 3 MB por mensaje, a `SII_dte_impresos@sii.cl`, con el RUT y el nombre en el asunto. La web de maullin tiene una revisión online [OF:MUES].
- **Hoja:** mínimo 21,5 × 11 cm y máximo 21,5 × 33 cm. Papel continuo de ancho mínimo 7,5 cm. Margen de al menos 0,5 cm.
- **Recuadro superior derecho:**
  - en rojo o negro, nunca verde;
  - borde de 0,5 a 1 mm;
  - tamaño de 1,5 × 5,5 cm a 4 × 8 cm;
  - letra de 10 puntos o más, en negrita;
  - contenido: solo "R.U.T.: 76.xxx.xxx-x" (con puntos), el nombre del documento en mayúsculas (FACTURA ELECTRÓNICA, FACTURA NO AFECTA O EXENTA ELECTRÓNICA, GUÍA DE DESPACHO ELECTRÓNICA, NOTA DE CRÉDITO ELECTRÓNICA, NOTA DE DÉBITO ELECTRÓNICA) y "N° folio";
  - bajo el recuadro: "S.I.I. - <Dirección Regional>".
- **Orden de los bloques:**
  - superior izquierda: emisor (razón social destacada, giro sin abreviar, casa matriz, sucursales); el logo, si existe, arriba a la izquierda y como máximo 1/5 del documento;
  - luego: fecha de emisión, receptor (razón social, RUT, giro, dirección), referencias (tipo de documento en palabras, folio, fecha y motivo), detalle y totales;
  - totales: "Exento" cuando corresponde; el IVA con su tasa ("IVA 19%"); en la 34 solo Monto Exento y Monto Total.
- **Timbre:** PDF417 de 2 × 5 a 4 × 9 cm, en la parte inferior, a al menos 2 cm del borde izquierdo. Debajo, con letra de 6 puntos o más:
  - "Timbre Electrónico SII";
  - "Res. NN de AAAA - Verifique documento: www.sii.cl". En certificación: "Res. 0 de <año de FchResol>".
- **Datos como texto:** RUT, tipo, folio y montos deben ser texto, no imagen.
- **Copias cedibles** (33, 34, 52, 46, 43):
  - recuadro de acuse de recibo con Nombre, RUT, Fecha, Recinto y Firma;
  - texto obligatorio de la Res. 51/2005: "El acuse de recibo que se declara en este acto, de acuerdo a lo dispuesto en la letra b) del Art. 4°, y la letra c) del Art. 5° de la Ley 19.983, acredita que la entrega de mercaderías o servicio(s) prestado(s) ha(n) sido recibido(s).";
  - leyenda "CEDIBLE" abajo a la derecha; en la guía, "CEDIBLE CON SU FACTURA";
  - no titular el recuadro "Recibí conforme".
- **Lo que no lleva acuse ni cedible:** las NC y ND, y la guía no venta.
- **Otros requisitos:**
  - descuentos por línea siempre en monto (el % es adicional);
  - guía con el tipo de traslado escrito en palabras;
  - sin textos de tratos comerciales.

### 9.7 Declaración y paso a producción [OF:CERT 6.5-6.6]

- El representante legal declara en la web que cumple los procedimientos de: gestión del CAF, foliación única, respaldo, envío, intercambio, cuadratura y contingencias.
- Después hay que solicitar CAF de producción en palena. Cambian el host (maullin → palena), `FchResol` y `NroResol`, y el `RutReceptor` real en el intercambio. El token no se comparte entre ambientes.

---

## 10. Libros (IECV, libro de guías) y RCV

### 10.1 En certificación [OF:SET III-IV][OF:IECV][OF:XSD]

Los documentos de certificación piden enviar:
- **IEV (Libro de Ventas)** con los documentos del set: facturas, NC y ND;
- **IEC (Libro de Compras)** con los datos del "set de libro de compras";
- el **Libro de Guías**, si se certifica la 52.

Formato del IECV (`LibroCV_v10.xsd`):

```xml
<LibroCompraVenta xmlns="http://www.sii.cl/SiiDte" version="1.0">
 <EnvioLibro ID="LibroVentas">
  <Caratula>
   <RutEmisorLibro/><RutEnvia/><PeriodoTributario>2026-10</PeriodoTributario>
   <FchResol/><NroResol>0</NroResol>
   <TipoOperacion>VENTA</TipoOperacion><TipoLibro>ESPECIAL</TipoLibro><TipoEnvio>TOTAL</TipoEnvio>
   <FolioNotificacion>1</FolioNotificacion>
  </Caratula>
  <ResumenPeriodo><TotalesPeriodo><TpoDoc>33</TpoDoc><TotDoc/><TotMntExe/><TotMntNeto/><TotMntIVA/><TotMntTotal/></TotalesPeriodo>…</ResumenPeriodo>
  <Detalle><TpoDoc>33</TpoDoc><NroDoc>…</NroDoc><TasaImp>19</TasaImp><FchDoc/><RUTDoc/><RznSoc/><MntExe/>?<MntNeto/><MntIVA/><MntTotal/></Detalle>
  <TmstFirma>…</TmstFirma>
 </EnvioLibro>
 <Signature>…URI="#LibroVentas"…</Signature>
</LibroCompraVenta>
```

- Carátula del set [OF:SET]:
  - ventas: `TipoLibro`=`ESPECIAL`, `TipoEnvio`=`TOTAL`, **`FolioNotificacion`=1**;
  - compras: `TipoOperacion`=`COMPRA`, **`FolioNotificacion`=2**;
  - mismo período tributario para todos los documentos del set.
- El libro de compras usa además `TpoImp`, `IVAUsoComun`, `IVANoRec`, `OtrosImp` y otros campos según los casos [OF:IECV].
- El libro de guías (`LibroGuia_v10.xsd`) **solo admite `TipoLibro`=`ESPECIAL`** y `FolioNotificacion` es obligatorio.
  - Detalle: `Folio`, `Anulado` (1 = folio anulado, 2 = guía anulada), `TpoOper` (=`IndTraslado`), `FchDoc`, `RUTDoc`, `RznSoc`, `MntNeto`, `TasaImp`, `IVA`, `MntTotal` y referencias.
  - Resumen: `TotGuiaVenta`, `TotMntGuiaVta` y `TotTraslado` por tipo.
- Los libros se suben por el **mismo DTEUpload** [NV: así se hace en la práctica] y se consultan con QueryEstUp.
- **Pendiente de verificar:** si el SII sigue exigiendo hoy los libros en certificación o si los sacó del set después del RCV [NV]. Mirar el contenido del set que se descargue: si trae secciones "LIBRO", hay que enviarlos.

### 10.2 En producción hoy (RCV) [NV]

- Desde agosto de 2017 (Res. Ex. SII N°61/2017), el Registro de Compras y Ventas (RCV) reemplazó la obligación de enviar el IECV mensual. El SII arma el RCV con los DTE recibidos.
- El contribuyente solo revisa, complementa y acepta en sii.cl (por ejemplo, documentos no electrónicos o clasificación de compras).
- `TpoTranVenta` y `TpoTranCompra` en el DTE alimentan esa clasificación [OF:FDTE bitácora 2017].
- El libro de guías se envía solo si el SII lo pide por notificación (así lo refleja el XSD, que solo admite ESPECIAL).
- El facturador no necesita generar IECV en producción, salvo libros especiales o rectificaciones solicitadas.

---

## 11. Rarezas y errores frecuentes que el SII documenta

1. **Primeras líneas del XML:** el SII valida que la línea 1 tenga `encoding="ISO-8859-1"` y la línea 2 el `schemaLocation`. Nada de XML en una sola línea [OF:INST A.3.1].
2. **Caracteres:** solo ISO-8859-1, más las 5 entidades XML. Si no, "Invalid Character" y rechazo por schema [OF:INST A.2.4].
3. **Firma del TED:** se calcula sobre el string `<DD>` sin espacios entre tags y sin namespaces. El CAF va intacto. `RSR`/`IT1` van en ISO-8859-1, máximo 40, con entidades [OF:INST A.2.4]. El TED no usa XMLDSig.
4. **Base64:** líneas de máximo 76 caracteres en certificados y firmas [OF:INST].
5. **Upload: User-Agent con `PROG 1.0`** para recibir XML [OF:UPL].
6. **Upload: boundary** con `--` al inicio y `--` final en el cierre; `Content-Length` sin headers; CRLF obligatorio [OF:UPL anexo 4].
7. **Upload: header Host:** no incluirlo en programas C con OpenSSL [OF:UPL anexo 4]. Con Python no aplica.
8. **QueryEstUp:** el ejemplo usa `<Rut>`/`<Dv>`, pero el WSDL dice `RutCompania`/`DvCompania` [OF:EUP]. El ejemplo de `SOK` muestra el texto `SDK`; el de FOK muestra `05`; el de PDR aparece como `PRD`. Son errores del manual.
9. **QueryEstDte:** `FechaEmisionDte` va en `DDMMAAAA`. Algunos ejemplos usan namespace `ssi.cl` (typo) y `GLOSA_ESTADO` en vez de `GLOSA` [OF:EDTE].
10. **Namespace SOAP:** el manual usa la URL del jws; el WSDL en vivo usa `http://DefaultNamespace` [OF:WSDL].
11. **Nombres de elementos en el instructivo que no son los del XSD:**
    - `TmsFirmaEnv` (formato AAAAMMDDHHMMSS) → `TmstFirmaEnv` (dateTime);
    - `SubTotDTE/TipoDTE` → `TpoDTE`;
    - `DetalleFactura` → `Detalle`;
    - `DescuentoRecargoGlobal` → `DscRcgGlobal`;
    - `RespuestaEnvioDTE` → `RespuestaDTE`;
    - `FMRT` → `FRMT`.
    
    Manda siempre el XSD.
12. **Typo en el ejemplo del manual de certificación:** `TmstFirma` aparece como `2003-09-08 T12:28:31`, con un espacio, y es inválido.
13. **Reparos en el set:** si un documento queda "aceptado con reparos", se reenvía con **otro folio**. Si se reusa el folio, se rechaza por duplicado [OF:SET II].
14. **Anulación de folios:** solo para folios que **no** se han enviado al SII [OF:INST 1.2]. Un DTE ya enviado se anula con una NC (`CodRef` 1).
15. **Una NC/ND que anula o corrige texto (`CodRef` 1 o 2) lleva una sola referencia.** Las NC/ND no llevan cedible ni acuse [OF:FDTE][OF:MUES].
16. **Factura 33 con todos los ítems exentos:** está mal; debe ser 34 [OF:FDTE].
17. **`PrcItem` y `QtyItem` no admiten 0** (mínimo 0.000001). Si no hay precio, se omiten [OF:XSD].
18. **Detalle:** máximo 60 líneas, que además deben caber en una hoja impresa (máximo tamaño oficio) [OF:FDTE][OF:MOD].
19. **El administrador no tiene por defecto los perfiles** de solicitar folios ni de enviar. Hay que asignárselos [OF:CERT 2.1].
20. **Plazo del set:** 2 meses. Se evalúa contra el último set descargado. Hay inactividad máxima de 6 meses en certificación [OF:CERT][OF:sii.cl].
21. **Política de uso de los WS:** el SII puede suspender el acceso si detecta uso masivo o anormal. Limitar el polling [OF:INST anexo 5].
22. **`CodRchDsc` en `ResultadoDTE`** es `negativeInteger` en el XSD [OF:XSD].
23. **Token y semilla:** la semilla dura 2 minutos. El RUT del certificado debe tener habilitada la autenticación con certificado en sii.cl (error `-07`) [OF:AUT].

---

## Anexo A. Archivos de referencia descargados (todos oficiales del SII)

Ruta base: `.../scratchpad/sii_docs/online/`

- `fm_formato_dte.pdf` (+ `.u.txt`): Formato DTE v2.2 de 2019, con obligatoriedades por tipo y la tabla de códigos de impuestos (sección 4).
- `fm_schema_dte/`: DTE_v10.xsd (06/02/2026), EnvioDTE_v10.xsd, SiiTypes_v10.xsd y xmldsignature_v10.xsd vigentes.
- `fm_schema_ic/RespuestaEnvioDTE_v10.xsd`, `fm_formato_ic.pdf`: respuesta de intercambio.
- `fm_schema19983/` (EnvioRecibos_v10.xsd, Recibos_v10.xsd), `fm_desc_19983.pdf`: recibos Ley 19.983.
- `fm_schema_iecv/`, `formato_iecv.pdf`: libros de compra y venta.
- `fm_schema_lgd/`, `formato_lgd.pdf`: libro de guías.
- `fm_schema_resp/RespSII_v10.xsd`: correo de resultado del SII.
- `fm_ejemplo_xml/F60T33-ejemplo.xml`: ejemplo oficial de EnvioDTE.
- `ws_reclamo_v12.pdf`: WS de registro de aceptación/reclamo.

## Anexo B. Lista de verificación de implementación (sin código)

1. Cargar el CAF y validar `FRMA` (llave del SII según `IDK`) y el par `RSASK`/`RSAPK` [OF:INST 1.4].
2. Construir el `Documento` en el orden del XSD y calcular los totales con `Decimal` y redondeo half-up.
3. Construir el `DD`, serializarlo a mano en un string ISO-8859-1 aplanado y firmarlo con RSA-SHA1 PKCS#1 v1.5. Probar con el caso del Manual de Certificación 5.2.
4. Insertar el `TED` y el `TmstFirma`.
5. Armar el `EnvioDTE` completo, firmar cada `Documento` dentro del árbol final y después firmar `SetDoc`.
6. Validar contra el XSD vigente y verificar las firmas localmente con xmlsec.
7. Serializar sin re-indentar lo que ya está firmado.
8. Obtener la semilla y el token, y hacer el upload con multipart, `PROG 1.0` y la cookie TOKEN.
9. Guardar el TRACKID y consultar QueryEstUp hasta un estado final. Conciliar con el correo `RESULTADO_ENVIO`.
10. Enviar el EnvioDTE al receptor por correo y procesar las respuestas (`RespuestaDTE` y `EnvioRecibos`). Para lo que se recibe, registrar ACD/ERM/RCD en el WS de reclamo dentro de 8 días.
11. Generar el PDF con el PDF417 (ECL 5, modo byte), el recuadro, las leyendas y la copia cedible.
