# 2. Laboratorio en la consola de AWS

Esta guía recorre el laboratorio **usando solo la consola web de AWS**: Redshift Query Editor v2, Athena, S3 y Glue. Es la segunda de dos:

1. [Despliegue de la infraestructura](01_despliegue_infraestructura.md): crea todo lo necesario con Terraform.
2. **Laboratorio en la consola de AWS** (este documento): qué hacer con esa infraestructura.

**Modalidad:** demo guiada del instructor, que cada alumno puede replicar siguiendo la grabación.
**Duración estimada:** 45 a 55 minutos (incluye 15 minutos opcionales de troubleshooting).
**Dataset:** TICKIT, el dataset de ejemplo oficial de AWS para Redshift (2 tablas de hechos y 5 dimensiones).

> Todo lo que se hace aquí a mano también se puede ejecutar con un comando por parte: `uv run python scripts/lab/run_lab.py --part N` (ver la sección *Automatización* al final). Esta guía es la versión para entender y mostrar cada paso.

## Antes de empezar

- La infraestructura debe estar desplegada ([guía 1](01_despliegue_infraestructura.md)).
- En la consola de AWS, **confirma que la región es N. Virginia (us-east-1)** (selector arriba a la derecha). Si estás en otra región no verás nada de lo creado.
- Ten a mano estos valores. Los obtienes con `terraform -chdir=infra output`:

| Valor | Comando | Dónde se usa |
|---|---|---|
| `workgroup_name` (p. ej. `redshift-lab-dev-wg`) | `terraform -chdir=infra output -raw workgroup_name` | Conectarse en Query Editor v2 y elegir el workgroup en Athena |
| `admin_secret_arn` | `terraform -chdir=infra output -raw admin_secret_arn` | Identificar el secreto de conexión |
| `bucket_name` | `terraform -chdir=infra output -raw bucket_name` | UNLOAD (Parte 5) |
| `no_permissions_role_arn` | `terraform -chdir=infra output -raw no_permissions_role_arn` | Provocar el error de la Parte 7 |

En los bloques SQL de esta guía, `<bucket_name>` y `<no_permissions_role_arn>` son los valores de la tabla anterior: **reemplázalos antes de ejecutar**. El resto del SQL se ejecuta tal cual.

## Narrativa de la demo

```text
S3 público (TICKIT)
   ↓ COPY
Redshift (modelo dimensional cargado)
   ↓ consulta analítica
Comparación Athena vs. Redshift
   ↓ UNLOAD
S3 del lab (resultado agregado)
   ↓ Spectrum
Consulta sobre S3 sin carga física
   ↓ (opcional)
Troubleshooting: COPY sin permisos IAM
```

## Parte 0 — Conectarse a Redshift con Query Editor v2

**Objetivo:** abrir una sesión SQL contra el workgroup que creó Terraform. Son tres pasos: (0.1) entrar con la identidad correcta, (0.2) inicializar Query Editor v2 en la cuenta, la primera vez, y (0.3) crear la conexión con el secreto.

### 0.1 Entra con un usuario IAM, no con root

Query Editor v2 **no funciona con el usuario root** de la cuenta: la pantalla de configuración falla con *User information couldn't be retrieved. You must have an account to use Redshift Query Editor V2.* Entra a la consola con un **usuario o rol IAM**:

- En un sandbox basta `AdministratorAccess`.
- Con permisos mínimos, necesita la política administrada **AmazonRedshiftQueryEditorV2FullAccess** y poder leer el secreto de administrador de Redshift (`secretsmanager:GetSecretValue`).

Si solo tienes root, créate un usuario en **IAM → Users → Create user** con acceso a la consola, adjúntale una de esas políticas y entra con la URL de inicio de sesión de IAM de tu cuenta (aparece en el resumen de IAM).

### 0.2 Inicializar Query Editor v2 en la cuenta (solo la primera vez)

1. En la consola de AWS, abre **Amazon Redshift**. En el menú de la izquierda elige **Query editor v2** (se abre en una pestaña nueva).
2. Si es la primera vez que se usa en esta cuenta y región, aparece la pantalla **Configure account**. Déjala con sus valores por defecto:
   - **AWS KMS encryption:** no marques *Customize encryption settings*. Se usa una clave que AWS gestiona por ti (esta opción no se puede cambiar después).
   - **S3 bucket (optional):** deja **S3 URI** vacío. Solo sirve para cargar archivos locales, que el lab no usa.
3. Elige **Configure account**. Se hace una sola vez: los alumnos que ya hayan usado el editor en su cuenta ven directamente el editor y saltan este paso.

### 0.3 Conectarse al workgroup con el secreto de Terraform

**Mientras no haya una conexión activa, el botón Run está deshabilitado** y los selectores **Cluster or workgroup** y **Database** de la barra superior aparecen vacíos. Para crearla:

1. En el panel izquierdo (árbol de conexiones) aparece el workgroup serverless del lab: **Serverless: redshift-lab-dev-wg**. Haz clic sobre su nombre. Si no se abre la ventana de conexión, haz clic derecho sobre el nombre y elige **Create connection**.
2. En **Authentication** elige **AWS Secrets Manager**.
3. En **Secret** selecciona el secreto cuyo nombre empieza por `redshift!redshift-lab-dev-ns-` y termina en `-awsuser`. Es el que corresponde al `admin_secret_arn` de las salidas de Terraform.
4. Elige **Create connection**.
5. Comprueba que la barra superior muestra el workgroup en **Cluster or workgroup** y `dev` en **Database**. Ahora **Run** está activo.
6. Abre una pestaña **Editor** y ejecuta esta consulta de comprobación:

```sql
SELECT current_user, current_database();
```

Debe devolver el usuario administrador (`awsuser`) y la base `dev`.

> **No uses el método "Database user name and password".** Con él, Query Editor v2 **crea por su cuenta un secreto `sqlworkbench-...` en Secrets Manager**. Terraform no lo conoce: no lo borra al destruir la infraestructura, sigue facturando y el verificador de la guía 1 no lo detecta. El método *AWS Secrets Manager* reutiliza el secreto que ya creó Terraform y no deja nada nuevo.

**Notas del editor:**
- Cada pestaña **Editor** abre por defecto una *sesión aislada*.
- Los resultados se limitan a **100 filas** por defecto (opción **Limit 100**). Las consultas de esta guía devuelven pocas filas, así que no afecta.
- **Si el secreto no aparece en la lista:** revisa que estás en us-east-1 y que tu usuario puede leer secretos (`secretsmanager:ListSecrets` y `secretsmanager:GetSecretValue`). El secreto gestionado por Redshift trae la etiqueta `Redshift`, que es la que el editor necesita para listarlo.

## Parte 1 — S3 → Redshift (COPY)

**Objetivo:** mostrar cómo los datos que están en S3 se cargan a Redshift de forma paralela.

### 1.0 ¿De dónde salen los datos?

Es la pregunta clave de esta parte. **El bucket que creó Terraform está vacío a propósito**: no es el origen de los datos. Los `COPY` leen de un **bucket público que mantiene AWS**, `s3://redshift-downloads/tickit/`, que ya contiene los archivos. No hay que crearlos ni subirlos.

Puedes verlos desde una terminal (no necesita credenciales):

```bash
aws s3 ls s3://redshift-downloads/tickit/ --no-sign-request
```

Verás estos 7 archivos (más la carpeta `spectrum/` que se usa en la Parte 6):

| Archivo en S3 | Tamaño | Tabla destino |
|---|---|---|
| `allusers_pipe.txt` | 5,9 MB | `users` |
| `venue_pipe.txt` | 8 KB | `venue` |
| `category_pipe.txt` | 0,5 KB | `category` |
| `date2008_pipe.txt` | 15 KB | `date` |
| `allevents_pipe.txt` | 446 KB | `event` |
| `listings_pipe.txt` | 11,6 MB | `listing` |
| `sales_tab.txt` | 11,3 MB | `sales` |

Tu bucket del lab solo se llenará más adelante: con los resultados de Athena (Parte 4) y con el resultado de UNLOAD (Parte 5).

### 1.1 Crear las tablas

Pega este bloque en el editor y pulsa **Run**. Primero borra las tablas si existen (así puedes repetir la parte sin duplicar datos) y luego crea las siete:

```sql
DROP TABLE IF EXISTS sales;

DROP TABLE IF EXISTS listing;

DROP TABLE IF EXISTS event;

DROP TABLE IF EXISTS date;

DROP TABLE IF EXISTS category;

DROP TABLE IF EXISTS venue;

DROP TABLE IF EXISTS users;

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
    eventid   INTEGER NOT NULL PRIMARY KEY,
    venueid   SMALLINT,
    catid     SMALLINT,
    dateid    SMALLINT NOT NULL,
    eventname VARCHAR(200),
    starttime TIMESTAMP
);

CREATE TABLE listing(
    listid         INTEGER NOT NULL PRIMARY KEY,
    sellerid       INTEGER,
    eventid        INTEGER,
    dateid         SMALLINT,
    numtickets     SMALLINT,
    priceperticket DECIMAL(8,2),
    totalprice     DECIMAL(8,2),
    listtime       TIMESTAMP
);

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

Debe terminar sin errores. En el panel izquierdo, bajo `dev` → `public` → **Tables** (actualiza el árbol si no las ves), aparecen las siete tablas.

> **Nota pedagógica (modelado dimensional):** `sales` es la **tabla de hechos**: su granularidad es una fila por venta y sus medidas son `qtysold`, `pricepaid` y `commission`. `users`, `venue`, `category`, `date`, `event` y `listing` son las **dimensiones**. Es un ejemplo real de *star schema*, no solo el diagrama de las slides.

### 1.2 Cargar los datos con COPY

Ahora se cargan los siete archivos del bucket público a las tablas que acabas de crear:

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

Qué hace cada elemento:

| Elemento | Qué significa |
|---|---|
| `FROM 's3://redshift-downloads/tickit/...'` | El archivo de origen: el bucket **público de AWS**, no tu bucket. |
| `IAM_ROLE DEFAULT` | Redshift lee S3 con el rol que Terraform dejó como **rol por defecto** del namespace. Ese rol solo puede **leer** `redshift-downloads/tickit/*` y leer/escribir tu bucket del lab. No hay claves de acceso en el SQL. |
| `DELIMITER '\|'` o `'\t'` | Cómo se separan las columnas en el archivo (barra vertical o tabulador). |
| `TIMEFORMAT '...'` | El formato de las fechas con hora en ese archivo (`event` y `sales`). |
| `REGION 'us-east-1'` | La región del bucket de origen. |

**Puntos a resaltar en vivo:**
- La autorización usa `IAM_ROLE`, **no claves de acceso en texto plano**: es la práctica recomendada por AWS.
- `COPY` carga **en paralelo** entre todos los slices del workgroup, a diferencia de un `INSERT` fila por fila.

### 1.3 Comprobar la carga

```sql
SELECT 'users' AS tabla, COUNT(*) AS filas FROM users
UNION ALL SELECT 'venue', COUNT(*) FROM venue
UNION ALL SELECT 'category', COUNT(*) FROM category
UNION ALL SELECT 'date', COUNT(*) FROM date
UNION ALL SELECT 'event', COUNT(*) FROM event
UNION ALL SELECT 'listing', COUNT(*) FROM listing
UNION ALL SELECT 'sales', COUNT(*) FROM sales;
```

Resultado esperado:

| tabla | filas |
|---|---|
| users | 49.990 |
| venue | 202 |
| category | 11 |
| date | 365 |
| event | 8.798 |
| listing | 192.497 |
| sales | 172.456 |

Que `sales` tenga **~172.000 filas** da la sensación de un volumen real de Data Warehouse, aunque sea pequeño.

> **Si un `COPY` falla con `Access Denied`:** es el mismo error que se provoca a propósito en la Parte 7. Revisa que estás usando `IAM_ROLE DEFAULT` y no otro rol.

## Parte 2 — Modelo dimensional ya cargado

**Objetivo:** mostrar el *star schema* funcionando, sin convertir la demo en una clase de modelado (eso ya se cubrió en las slides).

```sql
SELECT
    s.salesid, s.qtysold, s.pricepaid,
    d.caldate, d.month, d.year,
    e.eventname,
    v.venuename, v.venuestate
FROM sales s
JOIN date d  ON s.dateid  = d.dateid
JOIN event e ON s.eventid = e.eventid
JOIN venue v ON e.venueid = v.venueid
LIMIT 20;
```

Señalar en pantalla: `sales` (hechos) al centro y `date`, `event` y `venue` (dimensiones) alrededor. Es el mismo star schema de la Slide 10, ahora con datos reales. Las 20 filas que devuelve no tienen un orden garantizado.

## Parte 3 — Consulta analítica agregada

**Objetivo:** mostrar el propósito real de un Data Warehouse: agregaciones de negocio sobre datos históricos.

```sql
SELECT
    d.year,
    d.month,
    c.catgroup,
    SUM(s.qtysold)             AS total_tickets_vendidos,
    SUM(s.pricepaid)           AS ingresos_totales,
    ROUND(AVG(s.pricepaid), 2) AS ticket_promedio
FROM sales s
JOIN date d     ON s.dateid  = d.dateid
JOIN event e    ON s.eventid = e.eventid
JOIN category c ON e.catid   = c.catid
GROUP BY d.year, d.month, c.catgroup
ORDER BY d.year, d.month, ingresos_totales DESC;
```

Devuelve **24 filas** (12 meses × 2 grupos de categoría). Las primeras deben ser:

| year | month | catgroup | total_tickets_vendidos | ingresos_totales | ticket_promedio |
|---|---|---|---|---|---|
| 2008 | APR | Concerts | 18231 | 5916127.00 | 652.41 |
| 2008 | APR | Shows | 12596 | 4154861.00 | 658.87 |

**Idea a transmitir:** esta es la clase de consulta recurrente de BI (agregaciones por mes y categoría) que justifica tener un Data Warehouse en vez de solo un Data Lake.

## Parte 4 — Athena vs. Redshift

**Objetivo:** el eje central de la sesión: que el alumno **vea** la diferencia entre los dos motores, no solo la escuche.

### 4.1 Preparar la tabla externa que lee Athena

Athena consulta datos directamente en S3, pero necesita una tabla que le diga dónde están y cómo leerlos. Esa tabla vive en el **Glue Data Catalog**, en la base `spectrumdb` (ya creada por Terraform). La creamos desde Redshift, que la deja registrada en Glue; Athena la lee después desde ahí. La Parte 6 explica cada línea; aquí solo la ejecutamos:

```sql
CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum
FROM DATA CATALOG
DATABASE 'spectrumdb'
IAM_ROLE DEFAULT;

DROP TABLE IF EXISTS spectrum.sales;

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

Para comprobarlo, abre la consola de **AWS Glue** → **Databases** → `spectrumdb` → **Tables**: debe aparecer la tabla `sales`.

### 4.2 Consultar en Athena (datos crudos en S3)

1. Abre la consola de **Amazon Athena** → **Query editor**.
2. Arriba a la derecha, en **Workgroup**, elige el workgroup del lab (`redshift-lab-dev-wg`). Si aparece el cuadro *Workgroup settings*, elige **Acknowledge**. Ese workgroup ya tiene configurado dónde guardar los resultados: tu bucket del lab, en `athena-results/`.
3. En **Data source** deja `AwsDataCatalog` y en **Database** elige `spectrumdb`.
4. Ejecuta:

```sql
SELECT dateid, COUNT(*) AS ventas, SUM(pricepaid) AS ingresos
FROM spectrumdb.sales
GROUP BY dateid
ORDER BY ingresos DESC
LIMIT 10;
```

Debajo del resultado, la consola muestra el **tiempo de ejecución** (*Run time*) y los **datos escaneados** (*Data scanned*). Anótalos.

### 4.3 Consultar en Redshift (tabla ya cargada)

De vuelta en Query Editor v2:

```sql
SELECT dateid, COUNT(*) AS ventas, SUM(pricepaid) AS ingresos
FROM sales
GROUP BY dateid
ORDER BY ingresos DESC
LIMIT 10;
```

Las dos consultas devuelven **exactamente las mismas 10 filas** (la primera es `dateid` 1930, 583 ventas, 407440.00). Anota el tiempo que informa Query Editor v2.

### 4.4 Comparar en pantalla

| Aspecto | Athena | Redshift |
|---|---|---|
| Tiempo de respuesta | El que muestra la consola de Athena | El que muestra Query Editor v2 |
| Costo | **5 USD por TB escaneado** (mínimo 10 MB por consulta) | Cómputo del workgroup (RPUs), **no** por dato escaneado |
| ¿Requiere carga previa? | No: consulta directa sobre S3 | Sí: los datos ya estaban cargados (Parte 1) |

En nuestra prueba: Athena tardó unos 0,9 s y escaneó unos 12 MB (del orden de 0,00006 USD); Redshift tardó unos 0,3 s. Con un dataset tan pequeño **ambos responden en menos de un segundo**: la demo no demuestra velocidad, demuestra el **modelo de costo y de carga de trabajo**. Tus números serán parecidos, no idénticos.

**Mensaje clave:** no es "cuál es mejor", sino "qué carga de trabajo tiene cada uno". Athena sirve para exploración ad hoc; Redshift, para analytics empresarial recurrente sobre un modelo dimensional ya resuelto.

## Parte 5 — UNLOAD (Redshift → S3)

**Objetivo:** mostrar que Redshift también puede ser **productor** de datos hacia el Data Lake.

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

Reemplaza `<bucket_name>` por el nombre de **tu bucket del lab**. Qué hace:

- `UNLOAD` ejecuta la consulta y escribe el resultado en S3.
- `FORMAT AS PARQUET` lo guarda en formato columnar.
- `PARTITION BY (year)` lo organiza en carpetas por año.
- `ALLOWOVERWRITE` permite repetir el paso sin error.
- `IAM_ROLE DEFAULT` usa el rol que **sí** tiene permiso de escritura en tu bucket del lab.

**Ver el resultado:** consola de **Amazon S3** → tu bucket del lab → carpeta `gold/` → `ventas_agregadas/` → `year=2008/`. Verás varios archivos `.parquet` (cuatro en nuestra prueba). Fíjate también en la carpeta `athena-results/`, que dejó Athena en la Parte 4.

Con esto se cierra el ciclo COPY/UNLOAD: S3 → Redshift → S3.

## Parte 6 — Redshift Spectrum

**Objetivo:** consultar datos en S3 **sin cargarlos** físicamente al workgroup.

Ya ejecutaste la parte técnica en la 4.1. Estas son las ideas:

- **`CREATE EXTERNAL SCHEMA spectrum`** crea en Redshift un *puntero* al Glue Data Catalog (a la base `spectrumdb`). La base ya existía: la creó Terraform, y por eso se destruye junto con el resto.
- **`CREATE EXTERNAL TABLE spectrum.sales`** registra en Glue una tabla cuyos datos siguen en S3, en `s3://redshift-downloads/tickit/spectrum/sales/`. TICKIT incluye esa carpeta pensada para este caso.
- Los datos **nunca se cargan** al workgroup: Redshift los lee directamente de S3 usando el Glue Data Catalog como metastore.

### 6.1 Consultar sin haber cargado nada

```sql
SELECT COUNT(*) FROM spectrum.sales;

SELECT sp.salesid, sp.pricepaid, u.city
FROM spectrum.sales sp
JOIN users u ON sp.buyerid = u.userid
LIMIT 10;
```

La primera consulta devuelve **172.456** filas, las mismas que `sales` (aunque esta tabla nunca se cargó). La segunda **une datos externos (Spectrum) con una tabla ya cargada en Redshift** (`users`).

**Mensaje clave:** el Data Warehouse y el Data Lake no son excluyentes: Redshift puede consultar el lake y combinarlo con lo que ya tiene cargado.

## Parte 7 (opcional, ~15 min) — Troubleshooting: COPY sin permisos IAM

**Objetivo:** un solo caso, ligero: aprender a leer un error de permisos de un `COPY`.

### 7.1 Provocar el error

Terraform creó `rol-sin-permisos`, un rol asociado a Redshift pero **sin ningún permiso** sobre S3. Reemplaza `<no_permissions_role_arn>` por su ARN:

```sql
COPY users
FROM 's3://redshift-downloads/tickit/allusers_pipe.txt'
IAM_ROLE '<no_permissions_role_arn>'
DELIMITER '|' REGION 'us-east-1';
```

Redshift devuelve un error como este:

```text
ERROR: S3ServiceException:Access Denied,Status 403,Error AccessDenied,...
```

### 7.2 Diagnosticar

La pista está en **el propio mensaje de error**: `S3ServiceException` y `Access Denied (403)` indican que el problema es de **permisos del rol**, no de sintaxis SQL ni del formato de los datos.

Ahora comprueba dónde **no** está la respuesta:

```sql
SELECT * FROM sys_load_error_detail ORDER BY start_time DESC LIMIT 5;

SELECT query_id, status, error_message
FROM sys_query_history
WHERE query_text LIKE 'COPY users%'
ORDER BY start_time DESC
LIMIT 5;
```

- `sys_load_error_detail` sale **vacía**: esa vista registra errores de datos fila a fila, no de acceso.
- `sys_query_history` muestra la consulta como `failed`, pero con un mensaje genérico (`sending CmdAbort`).

**Lección:** ante un `COPY` que falla, lee primero el mensaje que devuelve el propio comando; las vistas del sistema ayudan con errores de datos, no con permisos.

### 7.3 Corregir

La tabla `users` ya se había cargado en la Parte 1, así que la vaciamos y repetimos el mismo `COPY` con el rol correcto (el rol por defecto, como en la Parte 1):

```sql
TRUNCATE users;

COPY users
FROM 's3://redshift-downloads/tickit/allusers_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';
```

Vuelve a ejecutar la consulta de la sección 1.3 y confirma que `users` tiene otra vez **49.990** filas.

## Checklist de cierre de la demo

- [ ] Infraestructura desplegada con Terraform y salidas anotadas
- [ ] Entré con un usuario IAM (no root) y Query Editor v2 está configurado (*Configure account*)
- [ ] Conectado a Query Editor v2 con el método *AWS Secrets Manager* (el botón Run está activo)
- [ ] Las 7 tablas TICKIT creadas y cargadas (conteos verificados)
- [ ] Tabla externa `spectrumdb.sales` visible en Glue y consultable desde Athena y Redshift
- [ ] Resultado de UNLOAD visible en S3 (`gold/ventas_agregadas/`)
- [ ] Decidido si se incluye la Parte 7 según el tiempo disponible
- [ ] `terraform destroy` ejecutado y `verify_teardown.py` imprime `OK` ([guía 1, sección 4](01_despliegue_infraestructura.md#4-destruir-la-infraestructura-siempre-al-terminar))

## Automatización

Cada parte se puede ejecutar sin la consola, con el mismo SQL de la carpeta `sql/`:

```bash
uv run python scripts/lab/run_lab.py --part 1      # repite --part N para cada parte
uv run python scripts/lab/run_lab.py --all         # las 7 partes
uv run python scripts/lab/run_lab.py --check       # valida los conteos de TICKIT
```

## Referencia cruzada con el material del curso

Esta guía sigue el orden narrativo de `propuesta_diseno_ppts_sesion_5_redshift.md`:

| Parte de la demo | Bloque de las slides |
|---|---|
| Parte 1 (COPY) | Bloque 4 — Data Movement |
| Parte 2 (modelo dimensional) | Bloque 2 — Modelado dimensional |
| Parte 3 (consulta analítica) | Bloque 1 — Data Warehouse |
| Parte 4 (Athena vs. Redshift) | Bloque 12 — Redshift vs. Athena |
| Parte 5 (UNLOAD) | Bloque 4 — Data Movement |
| Parte 6 (Spectrum) | Bloque 5 — Datos externos |
| Parte 7 (troubleshooting, opcional) | Bloque 8 — Observabilidad y Troubleshooting (versión ligera) |

## Fuentes consultadas (documentación de AWS)

- [Conectarse a una base de datos con Query Editor v2](https://docs.aws.amazon.com/redshift/latest/mgmt/query-editor-v2-connecting.html)
- [Crear un secreto de credenciales de conexión (Redshift Serverless)](https://docs.aws.amazon.com/redshift/latest/mgmt/redshift-secrets-manager-integration-create.html)
- [Ejecutar consultas en Query Editor v2](https://docs.aws.amazon.com/redshift/latest/mgmt/query-editor-v2-query-run.html)
- [Cambiar de workgroup en Athena](https://docs.aws.amazon.com/athena/latest/ug/switching-workgroups.html)
- [Sample database (esquema TICKIT)](https://docs.aws.amazon.com/redshift/latest/dg/c_sampledb.html)
- [Cargar datos con COPY desde Amazon S3](https://docs.aws.amazon.com/redshift/latest/dg/t_loading-tables-from-s3.html)
- [Ejemplos de COPY (bucket tickit)](https://docs.aws.amazon.com/redshift/latest/dg/r_COPY_command_examples.html)
- [Introducción a Redshift Spectrum (tickit/spectrum/sales)](https://docs.aws.amazon.com/redshift/latest/dg/c-getting-started-using-spectrum.html)
- [Tablas externas para Redshift Spectrum](https://docs.aws.amazon.com/redshift/latest/dg/c-spectrum-external-tables.html)
- [Precios de Amazon Athena (5 USD/TB, mínimo 10 MB)](https://docs.aws.amazon.com/whitepapers/latest/big-data-analytics-options/amazon-athena.html)
