# Azure — Fase 2 (diseño)

Candidato de segunda/tercera nube en Fase 2B, particularmente relevante si
la organización ya usa Microsoft 365 / Entra ID para identidad. Ver
justificación completa en `docs/phase-2-multicloud.md`, secciones 2 y 5.

Resumen de la decisión para Azure:

- **Cluster K8s**: AKS, usando el módulo Terraform común
  (`infra/future/terraform/modules/k8s-cluster`) con el root module
  específico de Azure.
- **Almacenamiento**: Azure Blob Storage — requiere un shim o gateway
  S3-compatible si se quiere mantener la interfaz de almacenamiento
  idéntica a la de DigitalOcean/AWS (documentado explícitamente como la
  diferencia real de portabilidad entre las 3 nubes).
- **Secretos**: Azure Key Vault, integrado vía External Secrets Operator.
- **Identidad**: si la organización usa Entra ID, este es el punto natural
  para SSO de acceso al cluster/servicios internos en Fase 2C.

Nada de esto está implementado aún — este README es un marcador de
intención, no una guía operativa.
