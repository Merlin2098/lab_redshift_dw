# Laboratorio Redshift (Sesión 5) — Diseño

**Estado:** Las cuatro secciones de diseño fueron aprobadas en brainstorming (2026-09-30).
Pendiente: revisión de este documento por Ricardo. No hay plan de implementación ni código todavía.

**Fuente funcional:** [guia_laboratorio_sesion5_redshift.md](../guia_laboratorio_sesion5_redshift.md)

---

## 1. Propósito y alcance

Laboratorio de Amazon Redshift Serverless sobre el dataset TICKIT, gestionado
100 % con Terraform (módulos separados) y con **destrucción completa y
verificable** al terminar.

- **Origen:** demo guiada del instructor, grabada.
- **Uso real:** cada alumno **replica el lab por su cuenta, en su propia cuenta AWS**, siguiendo la grabación.
- **Consecuencias de diseño:**
  - Nada atado a la cuenta del instructor (sin ARNs, account IDs ni nombres fijos). Todo por variables.
  - Nombres únicos por cuenta (el bucket lleva el account ID).
  - Seguro por defecto: sin contraseñas en variables ni en `.tfvars`.
  - El teardown es un comando explícito más una verificación automatizada.
  - El repo debe servir como guía paso a paso, en el mismo orden que las Partes 0–7 de la guía.

### Decisiones tomadas

| # | Decisión | Elegido |
|---|---|---|
| 1 | Alcance de la automatización | Infra (Terraform) **y** SQL del lab versionado en el repo, ejecutado por script (Data API) |
| 2 | Red | Módulo `network` propio: VPC dedicada con subnets privadas (no depender de la VPC por defecto) |
| 3 | Enhanced VPC routing (EVR) | **Apagado** por defecto (`enable_enhanced_vpc_routing = false`) |
| 4 | Capacidad base | **4 RPUs** por defecto, con validación (4, o múltiplos de 8) |
| 5 | Teardown | `terraform destroy` + script verificador de residuos + tope diario de RPU-horas + checklist en README |
| 6 | Plantilla existente | Se reemplaza todo el contenido de plantilla, excepto `scripts/` |
| 7 | Parte 4 (Athena vs. Redshift) | Incluida de punta a punta: módulo `athena` |
| 8 | Outputs por módulo | `resource_arn` en todos; `log_group_name/arn` solo donde hay log group (`redshift`) |
| 9 | Tag `CostCenter` | Variable, default `"redshift-lab"` |
| 10 | Credenciales | `.env.credentials` (ignorado por git); Terraform las recibe como variables de entorno; scripts Python vía `python-dotenv` y helper compartido, con TLS verificado |

---

## 2. Sección 1 — Infraestructura (APROBADA)

`infra/main.tf` solo compone módulos. Recibe `common_tags` (`Project`,
`Environment`, `Owner`, `ManagedBy`, `CostCenter`) y lo pasa a todos.

```
network ─────────────────────────┐
s3 ──────┬──► iam ───────────────┼──► redshift
data_catalog ┘                   │
s3 ──► athena            budget (opcional, apagado por defecto)
```

Sin dependencias circulares, por lo que la regla de colocación IAM entre
módulos de `AGENTS.md` no se activa: `iam` recibe los ARN de `s3` y
`data_catalog` como variables.

| Módulo | Contenido |
|---|---|
| `network` | VPC, 2 subnets privadas en 2 AZs, security group. Sin NAT ni endpoints. Variable `enable_enhanced_vpc_routing` (default `false`). |
| `s3` | Bucket `<prefijo>-<account_id>-lab` (destino de UNLOAD y resultados de Athena). SSE-AES256, bloqueo de acceso público, `force_destroy = true`, sin versioning. |
| `data_catalog` | `aws_glue_catalog_database` para `spectrumdb`, para que el destroy lo elimine (la guía lo crea con `CREATE EXTERNAL DATABASE`, fuera de Terraform). |
| `iam` | Rol de Redshift (trust `redshift.amazonaws.com`; lectura de `redshift-downloads/tickit*`; lectura/escritura del bucket del lab; acceso a Glue). Rol vacío `rol-sin-permisos` para la Parte 7. |
| `redshift` | Namespace (db `dev`, `manage_admin_password = true`, rol por defecto), workgroup (`base_capacity = 4`, `publicly_accessible = false`), `max_capacity`, usage limit diario, log groups explícitos con `retention_in_days = 7`. |
| `athena` | Workgroup con resultados en `s3://<bucket>/athena-results/`, `force_destroy`. |
| `budget` | El Budget de la plantilla (sin su SNS, que sus notificaciones nunca usaban, y con el filtro de tag corregido: `$${var.project_name}` producía el texto literal), detrás de `enable_budget_guardrail` (default `false`). |

### Controles de costo (`redshift`)

- `max_capacity`: techo del escalado automático.
- `usage_limit` diario (default 16 RPU-horas, variable) con acción "turn off user queries" (`deactivate`).
- Nota verificada en la documentación: **el compute ocioso no se factura**; solo se factura mientras corren consultas (por segundo) más el almacenamiento RMS. El tope protege contra consultas descontroladas, no contra tiempo ocioso. Olvidar el destroy cuesta almacenamiento (mínimo) y el secret de Secrets Manager; conviene decirlo así en el README.

### Red — requisitos confirmados (AWS Docs)

| Tema | Requisito |
|---|---|
| Subnets/AZs | Sin EVR: mínimo 2 subnets en 2 AZs, 3 IPs libres por subnet. Con EVR: 3 subnets en 3 AZs, 9 IPs libres a 8 RPU (CIDR mínimo /27). |
| Endpoints | Solo necesarios con EVR: gateway endpoint de S3 e interface endpoint de Glue (Lake Formation solo si se usa). Los gateway endpoints de S3 solo cubren buckets de la misma región. |
| Región | `us-east-1` es obligatoria en esta versión del lab: el dataset público TICKIT reside allí (opción A de la guía). |
| 4 RPUs | Disponible en `us-east-1`. Límite de 100 columnas por tabla (la mayor de TICKIT tiene 18). La guía original dice que 8 es el mínimo; ya no es cierto. |

Fuentes: serverless-usage-considerations, serverless-capacity, enhanced-vpc-routing,
spectrum-enhanced-vpc, serverless-billing-on-demand (docs.aws.amazon.com/redshift/latest/mgmt/).

### Riesgos abiertos de la sección 1

- **Spectrum sin EVR (CONFIRMADO en el primer despliegue, ver sección 9):** la documentación describe Spectrum/Glue solo para el caso con EVR. Sin EVR en subnets privadas sin NAT, COPY y UNLOAD funcionan en la práctica, pero Spectrum en Serverless **no está confirmado**. Se valida con un smoke test en el primer despliegue. Si falla, el fallback es `enable_enhanced_vpc_routing = true` con 3 subnets/3 AZs y los endpoints (el endpoint de Glue tiene costo por hora).
- **Argumentos del provider AWS:** verificados el 2026-09-30 contra la documentación del provider: `manage_admin_password`, `default_iam_role_arn` (debe estar también en `iam_roles`), `log_exports`, `max_capacity`, `usage_limit` (`deactivate`). **Conflicto abierto:** la documentación del provider exige 3 subnets en 3 AZs; la de AWS dice 2 sin EVR. Fallback: `availability_zone_count = 3`.
- **Log group de Redshift:** el nombre real es `/aws/redshift/<namespace>/<log_type>`; si no existe, Redshift lo crea con retención "Never Expire" fuera de Terraform. Por eso se crea en Terraform antes del namespace y solo se exporta `connectionlog`.
- **Trust de los roles:** deben incluir `redshift.amazonaws.com` y `redshift-serverless.amazonaws.com`.
- **Entorno local:** un antivirus que inspecciona TLS (AVG) rompe el canal local Terraform↔provider (`x509: certificate signed by unknown authority`); se evita con `TF_DISABLE_PLUGIN_TLS=1` o excluyendo el binario del provider de la inspección.

---

## 3. Sección 2 — SQL y ejecutor del lab (APROBADA)

### SQL en `sql/` (separado de Python)

Un archivo por parte de la guía, legibles y copiables a Query Editor v2:
`01_ddl.sql`, `02_copy.sql`, `03_star_schema.sql`, `04_analytics.sql`,
`05_athena_vs_redshift.sql`, `06_unload.sql`, `07_spectrum_setup.sql`,
`07_spectrum_queries.sql`, `08_troubleshooting.sql`. Las Partes 4 y 6 ejecutan primero
`07_spectrum_setup.sql` (idempotente) porque ambas necesitan la tabla externa.

- **Sin ARNs en el SQL:** se usa `IAM_ROLE DEFAULT` (el namespace fija el rol por defecto).
  - Confirmado en la documentación: COPY (`IAM_ROLE { default | 'SESSION' | 'arn…' }`) y `CREATE EXTERNAL SCHEMA`.
  - UNLOAD: confirmado en el primer despliegue (sección 9).
- Solo dos placeholders, sustituidos con `string.Template` de la stdlib: `${bucket}` (UNLOAD, LOCATION) y `${role_sin_permisos}` (Parte 7).

### Ejecutor: `scripts/lab/run_lab.py`

`python scripts/lab/run_lab.py --part N | --all | --check`

- Toda la configuración sale de `terraform output -json` (workgroup, database, secret ARN, bucket, roles, workgroup de Athena, región). Sin valores hardcodeados.
- **Redshift:** Data API de boto3 (`redshift-data`), autenticada con el secret de la contraseña gestionada. **Una sentencia por llamada**: `BatchExecuteStatement` corre en una transacción y `CREATE EXTERNAL TABLE` no puede ir dentro de una. División de sentencias por `;` (límite conocido: sin `;` dentro de literales).
- Imprime cada sentencia antes de ejecutarla, para que la grabación y el lector vean qué corre.
- **Parte 4:** mismo cálculo sobre `sales` en ambos motores; tabla con tiempo de cada uno, bytes escaneados de Athena y costo estimado ($5/TB, mínimo 10 MB por consulta).
- **Parte 7:** provoca el error con el rol vacío, lo espera, consulta `sys_load_error_detail` y corrige con el rol correcto.
- **`--check`:** valida counts esperados (p. ej. `sales` ≈ 172k filas); falla si no coinciden.

### Tests

- `tests/` (locales, sin AWS): sustitución de placeholders, división de sentencias, parseo de argumentos.
- `tests/aws/` (marcados `cloud`, se saltan sin credenciales; usan el helper compartido `scripts/lab/aws_session.py`, ver sección 7): workgroup privado, bucket sin acceso público, trust del rol, retención de log groups, counts tras la carga.

### Verificador de teardown: `scripts/lab/verify_teardown.py` (solo lectura)

Tras el destroy, revisa por nombre y tag: workgroup y namespace de Redshift Serverless, buckets, roles IAM, log groups, VPC, base de Glue, workgroup de Athena y secret de Secrets Manager. Sale con código distinto de cero y lista lo que queda.
Punto por resolver en la implementación: un secret en ventana de recuperación puede seguir apareciendo en listados; el verificador debe distinguirlo de un residuo real.

### Flujo del alumno

Prerrequisitos → `terraform init/plan/apply` → `run_lab.py --all` (o parte por parte) → `terraform destroy` → `verify_teardown.py`.

---

## 4. Limpieza de la plantilla

Nada se toca hasta que el spec esté aprobado.

- **Se reemplaza/elimina:** contenido de `infra/` (`main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars.example`; `providers.tf` y `backend.tf.example` se ajustan); `src/` completo; `tests/test_example_job.py`; dependencias de `pyproject.toml` que el lab no use.
- **Se conserva:** `scripts/`, `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.env.example`, `.gitignore`, `docs/guia_laboratorio_sesion5_redshift.md`.
- **Acoplamientos con `scripts/` a verificar al implementar:** `scripts/package.py` empaqueta `src/`; `tests/test_script_wrappers.py` usa `test_example_job.py` como argumento. Se corre la suite tras el cambio y se conservan las dependencias que los scripts necesiten. (`truststore` se retira si ningún script conservado lo importa; `check_ssl_regression.py` no lo usa.)
- **Sin decidir:** `data/guia_reestructuracion_curso_aws_data_engineer.md` (guía del curso, no código de plantilla); se deja intacto salvo indicación contraria.

## 5. Correcciones a la guía (mismo cambio)

- Base capacity 4 RPUs (la guía dice 8 como mínimo).
- Despliegue con Terraform en vez de CLI con contraseña en texto plano.
- `IAM_ROLE DEFAULT` en lugar del ARN.
- Parte 4: la consulta de Athena hace `GROUP BY catgroup` sobre `sales`, columna que esa tabla no tiene. Se reemplaza por una consulta equivalente solo con columnas de `sales`, ejecutable en ambos motores sobre la tabla `spectrumdb.sales` (Glue).
- Riesgo a confirmar con el smoke test: que Athena lea sin problema la tabla de Glue creada por `CREATE EXTERNAL TABLE` desde Redshift.

---

## 6. Sección 3 — Teardown y gobernanza (APROBADA)

### ADR

Un solo ADR, `docs/internal/adr/0001-redshift-lab-architecture.md`, que recoge las
decisiones 2–7 (VPC propia, EVR apagado, 4 RPUs, reemplazo de la plantilla,
módulo `athena`, `IAM_ROLE DEFAULT`). Es la **primera tarea del plan**, antes de
escribir Terraform (`AGENTS.md`: ADR obligatorio antes de implementar cambios de arquitectura).

### Quién hace qué

| Acción | Quién | Motivo |
|---|---|---|
| Escribir módulos, `fmt`, `validate`, `plan`, tests locales | Claude | Permitido en `.claude/settings.json` |
| `terraform apply` y `destroy` | Ricardo, o Claude con aprobación en el momento | En `deny` y en "never without approval" |
| Políticas del módulo `iam` | Checkpoint de revisión de Ricardo antes del apply | `AGENTS.md`: cambios de IAM requieren aprobación |
| Primer apply (servicio de pago) | Aprobación explícita de Ricardo | `AGENTS.md`: servicios de pago |
| `run_lab.py` (escribe datos en el warehouse) | Ricardo por defecto | Escribe datos en una cuenta real |
| `verify_teardown.py` (solo lectura) | Claude | Solo lectura |

**Validar roles IAM antes de aplicar** se implementa así: revisión humana del diff de
IAM del `plan` antes del apply, y `tests/aws/` comprueba después trust y políticas.
Sin herramientas adicionales.

### Orden de destrucción

Resuelto por el grafo de dependencias de Terraform: `redshift` → `athena` → `iam` →
`s3`, `data_catalog`, `network`.

- La base de Glue la gestiona Terraform; al destruirla se eliminan las tablas externas de Spectrum.
- `force_destroy` vacía el bucket (salida de UNLOAD y resultados de Athena).
- Los log groups se destruyen con el resto (cubierto por la aprobación del destroy, por la regla de preguntar antes de borrar log groups).

### Riesgos de teardown sin cerrar

1. **Snapshots manuales** creados desde la consola sobreviven al destroy y se facturan; `verify_teardown.py` debe listarlos.
2. **ENI/endpoint del workgroup** puede tardar en liberarse y hacer fallar el borrado de subnets (`DependencyViolation`). No verificado. El README indica repetir `terraform destroy` (idempotente).
3. **Estado local perdido:** sin `terraform.tfstate` los recursos quedan huérfanos. El README advierte no borrarlo nunca; el verificador busca por tag `Project` y por nombre, no por estado.

---

## 7. Sección 4 — Documentación, credenciales y orden de entrega (APROBADA)

### README paso a paso (`README.md` en la raíz)

En el mismo orden que la grabación:

0. **Prerrequisitos:** cuenta AWS propia de sandbox, credenciales en `.env.credentials` (a partir de `.env.example`), Terraform ≥ 1.6, `uv`, región `us-east-1`. La identidad IAM de esas credenciales debe poder crear y leer todos los recursos del lab (en una cuenta sandbox, lo más simple es `AdministratorAccess`).
1. **Qué se crea y cuánto cuesta:** incluye que el compute ocioso no se factura pero el almacenamiento y el secret sí.
2. **Desplegar:** `terraform init/plan/apply` con `terraform.tfvars` copiado del `.example`.
3. **Ejecutar el lab:** `run_lab.py --part N | --all | --check`.
4. **Destruir:** `terraform destroy` y luego `verify_teardown.py`.
5. **Si algo falla:** repetir el destroy, no borrar `terraform.tfstate`, qué hacer con snapshots manuales.

`docs/guia_laboratorio_sesion5_redshift.md` se corrige (sección 5) y queda como guion de la demo; el README es el manual de ejecución.

### Credenciales (`.env.credentials`)

- `.gitignore` las cubre: la regla `.env.*` (con excepción `!.env.example`) ignora `.env.credentials`. Verificado.
- Claude **no abre, imprime ni envía** ese archivo (`AGENTS.md`: nunca enviar archivos sensibles a servicios externos).
- **Terraform no lee archivos dotenv.** El README documenta cargarlas en Git Bash antes de usar Terraform: `set -a; . ./.env.credentials; set +a`. Consecuencia: un comando compuesto así no coincide con las reglas `allow` de `.claude/settings.json` (que solo cubren `terraform -chdir=infra plan:*` simple), por lo que generará un prompt de permiso cuando Claude corra `plan`. Alternativa: Ricardo ejecuta `plan` desde su terminal, o añade una regla `allow`.
- **Scripts Python:** un helper compartido `scripts/lab/aws_session.py` llama a `load_dotenv` sobre `.env.credentials` y usa la cadena de credenciales por defecto de boto3. Así se respeta `AWS_SESSION_TOKEN` (credenciales temporales), que el helper actual `tests/aws/aws_session.py` ignora al pasar solo clave y secreto. `tests/aws/aws_session.py` pasa a reutilizar ese helper.
- **Sin `verify=False`:** `scripts/testing/check_ssl_regression.py` (ejecutado el 2026-09-30, Python 3.14.7, OpenSSL 3.5.7) reporta `NATIVE SSL: OK`; el workaround del helper actual ya no es necesario, y los scripts nuevos verifican TLS. Se retira también la dependencia `truststore` si ningún script conservado la importa (verificar al limpiar).
- Ese script y su mensaje mencionan `tests/aws/conftest.py` y `docs/workaround-python314-ssl-boto3.md`, que no existen en el repo (restos de la plantilla). No se tocan: `scripts/` se conserva.

### Orden de implementación

Cada paso deja el repo verificable antes del siguiente:

1. ADR 0001.
2. Limpieza de la plantilla (correr la suite para detectar acoplamientos con `scripts/`; recortar `pyproject.toml`).
3. Módulos sin servicio de pago: `network`, `s3`, `data_catalog`, `budget` (`fmt` y `validate`).
4. Módulos `iam`, `athena`, `redshift`. Checkpoint de revisión de IAM y revisión del `plan`. Antes de `redshift`, verificar los argumentos del provider en su documentación.
5. `sql/` y `run_lab.py` con tests locales.
6. `verify_teardown.py` y `tests/aws/`.
7. README y corrección de la guía.
8. Primer despliegue real con aprobación de Ricardo: apply, smoke test de Spectrum sin EVR, `run_lab.py --all`, destroy, `verify_teardown.py`. Único paso con gasto; cierra los riesgos abiertos.

**Dependencia externa:** hasta renovar las credenciales de `.env.credentials` (las actuales del entorno fallan con `InvalidClientTokenId`), no se puede validar nada de los pasos 4 a 8 contra AWS. Sí se puede hacer `init`, `fmt`, `validate` y `plan` sin gastar, pero `plan` necesita credenciales válidas (data source `aws_caller_identity` y validaciones del provider).

## 8. Restricciones heredadas de AGENTS.md

Tags comunes con `CostCenter` en todo recurso; `aws_cloudwatch_log_group` explícito con `retention_in_days`; budget detrás de `enable_budget_guardrail` (default `false`); sin versioning de S3 por defecto; sin tocar `terraform.tfstate`; tests `tests/aws/` al desplegar; validar roles IAM antes de aplicar; SQL separado de Python; configuración sobre hardcoding.

---

## 9. Resultados del primer despliegue (2026-09-30)

Despliegue con valores por defecto (sin `terraform.tfvars`), ejecutado por Ricardo; pruebas ejecutadas después con `run_lab.py`.

| Riesgo / supuesto | Resultado |
|---|---|
| Spectrum sin EVR en subnets privadas sin NAT | **Funciona.** `SELECT COUNT(*) FROM spectrum.sales` devuelve 172.456 filas; el join con `users` también. |
| 2 subnets en 2 AZs | **Aceptado por AWS** (el estado tiene 2 `aws_subnet.private`). La doc del provider que exige 3 no aplica sin EVR. |
| `IAM_ROLE DEFAULT` en COPY, UNLOAD y `CREATE EXTERNAL SCHEMA` | **Funciona en los tres.** UNLOAD escribió 4 archivos Parquet en `gold/ventas_agregadas/year=2008/`. |
| Athena lee la tabla de Glue creada por Redshift | **Funciona** y devuelve exactamente los mismos resultados que Redshift. Athena: 898 ms, 11,9 MB escaneados (~0,00006 USD); Redshift: 295 ms. |
| Conteos de TICKIT | **Coinciden** con `EXPECTED_COUNTS` (`--check` OK), también tras recargar con `--all`. |
| Idempotencia de la Parte 1 | **Confirmada:** recargar no duplica filas. |
| Parte 7 | El COPY con `rol-sin-permisos` devuelve `S3ServiceException: Access Denied (403)`. `sys_load_error_detail` queda **vacío** y `sys_query_history` solo dice `sending CmdAbort`: la guía y el SQL se corrigieron (la pista real es el error del propio COPY). |
| Nombre del secret gestionado | `redshift!redshift-lab-dev-ns-awsuser`; el filtro `redshift!<prefijo>` del verificador lo encuentra. |
| Verificador de teardown (control positivo con la infra viva) | Encuentra las 10 categorías de recursos. **Bug real encontrado y corregido:** boto3 no tiene paginador para `athena list_work_groups` (los fakes de los tests lo ocultaban); ahora se pagina a mano y un test contra clientes boto3 reales lo vigila. |
| Tests `cloud` | 6/6 en verde contra el lab desplegado. |

**Pendiente:** `terraform destroy` y `verify_teardown.py` debe imprimir `OK` (lo ejecuta Ricardo). Quedan sin observar el tiempo de destroy y un posible `DependencyViolation` de ENIs.
