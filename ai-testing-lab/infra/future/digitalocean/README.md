# DigitalOcean — Fase 2 (diseño)

Nube recomendada para empezar (Fase 2A y primer target de Fase 2B). Ver
justificación completa en `docs/phase-2-multicloud.md`, secciones 1, 2 y 5.

Resumen de la decisión para DigitalOcean:

- **2A**: 1 Droplet + Docker Compose (el mismo `docker-compose.yml` de la
  raíz del repo) + Caddy como reverse proxy con TLS automático + DO Spaces
  para backups.
- **2B**: DOKS (Kubernetes administrado, control plane gratis) como
  cluster objetivo, usando los módulos Terraform comunes de
  `infra/future/terraform/modules/` con un root module específico de DO.
- **Secretos**: DigitalOcean no tiene un secret manager nativo — se usa
  Vault/Doppler o `SecretStore` genérico de External Secrets Operator (ver
  `docs/phase-2-multicloud.md`, sección 2).

Nada de esto está implementado aún — este README es un marcador de
intención, no una guía operativa.
