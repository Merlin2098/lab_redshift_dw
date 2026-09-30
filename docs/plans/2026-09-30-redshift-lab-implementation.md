# Laboratorio Redshift (Sesión 5) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el laboratorio de Redshift Serverless (dataset TICKIT) con Terraform modular, SQL versionado ejecutado por script, y un teardown verificable, para que cada alumno lo replique en su propia cuenta AWS.

**Architecture:** `infra/` compone 7 módulos (`network`, `s3`, `data_catalog`, `iam`, `redshift`, `athena`, `budget`) verificados offline con `terraform test` + `mock_provider`. El SQL de la guía vive en `sql/` (un archivo por parte); `scripts/lab/run_lab.py` lo ejecuta vía Redshift Data API y Athena (boto3) leyendo `terraform output -json`. `scripts/lab/verify_teardown.py` (solo lectura) busca residuos tras el destroy.

**Tech Stack:** Terraform ≥ 1.7 (instalado: 1.14.7) con provider AWS `~> 5.0`; Python ≥ 3.11 (venv 3.14.7) con `boto3`, `python-dotenv`, `pytest`, `ruff`; uv.

**Spec:** [docs/specs/2026-09-30-redshift-lab-design.md](../specs/2026-09-30-redshift-lab-design.md) (aprobado). Leer ambos antes de ejecutar.

## Global Constraints

Valores tomados literalmente del spec y de `AGENTS.md`; todas las tareas los incluyen implícitamente.

- Región del lab: `us-east-1` (validación en variable `aws_region`). Dataset: `s3://redshift-downloads/tickit/`.
- `base_capacity` default **4** (válido: 4, o múltiplo de 8). `max_capacity` default 8. `usage_limit` diario default **16** RPU-horas, `breach_action = "deactivate"`.
- Workgroup **privado** (`publicly_accessible = false`), `enable_enhanced_vpc_routing = false` por defecto, 2 subnets privadas en 2 AZs, sin NAT.
- `manage_admin_password = true`: ninguna contraseña en variables, `.tfvars` ni código.
- Tags comunes en **todo** recurso: `Project`, `Environment`, `Owner`, `ManagedBy`, `CostCenter` (`CostCenter` default `"redshift-lab"`).
- Log groups explícitos con `retention_in_days` (default 7); los de Redshift se crean **antes** que el namespace (Redshift crearía los suyos con retención "Never Expire" fuera de Terraform).
- S3: bloqueo de acceso público, SSE-AES256, `force_destroy = true`, **sin** `aws_s3_bucket_versioning`.
- Budget detrás de `enable_budget_guardrail` (default `false`).
- Cada módulo expone `resource_arn`; los de log group (`log_group_name`, `log_group_arn`) solo donde existe un log group (`redshift`).
- Sin wildcard (`"*"`) en `Resource` de políticas IAM. Todo permiso declarado en Terraform.
- SQL separado de Python. Sin valores de entorno hardcodeados: todo sale de `terraform output`.
- Jamás abrir, imprimir ni enviar `.env.credentials`. Jamás borrar `terraform.tfstate`.
- `terraform apply` y `terraform destroy`: **solo con aprobación explícita de Ricardo** (están en `deny`). El primer apply es un servicio de pago. Los cambios de IAM requieren su aprobación (gate en Task 5).
- El repo **no está bajo git** hoy. Task 1 lo inicializa (commit base antes de borrar nada). Los commits terminan con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (segundo `-m`).
- Comandos que requieren prompt de permiso (no están en `.claude/settings.json`): `terraform test`, `terraform init` dentro de `infra/modules/*`, `git init/add/commit`, comandos `aws`, y cualquier comando compuesto que cargue `.env.credentials`.
- Código y comentarios en inglés; documentación en español.

## Review Focus

Modos de fallo que el spec implica y que ninguna tarea cubre "de serie"; cada uno tiene su prueba en la tarea indicada.

1. **Re-ejecutar `--part 1` dos veces** duplicaría filas si el DDL no fuera idempotente → `01_ddl.sql` empieza con `DROP TABLE IF EXISTS` de las 7 tablas (Task 8, test `test_ddl_drops_every_table_before_creating`).
2. **Destroy parcial o repetido** deja recursos: el verificador debe listarlos y salir ≠ 0 (Task 12, `test_find_residuals_*`, `test_main_exit_code`).
3. **`terraform.tfstate` perdido**: el verificador busca por prefijo/tag, no por estado (Task 12, `test_vpc_lookup_uses_project_tag_filter`).
4. **Credenciales temporales** (`AWS_SESSION_TOKEN`) deben respetarse; el helper antiguo las ignoraba (Task 9, `test_session_token_is_loaded`).
5. **Nombre de proyecto inválido o muy largo** rompe el nombre del bucket/namespace → validación de `project_name` en la raíz (Task 7, `run "rejects_invalid_project_name"`).
6. **Una sentencia marcada `@expect-error` que tiene éxito** (Parte 7 sin error real) debe fallar el lab y no pasar en silencio (Task 10, `test_expected_error_that_succeeds_raises`).

---

## Mapa de archivos

| Ruta | Responsabilidad |
|---|---|
| `docs/internal/adr/0001-redshift-lab-architecture.md` | ADR obligatorio por `AGENTS.md` |
| `infra/providers.tf`, `variables.tf`, `main.tf`, `outputs.tf`, `terraform.tfvars.example` | Raíz: solo composición de módulos |
| `infra/tests/root.tftest.hcl` | Test de cableado de la raíz (offline) |
| `infra/modules/<m>/{versions,variables,main,outputs}.tf` | Un módulo por responsabilidad |
| `infra/modules/<m>/tests/<m>.tftest.hcl` | Tests offline del módulo (`mock_provider`) |
| `sql/*.sql` | SQL del lab, un archivo por parte; placeholders `${bucket}`, `${glue_database}`, `${no_permissions_role_arn}`, `${redshift_role_arn}` |
| `scripts/lab/aws_session.py` | Carga de `.env.credentials` y creación de clientes boto3 |
| `scripts/lab/config.py` | `LabConfig` desde `terraform output -json` |
| `scripts/lab/sql.py` | Partes, render de placeholders, división de sentencias |
| `scripts/lab/redshift.py`, `athena.py` | Ejecutores (Data API / Athena) con `Result` común |
| `scripts/lab/runner.py` | Ejecuta una parte, formatea tablas y comparación Parte 4 |
| `scripts/lab/checks.py` | Conteos esperados TICKIT |
| `scripts/lab/run_lab.py` | CLI `--part N \| --all \| --check` |
| `scripts/lab/teardown.py`, `verify_teardown.py` | Búsqueda de residuos y CLI |
| `tests/lab/*.py` | Tests locales (sin AWS) |
| `tests/aws/*.py` | Tests `cloud` (se saltan sin credenciales/infra) |
| `README.md` | Manual de ejecución para el alumno |

---

### Task 1: Git, línea base y ADR

**Files:**
- Create: `.git/` (vía `git init`), `docs/internal/adr/0001-redshift-lab-architecture.md`
- Modify: `.gitignore` (añadir reglas Terraform si faltan)

**Interfaces:**
- Consumes: nada.
- Produces: repo git con commit base (snapshot de la plantilla, reversible) y el ADR.

- [ ] **Step 1: Registrar la línea base de tests (antes de tocar nada)**

Run: `python scripts/testing/run_pytest.py 2>&1 | tail -25`
Expected: resumen de pytest. **Anotar qué tests pasan y cuáles fallan** (p. ej. `tests/test_installer.py` importa `install_linux`, que no está en el repo; puede fallar de origen). Esta lista es la referencia de Task 2.

- [ ] **Step 2: Inicializar git y verificar que las credenciales quedan ignoradas**

```bash
git init -b main
git check-ignore -v .env.credentials
```
Expected: `.gitignore:101:.env.*	.env.credentials`. Si no imprime nada: **detenerse**, no continuar hasta ignorar el archivo.

- [ ] **Step 3: Añadir reglas de Terraform a `.gitignore` si faltan**

```bash
for rule in ".terraform/" "*.tfstate" "*.tfstate.*" "*.tfplan" "tfplan" "crash.log" "infra/modules/**/.terraform.lock.hcl"; do
  grep -qxF "$rule" .gitignore || echo "$rule" >> .gitignore
done
tail -8 .gitignore
```

- [ ] **Step 4: Revisar qué se va a versionar y hacer el commit base**

```bash
git add -A
git status --short | grep -E "\.venv|\.env\.credentials|\.tfstate" && echo "STOP: unexpected file staged" || echo "staging looks clean"
git commit -m "chore: baseline snapshot (template, spec and plan) before the Redshift lab rewrite" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
Expected: `staging looks clean`, commit creado. Si aparece `STOP`, `git reset` y corregir `.gitignore`.

- [ ] **Step 5: Escribir el ADR**

Create `docs/internal/adr/0001-redshift-lab-architecture.md`:

```markdown
# ADR 0001 — Arquitectura del laboratorio Redshift (Sesión 5)

- **Estado:** Aceptado (2026-09-30)
- **Spec:** docs/specs/2026-09-30-redshift-lab-design.md

## Contexto

El repo era una plantilla genérica (bucket de artefactos, rol de Glue, bundle .zip).
Se convierte en el laboratorio de Amazon Redshift Serverless de la Sesión 5. Es una demo
del instructor que cada alumno replica en su propia cuenta AWS a partir de la grabación.
Requisitos: Terraform modular, SQL del lab reproducible y destrucción completa y verificable.

## Decisión

1. Infra con Terraform en 7 módulos: `network`, `s3`, `data_catalog`, `iam`, `redshift`, `athena`, `budget`.
2. VPC propia con 2 subnets privadas en 2 AZs, sin NAT; enhanced VPC routing apagado por defecto
   (variable `enable_enhanced_vpc_routing`; al activarla se crean endpoints de S3 y Glue).
3. Redshift Serverless con `base_capacity = 4` RPUs, workgroup privado, contraseña de admin
   gestionada por Secrets Manager y tope diario de RPU-horas (`deactivate`).
4. La plantilla anterior (`src/`, `infra/*.tf` planos, dependencias no usadas) se reemplaza; `scripts/` se conserva.
5. Parte 4 (Athena vs. Redshift) incluida: módulo `athena` y tabla Glue `spectrumdb.sales`.
6. SQL en `sql/` con `IAM_ROLE DEFAULT`; ejecutado por `scripts/lab/run_lab.py` (Data API + Athena).
7. Teardown: `terraform destroy` + `scripts/lab/verify_teardown.py` (solo lectura, busca por prefijo y tag).

## Consecuencias

- Cada alumno paga sus propios costos (solo mientras corren consultas, más almacenamiento y el secret).
- Spectrum sin EVR no está confirmado por la documentación de AWS; se valida en el primer despliegue,
  con `enable_enhanced_vpc_routing = true` como fallback.
- `IAM_ROLE DEFAULT` en UNLOAD no está confirmado; fallback: `IAM_ROLE '${redshift_role_arn}'`.
- El lab solo funciona en `us-east-1` (región del dataset público).
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore docs/internal/adr/0001-redshift-lab-architecture.md
git commit -m "docs: add ADR 0001 for the Redshift lab architecture" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Limpieza de la plantilla

**Files:**
- Delete: `src/`, `tests/test_example_job.py`, `infra/main.tf`, `infra/variables.tf`, `infra/outputs.tf`, `infra/terraform.tfvars.example`
- Modify: `tests/test_script_wrappers.py`, `pyproject.toml`, `uv.lock` (regenerado)

**Interfaces:**
- Consumes: lista base de tests de Task 1, Step 1.
- Produces: repo sin plantilla, suite igual a la base (o mejor), dependencias recortadas a `boto3` + `python-dotenv` (+ `pytest`, `ruff` en dev).

- [ ] **Step 1: Borrar lo que es plantilla**

```bash
git rm -r -q src tests/test_example_job.py infra/main.tf infra/variables.tf infra/outputs.tf infra/terraform.tfvars.example
ls infra
```
Expected: `infra` contiene `backend.tf.example` y `providers.tf`.

- [ ] **Step 2: Arreglar el test que usaba `test_example_job.py` como argumento real**

Run: `grep -n "test_example_job" tests/test_script_wrappers.py`
Reemplazar **cada** ocurrencia de `"tests/test_example_job.py"` por `"scripts/testing/run_pytest.py"` (archivo que existe y es válido para ruff). Con la herramienta Edit, `replace_all: true`.

- [ ] **Step 3: Recortar `pyproject.toml`**

Reemplazar el archivo completo por:

```toml
[project]
name = "lab-redshift-dw"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "boto3==1.35.49",
    "python-dotenv==1.2.2",
]

[dependency-groups]
dev = [
    "pytest==9.0.3",
    "ruff==0.15.12",
]

[tool.pytest.ini_options]
pythonpath = ["."]
markers = [
    "cloud: tests that require live AWS credentials and a deployed lab (skipped without them)",
]

[tool.uv]
package = false
```

`pythonpath = ["."]` hace que `from scripts...` funcione también con `pytest` a secas y no solo con `python -m pytest`.

- [ ] **Step 4: Regenerar el entorno**

Run: `uv lock && uv sync`
Expected: sin errores; `uv.lock` mucho más corto.

- [ ] **Step 5: Verificar que la suite no empeoró respecto a la línea base**

Run: `python scripts/testing/run_pytest.py 2>&1 | tail -25`
Expected: mismos tests que pasaban en Task 1 Step 1 siguen pasando. Si un test que pasaba ahora falla por una dependencia eliminada (`ModuleNotFoundError`), añadir **solo** esa dependencia a `pyproject.toml`, repetir `uv lock && uv sync` y volver a correr. Los tests que ya fallaban de origen (p. ej. `install_linux`) se dejan como estaban y se anotan en el mensaje del commit.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove template code and trim dependencies for the Redshift lab" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Módulo `network` (+ base de Terraform)

**Files:**
- Modify: `infra/providers.tf`
- Create: `infra/modules/network/versions.tf`, `variables.tf`, `main.tf`, `outputs.tf`, `tests/network.tftest.hcl`

**Interfaces:**
- Consumes: nada.
- Produces (`module.network`): variables `name_prefix: string`, `aws_region: string`, `vpc_cidr: string = "10.42.0.0/16"`, `availability_zone_count: number = 2` (2–3), `availability_zone_names: list(string) = null`, `enable_enhanced_vpc_routing: bool = false`, `tags: map(string)`. Outputs `vpc_id`, `subnet_ids: list(string)`, `security_group_id`, `resource_arn`.

**Nota sobre los tests offline:** todos los `*.tftest.hcl` usan `mock_provider "aws"` con `command = apply`. No crea nada en AWS y no necesita credenciales; `apply` (y no `plan`) hace que los atributos calculados tengan valor para poder afirmar sobre ellos. Si el provider rechaza un valor generado por el mock (p. ej. un ARN inválido), añadir un `mock_resource` con `defaults` del atributo afectado.

- [ ] **Step 1: Subir el mínimo de Terraform a 1.7 (requerido por `mock_provider`)**

En `infra/providers.tf` cambiar `required_version = ">= 1.6.0"` por `required_version = ">= 1.7.0"`.

- [ ] **Step 2: Escribir el test que falla**

Create `infra/modules/network/tests/network.tftest.hcl`:

```hcl
mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = {
      names = ["us-east-1a", "us-east-1b", "us-east-1c"]
    }
  }
}

variables {
  name_prefix = "redshift-lab-dev"
  aws_region  = "us-east-1"
  tags = {
    Project    = "redshift-lab"
    CostCenter = "redshift-lab"
  }
}

run "defaults_two_private_subnets_and_no_endpoints" {
  command = apply

  assert {
    condition     = length(aws_subnet.private) == 2
    error_message = "Default must create exactly 2 private subnets."
  }

  assert {
    condition     = alltrue([for s in aws_subnet.private : s.map_public_ip_on_launch == false])
    error_message = "Subnets must be private."
  }

  assert {
    condition     = length(aws_vpc_endpoint.s3) == 0 && length(aws_vpc_endpoint.glue) == 0
    error_message = "No VPC endpoints without enhanced VPC routing."
  }

  assert {
    condition     = aws_vpc.this.tags["CostCenter"] == "redshift-lab"
    error_message = "Common tags must be applied to the VPC."
  }
}

run "enhanced_vpc_routing_adds_endpoints" {
  command = apply

  variables {
    enable_enhanced_vpc_routing = true
    availability_zone_count     = 3
  }

  assert {
    condition     = length(aws_subnet.private) == 3
    error_message = "Three subnets expected for three AZs."
  }

  assert {
    condition     = length(aws_vpc_endpoint.s3) == 1 && length(aws_vpc_endpoint.glue) == 1
    error_message = "S3 gateway and Glue interface endpoints expected with enhanced VPC routing."
  }
}

run "rejects_single_az" {
  command = plan

  variables {
    availability_zone_count = 1
  }

  expect_failures = [var.availability_zone_count]
}
```

- [ ] **Step 3: Ejecutar y ver que falla**

```bash
terraform -chdir=infra/modules/network init -backend=false
terraform -chdir=infra/modules/network test
```
Expected: FAIL (el módulo no tiene variables ni recursos: `Unsupported argument`/`Reference to undeclared resource`).

- [ ] **Step 4: Implementar el módulo**

Create `infra/modules/network/versions.tf`:

```hcl
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

Create `infra/modules/network/variables.tf`:

```hcl
variable "name_prefix" {
  description = "Prefix for resource names, e.g. redshift-lab-dev."
  type        = string
}

variable "aws_region" {
  description = "Region of the VPC endpoints (only used when enhanced VPC routing is on)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR of the lab VPC. Each subnet is a /24, well above the /27 Redshift Serverless needs."
  type        = string
  default     = "10.42.0.0/16"
}

variable "availability_zone_count" {
  description = "Number of AZs/subnets. Redshift Serverless needs 2 without enhanced VPC routing and 3 with it."
  type        = number
  default     = 2

  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 3
    error_message = "availability_zone_count must be 2 or 3."
  }
}

variable "availability_zone_names" {
  description = "Optional explicit AZ names. Use it if the default AZs are not supported by Redshift Serverless in your account. Overrides availability_zone_count."
  type        = list(string)
  default     = null
}

variable "enable_enhanced_vpc_routing" {
  description = "Create the S3 gateway and Glue interface endpoints needed when the workgroup uses enhanced VPC routing."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
```

Create `infra/modules/network/main.tf`:

```hcl
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = var.availability_zone_names != null ? var.availability_zone_names : slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_subnet" "private" {
  count                   = length(local.azs)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-private-${local.azs[count.index]}" })
}

# No inbound rules: access is through Query Editor v2 and the Data API, never a direct connection.
resource "aws_security_group" "workgroup" {
  name        = "${var.name_prefix}-redshift"
  description = "Redshift Serverless workgroup. No inbound rules."
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-redshift" })
}

# The subnets have no internet route, so open egress only matters for the endpoints below.
resource "aws_vpc_security_group_egress_rule" "workgroup_all" {
  security_group_id = aws_security_group.workgroup.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "Egress for the workgroup network interfaces."
  tags              = var.tags
}

resource "aws_vpc_endpoint" "s3" {
  count             = var.enable_enhanced_vpc_routing ? 1 : 0
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_vpc.this.main_route_table_id]
  tags              = merge(var.tags, { Name = "${var.name_prefix}-s3" })
}

resource "aws_security_group" "endpoints" {
  count       = var.enable_enhanced_vpc_routing ? 1 : 0
  name        = "${var.name_prefix}-endpoints"
  description = "Interface endpoints: HTTPS from inside the VPC only."
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-endpoints" })
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_https" {
  count             = var.enable_enhanced_vpc_routing ? 1 : 0
  security_group_id = aws_security_group.endpoints[0].id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = var.vpc_cidr
  description       = "HTTPS from the lab VPC."
  tags              = var.tags
}

resource "aws_vpc_endpoint" "glue" {
  count               = var.enable_enhanced_vpc_routing ? 1 : 0
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${var.aws_region}.glue"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints[0].id]
  private_dns_enabled = true
  tags                = merge(var.tags, { Name = "${var.name_prefix}-glue" })
}
```

Create `infra/modules/network/outputs.tf`:

```hcl
output "vpc_id" {
  description = "ID of the lab VPC."
  value       = aws_vpc.this.id
}

output "subnet_ids" {
  description = "IDs of the private subnets for the Redshift Serverless workgroup."
  value       = aws_subnet.private[*].id
}

output "security_group_id" {
  description = "ID of the workgroup security group."
  value       = aws_security_group.workgroup.id
}

output "resource_arn" {
  description = "ARN of the lab VPC."
  value       = aws_vpc.this.arn
}
```

- [ ] **Step 5: Formato y test en verde**

```bash
terraform fmt -recursive infra
terraform -chdir=infra/modules/network validate
terraform -chdir=infra/modules/network test
```
Expected: `3 passed, 0 failed`.

- [ ] **Step 6: Commit**

```bash
git add infra
git commit -m "feat(infra): add network module with private subnets and optional EVR endpoints" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Módulos `s3`, `data_catalog` y `budget`

**Files:**
- Create: `infra/modules/s3/{versions,variables,main,outputs}.tf`, `tests/s3.tftest.hcl`
- Create: `infra/modules/data_catalog/{versions,variables,main,outputs}.tf`, `tests/data_catalog.tftest.hcl`
- Create: `infra/modules/budget/{versions,variables,main,outputs}.tf`, `tests/budget.tftest.hcl`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `module.s3`: vars `bucket_name: string`, `force_destroy: bool = true`, `tags: map(string)`; outputs `bucket_name`, `bucket_arn`, `resource_arn`.
  - `module.data_catalog`: vars `database_name: string = "spectrumdb"`, `tags`; outputs `database_name`, `database_arn`, `resource_arn`.
  - `module.budget`: vars `enabled: bool = false`, `name_prefix`, `project_name`, `limit_usd: number = 25`, `alert_email: string = ""`, `time_period_start: string = "2024-01-01_00:00"`, `tags`; outputs `budget_name` (`""` si apagado), `resource_arn` (`""` si apagado).

Cada módulo lleva el mismo `versions.tf` de Task 3 (copiarlo tal cual).

- [ ] **Step 1: Escribir los tres tests que fallan**

Create `infra/modules/s3/tests/s3.tftest.hcl`:

```hcl
mock_provider "aws" {}

variables {
  bucket_name = "redshift-lab-dev-123456789012-lab"
  tags        = { CostCenter = "redshift-lab" }
}

run "bucket_is_private_encrypted_and_destroyable" {
  command = apply

  assert {
    condition     = aws_s3_bucket.this.force_destroy == true
    error_message = "force_destroy must be true so destroy empties UNLOAD and Athena output."
  }

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.this.block_public_acls,
      aws_s3_bucket_public_access_block.this.block_public_policy,
      aws_s3_bucket_public_access_block.this.ignore_public_acls,
      aws_s3_bucket_public_access_block.this.restrict_public_buckets,
    ])
    error_message = "All public access must be blocked."
  }

  assert {
    condition     = one(aws_s3_bucket_server_side_encryption_configuration.this.rule).apply_server_side_encryption_by_default[0].sse_algorithm == "AES256"
    error_message = "SSE-AES256 expected."
  }

  assert {
    condition     = strcontains(aws_s3_bucket_policy.tls_only.policy, "aws:SecureTransport")
    error_message = "A TLS-only bucket policy is expected."
  }

  assert {
    condition     = output.resource_arn == output.bucket_arn
    error_message = "resource_arn must equal the bucket ARN."
  }
}
```

Create `infra/modules/data_catalog/tests/data_catalog.tftest.hcl`:

```hcl
mock_provider "aws" {}

variables {
  tags = { CostCenter = "redshift-lab" }
}

run "creates_the_spectrum_database" {
  command = apply

  assert {
    condition     = aws_glue_catalog_database.this.name == "spectrumdb"
    error_message = "Default database name must be spectrumdb."
  }

  assert {
    condition     = aws_glue_catalog_database.this.tags["CostCenter"] == "redshift-lab"
    error_message = "Common tags must be applied."
  }
}
```

Create `infra/modules/budget/tests/budget.tftest.hcl`:

```hcl
mock_provider "aws" {}

variables {
  name_prefix  = "redshift-lab-dev"
  project_name = "redshift-lab"
  tags         = { CostCenter = "redshift-lab" }
}

run "disabled_by_default" {
  command = apply

  assert {
    condition     = length(aws_budgets_budget.monthly) == 0 && output.budget_name == ""
    error_message = "The budget must not exist unless enabled."
  }
}

run "enabled_filters_by_project_tag" {
  command = apply

  variables {
    enabled     = true
    alert_email = "student@example.com"
  }

  assert {
    condition     = tolist(one(aws_budgets_budget.monthly[0].cost_filter).values)[0] == "user:Project$redshift-lab"
    error_message = "Cost filter must match the literal tag value user:Project$<project_name>."
  }
}

run "enabled_without_email_is_rejected" {
  command = plan

  variables {
    enabled = true
  }

  expect_failures = [aws_budgets_budget.monthly]
}
```

- [ ] **Step 2: Ejecutar y ver que fallan**

```bash
for m in s3 data_catalog budget; do cp infra/modules/network/versions.tf infra/modules/$m/versions.tf; terraform -chdir=infra/modules/$m init -backend=false -input=false >/dev/null; terraform -chdir=infra/modules/$m test 2>&1 | tail -4; done
```
Expected: FAIL en los tres (sin variables ni recursos).

- [ ] **Step 3: Implementar `s3`**

`infra/modules/s3/variables.tf`:

```hcl
variable "bucket_name" {
  description = "Globally unique bucket name."
  type        = string
}

variable "force_destroy" {
  description = "Let destroy delete the bucket even if it holds objects (UNLOAD output, Athena results)."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
```

`infra/modules/s3/main.tf`:

```hcl
resource "aws_s3_bucket" "this" {
  bucket        = var.bucket_name
  force_destroy = var.force_destroy
  tags          = var.tags
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  bucket = aws_s3_bucket.this.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })

  depends_on = [aws_s3_bucket_public_access_block.this]
}
```

`infra/modules/s3/outputs.tf`:

```hcl
output "bucket_name" {
  description = "Name of the lab bucket."
  value       = aws_s3_bucket.this.bucket
}

output "bucket_arn" {
  description = "ARN of the lab bucket."
  value       = aws_s3_bucket.this.arn
}

output "resource_arn" {
  description = "ARN of the lab bucket."
  value       = aws_s3_bucket.this.arn
}
```

- [ ] **Step 4: Implementar `data_catalog`**

`infra/modules/data_catalog/variables.tf`:

```hcl
variable "database_name" {
  description = "Glue database that backs the Redshift Spectrum external schema and the Athena queries."
  type        = string
  default     = "spectrumdb"
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
```

`infra/modules/data_catalog/main.tf`:

```hcl
# Owned by Terraform (not by CREATE EXTERNAL DATABASE) so that destroy removes it
# together with the external tables Redshift creates inside it.
resource "aws_glue_catalog_database" "this" {
  name        = var.database_name
  description = "Redshift lab: external tables for Spectrum and Athena."
  tags        = var.tags
}
```

`infra/modules/data_catalog/outputs.tf`:

```hcl
output "database_name" {
  description = "Name of the Glue database."
  value       = aws_glue_catalog_database.this.name
}

output "database_arn" {
  description = "ARN of the Glue database."
  value       = aws_glue_catalog_database.this.arn
}

output "resource_arn" {
  description = "ARN of the Glue database."
  value       = aws_glue_catalog_database.this.arn
}
```

- [ ] **Step 5: Implementar `budget`** (sin el SNS de la plantilla: sus notificaciones nunca lo referenciaban; y con el filtro corregido: la plantilla escribía `$${var.project_name}`, que produce el texto literal `${var.project_name}`)

`infra/modules/budget/variables.tf`:

```hcl
variable "enabled" {
  description = "Create the monthly AWS Budget. Off by default for student deployments."
  type        = bool
  default     = false
}

variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "project_name" {
  description = "Value of the Project tag the budget filters on."
  type        = string
}

variable "limit_usd" {
  description = "Monthly limit in USD. Alerts at 80% (actual) and 100% (forecasted)."
  type        = number
  default     = 25
}

variable "alert_email" {
  description = "Email for budget alerts. Required when enabled."
  type        = string
  default     = ""
}

variable "time_period_start" {
  description = "Budget start, format YYYY-MM-DD_HH:MM."
  type        = string
  default     = "2024-01-01_00:00"
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
```

`infra/modules/budget/main.tf`:

```hcl
resource "aws_budgets_budget" "monthly" {
  count             = var.enabled ? 1 : 0
  name              = "${var.name_prefix}-monthly-budget"
  budget_type       = "COST"
  limit_amount      = tostring(var.limit_usd)
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = var.time_period_start
  tags              = var.tags

  cost_filter {
    name   = "TagKeyValue"
    values = [format("user:Project$%s", var.project_name)]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }

  lifecycle {
    precondition {
      condition     = var.alert_email != ""
      error_message = "alert_email is required when the budget is enabled."
    }
  }
}
```

`infra/modules/budget/outputs.tf`:

```hcl
output "budget_name" {
  description = "Budget name. Empty string when the guardrail is disabled."
  value       = try(aws_budgets_budget.monthly[0].name, "")
}

output "resource_arn" {
  description = "Budget ARN. Empty string when the guardrail is disabled."
  value       = try(aws_budgets_budget.monthly[0].arn, "")
}
```

- [ ] **Step 6: Formato y tests en verde**

```bash
terraform fmt -recursive infra
for m in s3 data_catalog budget; do terraform -chdir=infra/modules/$m validate && terraform -chdir=infra/modules/$m test 2>&1 | tail -3; done
```
Expected: `passed` en los tres (s3: 1, data_catalog: 1, budget: 3).

- [ ] **Step 7: Commit**

```bash
git add infra
git commit -m "feat(infra): add s3, data_catalog and budget modules" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Módulo `iam` (con gate de aprobación)

**Files:**
- Create: `infra/modules/iam/{versions,variables,main,outputs}.tf`, `tests/iam.tftest.hcl`

**Interfaces:**
- Consumes: `module.s3.bucket_arn`, `module.data_catalog.database_name` y `database_arn` (llegan como variables desde la raíz).
- Produces (`module.iam`): vars `name_prefix: string`, `account_id: string`, `aws_region: string`, `lab_bucket_arn: string`, `glue_database_name: string`, `glue_database_arn: string`, `dataset_bucket_name: string = "redshift-downloads"`, `dataset_prefix: string = "tickit"`, `tags`. Outputs `redshift_role_arn`, `redshift_role_name`, `no_permissions_role_arn`, `resource_arn` (= `redshift_role_arn`).

- [ ] **Step 1: Escribir el test que falla**

Create `infra/modules/iam/tests/iam.tftest.hcl`:

```hcl
mock_provider "aws" {}

variables {
  name_prefix        = "redshift-lab-dev"
  account_id         = "123456789012"
  aws_region         = "us-east-1"
  lab_bucket_arn     = "arn:aws:s3:::redshift-lab-dev-123456789012-lab"
  glue_database_name = "spectrumdb"
  glue_database_arn  = "arn:aws:glue:us-east-1:123456789012:database/spectrumdb"
  tags               = { CostCenter = "redshift-lab" }
}

run "trust_includes_both_redshift_principals" {
  command = apply

  assert {
    condition = alltrue([
      for role in [aws_iam_role.redshift, aws_iam_role.no_permissions] :
      toset(flatten([for s in jsondecode(role.assume_role_policy).Statement : s.Principal.Service])) == toset(["redshift.amazonaws.com", "redshift-serverless.amazonaws.com"])
    ])
    error_message = "Both roles must be assumable by redshift.amazonaws.com and redshift-serverless.amazonaws.com."
  }
}

run "policies_are_scoped_without_wildcard_resources" {
  command = apply

  assert {
    condition = alltrue([
      for p in [aws_iam_role_policy.dataset_read.policy, aws_iam_role_policy.lab_bucket.policy, aws_iam_role_policy.glue_catalog.policy] :
      !contains(flatten([for s in jsondecode(p).Statement : s.Resource]), "*")
    ])
    error_message = "No policy statement may use Resource \"*\"."
  }

  assert {
    condition     = contains(flatten([for s in jsondecode(aws_iam_role_policy.dataset_read.policy).Statement : s.Resource]), "arn:aws:s3:::redshift-downloads/tickit/*")
    error_message = "Dataset read must be limited to the tickit prefix."
  }

  assert {
    condition     = contains(flatten([for s in jsondecode(aws_iam_role_policy.lab_bucket.policy).Statement : s.Resource]), "arn:aws:s3:::redshift-lab-dev-123456789012-lab/*")
    error_message = "Lab bucket access must be limited to the lab bucket."
  }

  assert {
    condition     = contains(flatten([for s in jsondecode(aws_iam_role_policy.glue_catalog.policy).Statement : s.Resource]), "arn:aws:glue:us-east-1:123456789012:database/spectrumdb")
    error_message = "Glue access must include the lab database."
  }
}

run "no_permissions_role_is_named_for_part_7" {
  command = apply

  assert {
    condition     = endswith(aws_iam_role.no_permissions.name, "-rol-sin-permisos")
    error_message = "The empty role must be named ...-rol-sin-permisos."
  }
}
```

- [ ] **Step 2: Ejecutar y ver que falla**

```bash
cp infra/modules/network/versions.tf infra/modules/iam/versions.tf
terraform -chdir=infra/modules/iam init -backend=false -input=false >/dev/null
terraform -chdir=infra/modules/iam test 2>&1 | tail -4
```
Expected: FAIL.

- [ ] **Step 3: Implementar**

`infra/modules/iam/variables.tf`:

```hcl
variable "name_prefix" {
  description = "Prefix for role names."
  type        = string
}

variable "account_id" {
  description = "AWS account ID (used to build Glue ARNs)."
  type        = string
}

variable "aws_region" {
  description = "AWS region (used to build Glue ARNs)."
  type        = string
}

variable "lab_bucket_arn" {
  description = "ARN of the lab bucket (UNLOAD target)."
  type        = string
}

variable "glue_database_name" {
  description = "Glue database used by Spectrum and Athena."
  type        = string
}

variable "glue_database_arn" {
  description = "ARN of the Glue database."
  type        = string
}

variable "dataset_bucket_name" {
  description = "Public bucket that holds the TICKIT dataset."
  type        = string
  default     = "redshift-downloads"
}

variable "dataset_prefix" {
  description = "Prefix of the TICKIT dataset inside the dataset bucket."
  type        = string
  default     = "tickit"
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
```

`infra/modules/iam/main.tf`:

```hcl
locals {
  # Redshift Serverless requires both service principals in the trust relationship.
  trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = ["redshift.amazonaws.com", "redshift-serverless.amazonaws.com"] }
      Action    = "sts:AssumeRole"
    }]
  })

  dataset_bucket_arn = "arn:aws:s3:::${var.dataset_bucket_name}"
  glue_catalog_arn   = "arn:aws:glue:${var.aws_region}:${var.account_id}:catalog"
  glue_tables_arn    = "arn:aws:glue:${var.aws_region}:${var.account_id}:table/${var.glue_database_name}/*"
}

resource "aws_iam_role" "redshift" {
  name               = "${var.name_prefix}-redshift-role"
  assume_role_policy = local.trust_policy
  tags               = var.tags
}

# Read the public TICKIT dataset (COPY and Spectrum).
resource "aws_iam_role_policy" "dataset_read" {
  name = "${var.name_prefix}-dataset-read"
  role = aws_iam_role.redshift.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${local.dataset_bucket_arn}/${var.dataset_prefix}/*"]
      },
      {
        Effect    = "Allow"
        Action    = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource  = [local.dataset_bucket_arn]
        Condition = { StringLike = { "s3:prefix" = ["${var.dataset_prefix}/*"] } }
      },
    ]
  })
}

# Read and write the lab bucket (UNLOAD output).
resource "aws_iam_role_policy" "lab_bucket" {
  name = "${var.name_prefix}-lab-bucket"
  role = aws_iam_role.redshift.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"]
        Resource = ["${var.lab_bucket_arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = [var.lab_bucket_arn]
      },
    ]
  })
}

# Spectrum: read the catalog and create/update external tables inside the lab database only.
resource "aws_iam_role_policy" "glue_catalog" {
  name = "${var.name_prefix}-glue-catalog"
  role = aws_iam_role.redshift.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "glue:GetDatabase", "glue:GetDatabases",
        "glue:GetTable", "glue:GetTables", "glue:CreateTable", "glue:UpdateTable", "glue:DeleteTable", "glue:BatchDeleteTable",
        "glue:GetPartition", "glue:GetPartitions", "glue:BatchGetPartition",
        "glue:CreatePartition", "glue:BatchCreatePartition", "glue:UpdatePartition", "glue:DeletePartition", "glue:BatchDeletePartition",
      ]
      Resource = [local.glue_catalog_arn, var.glue_database_arn, local.glue_tables_arn]
    }]
  })
}

# Part 7 (troubleshooting): associated with the namespace but with no permissions at all,
# so COPY fails with S3 Access Denied and not with "role not associated".
resource "aws_iam_role" "no_permissions" {
  name               = "${var.name_prefix}-rol-sin-permisos"
  assume_role_policy = local.trust_policy
  tags               = var.tags
}
```

`infra/modules/iam/outputs.tf`:

```hcl
output "redshift_role_arn" {
  description = "ARN of the Redshift role (namespace default role)."
  value       = aws_iam_role.redshift.arn
}

output "redshift_role_name" {
  description = "Name of the Redshift role."
  value       = aws_iam_role.redshift.name
}

output "no_permissions_role_arn" {
  description = "ARN of the empty role used to provoke the COPY error in Part 7."
  value       = aws_iam_role.no_permissions.arn
}

output "resource_arn" {
  description = "ARN of the Redshift role."
  value       = aws_iam_role.redshift.arn
}
```

- [ ] **Step 4: Formato y tests en verde**

```bash
terraform fmt -recursive infra
terraform -chdir=infra/modules/iam validate && terraform -chdir=infra/modules/iam test 2>&1 | tail -3
```
Expected: `3 passed`.

- [ ] **Step 5: GATE DE APROBACIÓN (IAM) — detenerse**

`AGENTS.md`: los cambios de IAM requieren aprobación. **No continuar a Task 6 hasta que Ricardo revise** `infra/modules/iam/main.tf` (trust de ambos principals, lectura limitada a `redshift-downloads/tickit/*`, escritura limitada al bucket del lab, Glue limitado a la base del lab, y el rol vacío). Registrar su respuesta. Si pide cambios, editar y repetir Step 4.

- [ ] **Step 6: Commit (solo tras la aprobación)**

```bash
git add infra
git commit -m "feat(infra): add iam module with scoped Redshift roles" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Módulos `athena` y `redshift`

**Files:**
- Create: `infra/modules/athena/{versions,variables,main,outputs}.tf`, `tests/athena.tftest.hcl`
- Create: `infra/modules/redshift/{versions,variables,main,outputs}.tf`, `tests/redshift.tftest.hcl`

**Interfaces:**
- Consumes: `module.network.subnet_ids`/`security_group_id`, `module.iam.redshift_role_arn`/`no_permissions_role_arn`, `module.s3.bucket_name`.
- Produces:
  - `module.athena`: vars `name_prefix`, `results_bucket_name`, `results_prefix: string = "athena-results"`, `bytes_scanned_cutoff_per_query: number = 1073741824`, `tags`; outputs `workgroup_name`, `resource_arn`.
  - `module.redshift`: vars `name_prefix`, `subnet_ids: list(string)`, `security_group_ids: list(string)`, `default_iam_role_arn`, `additional_iam_role_arns: list(string) = []`, `enable_enhanced_vpc_routing: bool = false`, `base_capacity: number = 4`, `max_capacity: number = 8`, `usage_limit_rpu_hours_daily: number = 16`, `log_retention_days: number = 7`, `db_name: string = "dev"`, `admin_username: string = "awsuser"`, `tags`; outputs `namespace_name`, `workgroup_name`, `database_name`, `admin_secret_arn`, `workgroup_endpoint`, `resource_arn`, `log_group_name`, `log_group_arn`.

**Hechos verificados contra la documentación del provider y de AWS (2026-09-30):** `manage_admin_password`, `default_iam_role_arn` (debe estar también en `iam_roles`), `log_exports`, `max_capacity`, `enhanced_vpc_routing`, `publicly_accessible`; `aws_redshiftserverless_usage_limit` con `usage_type = "serverless-compute"`, `period = "daily"`, `breach_action = "deactivate"`; log group real: `/aws/redshift/<namespace>/<log_type>`. **Conflicto abierto:** la doc del provider dice que `subnet_ids` "debe contener al menos tres subnets en tres AZs"; la doc de AWS dice dos AZs sin EVR. Si el primer apply (Task 14) rechaza dos subnets, usar `availability_zone_count = 3`.

- [ ] **Step 1: Escribir los tests que fallan**

Create `infra/modules/athena/tests/athena.tftest.hcl`:

```hcl
mock_provider "aws" {}

variables {
  name_prefix         = "redshift-lab-dev"
  results_bucket_name = "redshift-lab-dev-123456789012-lab"
  tags                = { CostCenter = "redshift-lab" }
}

run "workgroup_writes_to_the_lab_bucket_and_is_destroyable" {
  command = apply

  assert {
    condition     = aws_athena_workgroup.this.force_destroy == true
    error_message = "force_destroy must be true."
  }

  assert {
    condition     = one(aws_athena_workgroup.this.configuration).enforce_workgroup_configuration == true
    error_message = "Workgroup settings must override client-side settings."
  }

  assert {
    condition     = one(one(aws_athena_workgroup.this.configuration).result_configuration).output_location == "s3://redshift-lab-dev-123456789012-lab/athena-results/"
    error_message = "Results must go to the lab bucket under athena-results/."
  }

  assert {
    condition     = one(one(one(aws_athena_workgroup.this.configuration).result_configuration).encryption_configuration).encryption_option == "SSE_S3"
    error_message = "Results must be encrypted with SSE_S3."
  }
}
```

Create `infra/modules/redshift/tests/redshift.tftest.hcl`:

```hcl
mock_provider "aws" {
  mock_resource "aws_redshiftserverless_workgroup" {
    defaults = {
      arn = "arn:aws:redshift-serverless:us-east-1:123456789012:workgroup/mock"
    }
  }
}

variables {
  name_prefix              = "redshift-lab-dev"
  subnet_ids               = ["subnet-aaa", "subnet-bbb"]
  security_group_ids       = ["sg-aaa"]
  default_iam_role_arn     = "arn:aws:iam::123456789012:role/redshift-lab-dev-redshift-role"
  additional_iam_role_arns = ["arn:aws:iam::123456789012:role/redshift-lab-dev-rol-sin-permisos"]
  tags                     = { CostCenter = "redshift-lab" }
}

run "workgroup_is_private_small_and_capped" {
  command = apply

  assert {
    condition     = aws_redshiftserverless_workgroup.this.base_capacity == 4 && aws_redshiftserverless_workgroup.this.max_capacity == 8
    error_message = "Defaults must be base 4 and max 8 RPUs."
  }

  assert {
    condition     = aws_redshiftserverless_workgroup.this.publicly_accessible == false
    error_message = "The workgroup must not be publicly accessible."
  }

  assert {
    condition     = aws_redshiftserverless_workgroup.this.enhanced_vpc_routing == false
    error_message = "Enhanced VPC routing is off by default."
  }

  assert {
    condition     = aws_redshiftserverless_usage_limit.daily.period == "daily" && aws_redshiftserverless_usage_limit.daily.breach_action == "deactivate" && aws_redshiftserverless_usage_limit.daily.amount == 16
    error_message = "A daily 16 RPU-hour limit with deactivate is expected."
  }
}

run "namespace_uses_managed_password_and_default_role" {
  command = apply

  assert {
    condition     = aws_redshiftserverless_namespace.this.manage_admin_password == true
    error_message = "The admin password must be managed by Secrets Manager."
  }

  assert {
    condition     = aws_redshiftserverless_namespace.this.default_iam_role_arn == var.default_iam_role_arn && contains(aws_redshiftserverless_namespace.this.iam_roles, var.default_iam_role_arn)
    error_message = "The default role must be set and also be in iam_roles."
  }

  assert {
    condition     = contains(aws_redshiftserverless_namespace.this.iam_roles, var.additional_iam_role_arns[0])
    error_message = "The no-permissions role must be associated with the namespace (Part 7)."
  }
}

run "log_group_is_explicit_and_named_like_the_service_expects" {
  command = apply

  assert {
    condition     = aws_cloudwatch_log_group.connectionlog.name == "/aws/redshift/redshift-lab-dev-ns/connectionlog"
    error_message = "The log group must be /aws/redshift/<namespace>/connectionlog."
  }

  assert {
    condition     = aws_cloudwatch_log_group.connectionlog.retention_in_days == 7
    error_message = "Retention must be set (7 days by default)."
  }
}

run "rejects_invalid_base_capacity" {
  command = plan

  variables {
    base_capacity = 6
  }

  expect_failures = [var.base_capacity]
}

run "rejects_max_capacity_below_base" {
  command = plan

  variables {
    base_capacity = 16
    max_capacity  = 8
  }

  expect_failures = [aws_redshiftserverless_workgroup.this]
}
```

- [ ] **Step 2: Ejecutar y ver que fallan**

```bash
for m in athena redshift; do cp infra/modules/network/versions.tf infra/modules/$m/versions.tf; terraform -chdir=infra/modules/$m init -backend=false -input=false >/dev/null; terraform -chdir=infra/modules/$m test 2>&1 | tail -3; done
```
Expected: FAIL en ambos.

- [ ] **Step 3: Implementar `athena`**

`infra/modules/athena/variables.tf`:

```hcl
variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "results_bucket_name" {
  description = "Bucket where Athena writes query results."
  type        = string
}

variable "results_prefix" {
  description = "Prefix inside the bucket for Athena results."
  type        = string
  default     = "athena-results"
}

variable "bytes_scanned_cutoff_per_query" {
  description = "Per-query scan limit in bytes (cost guard). Default 1 GiB; the TICKIT data is far smaller."
  type        = number
  default     = 1073741824
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
```

`infra/modules/athena/main.tf`:

```hcl
resource "aws_athena_workgroup" "this" {
  name          = "${var.name_prefix}-wg"
  force_destroy = true
  tags          = var.tags

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = false
    bytes_scanned_cutoff_per_query     = var.bytes_scanned_cutoff_per_query

    result_configuration {
      output_location = "s3://${var.results_bucket_name}/${var.results_prefix}/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}
```

`infra/modules/athena/outputs.tf`:

```hcl
output "workgroup_name" {
  description = "Name of the Athena workgroup."
  value       = aws_athena_workgroup.this.name
}

output "resource_arn" {
  description = "ARN of the Athena workgroup."
  value       = aws_athena_workgroup.this.arn
}
```

- [ ] **Step 4: Implementar `redshift`**

`infra/modules/redshift/variables.tf`:

```hcl
variable "name_prefix" {
  description = "Prefix for resource names, e.g. redshift-lab-dev."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets for the workgroup."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security groups for the workgroup."
  type        = list(string)
}

variable "default_iam_role_arn" {
  description = "Role used by IAM_ROLE DEFAULT (COPY, UNLOAD, CREATE EXTERNAL SCHEMA)."
  type        = string
}

variable "additional_iam_role_arns" {
  description = "Extra roles associated with the namespace but not default (the empty role for Part 7)."
  type        = list(string)
  default     = []
}

variable "enable_enhanced_vpc_routing" {
  description = "Route COPY/UNLOAD/Spectrum traffic through the VPC. Needs 3 AZs and the endpoints from the network module."
  type        = bool
  default     = false
}

variable "base_capacity" {
  description = "Base capacity in RPUs. 4 (minimum) or a multiple of 8."
  type        = number
  default     = 4

  validation {
    condition     = var.base_capacity == 4 || (var.base_capacity >= 8 && var.base_capacity % 8 == 0)
    error_message = "base_capacity must be 4 or a multiple of 8."
  }
}

variable "max_capacity" {
  description = "Ceiling for automatic scaling, in RPUs. Must be >= base_capacity."
  type        = number
  default     = 8
}

variable "usage_limit_rpu_hours_daily" {
  description = "Daily RPU-hour cap; queries are turned off when it is reached."
  type        = number
  default     = 16
}

variable "log_retention_days" {
  description = "CloudWatch retention for the exported connection log."
  type        = number
  default     = 7
}

variable "db_name" {
  description = "First database created in the namespace."
  type        = string
  default     = "dev"
}

variable "admin_username" {
  description = "Admin user; its password is generated and stored by Secrets Manager."
  type        = string
  default     = "awsuser"
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
```

`infra/modules/redshift/main.tf`:

```hcl
locals {
  namespace_name = "${var.name_prefix}-ns"
  workgroup_name = "${var.name_prefix}-wg"
}

# Created BEFORE the namespace: if the group does not exist Redshift creates it itself with
# "Never Expire" retention and outside Terraform, which would survive the destroy.
resource "aws_cloudwatch_log_group" "connectionlog" {
  name              = "/aws/redshift/${local.namespace_name}/connectionlog"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_redshiftserverless_namespace" "this" {
  namespace_name        = local.namespace_name
  db_name               = var.db_name
  admin_username        = var.admin_username
  manage_admin_password = true
  default_iam_role_arn  = var.default_iam_role_arn
  iam_roles             = concat([var.default_iam_role_arn], var.additional_iam_role_arns)
  log_exports           = ["connectionlog"]
  tags                  = var.tags

  depends_on = [aws_cloudwatch_log_group.connectionlog]
}

resource "aws_redshiftserverless_workgroup" "this" {
  namespace_name       = aws_redshiftserverless_namespace.this.namespace_name
  workgroup_name       = local.workgroup_name
  base_capacity        = var.base_capacity
  max_capacity         = var.max_capacity
  enhanced_vpc_routing = var.enable_enhanced_vpc_routing
  publicly_accessible  = false
  subnet_ids           = var.subnet_ids
  security_group_ids   = var.security_group_ids
  tags                 = var.tags

  lifecycle {
    precondition {
      condition     = var.max_capacity >= var.base_capacity
      error_message = "max_capacity must be greater than or equal to base_capacity."
    }
  }
}

resource "aws_redshiftserverless_usage_limit" "daily" {
  resource_arn  = aws_redshiftserverless_workgroup.this.arn
  usage_type    = "serverless-compute"
  amount        = var.usage_limit_rpu_hours_daily
  period        = "daily"
  breach_action = "deactivate"
}
```

`infra/modules/redshift/outputs.tf`:

```hcl
output "namespace_name" {
  description = "Name of the Redshift Serverless namespace."
  value       = aws_redshiftserverless_namespace.this.namespace_name
}

output "workgroup_name" {
  description = "Name of the Redshift Serverless workgroup."
  value       = aws_redshiftserverless_workgroup.this.workgroup_name
}

output "database_name" {
  description = "Name of the first database."
  value       = aws_redshiftserverless_namespace.this.db_name
}

output "admin_secret_arn" {
  description = "ARN of the Secrets Manager secret with the admin credentials (used by the Data API)."
  value       = aws_redshiftserverless_namespace.this.admin_password_secret_arn
}

output "workgroup_endpoint" {
  description = "Endpoint address of the workgroup. Empty until the endpoint exists."
  value       = try(aws_redshiftserverless_workgroup.this.endpoint[0].address, "")
}

output "resource_arn" {
  description = "ARN of the workgroup."
  value       = aws_redshiftserverless_workgroup.this.arn
}

output "log_group_name" {
  description = "CloudWatch log group for the exported connection log."
  value       = aws_cloudwatch_log_group.connectionlog.name
}

output "log_group_arn" {
  description = "ARN of the connection log group."
  value       = aws_cloudwatch_log_group.connectionlog.arn
}
```

- [ ] **Step 5: Formato y tests en verde**

```bash
terraform fmt -recursive infra
for m in athena redshift; do terraform -chdir=infra/modules/$m validate && terraform -chdir=infra/modules/$m test 2>&1 | tail -3; done
```
Expected: athena `1 passed`; redshift `5 passed`. Si un test falla por un valor generado por el mock (p. ej. ARN inválido), añadir `mock_resource` con `defaults` para ese atributo; no relajar las aserciones.

- [ ] **Step 6: Commit**

```bash
git add infra
git commit -m "feat(infra): add athena and redshift serverless modules" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Raíz de Terraform (composición)

**Files:**
- Create: `infra/variables.tf`, `infra/main.tf`, `infra/outputs.tf`, `infra/terraform.tfvars.example`, `infra/tests/root.tftest.hcl`
- Modify: `infra/providers.tf` (sin cambios de contenido si ya está en `>= 1.7.0`)

**Interfaces:**
- Consumes: todos los módulos de Tasks 3–6 (firmas exactas en sus bloques **Interfaces**).
- Produces: outputs de la raíz que consume `scripts/lab/config.py`: `aws_region`, `workgroup_name`, `database_name`, `admin_secret_arn`, `bucket_name`, `redshift_role_arn`, `no_permissions_role_arn`, `athena_workgroup_name`, `glue_database_name`; más `namespace_name`, `log_group_name`, `log_group_arn`, `budget_name`, `resource_arns`.

- [ ] **Step 1: Escribir el test de la raíz que falla**

Create `infra/tests/root.tftest.hcl`:

```hcl
mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_availability_zones" {
    defaults = { names = ["us-east-1a", "us-east-1b", "us-east-1c"] }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mock" }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::mock-bucket" }
  }
  mock_resource "aws_glue_catalog_database" {
    defaults = { arn = "arn:aws:glue:us-east-1:123456789012:database/mock" }
  }
  mock_resource "aws_redshiftserverless_workgroup" {
    defaults = { arn = "arn:aws:redshift-serverless:us-east-1:123456789012:workgroup/mock" }
  }
}

run "wires_the_lab_with_default_names" {
  command = apply

  assert {
    condition     = output.bucket_name == "redshift-lab-dev-123456789012-lab"
    error_message = "Bucket name must be <project>-<env>-<account>-lab."
  }

  assert {
    condition     = output.workgroup_name == "redshift-lab-dev-wg" && output.namespace_name == "redshift-lab-dev-ns"
    error_message = "Workgroup and namespace names must derive from the prefix."
  }

  assert {
    condition     = output.glue_database_name == "spectrumdb"
    error_message = "The Glue database must be spectrumdb."
  }

  assert {
    condition     = output.budget_name == ""
    error_message = "The budget must be off by default."
  }

  assert {
    condition     = length(module.network.subnet_ids) == 2
    error_message = "Two subnets expected by default."
  }
}

run "enhanced_vpc_routing_forces_three_azs" {
  command = apply

  variables {
    enable_enhanced_vpc_routing = true
  }

  assert {
    condition     = length(module.network.subnet_ids) == 3
    error_message = "Enhanced VPC routing needs at least three AZs."
  }
}

run "rejects_invalid_project_name" {
  command = plan

  variables {
    project_name = "Bad_Name"
  }

  expect_failures = [var.project_name]
}

run "rejects_other_regions" {
  command = plan

  variables {
    aws_region = "eu-west-1"
  }

  expect_failures = [var.aws_region]
}
```

- [ ] **Step 2: Ejecutar y ver que falla**

```bash
terraform -chdir=infra init -backend=false -input=false
terraform -chdir=infra test 2>&1 | tail -5
```
Expected: FAIL (la raíz no declara variables ni módulos).

- [ ] **Step 3: Implementar la raíz**

`infra/variables.tf`:

```hcl
variable "project_name" {
  description = "Project name used in resource naming (lowercase letters, digits, hyphens)."
  type        = string
  default     = "redshift-lab"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,20}$", var.project_name))
    error_message = "project_name must be 3-20 characters: lowercase letters, digits and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Owner tag applied to all resources."
  type        = string
  default     = "lab-student"
}

variable "cost_center" {
  description = "CostCenter tag applied to all resources."
  type        = string
  default     = "redshift-lab"
}

variable "aws_region" {
  description = "AWS region. Must be us-east-1: the public TICKIT dataset lives there and 4 RPUs is available there."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "This lab only supports us-east-1."
  }
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}

variable "glue_database_name" {
  description = "Glue database for Spectrum and Athena."
  type        = string
  default     = "spectrumdb"
}

variable "availability_zone_count" {
  description = "AZs/subnets for the workgroup: 2 without enhanced VPC routing (3 is forced with it). Use 3 if the first apply rejects 2."
  type        = number
  default     = 2
}

variable "availability_zone_names" {
  description = "Optional explicit AZ names if the default AZs are not supported by Redshift Serverless in your account."
  type        = list(string)
  default     = null
}

variable "enable_enhanced_vpc_routing" {
  description = "Turn on enhanced VPC routing (creates S3 and Glue endpoints; the Glue one has an hourly cost)."
  type        = bool
  default     = false
}

variable "base_capacity" {
  description = "Redshift Serverless base capacity in RPUs (4, or a multiple of 8)."
  type        = number
  default     = 4
}

variable "max_capacity" {
  description = "Redshift Serverless scaling ceiling in RPUs."
  type        = number
  default     = 8
}

variable "usage_limit_rpu_hours_daily" {
  description = "Daily RPU-hour cap; queries are turned off when reached."
  type        = number
  default     = 16
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 7
}

variable "enable_budget_guardrail" {
  description = "Create a monthly AWS Budget. Off by default for student deployments."
  type        = bool
  default     = false
}

variable "budget_limit_usd" {
  description = "Monthly budget limit in USD."
  type        = number
  default     = 25
}

variable "budget_alert_email" {
  description = "Email for budget alerts. Required when enable_budget_guardrail is true."
  type        = string
  default     = ""
}
```

`infra/main.tf`:

```hcl
data "aws_caller_identity" "current" {}

locals {
  name_prefix = lower(replace("${var.project_name}-${var.environment}", "_", "-"))
  bucket_name = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}-lab"
  az_count    = var.enable_enhanced_vpc_routing ? max(3, var.availability_zone_count) : var.availability_zone_count

  common_tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "Terraform"
    CostCenter  = var.cost_center
  })
}

module "network" {
  source                      = "./modules/network"
  name_prefix                 = local.name_prefix
  aws_region                  = var.aws_region
  availability_zone_count     = local.az_count
  availability_zone_names     = var.availability_zone_names
  enable_enhanced_vpc_routing = var.enable_enhanced_vpc_routing
  tags                        = local.common_tags
}

module "s3" {
  source      = "./modules/s3"
  bucket_name = local.bucket_name
  tags        = local.common_tags
}

module "data_catalog" {
  source        = "./modules/data_catalog"
  database_name = var.glue_database_name
  tags          = local.common_tags
}

module "iam" {
  source             = "./modules/iam"
  name_prefix        = local.name_prefix
  account_id         = data.aws_caller_identity.current.account_id
  aws_region         = var.aws_region
  lab_bucket_arn     = module.s3.bucket_arn
  glue_database_name = module.data_catalog.database_name
  glue_database_arn  = module.data_catalog.database_arn
  tags               = local.common_tags
}

module "redshift" {
  source                      = "./modules/redshift"
  name_prefix                 = local.name_prefix
  subnet_ids                  = module.network.subnet_ids
  security_group_ids          = [module.network.security_group_id]
  default_iam_role_arn        = module.iam.redshift_role_arn
  additional_iam_role_arns    = [module.iam.no_permissions_role_arn]
  enable_enhanced_vpc_routing = var.enable_enhanced_vpc_routing
  base_capacity               = var.base_capacity
  max_capacity                = var.max_capacity
  usage_limit_rpu_hours_daily = var.usage_limit_rpu_hours_daily
  log_retention_days          = var.log_retention_days
  tags                        = local.common_tags
}

module "athena" {
  source              = "./modules/athena"
  name_prefix         = local.name_prefix
  results_bucket_name = module.s3.bucket_name
  tags                = local.common_tags
}

module "budget" {
  source       = "./modules/budget"
  enabled      = var.enable_budget_guardrail
  name_prefix  = local.name_prefix
  project_name = var.project_name
  limit_usd    = var.budget_limit_usd
  alert_email  = var.budget_alert_email
  tags         = local.common_tags
}
```

`infra/outputs.tf`:

```hcl
output "aws_region" {
  description = "Region of the lab."
  value       = var.aws_region
}

output "bucket_name" {
  description = "Lab bucket (UNLOAD target and Athena results)."
  value       = module.s3.bucket_name
}

output "namespace_name" {
  description = "Redshift Serverless namespace."
  value       = module.redshift.namespace_name
}

output "workgroup_name" {
  description = "Redshift Serverless workgroup."
  value       = module.redshift.workgroup_name
}

output "database_name" {
  description = "First Redshift database."
  value       = module.redshift.database_name
}

output "admin_secret_arn" {
  description = "Secrets Manager secret with the admin credentials (Data API authentication)."
  value       = module.redshift.admin_secret_arn
}

output "redshift_role_arn" {
  description = "Default IAM role of the namespace."
  value       = module.iam.redshift_role_arn
}

output "no_permissions_role_arn" {
  description = "Empty IAM role for the Part 7 troubleshooting case."
  value       = module.iam.no_permissions_role_arn
}

output "athena_workgroup_name" {
  description = "Athena workgroup."
  value       = module.athena.workgroup_name
}

output "glue_database_name" {
  description = "Glue database for Spectrum and Athena."
  value       = module.data_catalog.database_name
}

output "log_group_name" {
  description = "CloudWatch log group of the Redshift namespace."
  value       = module.redshift.log_group_name
}

output "log_group_arn" {
  description = "ARN of the Redshift namespace log group."
  value       = module.redshift.log_group_arn
}

output "budget_name" {
  description = "Budget name. Empty string when the guardrail is disabled."
  value       = module.budget.budget_name
}

output "resource_arns" {
  description = "ARN of the main resource of each module."
  value = {
    network      = module.network.resource_arn
    s3           = module.s3.resource_arn
    data_catalog = module.data_catalog.resource_arn
    iam          = module.iam.resource_arn
    redshift     = module.redshift.resource_arn
    athena       = module.athena.resource_arn
    budget       = module.budget.resource_arn
  }
}
```

`infra/terraform.tfvars.example`:

```hcl
# Copy to terraform.tfvars. Every value below is optional; these are the defaults.
project_name = "redshift-lab"
environment  = "dev"
aws_region   = "us-east-1"
owner        = "lab-student"
cost_center  = "redshift-lab"

# Cost guards
base_capacity               = 4
max_capacity                = 8
usage_limit_rpu_hours_daily = 16

# Network: use 3 if the first apply rejects 2 subnets.
availability_zone_count     = 2
enable_enhanced_vpc_routing = false

# Optional monthly budget with email alerts (needs an email).
enable_budget_guardrail = false
# budget_alert_email    = "you@example.com"
```

- [ ] **Step 4: Formato y tests en verde**

```bash
terraform fmt -recursive infra
terraform -chdir=infra validate
terraform -chdir=infra test 2>&1 | tail -4
```
Expected: `4 passed`. Correr también los tests de todos los módulos: `for m in network s3 data_catalog iam redshift athena budget; do terraform -chdir=infra/modules/$m test 2>&1 | tail -1; done` (todos `passed`).

- [ ] **Step 5: Commit**

```bash
git add infra
git commit -m "feat(infra): compose the lab modules in the root with validated variables" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: SQL del lab y su carga (`sql/` + `scripts/lab/sql.py`)

**Files:**
- Create: `sql/01_ddl.sql`, `02_copy.sql`, `03_star_schema.sql`, `04_analytics.sql`, `05_athena_vs_redshift.sql`, `06_unload.sql`, `07_spectrum_setup.sql`, `07_spectrum_queries.sql`, `08_troubleshooting.sql`
- Create: `scripts/lab/sql.py`, `tests/lab/test_sql.py`

**Interfaces:**
- Consumes: nada.
- Produces (`scripts/lab/sql.py`):
  - `SQL_DIR: Path`, `PARTS: dict[int, tuple[str, ...]]`
  - `@dataclass(frozen=True) Statement(sql: str, engine: str = "redshift", expect_error: bool = False)`
  - `render(text: str, values: Mapping[str, str]) -> str` (lanza `KeyError` si falta un placeholder)
  - `split_statements(text: str) -> list[Statement]` (directivas `-- @engine: athena` y `-- @expect-error`)
  - `statements_for_part(part: int, values: Mapping[str, str]) -> list[Statement]`

Convención de directivas (solo se reconocen en líneas propias, fuera de una sentencia): `-- @engine: <redshift|athena>` fija el motor de las sentencias siguientes (vuelve a `redshift` al empezar cada archivo); `-- @expect-error` marca **solo la sentencia siguiente**.

- [ ] **Step 1: Escribir los tests que fallan**

Create `tests/lab/test_sql.py`:

```python
import re

import pytest

from scripts.lab.sql import PARTS, SQL_DIR, Statement, render, split_statements, statements_for_part

VALUES = {
    "bucket": "my-bucket",
    "glue_database": "spectrumdb",
    "no_permissions_role_arn": "arn:aws:iam::123456789012:role/empty",
    "redshift_role_arn": "arn:aws:iam::123456789012:role/redshift",
}


def test_split_basic_and_ignores_comments():
    text = "-- a comment\nSELECT 1; -- trailing\nSELECT 2;\n"
    assert [s.sql for s in split_statements(text)] == ["SELECT 1", "SELECT 2"]


def test_split_keeps_semicolons_and_dashes_inside_quotes():
    text = "SELECT 'a;b--c';\nSELECT 2;"
    assert [s.sql for s in split_statements(text)] == ["SELECT 'a;b--c'", "SELECT 2"]


def test_split_handles_escaped_quotes():
    text = "SELECT 'it''s; fine';SELECT 2;"
    assert [s.sql for s in split_statements(text)] == ["SELECT 'it''s; fine'", "SELECT 2"]


def test_split_last_statement_without_semicolon():
    assert [s.sql for s in split_statements("SELECT 1")] == ["SELECT 1"]


def test_engine_directive_persists_and_expect_error_applies_once():
    text = "-- @engine: athena\nSELECT 1;\nSELECT 2;\n-- @engine: redshift\n-- @expect-error\nSELECT 3;\nSELECT 4;"
    assert split_statements(text) == [
        Statement("SELECT 1", "athena", False),
        Statement("SELECT 2", "athena", False),
        Statement("SELECT 3", "redshift", True),
        Statement("SELECT 4", "redshift", False),
    ]


def test_render_substitutes_and_fails_on_missing_placeholder():
    assert render("COPY x TO 's3://${bucket}/y'", {"bucket": "b"}) == "COPY x TO 's3://b/y'"
    with pytest.raises(KeyError):
        render("${missing}", {})


def test_every_part_file_exists_and_renders_with_the_standard_values():
    for part, files in PARTS.items():
        assert files, f"part {part} has no files"
        for name in files:
            assert (SQL_DIR / name).is_file(), name
        assert statements_for_part(part, VALUES), f"part {part} produced no statements"


def test_no_hardcoded_account_arns_in_sql():
    for path in SQL_DIR.glob("*.sql"):
        assert not re.search(r"arn:aws:iam::\d{12}", path.read_text(encoding="utf-8")), path.name


def test_ddl_drops_every_table_before_creating():
    text = (SQL_DIR / "01_ddl.sql").read_text(encoding="utf-8")
    for table in ("sales", "listing", "event", "date", "category", "venue", "users"):
        assert f"DROP TABLE IF EXISTS {table};" in text
        assert text.index(f"DROP TABLE IF EXISTS {table};") < text.index(f"CREATE TABLE {table}(")


def test_part_7_marks_the_denied_copy_as_expected_error():
    statements = statements_for_part(7, VALUES)
    assert statements[0].expect_error is True
    assert "empty" in statements[0].sql
    assert not any(s.expect_error for s in statements[1:])


def test_part_4_compares_both_engines():
    engines = [s.engine for s in statements_for_part(4, VALUES) if s.sql.startswith("SELECT")]
    assert engines == ["athena", "redshift"]
```

Nota: `test_part_7...` afirma que `"empty"` aparece en el SQL renderizado de la primera sentencia (el ARN de prueba termina en `role/empty`).

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `python -m pytest tests/lab/test_sql.py -v`
Expected: FAIL (`ModuleNotFoundError: scripts.lab.sql`).

- [ ] **Step 3: Escribir los archivos SQL**

`sql/01_ddl.sql`:

```sql
-- Part 1.1 - TICKIT tables. sales is the fact table; the rest are dimensions (star schema).
-- Dropped first so that re-running Part 1 never duplicates data.
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

-- Fact table: grain = one sale; measures = qtysold, pricepaid, commission.
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

`sql/02_copy.sql`:

```sql
-- Part 1.2 - Parallel load from S3. Authorization uses the namespace default IAM role
-- (IAM_ROLE DEFAULT): no access keys and no account-specific ARN in the SQL.
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

`sql/03_star_schema.sql`:

```sql
-- Part 2 - The star schema with real data: sales (fact) in the center, date/event/venue around it.
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

`sql/04_analytics.sql`:

```sql
-- Part 3 - Recurring BI aggregation (by month and category group).
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

`sql/05_athena_vs_redshift.sql`:

```sql
-- Part 4.2 - The same business question on both engines. Both queries use only columns of sales,
-- so Athena can answer it straight from S3 (through the Glue table created in 07_spectrum_setup.sql).

-- @engine: athena
SELECT dateid, COUNT(*) AS ventas, SUM(pricepaid) AS ingresos
FROM ${glue_database}.sales
GROUP BY dateid
ORDER BY ingresos DESC
LIMIT 10;

-- @engine: redshift
SELECT dateid, COUNT(*) AS ventas, SUM(pricepaid) AS ingresos
FROM sales
GROUP BY dateid
ORDER BY ingresos DESC
LIMIT 10;
```

`sql/06_unload.sql`:

```sql
-- Part 5 - Redshift as a data producer: aggregated result to the lab bucket as partitioned Parquet.
-- If IAM_ROLE DEFAULT is rejected by UNLOAD, replace it with IAM_ROLE '${redshift_role_arn}'.
UNLOAD ('SELECT d.year, d.month, c.catgroup, SUM(s.pricepaid) AS ingresos
         FROM sales s
         JOIN date d ON s.dateid = d.dateid
         JOIN event e ON s.eventid = e.eventid
         JOIN category c ON e.catid = c.catid
         GROUP BY d.year, d.month, c.catgroup')
TO 's3://${bucket}/gold/ventas_agregadas/'
IAM_ROLE DEFAULT
FORMAT AS PARQUET
PARTITION BY (year)
ALLOWOVERWRITE;
```

`sql/07_spectrum_setup.sql`:

```sql
-- Part 6.1/6.2 - External schema and table. The Glue database already exists (created by Terraform),
-- so there is no CREATE EXTERNAL DATABASE: destroy removes it together with this table.
CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum
FROM DATA CATALOG
DATABASE '${glue_database}'
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

`sql/07_spectrum_queries.sql`:

```sql
-- Part 6.3 - Query S3 without loading anything into the workgroup.
SELECT COUNT(*) FROM spectrum.sales;

-- Join external data (Spectrum) with data already loaded in Redshift.
SELECT sp.salesid, sp.pricepaid, u.city
FROM spectrum.sales sp
JOIN users u ON sp.buyerid = u.userid
LIMIT 10;
```

`sql/08_troubleshooting.sql`:

```sql
-- Part 7 - COPY with a role that has no S3 permissions: the error is about the role, not the SQL or the data.
-- @expect-error
COPY users
FROM 's3://redshift-downloads/tickit/allusers_pipe.txt'
IAM_ROLE '${no_permissions_role_arn}'
DELIMITER '|' REGION 'us-east-1';

-- Diagnose. Row-level load errors show up here; a permission error may only appear in the query history.
SELECT * FROM sys_load_error_detail ORDER BY start_time DESC LIMIT 5;

SELECT query_id, status, error_message
FROM sys_query_history
WHERE query_text LIKE 'COPY users%'
ORDER BY start_time DESC
LIMIT 5;

-- Fix: same COPY with the default role. users was already loaded in Part 1, so empty it first.
TRUNCATE users;

COPY users
FROM 's3://redshift-downloads/tickit/allusers_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';
```

- [ ] **Step 4: Implementar `scripts/lab/sql.py`**

```python
"""SQL file loading, placeholder rendering and statement splitting for the Redshift lab."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from string import Template

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"

# Part number (as in docs/guia_laboratorio_sesion5_redshift.md) -> SQL files, in execution order.
# Parts 4 and 6 both need the external table, so both start with 07_spectrum_setup.sql (idempotent).
PARTS: dict[int, tuple[str, ...]] = {
    1: ("01_ddl.sql", "02_copy.sql"),
    2: ("03_star_schema.sql",),
    3: ("04_analytics.sql",),
    4: ("07_spectrum_setup.sql", "05_athena_vs_redshift.sql"),
    5: ("06_unload.sql",),
    6: ("07_spectrum_setup.sql", "07_spectrum_queries.sql"),
    7: ("08_troubleshooting.sql",),
}

_ENGINE = re.compile(r"^--\s*@engine:\s*(\w+)\s*$")
_EXPECT_ERROR = re.compile(r"^--\s*@expect-error\s*$")


@dataclass(frozen=True)
class Statement:
    sql: str
    engine: str = "redshift"
    expect_error: bool = False


def render(text: str, values: Mapping[str, str]) -> str:
    """Substitute ${name} placeholders. Raises KeyError if a placeholder has no value."""
    return Template(text).substitute(values)


def split_statements(text: str) -> list[Statement]:
    """Split SQL text into statements, honoring quotes, `--` comments and the lab directives.

    Directives are recognised only on their own line, outside a statement:
    `-- @engine: athena` sets the engine for the statements that follow;
    `-- @expect-error` marks only the next statement.
    """
    statements: list[Statement] = []
    engine = "redshift"
    expect_error = False
    buffer: list[str] = []
    in_quote = False

    def flush() -> None:
        nonlocal expect_error
        sql = "".join(buffer).strip()
        buffer.clear()
        if sql:
            statements.append(Statement(sql, engine, expect_error))
            expect_error = False

    for line in text.splitlines():
        if not in_quote and not "".join(buffer).strip():
            engine_match = _ENGINE.match(line.strip())
            if engine_match:
                engine = engine_match.group(1)
                continue
            if _EXPECT_ERROR.match(line.strip()):
                expect_error = True
                continue
        index = 0
        while index < len(line):
            char = line[index]
            if in_quote:
                buffer.append(char)
                if char == "'":
                    in_quote = False
            elif char == "'":
                in_quote = True
                buffer.append(char)
            elif line.startswith("--", index):
                break
            elif char == ";":
                flush()
            else:
                buffer.append(char)
            index += 1
        buffer.append("\n")
    flush()
    return statements


def statements_for_part(part: int, values: Mapping[str, str]) -> list[Statement]:
    """Render and split every file of a part, in order."""
    statements: list[Statement] = []
    for name in PARTS[part]:
        text = render((SQL_DIR / name).read_text(encoding="utf-8"), values)
        statements.extend(split_statements(text))
    return statements
```

- [ ] **Step 5: Tests en verde y lint**

```bash
python -m pytest tests/lab/test_sql.py -v
python scripts/testing/run_ruff_check.py scripts/lab tests/lab
python scripts/testing/run_ruff_format.py scripts/lab tests/lab
```
Expected: `10 passed`; ruff sin errores (el format puede reescribir archivos: volver a correr los tests).

- [ ] **Step 6: Commit**

```bash
git add sql scripts/lab tests/lab
git commit -m "feat(lab): add lab SQL files and the statement splitter" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Sesión AWS y configuración desde Terraform

**Files:**
- Create: `scripts/lab/aws_session.py`, `scripts/lab/config.py`, `tests/lab/test_aws_session.py`, `tests/lab/test_config.py`
- Modify: `tests/aws/aws_session.py` (pasa a reutilizar el helper compartido)

**Interfaces:**
- Consumes: outputs de la raíz de Terraform (Task 7).
- Produces:
  - `scripts/lab/aws_session.py`: `REPO_ROOT: Path`, `DEFAULT_REGION = "us-east-1"`, `load_credentials_file(path: Path | None = None) -> bool`, `get_client(service: str, region: str | None = None)`
  - `scripts/lab/config.py`: `@dataclass(frozen=True) LabConfig(region, workgroup_name, database_name, admin_secret_arn, bucket_name, redshift_role_arn, no_permissions_role_arn, athena_workgroup_name, glue_database_name)` con `sql_values() -> dict[str, str]`; `parse_outputs(raw: str) -> LabConfig`; `load_config(infra_dir: Path = INFRA_DIR) -> LabConfig`

- [ ] **Step 1: Escribir los tests que fallan**

Create `tests/lab/test_aws_session.py`:

```python
import os

from scripts.lab import aws_session


def _isolate(monkeypatch, *names):
    """Start from an unset variable and make monkeypatch remove whatever load_dotenv sets afterwards."""
    for name in names:
        monkeypatch.setenv(name, "placeholder")
        monkeypatch.delenv(name)


def test_credentials_file_is_loaded_into_the_environment(tmp_path, monkeypatch):
    _isolate(monkeypatch, "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
    env_file = tmp_path / ".env.credentials"
    env_file.write_text("AWS_ACCESS_KEY_ID=AKIAFAKEFAKEFAKE\nAWS_SECRET_ACCESS_KEY=fakefake\n", encoding="utf-8")

    assert aws_session.load_credentials_file(env_file) is True
    assert os.environ["AWS_ACCESS_KEY_ID"] == "AKIAFAKEFAKEFAKE"


def test_session_token_is_loaded(tmp_path, monkeypatch):
    _isolate(monkeypatch, "AWS_SESSION_TOKEN")
    env_file = tmp_path / ".env.credentials"
    env_file.write_text("AWS_SESSION_TOKEN=faketoken\n", encoding="utf-8")

    aws_session.load_credentials_file(env_file)

    assert os.environ["AWS_SESSION_TOKEN"] == "faketoken"


def test_real_environment_wins_over_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "from-env")
    env_file = tmp_path / ".env.credentials"
    env_file.write_text("AWS_ACCESS_KEY_ID=from-file\n", encoding="utf-8")

    aws_session.load_credentials_file(env_file)

    assert os.environ["AWS_ACCESS_KEY_ID"] == "from-env"


def test_get_client_uses_tls_verification_and_the_requested_region(monkeypatch):
    captured = {}

    def fake_client(service, **kwargs):
        captured.update(service=service, **kwargs)
        return object()

    monkeypatch.setattr(aws_session.boto3, "client", fake_client)
    monkeypatch.setattr(aws_session, "load_credentials_file", lambda path=None: False)

    aws_session.get_client("athena", "us-east-1")

    assert captured == {"service": "athena", "region_name": "us-east-1"}
    assert "verify" not in captured
```

Create `tests/lab/test_config.py`:

```python
import json

import pytest

from scripts.lab.config import LabConfig, parse_outputs

OUTPUTS = {
    "aws_region": "us-east-1",
    "workgroup_name": "redshift-lab-dev-wg",
    "database_name": "dev",
    "admin_secret_arn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:redshift!x",
    "bucket_name": "redshift-lab-dev-123456789012-lab",
    "redshift_role_arn": "arn:aws:iam::123456789012:role/redshift-lab-dev-redshift-role",
    "no_permissions_role_arn": "arn:aws:iam::123456789012:role/redshift-lab-dev-rol-sin-permisos",
    "athena_workgroup_name": "redshift-lab-dev-wg",
    "glue_database_name": "spectrumdb",
}


def _raw(outputs):
    return json.dumps({k: {"value": v, "type": "string", "sensitive": False} for k, v in outputs.items()})


def test_parse_outputs_builds_the_config():
    config = parse_outputs(_raw(OUTPUTS))
    assert isinstance(config, LabConfig)
    assert config.workgroup_name == "redshift-lab-dev-wg"
    assert config.region == "us-east-1"


def test_sql_values_expose_only_the_documented_placeholders():
    values = parse_outputs(_raw(OUTPUTS)).sql_values()
    assert values == {
        "bucket": OUTPUTS["bucket_name"],
        "glue_database": "spectrumdb",
        "no_permissions_role_arn": OUTPUTS["no_permissions_role_arn"],
        "redshift_role_arn": OUTPUTS["redshift_role_arn"],
    }


def test_missing_outputs_explain_that_the_infra_may_not_be_applied():
    with pytest.raises(ValueError, match="applied"):
        parse_outputs("{}")
```

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `python -m pytest tests/lab/test_aws_session.py tests/lab/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `aws_session.py`**

```python
"""Shared AWS session helper: loads .env.credentials and builds boto3 clients.

boto3's default credential chain is used after the file is loaded, so temporary
credentials (AWS_SESSION_TOKEN) work. TLS verification stays on (see
scripts/testing/check_ssl_regression.py: the Python 3.14 workaround is no longer needed).
"""

from __future__ import annotations

import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGION = "us-east-1"


def load_credentials_file(path: Path | None = None) -> bool:
    """Load .env.credentials into the environment. Variables already set are not overridden."""
    return load_dotenv(path or REPO_ROOT / ".env.credentials")


def get_client(service: str, region: str | None = None):
    load_credentials_file()
    return boto3.client(service, region_name=region or os.environ.get("AWS_DEFAULT_REGION", DEFAULT_REGION))
```

- [ ] **Step 4: Implementar `config.py`**

```python
"""Lab configuration read from `terraform output -json` (no hardcoded environment values)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

INFRA_DIR = Path(__file__).resolve().parents[2] / "infra"


@dataclass(frozen=True)
class LabConfig:
    region: str
    workgroup_name: str
    database_name: str
    admin_secret_arn: str
    bucket_name: str
    redshift_role_arn: str
    no_permissions_role_arn: str
    athena_workgroup_name: str
    glue_database_name: str

    def sql_values(self) -> dict[str, str]:
        """Values for the ${placeholders} used in sql/*.sql."""
        return {
            "bucket": self.bucket_name,
            "glue_database": self.glue_database_name,
            "no_permissions_role_arn": self.no_permissions_role_arn,
            "redshift_role_arn": self.redshift_role_arn,
        }


def parse_outputs(raw: str) -> LabConfig:
    data = json.loads(raw)
    try:
        return LabConfig(
            region=data["aws_region"]["value"],
            workgroup_name=data["workgroup_name"]["value"],
            database_name=data["database_name"]["value"],
            admin_secret_arn=data["admin_secret_arn"]["value"],
            bucket_name=data["bucket_name"]["value"],
            redshift_role_arn=data["redshift_role_arn"]["value"],
            no_permissions_role_arn=data["no_permissions_role_arn"]["value"],
            athena_workgroup_name=data["athena_workgroup_name"]["value"],
            glue_database_name=data["glue_database_name"]["value"],
        )
    except KeyError as exc:
        raise ValueError(f"terraform output is missing {exc}; has the infra been applied?") from exc


def load_config(infra_dir: Path = INFRA_DIR) -> LabConfig:
    result = subprocess.run(
        ["terraform", f"-chdir={infra_dir}", "output", "-json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"terraform output failed: {result.stderr.strip()}")
    return parse_outputs(result.stdout)
```

- [ ] **Step 5: Reutilizar el helper en `tests/aws/aws_session.py`**

Reemplazar el contenido completo por:

```python
"""Client factory for the cloud tests. Thin wrapper over the shared lab helper."""

from scripts.lab.aws_session import get_client

__all__ = ["get_client"]
```

- [ ] **Step 6: Tests en verde, lint y commit**

```bash
python -m pytest tests/lab -v
python scripts/testing/run_ruff_check.py scripts tests
python scripts/testing/run_ruff_format.py scripts tests
git add scripts/lab tests
git commit -m "feat(lab): add shared AWS session helper and terraform-output config" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
Expected: todos los tests de `tests/lab` en verde.

---

### Task 10: Ejecutores, tabla de comparación y CLI `run_lab.py`

**Files:**
- Create: `scripts/lab/redshift.py`, `athena.py`, `runner.py`, `checks.py`, `run_lab.py`
- Create: `tests/lab/test_redshift.py`, `test_athena.py`, `test_runner.py`, `test_checks.py`, `test_run_lab_cli.py`

**Interfaces:**
- Consumes: `LabConfig`, `Statement`, `statements_for_part`, `PARTS`, `get_client`, `load_config`.
- Produces:
  - `scripts/lab/redshift.py`: `@dataclass Result(engine: str, sql: str, status: str, duration_ms: int | None, bytes_scanned: int | None = None, columns: list[str] = [], rows: list[list[str]] = [], error: str | None = None)` con propiedad `ok` (`status == "FINISHED"`); `RedshiftRunner(client, workgroup, database, secret_arn, poll_seconds=1.0, sleep=time.sleep)` con `.run(sql: str) -> Result`
  - `scripts/lab/athena.py`: `AthenaRunner(client, workgroup, database, poll_seconds=1.0, sleep=time.sleep)` con `.run(sql: str) -> Result` (estado `SUCCEEDED` se normaliza a `FINISHED`)
  - `scripts/lab/runner.py`: `LabError(Exception)`; `format_table(columns, rows, limit=10) -> str`; `athena_cost_usd(bytes_scanned: int) -> float`; `format_comparison(results: list[Result]) -> str`; `run_part(part: int, config: LabConfig, runners: Mapping[str, Runner], out=print) -> list[Result]`
  - `scripts/lab/checks.py`: `EXPECTED_COUNTS: dict[str, int]`; `check_counts(runner) -> list[str]` (lista de discrepancias; vacía = OK)

- [ ] **Step 1: Escribir los tests que fallan**

Create `tests/lab/test_redshift.py`:

```python
from scripts.lab.redshift import RedshiftRunner


class FakeDataApi:
    def __init__(self, statuses, has_result=False, records=None, columns=None, duration=2_500_000_000, error=None):
        self._statuses = list(statuses)
        self._has_result = has_result
        self._records = records or []
        self._columns = columns or []
        self._duration = duration
        self._error = error
        self.executed = None

    def execute_statement(self, **kwargs):
        self.executed = kwargs
        return {"Id": "stmt-1"}

    def describe_statement(self, Id):
        status = self._statuses.pop(0)
        described = {"Status": status, "HasResultSet": self._has_result, "Duration": self._duration}
        if self._error and status in ("FAILED", "ABORTED"):
            described["Error"] = self._error
        return described

    def get_statement_result(self, Id, **kwargs):
        return {"ColumnMetadata": [{"name": c} for c in self._columns], "Records": self._records}


def _runner(client):
    return RedshiftRunner(client, "wg", "dev", "arn:secret", poll_seconds=0, sleep=lambda s: None)


def test_run_passes_workgroup_database_and_secret_and_polls_until_finished():
    client = FakeDataApi(["STARTED", "FINISHED"])
    result = _runner(client).run("SELECT 1")

    assert client.executed == {"WorkgroupName": "wg", "Database": "dev", "SecretArn": "arn:secret", "Sql": "SELECT 1"}
    assert result.ok and result.engine == "redshift"
    assert result.duration_ms == 2500


def test_run_returns_rows_and_columns_for_selects():
    records = [[{"longValue": 7}, {"stringValue": "x"}], [{"isNull": True}, {"stringValue": "y"}]]
    client = FakeDataApi(["FINISHED"], has_result=True, records=records, columns=["a", "b"])
    result = _runner(client).run("SELECT a, b FROM t")

    assert result.columns == ["a", "b"]
    assert result.rows == [["7", "x"], ["NULL", "y"]]


def test_run_reports_failures_without_raising():
    client = FakeDataApi(["FAILED"], error="S3ServiceException: Access Denied")
    result = _runner(client).run("COPY ...")

    assert not result.ok
    assert result.error == "S3ServiceException: Access Denied"
```

Create `tests/lab/test_athena.py`:

```python
from scripts.lab.athena import AthenaRunner


class FakeAthena:
    def __init__(self, states, rows=None, stats=None, reason=None):
        self._states = list(states)
        self._rows = rows or []
        self._stats = stats or {}
        self._reason = reason
        self.started = None

    def start_query_execution(self, **kwargs):
        self.started = kwargs
        return {"QueryExecutionId": "q-1"}

    def get_query_execution(self, QueryExecutionId):
        state = self._states.pop(0)
        status = {"State": state}
        if self._reason:
            status["StateChangeReason"] = self._reason
        return {"QueryExecution": {"Status": status, "Statistics": self._stats}}

    def get_query_results(self, QueryExecutionId, **kwargs):
        return {"ResultSet": {"Rows": self._rows}}


def _runner(client):
    return AthenaRunner(client, "wg", "spectrumdb", poll_seconds=0, sleep=lambda s: None)


def test_run_normalizes_succeeded_and_collects_statistics():
    rows = [{"Data": [{"VarCharValue": "dateid"}, {"VarCharValue": "ventas"}]}, {"Data": [{"VarCharValue": "1827"}, {"VarCharValue": "33"}]}]
    client = FakeAthena(["RUNNING", "SUCCEEDED"], rows=rows, stats={"EngineExecutionTimeInMillis": 812, "DataScannedInBytes": 5_000_000})
    result = _runner(client).run("SELECT 1")

    assert client.started["WorkGroup"] == "wg"
    assert client.started["QueryExecutionContext"] == {"Database": "spectrumdb"}
    assert result.ok and result.engine == "athena"
    assert result.duration_ms == 812 and result.bytes_scanned == 5_000_000
    assert result.columns == ["dateid", "ventas"] and result.rows == [["1827", "33"]]


def test_run_reports_failure_reason():
    client = FakeAthena(["FAILED"], reason="SYNTAX_ERROR")
    result = _runner(client).run("SELEC")

    assert not result.ok and result.status == "FAILED" and result.error == "SYNTAX_ERROR"
```

Create `tests/lab/test_runner.py`:

```python
import pytest

from scripts.lab.config import LabConfig
from scripts.lab.redshift import Result
from scripts.lab.runner import LabError, athena_cost_usd, format_comparison, format_table, run_part

CONFIG = LabConfig(
    region="us-east-1",
    workgroup_name="wg",
    database_name="dev",
    admin_secret_arn="arn:secret",
    bucket_name="b",
    redshift_role_arn="arn:aws:iam::123456789012:role/r",
    no_permissions_role_arn="arn:aws:iam::123456789012:role/empty",
    athena_workgroup_name="awg",
    glue_database_name="spectrumdb",
)


class FakeRunner:
    def __init__(self, engine, ok=True, error=None, bytes_scanned=None):
        self.engine, self.ok, self.error, self.bytes_scanned = engine, ok, error, bytes_scanned
        self.ran = []

    def run(self, sql):
        self.ran.append(sql)
        status = "FINISHED" if self.ok else "FAILED"
        return Result(self.engine, sql, status, 100, self.bytes_scanned, ["c"], [["1"]], None if self.ok else self.error)


def test_format_table_aligns_columns_and_limits_rows():
    text = format_table(["a", "bb"], [["1", "x"], ["22", "y"], ["3", "z"]], limit=2)
    assert text.splitlines()[0].split() == ["a", "bb"]
    assert "(1 more rows)" in text


def test_athena_cost_uses_the_10mb_minimum():
    assert athena_cost_usd(1_000_000_000_000) == pytest.approx(5.0)
    assert athena_cost_usd(0) == pytest.approx(10 * 1024**2 / 1e12 * 5)


def test_format_comparison_lists_both_engines():
    results = [Result("athena", "q", "FINISHED", 812, 5_000_000), Result("redshift", "q", "FINISHED", 95)]
    text = format_comparison(results)
    assert "athena" in text and "redshift" in text and "812" in text and "95" in text


def test_run_part_executes_statements_in_order_and_returns_results():
    runners = {"redshift": FakeRunner("redshift"), "athena": FakeRunner("athena")}
    lines = []
    results = run_part(2, CONFIG, runners, out=lines.append)

    assert len(results) == 1 and runners["redshift"].ran[0].startswith("SELECT")
    assert any("SELECT" in line for line in lines)


def test_run_part_raises_on_unexpected_failure():
    runners = {"redshift": FakeRunner("redshift", ok=False, error="boom"), "athena": FakeRunner("athena")}
    with pytest.raises(LabError, match="boom"):
        run_part(2, CONFIG, runners, out=lambda line: None)


def test_expected_error_is_reported_and_execution_continues():
    redshift = FakeRunner("redshift")
    original_run = redshift.run
    outcomes = iter([False] + [True] * 10)

    def run(sql):
        redshift.ok = next(outcomes)
        redshift.error = "S3ServiceException: Access Denied"
        return original_run(sql)

    redshift.run = run
    lines = []
    results = run_part(7, CONFIG, {"redshift": redshift, "athena": FakeRunner("athena")}, out=lines.append)

    assert len(results) == 5
    assert any("Access Denied" in line for line in lines)


def test_expected_error_that_succeeds_raises():
    runners = {"redshift": FakeRunner("redshift", ok=True), "athena": FakeRunner("athena")}
    with pytest.raises(LabError, match="expected to fail"):
        run_part(7, CONFIG, runners, out=lambda line: None)
```

Create `tests/lab/test_checks.py`:

```python
from scripts.lab.checks import EXPECTED_COUNTS, check_counts
from scripts.lab.redshift import Result


class CountRunner:
    def __init__(self, counts):
        self.counts = counts

    def run(self, sql):
        table = sql.split("FROM ")[1].strip()
        return Result("redshift", sql, "FINISHED", 1, rows=[[str(self.counts[table])]])


def test_no_discrepancies_when_counts_match():
    assert check_counts(CountRunner(dict(EXPECTED_COUNTS))) == []


def test_reports_each_mismatch():
    counts = dict(EXPECTED_COUNTS)
    counts["sales"] = 1
    problems = check_counts(CountRunner(counts))
    assert len(problems) == 1 and "sales" in problems[0]


def test_expected_counts_cover_the_seven_tickit_tables():
    assert set(EXPECTED_COUNTS) == {"users", "venue", "category", "date", "event", "listing", "sales"}
```

Create `tests/lab/test_run_lab_cli.py`:

```python
import pytest

from scripts.lab.run_lab import build_parser, selected_parts


def test_all_selects_every_part_in_order():
    assert selected_parts(build_parser().parse_args(["--all"])) == [1, 2, 3, 4, 5, 6, 7]


def test_part_can_be_repeated():
    assert selected_parts(build_parser().parse_args(["--part", "4", "--part", "1"])) == [4, 1]


def test_an_action_is_required():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args([])
    assert exc.value.code == 2


def test_rejects_unknown_parts():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--part", "9"])
```

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `python -m pytest tests/lab -v 2>&1 | tail -15`
Expected: los 5 archivos nuevos fallan por `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `redshift.py`**

```python
"""Redshift Data API runner (one statement per call: CREATE EXTERNAL TABLE cannot run in a transaction)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

_TERMINAL = ("FINISHED", "FAILED", "ABORTED")


@dataclass
class Result:
    engine: str
    sql: str
    status: str
    duration_ms: int | None
    bytes_scanned: int | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "FINISHED"


def _cell(value: dict[str, Any]) -> str:
    if value.get("isNull"):
        return "NULL"
    return str(next(iter(value.values())))


class RedshiftRunner:
    def __init__(self, client, workgroup: str, database: str, secret_arn: str, poll_seconds: float = 1.0, sleep=time.sleep):
        self._client = client
        self._workgroup = workgroup
        self._database = database
        self._secret_arn = secret_arn
        self._poll_seconds = poll_seconds
        self._sleep = sleep

    def run(self, sql: str) -> Result:
        statement_id = self._client.execute_statement(
            WorkgroupName=self._workgroup, Database=self._database, SecretArn=self._secret_arn, Sql=sql
        )["Id"]
        while True:
            described = self._client.describe_statement(Id=statement_id)
            if described["Status"] in _TERMINAL:
                break
            self._sleep(self._poll_seconds)

        nanoseconds = described.get("Duration")
        duration_ms = nanoseconds // 1_000_000 if isinstance(nanoseconds, int) and nanoseconds >= 0 else None
        result = Result("redshift", sql, described["Status"], duration_ms, error=described.get("Error"))
        if result.ok and described.get("HasResultSet"):
            result.columns, result.rows = self._fetch(statement_id)
        return result

    def _fetch(self, statement_id: str) -> tuple[list[str], list[list[str]]]:
        columns: list[str] = []
        rows: list[list[str]] = []
        token: str | None = None
        while True:
            kwargs = {"NextToken": token} if token else {}
            page = self._client.get_statement_result(Id=statement_id, **kwargs)
            columns = columns or [column["name"] for column in page.get("ColumnMetadata", [])]
            rows.extend([_cell(value) for value in record] for record in page.get("Records", []))
            token = page.get("NextToken")
            if not token:
                return columns, rows
```

- [ ] **Step 4: Implementar `athena.py`**

```python
"""Athena runner with the same Result shape as the Redshift runner."""

from __future__ import annotations

import time

from scripts.lab.redshift import Result

_TERMINAL = ("SUCCEEDED", "FAILED", "CANCELLED")


class AthenaRunner:
    def __init__(self, client, workgroup: str, database: str, poll_seconds: float = 1.0, sleep=time.sleep):
        self._client = client
        self._workgroup = workgroup
        self._database = database
        self._poll_seconds = poll_seconds
        self._sleep = sleep

    def run(self, sql: str) -> Result:
        query_id = self._client.start_query_execution(
            QueryString=sql,
            WorkGroup=self._workgroup,
            QueryExecutionContext={"Database": self._database},
        )["QueryExecutionId"]
        while True:
            execution = self._client.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]
            state = execution["Status"]["State"]
            if state in _TERMINAL:
                break
            self._sleep(self._poll_seconds)

        statistics = execution.get("Statistics", {})
        result = Result(
            "athena",
            sql,
            "FINISHED" if state == "SUCCEEDED" else state,
            statistics.get("EngineExecutionTimeInMillis"),
            statistics.get("DataScannedInBytes"),
            error=execution["Status"].get("StateChangeReason"),
        )
        if result.ok:
            result.columns, result.rows = self._fetch(query_id)
        return result

    def _fetch(self, query_id: str) -> tuple[list[str], list[list[str]]]:
        rows: list[list[str]] = []
        token: str | None = None
        first_page = True
        columns: list[str] = []
        while True:
            kwargs = {"NextToken": token} if token else {}
            page = self._client.get_query_results(QueryExecutionId=query_id, **kwargs)
            page_rows = [[cell.get("VarCharValue", "NULL") for cell in row["Data"]] for row in page["ResultSet"]["Rows"]]
            if first_page and page_rows:
                columns, page_rows = page_rows[0], page_rows[1:]
            first_page = False
            rows.extend(page_rows)
            token = page.get("NextToken")
            if not token:
                return columns, rows
```

- [ ] **Step 5: Implementar `runner.py`**

```python
"""Runs one lab part and formats what the student sees."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from scripts.lab.config import LabConfig
from scripts.lab.redshift import Result
from scripts.lab.sql import statements_for_part

ATHENA_MIN_BYTES = 10 * 1024**2
ATHENA_USD_PER_TB = 5.0


class LabError(Exception):
    """A lab statement failed unexpectedly, or an expected failure did not happen."""


class Runner(Protocol):
    def run(self, sql: str) -> Result: ...


def format_table(columns: list[str], rows: list[list[str]], limit: int = 10) -> str:
    shown = rows[:limit]
    widths = [max(len(str(c)) for c in [col, *[row[i] for row in shown]]) for i, col in enumerate(columns)]
    lines = ["  ".join(str(col).ljust(width) for col, width in zip(columns, widths, strict=True))]
    lines += ["  ".join(str(cell).ljust(width) for cell, width in zip(row, widths, strict=True)) for row in shown]
    if len(rows) > limit:
        lines.append(f"({len(rows) - limit} more rows)")
    return "\n".join(lines)


def athena_cost_usd(bytes_scanned: int) -> float:
    """Approximate Athena cost: $5 per TB scanned, with a 10 MB minimum per query."""
    return max(bytes_scanned, ATHENA_MIN_BYTES) / 1e12 * ATHENA_USD_PER_TB


def format_comparison(results: list[Result]) -> str:
    lines = [f"{'engine':<10} {'time (ms)':>10} {'scanned (bytes)':>16} {'est. cost (USD)':>16}"]
    for result in results:
        scanned = "-" if result.bytes_scanned is None else f"{result.bytes_scanned:,}"
        cost = "workgroup RPUs" if result.engine == "redshift" else f"~{athena_cost_usd(result.bytes_scanned or 0):.6f}"
        lines.append(f"{result.engine:<10} {result.duration_ms if result.duration_ms is not None else '-':>10} {scanned:>16} {cost:>16}")
    return "\n".join(lines)


def run_part(part: int, config: LabConfig, runners: Mapping[str, Runner], out: Callable[[str], None] = print) -> list[Result]:
    results: list[Result] = []
    for statement in statements_for_part(part, config.sql_values()):
        out(f"\n-- [{statement.engine}]\n{statement.sql};")
        result = runners[statement.engine].run(statement.sql)
        if statement.expect_error:
            if result.ok:
                raise LabError(f"statement was expected to fail but succeeded: {statement.sql[:80]}")
            out(f"Expected error: {result.error}")
        elif not result.ok:
            raise LabError(f"[{statement.engine}] {result.status}: {result.error}\n{statement.sql}")
        elif result.rows:
            out(format_table(result.columns, result.rows))
        results.append(result)
    return results
```

- [ ] **Step 6: Implementar `checks.py`**

```python
"""Expected TICKIT row counts, used by `run_lab.py --check`."""

from __future__ import annotations

# Source: AWS TICKIT sample database documentation. Not re-verified against a live load:
# confirm on the first deployment (Task 14) and fix here if AWS changed the dataset.
EXPECTED_COUNTS: dict[str, int] = {
    "users": 49990,
    "venue": 202,
    "category": 11,
    "date": 365,
    "event": 8798,
    "listing": 192497,
    "sales": 172456,
}


def check_counts(runner) -> list[str]:
    """Return one message per table whose row count differs from the expected one."""
    problems: list[str] = []
    for table, expected in EXPECTED_COUNTS.items():
        result = runner.run(f"SELECT COUNT(*) FROM {table}")
        if not result.ok:
            problems.append(f"{table}: query failed: {result.error}")
            continue
        actual = int(result.rows[0][0])
        if actual != expected:
            problems.append(f"{table}: expected {expected}, found {actual}")
    return problems
```

- [ ] **Step 7: Implementar `run_lab.py`**

```python
"""Run the Redshift lab SQL against the deployed infrastructure.

Usage:
  python scripts/lab/run_lab.py --part 1            # one part (repeatable)
  python scripts/lab/run_lab.py --all               # parts 1-7
  python scripts/lab/run_lab.py --check             # validate TICKIT row counts

Reads the deployment from `terraform output -json` (run it after `terraform apply`).
Credentials come from .env.credentials or the environment.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.lab.athena import AthenaRunner  # noqa: E402
from scripts.lab.aws_session import get_client  # noqa: E402
from scripts.lab.checks import check_counts  # noqa: E402
from scripts.lab.config import load_config  # noqa: E402
from scripts.lab.redshift import RedshiftRunner  # noqa: E402
from scripts.lab.runner import LabError, format_comparison, run_part  # noqa: E402
from scripts.lab.sql import PARTS  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Redshift lab parts.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--part", type=int, choices=sorted(PARTS), action="append", help="Part number (repeatable).")
    group.add_argument("--all", action="store_true", help="Run every part in order.")
    group.add_argument("--check", action="store_true", help="Validate the loaded TICKIT row counts.")
    return parser


def selected_parts(args: argparse.Namespace) -> list[int]:
    return sorted(PARTS) if args.all else list(args.part)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config()
    runners = {
        "redshift": RedshiftRunner(
            get_client("redshift-data", config.region), config.workgroup_name, config.database_name, config.admin_secret_arn
        ),
        "athena": AthenaRunner(get_client("athena", config.region), config.athena_workgroup_name, config.glue_database_name),
    }

    if args.check:
        problems = check_counts(runners["redshift"])
        print("\n".join(problems) if problems else "OK: all TICKIT tables have the expected row counts.")
        return 1 if problems else 0

    try:
        for part in selected_parts(args):
            print(f"\n===== Part {part} =====")
            results = run_part(part, config, runners)
            if part == 4:
                print("\n" + format_comparison([r for r in results if r.sql.startswith("SELECT")]))
    except LabError as exc:
        print(f"\nLAB ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Tests en verde, lint y commit**

```bash
python -m pytest tests/lab -v 2>&1 | tail -8
python scripts/testing/run_ruff_check.py scripts tests
python scripts/testing/run_ruff_format.py scripts tests
python -m pytest tests/lab -q
git add scripts/lab tests/lab
git commit -m "feat(lab): add Redshift/Athena runners, comparison table and run_lab CLI" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
Expected: todos los tests de `tests/lab` en verde tras el formateo.

---

### Task 11: Tests `cloud` (`tests/aws/`)

**Files:**
- Create: `tests/aws/conftest.py`, `tests/aws/test_infra.py`, `tests/aws/test_lab_data.py`

**Interfaces:**
- Consumes: `load_config`, `get_client`, `check_counts`, `RedshiftRunner`.
- Produces: fixture `lab_config` (se salta si no hay credenciales o infra) y pruebas marcadas `cloud`.

- [ ] **Step 1: Escribir las pruebas**

`tests/aws/conftest.py`:

```python
import pytest

from scripts.lab.aws_session import get_client
from scripts.lab.config import load_config


@pytest.fixture(scope="session")
def lab_config():
    """Deployment settings from terraform output. Skips when there are no credentials or no deployment."""
    try:
        get_client("sts", "us-east-1").get_caller_identity()
    except Exception as exc:  # noqa: BLE001 - any failure means "no usable credentials"
        pytest.skip(f"no usable AWS credentials: {exc}")
    try:
        return load_config()
    except (RuntimeError, ValueError) as exc:
        pytest.skip(f"lab is not deployed: {exc}")
```

`tests/aws/test_infra.py`:

```python
import json

import pytest

from scripts.lab.aws_session import get_client

pytestmark = pytest.mark.cloud


def test_workgroup_is_private_and_small(lab_config):
    workgroup = get_client("redshift-serverless", lab_config.region).get_workgroup(workgroupName=lab_config.workgroup_name)["workgroup"]
    assert workgroup["publiclyAccessible"] is False
    assert workgroup["baseCapacity"] == 4


def test_usage_limit_is_daily_and_deactivates(lab_config):
    client = get_client("redshift-serverless", lab_config.region)
    arn = client.get_workgroup(workgroupName=lab_config.workgroup_name)["workgroup"]["workgroupArn"]
    limits = client.list_usage_limits(resourceArn=arn)["usageLimits"]
    assert any(limit["period"] == "daily" and limit["breachAction"] == "deactivate" for limit in limits)


def test_lab_bucket_blocks_public_access(lab_config):
    config = get_client("s3", lab_config.region).get_public_access_block(Bucket=lab_config.bucket_name)["PublicAccessBlockConfiguration"]
    assert all(config.values())


def test_redshift_role_trusts_both_service_principals(lab_config):
    name = lab_config.redshift_role_arn.rsplit("/", 1)[1]
    document = get_client("iam", lab_config.region).get_role(RoleName=name)["Role"]["AssumeRolePolicyDocument"]
    principals = {p for statement in document["Statement"] for p in _as_list(statement["Principal"]["Service"])}
    assert principals == {"redshift.amazonaws.com", "redshift-serverless.amazonaws.com"}


def test_connection_log_group_has_retention(lab_config):
    namespace = lab_config.workgroup_name.removesuffix("-wg") + "-ns"
    groups = get_client("logs", lab_config.region).describe_log_groups(logGroupNamePrefix=f"/aws/redshift/{namespace}/")["logGroups"]
    assert groups, "expected the Terraform-managed log group"
    assert all(group.get("retentionInDays") == 7 for group in groups), json.dumps([g["logGroupName"] for g in groups])


def _as_list(value):
    return value if isinstance(value, list) else [value]
```

`tests/aws/test_lab_data.py`:

```python
import pytest

from scripts.lab.aws_session import get_client
from scripts.lab.checks import check_counts
from scripts.lab.redshift import RedshiftRunner

pytestmark = pytest.mark.cloud


def test_tickit_tables_have_the_expected_counts(lab_config):
    runner = RedshiftRunner(
        get_client("redshift-data", lab_config.region), lab_config.workgroup_name, lab_config.database_name, lab_config.admin_secret_arn
    )
    assert check_counts(runner) == []
```

- [ ] **Step 2: Verificar que se saltan sin credenciales/infra y que el resto sigue verde**

Run: `python -m pytest tests/aws -v 2>&1 | tail -12` y `python scripts/testing/run_pytest.py 2>&1 | tail -6`
Expected: tests de `tests/aws` en `SKIPPED` (sin infra desplegada) — no `ERROR`; la suite no-cloud sigue verde.

- [ ] **Step 3: Lint y commit**

```bash
python scripts/testing/run_ruff_check.py tests
python scripts/testing/run_ruff_format.py tests
git add tests/aws
git commit -m "test(aws): add cloud validation tests for the deployed lab" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Verificador de teardown

**Files:**
- Create: `scripts/lab/teardown.py`, `scripts/lab/verify_teardown.py`, `tests/lab/test_teardown.py`

**Interfaces:**
- Consumes: `get_client`.
- Produces:
  - `scripts/lab/teardown.py`: `find_residuals(clients: Mapping[str, Any], *, prefix: str, project: str, glue_database: str) -> list[str]` (vacía = limpio). Claves de `clients`: `redshift-serverless`, `s3`, `iam`, `logs`, `ec2`, `glue`, `athena`, `secretsmanager`.
  - `scripts/lab/verify_teardown.py`: CLI `--prefix` (default `redshift-lab`), `--project` (default `redshift-lab`), `--glue-database` (default `spectrumdb`), `--region` (default `us-east-1`); `main(argv=None, clients=None) -> int` (0 = limpio, 1 = residuos).

- [ ] **Step 1: Escribir los tests que fallan**

Create `tests/lab/test_teardown.py`:

```python
from scripts.lab.teardown import find_residuals
from scripts.lab.verify_teardown import main


class FakePaginator:
    def __init__(self, pages, calls, operation):
        self._pages, self._calls, self._operation = pages, calls, operation

    def paginate(self, **kwargs):
        self._calls.append((self._operation, kwargs))
        return iter(self._pages)


class FakeClient:
    def __init__(self, pages=None, buckets=None):
        self._pages = pages or {}
        self._buckets = buckets or []
        self.calls = []

    def get_paginator(self, operation):
        return FakePaginator(self._pages.get(operation, [{}]), self.calls, operation)

    def list_buckets(self):
        return {"Buckets": [{"Name": name} for name in self._buckets]}


def clean_clients():
    return {
        name: FakeClient()
        for name in ("redshift-serverless", "s3", "iam", "logs", "ec2", "glue", "athena", "secretsmanager")
    }


def _find(clients):
    return find_residuals(clients, prefix="redshift-lab", project="redshift-lab", glue_database="spectrumdb")


def test_find_residuals_is_empty_when_everything_is_gone():
    assert _find(clean_clients()) == []


def test_find_residuals_reports_each_leftover_with_its_service():
    clients = clean_clients()
    clients["redshift-serverless"] = FakeClient(
        pages={
            "list_workgroups": [{"workgroups": [{"workgroupName": "redshift-lab-dev-wg"}, {"workgroupName": "other"}]}],
            "list_namespaces": [{"namespaces": [{"namespaceName": "redshift-lab-dev-ns"}]}],
            "list_snapshots": [{"snapshots": [{"snapshotName": "manual-1", "namespaceName": "redshift-lab-dev-ns"}]}],
        }
    )
    clients["s3"] = FakeClient(buckets=["redshift-lab-dev-123456789012-lab", "unrelated-bucket"])
    clients["iam"] = FakeClient(pages={"list_roles": [{"Roles": [{"RoleName": "redshift-lab-dev-redshift-role"}]}]})
    clients["logs"] = FakeClient(pages={"describe_log_groups": [{"logGroups": [{"logGroupName": "/aws/redshift/redshift-lab-dev-ns/connectionlog"}]}]})
    clients["glue"] = FakeClient(pages={"get_databases": [{"DatabaseList": [{"Name": "spectrumdb"}, {"Name": "default"}]}]})
    clients["athena"] = FakeClient(pages={"list_work_groups": [{"WorkGroups": [{"Name": "primary"}, {"Name": "redshift-lab-dev-wg"}]}]})
    clients["secretsmanager"] = FakeClient(pages={"list_secrets": [{"SecretList": [{"Name": "redshift!redshift-lab-dev-ns-awsuser"}]}]})
    clients["ec2"] = FakeClient(pages={"describe_vpcs": [{"Vpcs": [{"VpcId": "vpc-123"}]}]})

    residuals = _find(clients)
    text = "\n".join(residuals)

    assert len(residuals) == 10
    for expected in ("workgroup", "namespace", "snapshot", "bucket", "role", "log group", "glue database", "athena", "secret", "vpc"):
        assert expected in text.lower(), expected
    assert "other" not in text and "unrelated-bucket" not in text and "primary" not in text


def test_vpc_lookup_uses_project_tag_filter():
    clients = clean_clients()
    _find(clients)
    operation, kwargs = clients["ec2"].calls[0]
    assert operation == "describe_vpcs"
    assert kwargs["Filters"] == [{"Name": "tag:Project", "Values": ["redshift-lab"]}]


def test_main_exit_code_reflects_residuals(capsys):
    assert main(["--region", "us-east-1"], clients=clean_clients()) == 0
    assert "OK" in capsys.readouterr().out

    dirty = clean_clients()
    dirty["s3"] = FakeClient(buckets=["redshift-lab-dev-123456789012-lab"])
    assert main(["--region", "us-east-1"], clients=dirty) == 1
    assert "bucket" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `python -m pytest tests/lab/test_teardown.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `teardown.py`**

```python
"""Read-only search for resources that survive `terraform destroy`.

Everything is matched by name prefix or by the Project tag, never by Terraform state, so it still
works if terraform.tfstate was lost.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _paginate(client, operation: str, key: str, **kwargs) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in client.get_paginator(operation).paginate(**kwargs):
        items.extend(page.get(key, []))
    return items


def find_residuals(clients: Mapping[str, Any], *, prefix: str, project: str, glue_database: str) -> list[str]:
    residuals: list[str] = []

    serverless = clients["redshift-serverless"]
    residuals += [
        f"redshift-serverless workgroup: {wg['workgroupName']}"
        for wg in _paginate(serverless, "list_workgroups", "workgroups")
        if wg["workgroupName"].startswith(prefix)
    ]
    residuals += [
        f"redshift-serverless namespace: {ns['namespaceName']}"
        for ns in _paginate(serverless, "list_namespaces", "namespaces")
        if ns["namespaceName"].startswith(prefix)
    ]
    residuals += [
        f"redshift-serverless snapshot (billed): {snap['snapshotName']}"
        for snap in _paginate(serverless, "list_snapshots", "snapshots")
        if snap.get("namespaceName", "").startswith(prefix)
    ]

    residuals += [
        f"s3 bucket: {bucket['Name']}"
        for bucket in clients["s3"].list_buckets()["Buckets"]
        if bucket["Name"].startswith(prefix) and bucket["Name"].endswith("-lab")
    ]
    residuals += [
        f"iam role: {role['RoleName']}"
        for role in _paginate(clients["iam"], "list_roles", "Roles")
        if role["RoleName"].startswith(prefix)
    ]
    residuals += [
        f"cloudwatch log group: {group['logGroupName']}"
        for group in _paginate(clients["logs"], "describe_log_groups", "logGroups", logGroupNamePrefix=f"/aws/redshift/{prefix}")
    ]
    residuals += [
        f"vpc (tag Project={project}): {vpc['VpcId']}"
        for vpc in _paginate(clients["ec2"], "describe_vpcs", "Vpcs", Filters=[{"Name": "tag:Project", "Values": [project]}])
    ]
    residuals += [
        f"glue database: {db['Name']}"
        for db in _paginate(clients["glue"], "get_databases", "DatabaseList")
        if db["Name"] == glue_database
    ]
    residuals += [
        f"athena workgroup: {wg['Name']}"
        for wg in _paginate(clients["athena"], "list_work_groups", "WorkGroups")
        if wg["Name"].startswith(prefix)
    ]
    # Secrets already scheduled for deletion are excluded by list_secrets (IncludePlannedDeletion defaults to false).
    residuals += [
        f"secrets manager secret: {secret['Name']}"
        for secret in _paginate(
            clients["secretsmanager"], "list_secrets", "SecretList", Filters=[{"Key": "name", "Values": [f"redshift!{prefix}"]}]
        )
    ]
    return residuals
```

- [ ] **Step 4: Implementar `verify_teardown.py`**

```python
"""Verify that `terraform destroy` left nothing behind (read-only).

Usage:
  python scripts/lab/verify_teardown.py [--prefix redshift-lab] [--project redshift-lab]
                                        [--glue-database spectrumdb] [--region us-east-1]

Exit code 0 = clean, 1 = residual resources were found (they are listed).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.lab.aws_session import get_client  # noqa: E402
from scripts.lab.teardown import find_residuals  # noqa: E402

SERVICES = ("redshift-serverless", "s3", "iam", "logs", "ec2", "glue", "athena", "secretsmanager")


def main(argv: list[str] | None = None, clients=None) -> int:
    parser = argparse.ArgumentParser(description="Look for resources left after terraform destroy.")
    parser.add_argument("--prefix", default="redshift-lab", help="Name prefix (project_name) of the lab resources.")
    parser.add_argument("--project", default="redshift-lab", help="Value of the Project tag.")
    parser.add_argument("--glue-database", default="spectrumdb")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args(argv)

    clients = clients or {service: get_client(service, args.region) for service in SERVICES}
    residuals = find_residuals(clients, prefix=args.prefix, project=args.project, glue_database=args.glue_database)

    if not residuals:
        print("OK: no residual lab resources found.")
        return 0
    print("Residual resources found (delete them or run `terraform destroy` again):")
    print("\n".join(f"  - {item}" for item in residuals))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Tests en verde, lint y commit**

```bash
python -m pytest tests/lab/test_teardown.py -v
python scripts/testing/run_ruff_check.py scripts tests
python scripts/testing/run_ruff_format.py scripts tests
python -m pytest tests/lab -q
git add scripts/lab tests/lab
git commit -m "feat(lab): add read-only teardown verifier" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
Expected: `4 passed` en el archivo nuevo; `tests/lab` completo en verde.

---

### Task 13: README, guía corregida y spec sincronizado

**Files:**
- Create: `README.md`
- Modify: `docs/guia_laboratorio_sesion5_redshift.md`, `docs/specs/2026-09-30-redshift-lab-design.md`

**Interfaces:**
- Consumes: nombres y comandos de las Tasks 7–12.
- Produces: documentación ejecutable de punta a punta.

- [ ] **Step 1: Escribir `README.md`**

```markdown
# Laboratorio Redshift — Sesión 5

Laboratorio de Amazon Redshift Serverless sobre el dataset TICKIT. Toda la infraestructura
se crea y se destruye con Terraform. Guion de la demo: [docs/guia_laboratorio_sesion5_redshift.md](docs/guia_laboratorio_sesion5_redshift.md).

## 0. Prerrequisitos

- Cuenta AWS **propia de sandbox**. La identidad de tus credenciales debe poder crear y leer todos los
  recursos del lab (en una cuenta sandbox, lo más simple es `AdministratorAccess`).
- Región **us-east-1** (el dataset público TICKIT vive ahí).
- Terraform ≥ 1.7, [uv](https://docs.astral.sh/uv/) y Git Bash.
- Credenciales: copia `.env.example` a `.env.credentials` y completa `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY` (y `AWS_SESSION_TOKEN` si son temporales). Ese archivo está en `.gitignore`: **nunca lo subas**.
- `uv sync` (instala boto3 y las herramientas de test).

## 1. Qué se crea y cuánto cuesta

VPC propia (sin NAT), un bucket S3, una base de Glue, dos roles IAM, un namespace y workgroup de
Redshift Serverless (4 RPUs), un workgroup de Athena y un log group.

- **Redshift Serverless solo factura compute mientras corren consultas** (por segundo) más el almacenamiento.
- Además existe un tope diario de 16 RPU-horas: al alcanzarlo se desactivan las consultas.
- Si olvidas destruir el lab pagas almacenamiento (mínimo) y el secret de Secrets Manager. Aun así: **destruye al terminar**.

## 2. Desplegar

```bash
set -a; . ./.env.credentials; set +a      # Terraform no lee archivos .env: se cargan en la sesión
cp infra/terraform.tfvars.example infra/terraform.tfvars
terraform -chdir=infra init
terraform -chdir=infra plan
terraform -chdir=infra apply
```

Si `apply` rechaza las dos subnets, pon `availability_zone_count = 3` en `infra/terraform.tfvars`.

## 3. Ejecutar el lab

```bash
python scripts/lab/run_lab.py --part 1      # COPY: S3 -> Redshift (repite --part N para cada parte)
python scripts/lab/run_lab.py --all         # o todas las partes (1-7)
python scripts/lab/run_lab.py --check       # valida los conteos de TICKIT
```

| Parte | Qué muestra |
|---|---|
| 1 | Crear tablas y cargar con COPY |
| 2 | Star schema con datos reales |
| 3 | Consulta analítica agregada |
| 4 | Athena vs. Redshift (tiempo, bytes escaneados y costo estimado) |
| 5 | UNLOAD a S3 en Parquet particionado |
| 6 | Spectrum: consultar S3 sin cargar |
| 7 | Troubleshooting: COPY con un rol sin permisos |

El SQL de cada parte está en `sql/`: puedes leerlo o pegarlo en Query Editor v2
(reemplaza `${bucket}`, `${glue_database}` y `${no_permissions_role_arn}` por los valores de
`terraform -chdir=infra output`).

## 4. Destruir (siempre al terminar)

```bash
set -a; . ./.env.credentials; set +a
terraform -chdir=infra destroy
python scripts/lab/verify_teardown.py        # debe imprimir OK
```

## 5. Si algo falla

- **`destroy` falla por subnets o interfaces de red** (`DependencyViolation`): espera unos minutos y repite
  `terraform -chdir=infra destroy`. Es idempotente.
- **`verify_teardown.py` lista residuos:** repite el destroy; si persisten, bórralos a mano (la salida indica servicio y nombre).
- **Snapshots manuales** creados desde la consola sobreviven al destroy y se facturan: bórralos.
- **Nunca borres `terraform.tfstate`**: sin él Terraform no sabe qué destruir. Si se perdió, `verify_teardown.py`
  encuentra los recursos por prefijo y por tag.
```

- [ ] **Step 2: Corregir la guía (`docs/guia_laboratorio_sesion5_redshift.md`)**

Aplicar con Edit, en este orden:

1. **Sección 0.1:** reemplazar el bloque de los dos comandos `aws redshift-serverless create-namespace/create-workgroup` y el párrafo "`base-capacity 8` RPUs es el mínimo…" por: "El lab se despliega con Terraform (ver [README](../README.md#2-desplegar)): `terraform -chdir=infra apply` crea el namespace y el workgroup (**4 RPUs**, el mínimo actual en us-east-1 y suficiente para TICKIT), sin contraseñas en texto plano: la contraseña de admin la genera y guarda Secrets Manager."
2. **Sección 0.2:** reemplazar el contenido por: "El rol IAM lo crea Terraform y queda como **rol por defecto** del namespace, por eso el SQL usa `IAM_ROLE DEFAULT` y no lleva ARNs. Además se crea `rol-sin-permisos` para la Parte 7."
3. **Sección 0.3:** dejar solo la opción A (región `us-east-1`, validada por Terraform) y eliminar la opción B.
4. **Sección 0.4:** añadir que Query Editor v2 se conecta con la opción **AWS Secrets Manager** (secret `admin_secret_arn`, visible en `terraform -chdir=infra output admin_secret_arn`) en vez de usuario y contraseña.
5. **Partes 1, 5 y 6:** reemplazar cada `IAM_ROLE 'arn:aws:iam::<aws-account-id>:role/<tu-rol-redshift>'` por `IAM_ROLE DEFAULT`; en la Parte 6.1 quitar `CREATE EXTERNAL DATABASE IF NOT EXISTS` (la base la crea Terraform) y usar `DATABASE '<glue_database>'` (por defecto `spectrumdb`) más `CREATE EXTERNAL SCHEMA IF NOT EXISTS`; en la Parte 5 reemplazar `<tu-bucket>` por el output `bucket_name`.
6. **Parte 4.1:** sustituir el texto por: "La tabla externa `spectrumdb.sales` se crea con `sql/07_spectrum_setup.sql` (la misma de la Parte 6) y Athena la lee desde el Glue Data Catalog."
7. **Parte 4.2:** reemplazar ambas consultas por las de `sql/05_athena_vs_redshift.sql` (ambas usan solo columnas de `sales`: `dateid`, `COUNT(*)`, `SUM(pricepaid)`). Añadir la nota: "La consulta anterior de Athena hacía `GROUP BY catgroup` sobre `sales`, columna que esa tabla no tiene."
8. **Parte 7.2:** añadir, tras `sys_load_error_detail`, la consulta a `sys_query_history` de `sql/08_troubleshooting.sql`, con la nota: "un error de permisos puede aparecer solo en el historial de consultas". En 7.3 añadir `TRUNCATE users;` antes de repetir el COPY.
9. **Checklist de cierre:** añadir "`terraform destroy` ejecutado y `verify_teardown.py` imprime OK".
10. **Nueva sección 'Automatización':** "Cada parte se puede ejecutar con `python scripts/lab/run_lab.py --part N`."

- [ ] **Step 3: Sincronizar el spec con lo implementado**

En `docs/specs/2026-09-30-redshift-lab-design.md`, sección "SQL en `sql/`": reemplazar la lista de archivos por `01_ddl.sql`, `02_copy.sql`, `03_star_schema.sql`, `04_analytics.sql`, `05_athena_vs_redshift.sql`, `06_unload.sql`, `07_spectrum_setup.sql`, `07_spectrum_queries.sql`, `08_troubleshooting.sql`, y añadir la frase: "Las Partes 4 y 6 ejecutan primero `07_spectrum_setup.sql` (idempotente) porque ambas necesitan la tabla externa." En la sección 2, fila `budget`: indicar "el Budget de la plantilla (sin su SNS, que nunca se usaba, y con el filtro de tag corregido)". En "Riesgos abiertos de la sección 1", sustituir el bullet de argumentos del provider por: "Verificado (2026-09-30): `manage_admin_password`, `default_iam_role_arn`, `log_exports`, `max_capacity`, `usage_limit` (`deactivate`). Conflicto abierto: la doc del provider exige 3 subnets en 3 AZs; la de AWS dice 2 sin EVR. Fallback: `availability_zone_count = 3`." Añadir el hallazgo: "El log group real es `/aws/redshift/<namespace>/<log_type>`; se crea en Terraform antes del namespace."

- [ ] **Step 4: Verificar enlaces y commit**

```bash
python -c "import pathlib,re; t=pathlib.Path('README.md').read_text(encoding='utf-8'); [print(m) for m in re.findall(r'\]\(([^)#]+)', t) if not pathlib.Path(m).exists()]"
git add README.md docs
git commit -m "docs: add README, fix the lab guide for Terraform and sync the spec" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
Expected: el one-liner no imprime rutas (todos los enlaces locales existen).

---

### Task 14: Primer despliegue real (con aprobación de Ricardo)

**Este es el único paso que gasta dinero. Ninguna acción de esta tarea se ejecuta sin la aprobación explícita de Ricardo.** `apply` y `destroy` están en `deny`: los ejecuta Ricardo, o Claude tras su autorización expresa en ese momento. Requiere credenciales vigentes en `.env.credentials` (las actuales del entorno fallan con `InvalidClientTokenId`).

**Files:**
- Modify: `docs/specs/2026-09-30-redshift-lab-design.md` (registrar resultados), posibles ajustes en `sql/`, `scripts/lab/checks.py`, `infra/`.

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: riesgos abiertos del spec cerrados con evidencia.

- [ ] **Step 1: Comprobar credenciales y plan**

```bash
set -a; . ./.env.credentials; set +a
aws sts get-caller-identity
terraform -chdir=infra init
terraform -chdir=infra plan -out=tfplan
```
Expected: `get-caller-identity` devuelve la cuenta (sin `InvalidClientTokenId`); `Plan: 20 to add, 0 to change, 0 to destroy.` **Mostrar el diff de IAM del plan a Ricardo** (validación de roles antes de aplicar).

- [ ] **Step 2: Apply (aprobación explícita de Ricardo)**

Run: `terraform -chdir=infra apply tfplan`
Expected: `Apply complete! Resources: 20 added`. **Si falla por subnets** ("at least three subnets"): poner `availability_zone_count = 3` en `infra/terraform.tfvars`, `terraform -chdir=infra destroy` (recursos parciales), volver a Step 1 y registrar el hallazgo.

- [ ] **Step 3: Partes 1–3 y validación de conteos**

```bash
python scripts/lab/run_lab.py --part 1
python scripts/lab/run_lab.py --part 2
python scripts/lab/run_lab.py --part 3
python scripts/lab/run_lab.py --check
```
Expected: COPY de las 7 tablas sin error; `--check` imprime `OK`. **Si alguna cuenta difiere**, corregir `EXPECTED_COUNTS` en `scripts/lab/checks.py` con el valor real observado y registrar que la fuente era incorrecta.

- [ ] **Step 4: Smoke test de Spectrum sin EVR y Parte 4**

```bash
python scripts/lab/run_lab.py --part 6
python scripts/lab/run_lab.py --part 4
```
Expected: `SELECT COUNT(*) FROM spectrum.sales` devuelve un número; la Parte 4 imprime la tabla de comparación con ambos motores.
- Si Spectrum falla: poner `enable_enhanced_vpc_routing = true` (fuerza 3 AZs y crea los endpoints), volver a aplicar con aprobación y repetir.
- Si Athena no lee la tabla creada por Redshift: registrar el error exacto y ajustar el SQL de `05_athena_vs_redshift.sql`.

- [ ] **Step 5: UNLOAD y troubleshooting**

```bash
python scripts/lab/run_lab.py --part 5
python scripts/lab/run_lab.py --part 7
```
Expected: UNLOAD escribe Parquet bajo `s3://<bucket>/gold/ventas_agregadas/`; la Parte 7 muestra `Expected error: ... Access Denied` y termina repoblando `users`.
- Si UNLOAD rechaza `IAM_ROLE DEFAULT`: cambiar en `sql/06_unload.sql` a `IAM_ROLE '${redshift_role_arn}'` (el placeholder ya existe) y repetir.
- Anotar si `sys_load_error_detail` o `sys_query_history` muestran el error y si los nombres de columna son correctos.

- [ ] **Step 6: Tests cloud**

Run: `python -m pytest tests/aws -v`
Expected: todos `PASSED`.

- [ ] **Step 7: Destroy y verificación (aprobación explícita de Ricardo)**

```bash
terraform -chdir=infra destroy
python scripts/lab/verify_teardown.py
```
Expected: `Destroy complete!` y `OK: no residual lab resources found.` Si `verify_teardown.py` lista un secret `redshift!…` o un log group: anotar su nombre exacto y ajustar `teardown.py` (el patrón del secret de Secrets Manager no está confirmado). Si el destroy falla por `DependencyViolation`, repetir el destroy y registrar el tiempo de espera.

- [ ] **Step 8: Registrar resultados y commit**

Editar `docs/specs/2026-09-30-redshift-lab-design.md`: convertir cada riesgo abierto en un hecho con su resultado (Spectrum sin EVR, 2 vs 3 subnets, `IAM_ROLE DEFAULT` en UNLOAD, lectura de Athena, conteos TICKIT, nombre del secret, tiempo de destroy). Luego:

```bash
git add -A
git commit -m "chore: record first deployment results and adjust the lab accordingly" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Auto-revisión del plan

- **Cobertura del spec:** decisiones 1–10 → Tasks 3–7 (infra), 8–10 (SQL/runner), 12 (teardown), 2 (plantilla), 9 y README (credenciales); sección 3 del spec (ADR, gates, orden de destrucción, riesgos) → Tasks 1, 5, 14 y README; sección 5 (correcciones a la guía) → Task 13; limpieza y acoplamientos con `scripts/` → Task 2; riesgos abiertos → Task 14.
- **Desviaciones del spec (a revisar por Ricardo):** (a) `budget` sin SNS y con el filtro de tag corregido; (b) un solo log group exportado (`connectionlog`) para cumplir literalmente los outputs `log_group_name/arn`; (c) `07_spectrum_setup.sql` y `07_spectrum_queries.sql` en lugar de un único `07_spectrum.sql`, porque la Parte 4 necesita la tabla externa antes de la Parte 6; (d) variable `availability_zone_names` extra, por el riesgo de AZs no soportadas; (e) el rol vacío se asocia al namespace (sin eso el error de la Parte 7 no sería de permisos S3).
- **Consistencia de nombres:** `LabConfig`, `Result`, `Statement`, `PARTS`, `statements_for_part`, `run_part`, `find_residuals` se definen una vez y se usan con la misma firma; los outputs de la raíz coinciden con `parse_outputs`.
- **Sin placeholders:** los valores marcados como no verificados (conteos TICKIT, nombre del secret, columnas de `sys_query_history`) son riesgos explícitos con paso de verificación en Task 14, no huecos.
