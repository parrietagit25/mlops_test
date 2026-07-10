# AWS — Fase 2 (diseño)

Candidato de segunda nube en Fase 2B, o primera opción si el caso de uso
requiere específicamente un servicio de AWS (ej. GPU bajo demanda con
amplia disponibilidad, integración con Bedrock, Secrets Manager nativo).
Ver justificación completa en `docs/phase-2-multicloud.md`, secciones 2 y 5.

Resumen de la decisión para AWS:

- **Cluster K8s**: EKS, usando el módulo Terraform común
  (`infra/future/terraform/modules/k8s-cluster`) con el root module
  específico de AWS.
- **Almacenamiento**: S3 nativo (ya es el estándar de facto que el resto
  de la arquitectura asume como interfaz S3-compatible).
- **Secretos**: AWS Secrets Manager, integrado vía External Secrets
  Operator (mismo patrón que en las otras nubes, solo cambia el backend).
- **Model serving con GPU**: node pool con instancias `g5`/`g6` si se
  reemplaza Ollama por vLLM en esta fase.

Nada de esto está implementado aún — este README es un marcador de
intención, no una guía operativa.
