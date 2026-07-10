# infra/future — Fase 2 (solo diseño, nada implementado todavía)

Esta carpeta es intencionalmente un esqueleto. El diseño completo está en
`docs/phase-2-multicloud.md`. Aquí solo se deja la estructura sugerida para
cuando se implemente cada nube, más un README por proveedor con las
decisiones específicas de esa nube.

No hay Terraform, Helm charts ni pipelines reales todavía — implementarlos
antes de necesitarlos sería exactamente la "complejidad innecesaria" que
este proyecto evita a propósito en la Fase 1 (ver `docs/architecture.md`,
sección 5).

Estructura sugerida cuando se implemente la Fase 2B (ver
`docs/phase-2-multicloud.md`, sección 2):

```
infra/future/
├── terraform/
│   ├── modules/{k8s-cluster,networking,object-storage}/
│   ├── digitalocean/
│   ├── aws/
│   └── azure/
└── k8s/
    ├── base/
    └── overlays/{digitalocean,aws,azure}/
```
