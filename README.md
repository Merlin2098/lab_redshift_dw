# Laboratorio Redshift — Sesión 5

Laboratorio de Amazon Redshift Serverless sobre el dataset TICKIT. Toda la infraestructura
se crea y se destruye con Terraform. Guion de la demo: [docs/guia_laboratorio_sesion5_redshift.md](docs/guia_laboratorio_sesion5_redshift.md).

Dependencias entre los módulos de Terraform y las herramientas: [docs/architecture/architecture.svg](docs/architecture/architecture.svg)
(fuente: [architecture.dot](docs/architecture/architecture.dot)).

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
uv run python scripts/lab/run_lab.py --part 1      # COPY: S3 -> Redshift (repite --part N para cada parte)
uv run python scripts/lab/run_lab.py --all         # o todas las partes (1-7)
uv run python scripts/lab/run_lab.py --check       # valida los conteos de TICKIT
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
uv run python scripts/lab/verify_teardown.py        # debe imprimir OK
```

El verificador toma `project_name` y `glue_database_name` de `infra/terraform.tfvars` (si existe) y muestra
qué prefijo está revisando; si cambiaste esos valores sin usar el archivo, pásalos con `--prefix`, `--project` y `--glue-database`.

## 5. Si algo falla

- **`init`, `plan` o `destroy` fallan con `Plugin did not respond` / `x509: certificate signed by unknown authority`:**
  un antivirus que inspecciona TLS (por ejemplo AVG) rompe el canal local entre Terraform y el provider.
  Excluye `terraform-provider-aws*.exe` de la inspección HTTPS del antivirus, o ejecuta el comando con
  `TF_DISABLE_PLUGIN_TLS=1` (solo desactiva el cifrado de ese canal local, no el de las llamadas a AWS).
- **`destroy` falla por subnets o interfaces de red** (`DependencyViolation`): espera unos minutos y repite
  `terraform -chdir=infra destroy`. Es idempotente.
- **`verify_teardown.py` lista residuos:** repite el destroy; si persisten, bórralos a mano (la salida indica servicio y nombre).
- **Snapshots manuales** creados desde la consola sobreviven al destroy y se facturan: bórralos.
- **Nunca borres `terraform.tfstate`**: sin él Terraform no sabe qué destruir. Si se perdió, `verify_teardown.py`
  encuentra los recursos por prefijo y por tag.

## Pruebas

```bash
uv run python scripts/testing/run_pytest.py              # tests locales (sin AWS)
terraform -chdir=infra test                              # tests de Terraform (offline, con providers simulados)
terraform -chdir=infra/modules/<modulo> test             # tests de un módulo
uv run python scripts/testing/run_cloud_tests.py         # contra el lab desplegado (necesita credenciales)
```
