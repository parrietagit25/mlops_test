# reports/

Resultados de las suites de evaluación (`promptfoo`, `DeepEval`, `Ragas`,
`security`), generados por `scripts/run_all_evals.sh` (o por cada script
individual, según el caso). Cada corrida crea su propia carpeta:

```
reports/
└── 2026-07-10/
    └── 143512/
        ├── summary.md          # resumen consolidado de esa corrida
        ├── promptfoo/output.log
        ├── deepeval/output.log
        ├── ragas/output.log
        ├── ragas/last_run_results.csv   (copia, si Ragas la generó)
        └── security/output.log
```

El contenido de esta carpeta **no se versiona** (ver `.gitignore`): son
resultados de ejecución local, no código. Solo este `README.md` queda
trackeado para que la carpeta exista en un checkout nuevo.
