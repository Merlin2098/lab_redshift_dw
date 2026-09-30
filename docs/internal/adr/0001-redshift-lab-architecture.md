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
