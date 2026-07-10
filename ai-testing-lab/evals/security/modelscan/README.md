# Escaneo de artefactos de modelo con ModelScan (protectai/modelscan, Apache-2.0)

`modelscan` detecta código malicioso embebido en artefactos de modelos
serializados (pickle, PyTorch `.pt`, Keras H5, etc.) — el riesgo clásico de
"deserialización insegura" al descargar modelos de terceros (ej. Hugging
Face, repos no verificados).

## Cuándo aplica en este laboratorio

- Ollama descarga modelos empaquetados en formato GGUF desde su propio
  registro; el riesgo de pickle malicioso que ataca ModelScan **no aplica
  directamente** a los modelos `ollama pull` de la librería oficial.
- **Sí aplica** en cuanto:
  - Descargues manualmente un checkpoint `.pt`/`.pkl`/`.h5` de Hugging Face
    u otro origen para usarlo con LocalAI, vLLM o cualquier runtime que
    cargue pickle/torch directamente.
  - Integres modelos de embeddings, clasificadores o adaptadores LoRA de
    terceros descargados manualmente.

Por eso ModelScan queda documentado aquí como una **verificación previa
obligatoria** antes de cargar cualquier artefacto descargado manualmente
(ver `docs/security-notes.md` y la política de ejemplo en
`app/rag/sample_docs/testing_policy.txt`), en vez de forzarlo dentro del
flujo de Ollama donde no aporta valor real.

## Instalación y uso

```bash
pip install modelscan

# Escanear un archivo o carpeta de modelo descargado manualmente
modelscan --path /ruta/al/modelo/descargado

# Salida en JSON para integrarlo a CI más adelante (Fase 2)
modelscan --path /ruta/al/modelo --output-format json --output-file evals/security/modelscan/last_scan.json
```

## Qué hacer si ModelScan reporta hallazgos

1. No cargues el artefacto hasta entender el hallazgo.
2. Si es un modelo público conocido, busca si el hallazgo es un falso
   positivo documentado por la comunidad.
3. Si tienes dudas, no lo uses en este laboratorio; consulta con el
   responsable de seguridad antes de continuar.
