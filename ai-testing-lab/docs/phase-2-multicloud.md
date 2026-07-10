# Fase 2 — Diseño multi-cloud (DigitalOcean, AWS, Azure)

Este documento es **solo diseño**: no hay Terraform ni pipelines
implementados todavía. Objetivo: dejar clara la ruta de evolución desde el
laboratorio local (Fase 1) hasta un despliegue productivo multi-cloud, sin
tener que rediseñar la arquitectura en cada salto.

## 0. Principio rector: portabilidad por contenedores, no por abstracción prematura

La Fase 1 ya produce artefactos portables (imágenes Docker de `app/`,
configuración declarativa de Ollama/Phoenix). La Fase 2 **no reescribe la
aplicación**; añade capas de infraestructura alrededor de los mismos
contenedores. Esto es intencional: abstraer "multi-cloud" a nivel de
código de aplicación demasiado pronto es sobre-ingeniería; abstraerlo a
nivel de contenedor + IaC es el punto correcto de indirección.

## 1. Fase 2A — Despliegue simple en una sola nube

**Objetivo**: sacar el laboratorio de tu laptop a un servidor accesible,
con el menor salto de complejidad posible.

**Nube sugerida para empezar: DigitalOcean** (más simple y barato para
este tamaño de carga; ver comparación en la sección 5).

**Arquitectura 2A:**
- 1 Droplet (VM) con Docker + Docker Compose — literalmente el mismo
  `docker-compose.yml` de este repo, con 2 cambios: (a) un servicio
  adicional de reverse proxy, (b) variables de entorno apuntando a un
  dominio real.
- **Reverse proxy / TLS**: Caddy o Traefik delante de la API y de Phoenix,
  con certificados Let's Encrypt automáticos. Caddy se recomienda por
  configuración mínima (HTTPS automático con ~10 líneas de Caddyfile).
- **Almacenamiento**: DO Spaces (S3-compatible) para backups periódicos
  del índice RAG y de los datos de Phoenix (en vez de solo volúmenes
  locales del Droplet).
- **Secretos**: variables de entorno inyectadas vía DO App Platform
  secrets o, si es un Droplet plano, un `.env` con permisos restringidos
  (`chmod 600`) — no hay necesidad de un vault dedicado en este tamaño.
- **CI/CD mínimo**: GitHub Actions que en cada push a `main` construye la
  imagen de `app/`, la publica en GitHub Container Registry, y hace SSH al
  Droplet para `docker compose pull && docker compose up -d`.
- **Costo estimado**: 1 Droplet de 2-4 GB RAM (~$12-24/mes) + Spaces
  (~$5/mes). Sigue siendo modesto, ya no es "sin costo" pero es el salto
  mínimo razonable para tener el laboratorio disponible fuera de tu
  laptop.

**Qué NO se hace en 2A (a propósito):** Kubernetes, multi-región, alta
disponibilidad, secretos centralizados. Eso es 2B/2C.

## 2. Fase 2B — Despliegue multi-cloud portable

**Objetivo**: que el mismo conjunto de manifiestos pueda desplegarse en
DigitalOcean, AWS o Azure indistintamente, eligiendo la nube por costo,
disponibilidad de crédito, o requisito de cliente/proyecto.

**Decisión clave: Kubernetes como capa de portabilidad**, usando
Kubernetes *administrado* en cada nube (el mínimo común denominador real
entre las 3):

| Nube | Servicio K8s administrado | Por qué |
|---|---|---|
| DigitalOcean | DOKS (DigitalOcean Kubernetes) | Control plane gratis, el más simple de las 3 opciones. |
| AWS | EKS | El más maduro en integraciones (IAM, VPC, ALB), pero el más caro/complejo de operar. |
| Azure | AKS | Buena opción si ya hay integración con Entra ID / Microsoft 365 en la organización. |

**Estructura sugerida (a implementar cuando se llegue a esta fase):**

```
infra/future/
├── terraform/
│   ├── modules/
│   │   ├── k8s-cluster/       # interfaz común (variables: region, node_size, node_count)
│   │   ├── networking/
│   │   └── object-storage/
│   ├── digitalocean/          # root module que usa los módulos comunes
│   ├── aws/
│   └── azure/
└── k8s/
    ├── base/                  # manifiestos/Helm chart comunes (Kustomize base)
    └── overlays/
        ├── digitalocean/
        ├── aws/
        └── azure/
```

- **Terraform** con módulos reusables + un root module por nube: la lógica
  de "crear un cluster K8s con tal tamaño" se escribe una vez por nube
  (porque cada proveedor tiene su propio recurso), pero las *variables* de
  entrada son las mismas, y la salida (kubeconfig) es homogénea.
- **Kustomize/Helm** para los manifiestos de la aplicación: un `base/` con
  los Deployments/Services de `api`, `ollama` (o su reemplazo con GPU en
  nube, ver más abajo), y `phoenix`; overlays por nube solo para lo que
  realmente difiere (clase de storage, anotaciones de ingress específicas
  del proveedor).
- **Ingress**: `ingress-nginx` o Traefik + `cert-manager`, ambos
  cloud-agnostic — se instalan igual en DOKS/EKS/AKS.
- **Almacenamiento de objetos portable**: usar la API S3 como
  denominador común (AWS S3 nativo, DO Spaces es S3-compatible, Azure
  Blob Storage requiere el shim `azure-storage-blob` o un gateway
  S3-compatible). Documentar esta diferencia explícitamente para no
  asumir compatibilidad 100% transparente con Azure.
- **Secretos multi-cloud**: en vez de atarse al secret manager nativo de
  cada nube (lo cual rompe portabilidad), usar **External Secrets
  Operator** dentro de K8s, que sí sabe hablar con AWS Secrets Manager,
  Azure Key Vault y (vía plugin genérico) con Vault/Doppler para
  DigitalOcean (que no tiene secret manager nativo). Esto mantiene los
  manifiestos de K8s idénticos entre nubes; solo cambia el backend
  configurado en el `SecretStore`.
- **Model serving en nube con GPU**: aquí es donde entra `vllm-project/vllm`
  (dejado fuera de la Fase 1 por falta de GPU en laptop) — en 2B, si el
  caso de uso lo justifica, se reemplaza el contenedor `ollama` por un
  Deployment de vLLM sobre un node pool con GPU (disponible en las 3
  nubes, con distinta disponibilidad/precio). Mientras no haga falta ese
  throughput, Ollama sigue funcionando igual dentro de K8s sin cambios.
- **Observabilidad centralizada**: Phoenix (o su reemplazo por Langfuse si
  para entonces se justifica la infraestructura adicional) corre como un
  servicio único, sin importar en qué nube estén los workers de cómputo —
  todos exportan OTLP al mismo endpoint. Esto ya es así desde la Fase 1
  (`app/core/tracing.py` solo necesita la URL del colector).
- **CI/CD**: GitHub Actions con matrix build (una imagen, N destinos) —
  build una vez, deploy condicional a la nube elegida vía
  `workflow_dispatch` con un input `target_cloud: [digitalocean, aws, azure]`,
  reutilizando el mismo job de "build & push imagen" y solo variando el
  job de "terraform apply" + "kubectl apply/helm upgrade" según el input.

## 3. Fase 2C — Endurecimiento para producción

Una vez que 2B funciona en al menos una nube:

- **Alta disponibilidad**: node pools multi-AZ, réplicas ≥2 de la API,
  PodDisruptionBudgets, readiness/liveness probes (ya triviales de añadir
  porque `GET /health` ya existe desde la Fase 1).
- **Base de datos administrada**: si el laboratorio crece a necesitar
  estado relacional real (ej. Langfuse con Postgres+ClickHouse), migrar de
  contenedores self-hosted a servicios administrados (RDS / Azure
  Database for PostgreSQL / DO Managed Databases) por backups automáticos
  y menor carga operativa.
- **CDN / WAF**: Cloudflare (u otro) delante del ingress, independiente de
  la nube subyacente — refuerza la portabilidad y añade protección DDoS
  básica y reglas de firewall de aplicación.
- **GitOps**: reemplazar el "kubectl apply" manual de GitHub Actions por
  Argo CD o Flux, para que el estado del cluster sea siempre reproducible
  desde git (auditable, revertible).
- **Rotación de secretos y auditoría**: políticas de rotación automática en
  el secret manager de cada nube; logging centralizado (CloudTrail /
  Azure Monitor / DO Monitoring) enviado también a Phoenix/almacén de logs
  central si se requiere correlación con trazas de LLM.
- **Guardrails de costo**: alertas de presupuesto nativas de cada nube
  (AWS Budgets, Azure Cost Management, DO billing alerts) — especialmente
  importante si en esta fase se conectan modelos de pago como fallback.
- **Guardrails de seguridad en runtime**: aquí es donde `protectai/llm-guard`
  (dejado fuera de la Fase 1 por minimalismo) se vuelve relevante — un
  sidecar o middleware que filtra PII/prompt injection en tiempo real
  antes de servir tráfico externo real, complementando el red teaming
  offline que ya se hace con garak/promptfoo en Fase 1.

## 4. Tabla resumen de evolución

| | Fase 1 (actual) | Fase 2A | Fase 2B | Fase 2C |
|---|---|---|---|---|
| Cómputo | Docker Compose, 1 laptop | 1 Droplet, Docker Compose | K8s administrado (1 nube a la vez) | K8s multi-AZ, posible multi-nube activo |
| Costo | $0 | ~$15-30/mes | Variable según nube/tamaño | Producción (costo real de negocio) |
| Model serving | Ollama (CPU) | Ollama (CPU, VM más grande) | Ollama o vLLM (GPU opcional) | vLLM/serving dedicado con autoscaling |
| Observabilidad | Phoenix (1 contenedor) | Phoenix (1 contenedor) | Phoenix/Opik centralizado | Stack completo + alertas + logs centralizados |
| Secretos | `.env` local | `.env` con permisos restringidos | External Secrets Operator | Rotación automática + auditoría |
| CI/CD | Ninguno (manual) | GitHub Actions (build+deploy simple) | GitHub Actions (matrix multi-nube) | GitOps (Argo CD/Flux) |
| Networking | `localhost` | Reverse proxy + TLS (Caddy) | Ingress + cert-manager (K8s) | + CDN/WAF |

## 5. Trade-offs entre nubes (para esta carga de trabajo específica)

- **DigitalOcean**: la más simple de operar, control plane de Kubernetes
  gratis, precios predecibles. Menos servicios gestionados "premium"
  (sin secret manager nativo, catálogo de GPU más limitado). Buena
  elección para 2A y como primera nube en 2B.
- **AWS**: el catálogo más amplio (Bedrock si se quisiera complementar con
  modelos gestionados, Secrets Manager, GPU bajo demanda amplia
  disponibilidad), pero mayor complejidad de IAM/networking y curva de
  costos menos predecible si no se ponen guardrails desde el día uno.
- **Azure**: buena opción si la organización ya usa Microsoft 365/Entra ID
  (integración de identidad más directa), catálogo de GPU competitivo, pero
  con una experiencia de desarrollador algo más pesada que DO para un
  equipo pequeño.

**Recomendación práctica**: usar DigitalOcean para 2A y como primer target
de 2B (menor fricción para validar que el diseño portable realmente
funciona), y solo añadir AWS/Azure como segundo/tercer target cuando haya
una razón concreta (requisito de cliente, créditos disponibles, necesidad
de un servicio específico de esa nube) — no antes, para no pagar el costo
de mantener 3 integraciones activas sin necesidad real.
