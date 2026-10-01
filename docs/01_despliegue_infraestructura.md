# 1. Despliegue de la infraestructura (Terraform)

Esta guía crea **toda la infraestructura del laboratorio** en tu cuenta de AWS y, al final, la destruye. Es la primera de dos:

1. **Despliegue de la infraestructura** (este documento): credenciales y flujo de Terraform.
2. [Laboratorio en la consola de AWS](02_laboratorio_consola_aws.md): qué hacer con la infraestructura ya creada.

Todo se maneja con Terraform. No hay que crear nada a mano en la consola, y **nada de lo que crees a mano por tu cuenta lo borra Terraform** (ver la sección 4).

## 0. Prerrequisitos

| Qué | Para qué |
|---|---|
| Cuenta AWS **propia de sandbox** | Cada alumno despliega en su cuenta y paga su consumo. |
| Credenciales de una identidad IAM con permisos para crear y leer todo (en un sandbox, `AdministratorAccess`) | Terraform crea VPC, S3, IAM, Redshift, Athena y Glue. |
| Región **us-east-1** (N. Virginia) | El dataset público TICKIT vive ahí; Terraform rechaza otras regiones. |
| [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.7 | Crea y destruye la infraestructura. |
| [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) | Solo para comprobar que las credenciales funcionan. |
| [uv](https://docs.astral.sh/uv/) | Ejecuta el verificador de destrucción (`uv sync` una vez). |
| Git Bash (recomendado) o PowerShell | Los comandos de esta guía están en ambos. |

## 1. Credenciales desde `.env.credentials`

### 1.1 Crear el archivo

El repo trae una plantilla. Cópiala y complétala con tus claves:

```bash
cp .env.example .env.credentials
```

El archivo debe quedar así (sin comillas, una variable por línea):

```text
AWS_ACCESS_KEY_ID=AKIA................
AWS_SECRET_ACCESS_KEY=................................
AWS_SESSION_TOKEN=
AWS_DEFAULT_REGION=us-east-1
```

- Deja `AWS_SESSION_TOKEN=` vacío salvo que tus credenciales sean **temporales** (en ese caso pega aquí el token).
- Guárdalo con finales de línea **LF**. Si tu editor usa CRLF (el Bloc de notas de Windows), en Git Bash las variables se cargan con un `\r` pegado al valor y AWS responde con errores de firma poco claros.
- El archivo está en `.gitignore` (regla `.env.*`): **nunca lo subas al repositorio ni lo compartas.**

### 1.2 Cargarlas en tu terminal

Terraform y la AWS CLI **no leen archivos `.env`**: toman las credenciales de variables de entorno. Hay que cargarlas en cada terminal nueva que abras (solo valen para esa terminal).

**Git Bash:**

```bash
set -a; . ./.env.credentials; set +a
```

**PowerShell:**

```powershell
Get-Content .env.credentials |
  Where-Object { $_ -match '^\s*[^#\s].*=' } |
  ForEach-Object { $k, $v = $_ -split '=', 2; [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'Process') }
```

### 1.3 Comprobar que funcionan

```bash
aws sts get-caller-identity
```

Debe devolver tu `Account` (12 dígitos) y el `Arn` de tu usuario o rol. Anota el número de cuenta: aparece en el nombre del bucket del lab.

Si responde `InvalidClientTokenId` o `SignatureDoesNotMatch`, las claves están mal copiadas, vencieron (si son temporales) o el archivo tiene finales de línea CRLF.

## 2. Flujo de Terraform

Todos los comandos se ejecutan desde la raíz del repo y sobre la carpeta `infra/`.

### 2.1 Configurar variables (opcional)

Los valores por defecto sirven para el lab. Si quieres cambiar algo:

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
```

| Variable | Por defecto | Cuándo tocarla |
|---|---|---|
| `project_name` | `redshift-lab` | Si quieres otro prefijo para los nombres de recursos (3 a 20 caracteres: minúsculas, dígitos y guiones). |
| `availability_zone_count` | `2` | Pon `3` si `apply` rechaza las dos subnets. |
| `enable_enhanced_vpc_routing` | `false` | Solo si Spectrum falla sin él; crea endpoints de S3 y Glue (el de Glue tiene costo por hora). |
| `enable_budget_guardrail` y `budget_alert_email` | `false` y vacío | Si quieres un presupuesto mensual con alerta por correo. |

### 2.2 Inicializar, planificar y aplicar

```bash
terraform -chdir=infra init
terraform -chdir=infra plan
terraform -chdir=infra apply
```

1. **`init`** descarga el provider de AWS y prepara los módulos. Solo hace falta la primera vez.
2. **`plan`** muestra qué se va a crear, sin tocar nada. Con los valores por defecto debe terminar en `Plan: 20 to add, 0 to change, 0 to destroy.` Si ves recursos a **destruir**, detente y revisa.
3. **`apply`** vuelve a mostrar el plan y pide confirmación: escribe `yes`. Termina con `Apply complete! Resources: 20 added`.

### 2.3 Qué se creó

El diagrama de dependencias entre módulos está en [docs/architecture/architect_diagram.png](architecture/architect_diagram.png). En resumen:

| Módulo | Recursos |
|---|---|
| `network` | VPC propia con 2 subnets privadas y un security group sin reglas de entrada (no hay NAT). |
| `s3` | Un bucket **vacío** para este lab (destino de UNLOAD y de los resultados de Athena). |
| `data_catalog` | La base de Glue `spectrumdb`. |
| `iam` | El rol de Redshift (rol por defecto del namespace) y un rol vacío `rol-sin-permisos` para la Parte 7. |
| `redshift` | Namespace y workgroup de Redshift Serverless (4 RPUs), con un tope diario de consumo y un log group. |
| `athena` | Un workgroup de Athena con sus resultados en el bucket del lab. |
| `budget` | Solo si lo activaste. |

### 2.4 Anotar las salidas

Al terminar, Terraform imprime valores que usarás en la consola. Para verlos de nuevo en cualquier momento:

```bash
terraform -chdir=infra output
```

| Salida | Para qué la usarás en la guía 2 |
|---|---|
| `workgroup_name` | Elegir el workgroup en Query Editor v2 y en Athena. |
| `admin_secret_arn` | Referencia del secreto con el que te conectas a Redshift. |
| `bucket_name` | Destino de UNLOAD (Parte 5) y bucket donde ver los resultados. |
| `no_permissions_role_arn` | Provocar el error de permisos (Parte 7). |
| `glue_database_name` | Base que verás en Athena y en Glue. |

Para obtener un solo valor sin comillas, por ejemplo el bucket:

```bash
terraform -chdir=infra output -raw bucket_name
```

### 2.5 Costos

- **Redshift Serverless factura el cómputo solo mientras corren consultas** (por segundo), más el almacenamiento. Además hay un tope diario de 16 RPU-horas: al alcanzarlo se desactivan las consultas.
- Athena cobra por dato escaneado; con TICKIT son fracciones de centavo.
- Si olvidas destruir el lab sigues pagando el almacenamiento (mínimo) y el secreto de Secrets Manager. **Destruye al terminar** (sección 4).

## 3. Si algo falla

| Síntoma | Causa y solución |
|---|---|
| `init`, `plan` o `destroy` fallan con `Plugin did not respond` o `x509: certificate signed by unknown authority` | Un antivirus que inspecciona TLS (por ejemplo AVG) rompe el canal local entre Terraform y el provider. Excluye `terraform-provider-aws*.exe` de la inspección HTTPS del antivirus, o ejecuta el comando con `TF_DISABLE_PLUGIN_TLS=1` (solo desactiva el cifrado de ese canal local, no el de las llamadas a AWS). |
| `Error: ... No valid credential sources found` | No cargaste las credenciales en **esta** terminal (sección 1.2). |
| `apply` rechaza las subnets | Pon `availability_zone_count = 3` en `infra/terraform.tfvars` y repite `plan` y `apply`. |
| `apply` falla a medias con un error de permisos de IAM | Tu identidad no tiene permisos suficientes. Repite `apply` cuando los tengas: es idempotente. |
| `project_name` rechazado | Debe tener 3 a 20 caracteres, solo minúsculas, dígitos y guiones. |

## 4. Destruir la infraestructura (siempre al terminar)

```bash
terraform -chdir=infra destroy
uv run python scripts/lab/verify_teardown.py
```

1. **`destroy`** pide confirmación (`yes`) y elimina todo lo que creó Terraform, incluido el contenido del bucket del lab.
2. **`verify_teardown.py`** (solo lectura) busca en tu cuenta cualquier residuo por prefijo y por etiqueta, **sin depender del estado de Terraform**. Debe imprimir `OK: no residual lab resources found.` Toma `project_name` y `glue_database_name` de `infra/terraform.tfvars` si existe, y muestra qué prefijo revisa.

### Residuos que Terraform no puede borrar

- **Secretos `sqlworkbench-...`**: los crea Query Editor v2 si te conectas con **Database user name and password**. Por eso la guía 2 usa el método *AWS Secrets Manager*. Si ya creaste uno, bórralo en la consola de Secrets Manager.
- **Snapshots manuales** creados desde la consola: sobreviven al destroy y se facturan. Bórralos.
- **Tablas o archivos que hayas creado fuera del lab** dentro de tu cuenta.

### Si el destroy falla

- **`DependencyViolation` al borrar subnets o interfaces de red:** espera unos minutos y repite `terraform -chdir=infra destroy`. Es idempotente.
- **El verificador lista residuos:** repite el destroy; si persisten, bórralos a mano (la salida indica servicio y nombre).
- **Nunca borres `terraform.tfstate`**: sin él Terraform no sabe qué destruir. Si se perdió, `verify_teardown.py` aún encuentra los recursos por prefijo y etiqueta.

## 5. Checklist

- [ ] Credenciales cargadas en la terminal y `aws sts get-caller-identity` responde
- [ ] `plan` revisado: 20 recursos a crear, ninguno a destruir
- [ ] `apply` terminó con `Apply complete!`
- [ ] Salidas anotadas (`workgroup_name`, `admin_secret_arn`, `bucket_name`, `no_permissions_role_arn`)
- [ ] Laboratorio completado en la [guía 2](02_laboratorio_consola_aws.md)
- [ ] `destroy` ejecutado y `verify_teardown.py` imprime `OK`
