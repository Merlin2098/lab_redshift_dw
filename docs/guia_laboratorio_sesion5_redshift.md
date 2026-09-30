# Guía de Laboratorio — Sesión 5: Data Warehouse con Amazon Redshift

**Modalidad:** Demo guiada del instructor (pantalla compartida) — **sin laboratorio individual del alumno**, siguiendo el alcance definido en `03_temario.md` ("para evitar costo/complejidad operativa").
**Duración estimada:** 45–55 min (incluye troubleshooting opcional de 15 min).
**Dataset:** TICKIT — el dataset de ejemplo oficial de AWS para Amazon Redshift (2 fact tables + 5 dimensiones), alojado públicamente en `s3://redshift-downloads/tickit/`. No depende de que la Sesión 4 haya salido perfecta en todos los grupos.

Todos los comandos de esta guía están verificados contra la documentación oficial de AWS (ver fuentes al final).

---

## 0. Preparación previa (antes de la clase, no en vivo)

Para no quemar tiempo de sesión en provisioning, el cluster/workgroup debe estar desplegado **antes** de empezar la demo.

### 0.1. Desplegar Redshift Serverless

El lab se despliega con Terraform (ver [README](../README.md#2-desplegar)): `terraform -chdir=infra apply` crea el
namespace y el workgroup con **4 RPUs** (el mínimo actual en us-east-1 y suficiente para TICKIT, que no es un dataset
de gran volumen). No hay contraseñas en texto plano: la contraseña de admin la genera y guarda Secrets Manager.

### 0.2. IAM Role para COPY/UNLOAD/Spectrum

El rol IAM lo crea Terraform y queda como **rol por defecto** del namespace. Por eso el SQL usa `IAM_ROLE DEFAULT` y
no lleva ARNs. Además se crea `rol-sin-permisos` para la Parte 7. Solo puede haber un rol default por namespace.

### 0.3. Región

El bucket público `s3://redshift-downloads/tickit/` reside en **us-east-1**. El lab se despliega ahí (Terraform valida
la región) para evitar transferencia cross-region.

### 0.4. Conexión

Usar **Redshift Query Editor v2** (recomendado para la demo — no requiere instalar cliente SQL, permite proyectar pantalla completa y guardar notebooks). Conectar con la opción **AWS Secrets Manager** (secret del output `admin_secret_arn`, visible con `terraform -chdir=infra output admin_secret_arn`) sobre el workgroup del lab (output `workgroup_name`), base `dev`.

---

## Narrativa de la demo

```text
S3 (TICKIT)
   ↓ COPY
Redshift (modelo dimensional ya cargado)
   ↓ query analítica
Comparación Athena vs. Redshift
   ↓ UNLOAD
S3 (resultado agregado)
   ↓ Spectrum
Consulta sin carga física
   ↓ (opcional)
Troubleshooting: COPY sin permisos IAM
```

---

## Parte 1 — S3 → Redshift (COPY)

**Objetivo:** mostrar cómo datos que hoy están en S3 se cargan a Redshift de forma paralela.

### 1.1. Crear las tablas del modelo TICKIT

Ejecutar en el Query Editor v2 (proyectar en pantalla):

```sql
CREATE TABLE users(
    userid        INTEGER NOT NULL PRIMARY KEY,
    username      CHAR(8),
    firstname     VARCHAR(30),
    lastname      VARCHAR(30),
    city          VARCHAR(30),
    state         CHAR(2),
    email         VARCHAR(100),
    phone         CHAR(14),
    likesports    BOOLEAN,
    liketheatre   BOOLEAN,
    likeconcerts  BOOLEAN,
    likejazz      BOOLEAN,
    likeclassical BOOLEAN,
    likeopera     BOOLEAN,
    likerock      BOOLEAN,
    likevegas     BOOLEAN,
    likebroadway  BOOLEAN,
    likemusicals  BOOLEAN
);

CREATE TABLE venue(
    venueid    SMALLINT NOT NULL PRIMARY KEY,
    venuename  VARCHAR(100),
    venuecity  VARCHAR(30),
    venuestate CHAR(2),
    venueseats INTEGER
);

CREATE TABLE category(
    catid    SMALLINT NOT NULL PRIMARY KEY,
    catgroup VARCHAR(10),
    catname  VARCHAR(10),
    catdesc  VARCHAR(50)
);

CREATE TABLE date(
    dateid    SMALLINT NOT NULL PRIMARY KEY,
    caldate   DATE NOT NULL,
    day       CHAR(3) NOT NULL,
    week      SMALLINT NOT NULL,
    month     CHAR(5) NOT NULL,
    qtr       CHAR(5) NOT NULL,
    year      SMALLINT NOT NULL,
    holiday   BOOLEAN DEFAULT FALSE
);

CREATE TABLE event(
    eventid  INTEGER NOT NULL PRIMARY KEY,
    venueid  SMALLINT,
    catid    SMALLINT,
    dateid   SMALLINT NOT NULL,
    eventname VARCHAR(200),
    starttime TIMESTAMP
);

CREATE TABLE listing(
    listid    INTEGER NOT NULL PRIMARY KEY,
    sellerid  INTEGER,
    eventid   INTEGER,
    dateid    SMALLINT,
    numtickets SMALLINT,
    priceperticket DECIMAL(8,2),
    totalprice DECIMAL(8,2),
    listtime  TIMESTAMP
);

-- Fact table principal
CREATE TABLE sales(
    salesid    INTEGER NOT NULL PRIMARY KEY,
    listid     INTEGER NOT NULL,
    sellerid   INTEGER NOT NULL,
    buyerid    INTEGER NOT NULL,
    eventid    INTEGER NOT NULL,
    dateid     SMALLINT NOT NULL,
    qtysold    SMALLINT NOT NULL,
    pricepaid  DECIMAL(8,2),
    commission DECIMAL(8,2),
    saletime   TIMESTAMP
);
```

> **Nota pedagógica (Bloque 2 — Modelado dimensional):** `sales` es la fact table (measures: `qtysold`, `pricepaid`, `commission`; grain: una fila = una venta). `users`, `venue`, `category`, `date`, `event`, `listing` son las dimensiones — este es un ejemplo real de Star Schema, no solo el diagrama conceptual de las slides.

### 1.2. Cargar con COPY (paralelo, vía IAM_ROLE)

```sql
COPY users
FROM 's3://redshift-downloads/tickit/allusers_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';

COPY venue
FROM 's3://redshift-downloads/tickit/venue_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';

COPY category
FROM 's3://redshift-downloads/tickit/category_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';

COPY date
FROM 's3://redshift-downloads/tickit/date2008_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';

COPY event
FROM 's3://redshift-downloads/tickit/allevents_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' TIMEFORMAT 'YYYY-MM-DD HH:MI:SS' REGION 'us-east-1';

COPY listing
FROM 's3://redshift-downloads/tickit/listings_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';

COPY sales
FROM 's3://redshift-downloads/tickit/sales_tab.txt'
IAM_ROLE DEFAULT
DELIMITER '\t' TIMEFORMAT 'MM/DD/YYYY HH:MI:SS' REGION 'us-east-1';
```

**Puntos a resaltar en vivo (conectar con Bloque 4 de las slides):**
- La autorización usa `IAM_ROLE`, no claves de acceso en texto plano — práctica recomendada por AWS.
- `COPY` carga en paralelo entre todos los slices del workgroup, a diferencia de un `INSERT` fila por fila.
- Mostrar en el editor cuántas filas cargó cada tabla (`SELECT COUNT(*) FROM sales;` → ~172,000 filas), para dar sensación de "esto sí es un volumen real de Data Warehouse", aunque sea pequeño.

---

## Parte 2 — Modelo dimensional ya cargado

**Objetivo:** mostrar el Star Schema funcionando, sin convertir la demo en una clase de modelado (eso ya se cubrió en el Bloque 2 de las slides).

```sql
SELECT
    s.salesid, s.qtysold, s.pricepaid,
    d.caldate, d.month, d.year,
    e.eventname,
    v.venuename, v.venuestate
FROM sales s
JOIN date d    ON s.dateid  = d.dateid
JOIN event e   ON s.eventid = e.eventid
JOIN venue v   ON e.venueid = v.venueid
LIMIT 20;
```

Señalar en pantalla: `sales` (fact) al centro, `date`, `event`, `venue` (dimensiones) alrededor — es el mismo Star Schema de la Slide 10, ahora con datos reales.

---

## Parte 3 — Query analítica agregada

**Objetivo:** mostrar el propósito real de un Data Warehouse: agregaciones de negocio sobre datos históricos.

```sql
SELECT
    d.year,
    d.month,
    c.catgroup,
    SUM(s.qtysold)              AS total_tickets_vendidos,
    SUM(s.pricepaid)            AS ingresos_totales,
    ROUND(AVG(s.pricepaid), 2)  AS ticket_promedio
FROM sales s
JOIN date d     ON s.dateid  = d.dateid
JOIN event e    ON s.eventid = e.eventid
JOIN category c ON e.catid   = c.catid
GROUP BY d.year, d.month, c.catgroup
ORDER BY d.year, d.month, ingresos_totales DESC;
```

**Idea a transmitir:** esta es exactamente la clase de consulta recurrente de BI (agregaciones por mes/categoría) que justifica tener un Data Warehouse en vez de solo un Data Lake.

---

## Parte 4 — Athena vs. Redshift (comparación en vivo)

**Objetivo:** el eje central de la sesión según el temario — que el alumno vea la diferencia, no solo la escuche.

### 4.1. Exponer los mismos datos vía Spectrum/Athena

La tabla externa `spectrumdb.sales` se crea con `sql/07_spectrum_setup.sql` (la misma de la Parte 6) y Athena la lee
desde el Glue Data Catalog.

### 4.2. Ejecutar el mismo query conceptual en ambos motores

En **Athena**, sobre los datos crudos en S3:

```sql
SELECT dateid, COUNT(*) AS ventas, SUM(pricepaid) AS ingresos
FROM spectrumdb.sales
GROUP BY dateid
ORDER BY ingresos DESC
LIMIT 10;
```

En **Redshift**, sobre la tabla ya cargada:

```sql
SELECT dateid, COUNT(*) AS ventas, SUM(pricepaid) AS ingresos
FROM sales
GROUP BY dateid
ORDER BY ingresos DESC
LIMIT 10;
```

> La versión anterior de la consulta de Athena hacía `GROUP BY catgroup` sobre `sales`, columna que esa tabla no tiene.
> Ambas consultas usan ahora solo columnas de `sales`.

### 4.3. Comparar en pantalla

| Aspecto | Athena | Redshift |
|---|---|---|
| Tiempo de respuesta | Mostrar el tiempo real que reporta la consola | Mostrar el tiempo real que reporta la consola |
| Costo | $5 por TB escaneado (mínimo 10 MB/consulta) | Cómputo del workgroup (RPUs), no por dato escaneado |
| ¿Requiere carga previa? | No — consulta directa sobre S3 | Sí — los datos ya están cargados |

**Mensaje clave (ya presente en las slides, Bloque 12):** no es "cuál es mejor", sino "qué workload tiene cada uno" — Athena para exploración ad hoc, Redshift para analytics empresarial recurrente con modelo dimensional ya resuelto.

---

## Parte 5 — UNLOAD (Redshift → S3)

**Objetivo:** mostrar que Redshift también puede ser productor de datos hacia el Data Lake.

```sql
UNLOAD ('SELECT d.year, d.month, c.catgroup, SUM(s.pricepaid) AS ingresos
         FROM sales s
         JOIN date d ON s.dateid = d.dateid
         JOIN event e ON s.eventid = e.eventid
         JOIN category c ON e.catid = c.catid
         GROUP BY d.year, d.month, c.catgroup')
TO 's3://<bucket_name>/gold/ventas_agregadas/'
IAM_ROLE DEFAULT
FORMAT AS PARQUET
PARTITION BY (year)
ALLOWOVERWRITE;
```

Mostrar en la consola de S3 los archivos Parquet resultantes, particionados por año — cerrando el ciclo COPY/UNLOAD del Bloque 4. (`<bucket_name>` es el output `bucket_name` de Terraform.)

---

## Parte 6 — Redshift Spectrum

**Objetivo:** consultar datos en S3 sin cargarlos físicamente al cluster.

TICKIT ya incluye una carpeta pensada para esto: `s3://redshift-downloads/tickit/spectrum/sales/`.

### 6.1. Crear el external schema

La base de Glue `spectrumdb` ya existe: la crea Terraform (y la destruye con el resto), por eso no se usa `CREATE EXTERNAL DATABASE`.

```sql
CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum
FROM DATA CATALOG
DATABASE 'spectrumdb'
IAM_ROLE DEFAULT;
```

### 6.2. Crear la external table

```sql
CREATE EXTERNAL TABLE spectrum.sales(
    salesid    INTEGER,
    listid     INTEGER,
    sellerid   INTEGER,
    buyerid    INTEGER,
    eventid    INTEGER,
    dateid     SMALLINT,
    qtysold    SMALLINT,
    pricepaid  DECIMAL(8,2),
    commission DECIMAL(8,2),
    saletime   TIMESTAMP
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE
LOCATION 's3://redshift-downloads/tickit/spectrum/sales/';
```

### 6.3. Consultar sin haber cargado nada

```sql
SELECT COUNT(*) FROM spectrum.sales;

-- Combinar datos externos (Spectrum) con datos ya cargados en Redshift
SELECT sp.salesid, sp.pricepaid, u.city
FROM spectrum.sales sp
JOIN users u ON sp.buyerid = u.userid
LIMIT 10;
```

**Mensaje clave (Bloque 5):** los datos de `spectrum.sales` nunca se cargaron físicamente al workgroup — Redshift los lee directamente desde S3 usando el Glue Data Catalog como metastore.

> **Nota:** si el bucket de destino de la región del curso no está en `us-east-1`, copiar también esta subcarpeta al bucket propio (ver sección 0.3) y ajustar el `LOCATION`.

---

## Parte 7 (opcional, ~15 min) — Troubleshooting: COPY sin permisos IAM

Alineado con `04_rediseno_sesiones_3_a_9.md`: un solo caso, ligero, no una secuencia extensa de diagnóstico.

### 7.1. Provocar el error

Ejecutar un `COPY` usando un rol IAM que **no** tiene permiso de lectura sobre el bucket (Terraform ya crea `rol-sin-permisos`; su ARN es el output `no_permissions_role_arn`):

```sql
COPY users
FROM 's3://redshift-downloads/tickit/allusers_pipe.txt'
IAM_ROLE '<no_permissions_role_arn>'
DELIMITER '|' REGION 'us-east-1';
```

Redshift devuelve un error de tipo `S3ServiceException` / `Access Denied`.

### 7.2. Diagnosticar

```sql
-- Errores de carga a nivel de fila (datos mal formados). Para un error de permisos el resultado es VACÍO:
-- esta vista solo registra problemas de datos, no de acceso.
SELECT *
FROM sys_load_error_detail
ORDER BY start_time DESC
LIMIT 5;

-- El historial solo muestra que la consulta falló, con un mensaje genérico ("sending CmdAbort")
SELECT query_id, status, error_message
FROM sys_query_history
WHERE query_text LIKE 'COPY users%'
ORDER BY start_time DESC
LIMIT 5;
```

Guiar al alumno a leer **el mensaje de error que devuelve el propio `COPY`** (`S3ServiceException: Access Denied, Status 403`): ahí está la pista de que el problema es de **permisos del rol**, no de sintaxis SQL ni de formato de datos. Que `sys_load_error_detail` salga vacío es parte de la lección: esa vista es para errores de datos.

### 7.3. Corregir

Vaciar la tabla con `TRUNCATE users;` (ya se había cargado en la Parte 1), volver a ejecutar el mismo `COPY` con el rol correcto (`IAM_ROLE DEFAULT`, como en la Parte 1) y confirmar que carga exitosamente.

**Mensaje clave:** este es el mismo tipo de error (`COPY` sin permisos IAM del rol) que aparece documentado como caso de troubleshooting en el diseño general del curso — mantiene coherencia con las demás sesiones.

---

## Checklist de cierre de la demo

- [ ] Namespace/workgroup desplegado con Terraform y verificado antes de clase
- [ ] IAM Role por defecto del namespace (lo crea Terraform)
- [ ] Las 7 tablas TICKIT creadas y cargadas (validar counts)
- [ ] Bucket propio del curso listo para UNLOAD (con permisos de escritura en el rol)
- [ ] External schema de Spectrum probado de antemano (evita sorpresas de Lake Formation/permisos en vivo)
- [ ] Decidir si se incluye la Parte 7 (troubleshooting) según el tiempo disponible ese día
- [ ] `terraform destroy` ejecutado y `verify_teardown.py` imprime OK

---

## Automatización

Cada parte se puede ejecutar con `uv run python scripts/lab/run_lab.py --part N` (o `--all`), y `--check` valida los
conteos de TICKIT. El SQL de cada parte vive en `sql/`. Ver el [README](../README.md).

---

## Fuentes consultadas (AWS Documentation, vía AWS MCP)

- [Get started with Amazon Redshift provisioned data warehouses — TICKIT](https://docs.aws.amazon.com/redshift/latest/gsg/new-user.html)
- [Sample database (TICKIT schema)](https://docs.aws.amazon.com/redshift/latest/dg/c_sampledb.html)
- [Load data — TICKIT sample dataset](https://docs.aws.amazon.com/redshift/latest/gsg/cm-dev-t-load-sample-data.html)
- [Using the COPY command to load from Amazon S3](https://docs.aws.amazon.com/redshift/latest/dg/t_loading-tables-from-s3.html)
- [COPY command reference and examples (tickit bucket)](https://docs.aws.amazon.com/redshift/latest/dg/r_COPY_command_examples.html)
- [Getting started with Amazon Redshift Spectrum (tickit/spectrum/sales)](https://docs.aws.amazon.com/redshift/latest/dg/c-getting-started-using-spectrum.html)
- [External tables for Redshift Spectrum](https://docs.aws.amazon.com/redshift/latest/dg/c-spectrum-external-tables.html)
- [Workgroups and namespaces](https://docs.aws.amazon.com/redshift/latest/mgmt/serverless-workgroup-namespace.html)
- [Amazon Athena pricing ($5/TB, mínimo 10 MB)](https://docs.aws.amazon.com/whitepapers/latest/big-data-analytics-options/amazon-athena.html)

---

## Referencia cruzada con el material del curso

Esta guía está diseñada para ejecutarse en el orden narrativo de `propuesta_diseno_ppts_sesion_5_redshift.md`:

| Parte de la demo | Bloque de las slides |
|---|---|
| Parte 1 (COPY) | Bloque 4 — Data Movement |
| Parte 2 (modelo dimensional) | Bloque 2 — Modelado dimensional |
| Parte 3 (query analítica) | Bloque 1 — Data Warehouse |
| Parte 4 (Athena vs. Redshift) | Bloque 12 — Redshift vs. Athena |
| Parte 5 (UNLOAD) | Bloque 4 — Data Movement |
| Parte 6 (Spectrum) | Bloque 5 — Datos externos |
| Parte 7 (troubleshooting, opcional) | Bloque 8 — Observabilidad y Troubleshooting (versión ligera) |
