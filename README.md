# Laboratorio Redshift — Sesión 5

Laboratorio de Amazon Redshift Serverless sobre el dataset TICKIT. Toda la infraestructura
se crea y se destruye con Terraform, y el laboratorio se recorre en la consola de AWS.

## Cómo seguir el laboratorio

Son dos guías, en este orden:

1. **[Despliegue de la infraestructura](docs/01_despliegue_infraestructura.md):** prerrequisitos, credenciales cargadas
   desde `.env.credentials`, flujo de Terraform (`init`, `plan`, `apply`), cómo destruir todo y verificarlo.
2. **[Laboratorio en la consola de AWS](docs/02_laboratorio_consola_aws.md):** el lab paso a paso con Query Editor v2,
   Athena, S3 y Glue, explicando de dónde sale cada dato y qué observar en cada pantalla.

Dependencias entre los módulos de Terraform y las herramientas: [diagrama de arquitectura](docs/architecture/architect_diagram.png)
(grafo fuente en Graphviz: [architecture.dot](docs/architecture/architecture.dot)).

## Qué se crea y cuánto cuesta

VPC propia (sin NAT), un bucket S3 (vacío: recibe los resultados de Athena y de UNLOAD), una base de Glue, dos roles IAM,
un namespace y workgroup de Redshift Serverless (4 RPUs), un workgroup de Athena y un log group.

- **Redshift Serverless solo factura cómputo mientras corren consultas** (por segundo) más el almacenamiento, y hay un
  tope diario de 16 RPU-horas.
- Si olvidas destruir el lab pagas almacenamiento (mínimo) y el secreto de Secrets Manager. **Destruye al terminar.**
- **Nunca borres `terraform.tfstate`**, y no subas `.env.credentials` al repositorio (está en `.gitignore`).

## Referencia rápida

```bash
set -a; . ./.env.credentials; set +a            # cargar credenciales (Git Bash; PowerShell en la guía 1)
terraform -chdir=infra init && terraform -chdir=infra apply
uv run python scripts/lab/run_lab.py --all      # el lab sin consola (--part N, --check)
terraform -chdir=infra destroy
uv run python scripts/lab/verify_teardown.py    # debe imprimir OK
```

## Pruebas

```bash
uv run python scripts/testing/run_pytest.py              # tests locales (sin AWS)
terraform -chdir=infra test                              # tests de Terraform (offline, con providers simulados)
terraform -chdir=infra/modules/<modulo> test             # tests de un módulo
uv run python scripts/testing/run_cloud_tests.py         # contra el lab desplegado (necesita credenciales)
```

Si Terraform falla con `Plugin did not respond` o `x509: certificate signed by unknown authority`, es un antivirus que
inspecciona TLS: ver la tabla de problemas de la [guía 1](docs/01_despliegue_infraestructura.md#3-si-algo-falla).
