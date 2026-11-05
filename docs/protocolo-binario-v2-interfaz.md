# Protocolo binario V2 y módulo experimental en Streamlit

**Estado:** implementación en rama independiente, NO validada todavía en el equipo de investigación. **No iniciar experimentos facturables hasta pasar las pruebas y la revisión metodológica.**

## Regla de etiquetas

- NPA: \`not_potentially_abusive\` → \`no potencialmente abusiva\`.
- PA: \`potentially_abusive\` → \`potencialmente abusiva\`.
- La antigua \`strong_indications_of_abusiveness\` se fusiona con PA en la **referencia humana V2**, sin modificar el ground truth original V1.
- \`not_applicable\` se conserva como **estado de aplicabilidad**, nunca como tercera etiqueta de riesgo.

La proyección V2 contiene 547 fragmentos sin modificar: 321 NPA, 152 PA y 74 no aplicables. **473 evaluables**. La versión V2 se verifica con una huella propia derivada del V1 con SHA-256: no se deben mezclar archivos, checkpoints, ejecuciones o métricas entre versiones.

La ejecución previa ET01-R1 (DeepSeek + Holded, 21 unidades) pertenece a V1 y se conserva únicamente como evidencia técnica histórica. Debe volverse a ejecutar bajo el protocolo V2 si se desea incluir como resultado experimental confirmatorio.

## Interfaz integrada

Nueva navegación **Evaluación experimental** junto a **Análisis** y **Dashboard LLMOps**.

- **Diseño:** protocolo congelado, clase NPA/PA, corpus y tratamientos.
- **Ejecución:** elección de documento, tratamiento y repetición; autorización explícita del gasto.
- **Seguimiento:** estado, cola, reintentos manuales y trazabilidad.
- **Evidencias:** métricas binarias por documento, matriz de confusión y progresión por repetición.

La interfaz Streamlit no invoca el LLM directamente. La API FastAPI (/experimental) valida acceso con \`X-Experiment-Token\` y deposita una orden en una cola local. **Un único worker** de Docker Compose llama al LangGraph productivo y a los servidores MCP de conocimiento, análisis, informes y observabilidad. Los Web Scraper y Preprocesador se omiten solo en la evaluación controlada para conservar los fragmentos congelados.

Este diseño es un prototipo académico de **un único nodo**; la cola por archivos requiere migración a PostgreSQL antes de múltiples réplicas, acceso distribuido o despliegue público.

## Precaución: salida de Docker Compose y secretos

El comando `docker compose config` puede mostrar en pantalla las
credenciales efectivas cargadas desde `.env` y `backend/.env`.
Para validar la sintaxis sin exponerlas utiliza:

```powershell
docker compose config --quiet
docker compose --profile experiment config --quiet
```

Si alguna clave de OpenRouter, Langfuse o contraseña de base de datos
apareció en una captura, registro o conversación compartida,
**revocar/rotar los secretos expuestos** antes de continuar con pruebas
o despliegues. No adjuntar la salida completa de `docker compose config`
ni archivos `.env` a la tesis, GitHub o al chat. En PostgreSQL,
cambiar `POSTGRES_PASSWORD` no actualiza automáticamente la contraseña
de un rol en un volumen persistente; efectuar la rotación del rol y
actualizar después la configuración del backend. Nunca publicar
valores reales de credenciales en ejemplos o resultados.

## Configuración segura

Crear el archivo \`.env\` en la raíz a partir de \`.env.example\` y asignar valores secretos reales (NO subir a Git):

\`\`\`env
EXPERIMENT_ADMIN_TOKEN=<token-largo-aleatorio>
EXPERIMENT_OPERATOR_PASSWORD=<clave-única-investigador>
EXPERIMENT_EXECUTION_ENABLED=false
\`\`\`

**Por defecto la ejecución es imposible.** El frontend exige contraseña de investigador y el backend valida una segunda credencial. Para **solo consultar el panel**:

\`\`\`powershell
docker compose up -d --build
\`\`\`

Para autorizar llamadas con costo, después de validar pruebas, respaldo y presupuesto, cambiar temporalmente \`EXPERIMENT_EXECUTION_ENABLED=true\` y:

\`\`\`powershell
docker compose --profile experiment up -d --build
\`\`\`

No utilizar el worker con \`EXPERIMENT_EXECUTION_ENABLED=true\` sin un saldo verificado de OpenRouter. El límite de gasto implementado en el ejecutor CLI previo es blando entre documentos, no un tope de facturación duro. La nueva interfaz solicita confirmación por tarea y no garantiza un importe máximo.

Los archivos \`data/evaluation/\` deben existir en el host Docker y permanecer fuera de Git (volumen montado, ruta local). El CSV etiquetado solo es procesado por el cargador y evaluador; el modelo recibe \`id\`, \`platform\`, \`text\`, **nunca las etiquetas humanas**.

## Pruebas e integridad (NO facturan)

\`\`\`powershell
git switch experiment/binary-classification-ui-v2
git pull --ff-only origin experiment/binary-classification-ui-v2
$env:PYTHONPATH = (Resolve-Path ".\backend").Path

python scripts/prepare_binary_groundtruth_v2.py --csv data/evaluation/ground_truth_547.csv
python -m pytest tests/unit/test_binary_protocol_v2.py tests/unit/test_legal_analysis_schemas.py tests/unit/test_legal_analysis_prompt.py tests/unit/test_report_generator_agent.py tests/unit/test_document_metrics.py tests/unit/test_repetition_metrics.py tests/unit/test_orchestrated_experiment.py -q
python scripts/run_groundtruth_campaign.py --csv data/evaluation/ground_truth_547.csv --task-id ET01-R1
python scripts/score_groundtruth_campaign.py --csv data/evaluation/ground_truth_547.csv
\`\`\`

Esperado en la vista previa de V2: 90 tareas pendientes, cero inferencias formales V2, huella distinta de V1, y ausencia de errores de esquema. La prueba de interfaz y del worker en Docker debe completarse además antes de una campaña.

## Reproducibilidad

- Congelar hash de referencia, commit, corpus ChromaDB, prompt, modelo, temperatura y parámetros RAG.
- Registrar exclusivamente predicciones V2 en \`v2_binary_campaign_runs.jsonl\`; checkpoints V2 en \`v2_binary_unit_checkpoints.jsonl\`; contexto V2 en \`v2_binary_legal_context_snapshots.jsonl\`.
- La calidad binaria principal se calcula sobre unidades **humanamente evaluables**, con NPA y PA. El estado de aplicabilidad se analiza por separado. Las unidades no ejecutadas no constituyen errores del proveedor.
- No cambiar la clasificación de las unidades o el prompt tras observar resultados, salvo creando un protocolo distinto y justificándolo.
- Las cifras de capítulo IV solo son definitivas al completar tratamientos, repeticiones y auditoría de su ejecución.

## Documento de tesis

La única versión de la tesis disponible para inspección fue un PDF generado por Prism. Los cambios de redacción del proyecto LaTeX original deberán aplicarse sobre ese archivo fuente y recompilarse; el PDF previo no debe presentarse como una versión ya editada. Mantener los antecedentes científicos que usen otras escalas de clasificación, atribuidos a sus autores.

## Prueba integrada sin facturación (API → cola → worker → métricas)

Antes de ejecutar la evaluación real, verificar el circuito de control
mediante una simulación estrictamente local. El archivo
\`tests/unit/test_experimental_ui_worker_flow.py\` usa un corpus
**sintético**, la API FastAPI con \`TestClient\`, una cola temporal creada
por pytest y un doble de \`run_orchestrated_trial\` que **no realiza
llamadas a OpenRouter, MCP ni Langfuse**.

La prueba comprueba:
- bloqueo de endpoints para solicitudes sin credencial;
- rechazo de órdenes de pago cuando \`EXPERIMENT_EXECUTION_ENABLED=false\`;
- rechazo de autorizaciones ausentes, tareas desconocidas o duplicadas;
- encolado y transición de \`queued\` a \`completed\`;
- relectura del estado y métricas por documento/repetición desde FastAPI;
- detección de huella de dataset incompatible sin llamar al modelo.

\`\`\`powershell
git pull --ff-only origin experiment/binary-classification-ui-v2
$env:PYTHONPATH = (Resolve-Path ".\\backend").Path
python -m pytest tests/unit/test_experimental_ui_worker_flow.py -q
python -m pytest tests/unit -q
docker compose --profile experiment config --quiet
\`\`\`

**No ejecutar \`EXPERIMENT_EXECUTION_ENABLED=true\` en Docker** para
probar este circuito: el test activa esa bandera únicamente dentro del
proceso temporal de pruebas y sustituye todas las inferencias. La prueba
de UI real en Docker se hace con el trabajador apagado y la API en solo
lectura; por separado aún queda comprobar el funcionamiento real de
LangGraph/MCP en el protocolo V2, para lo cual habrá una autorización
de costo y auditoría posterior.



## Pantalla de seguimiento y UX (revisión posterior a la primera captura)

La revisión visual de Streamlit confirmó el acceso, el origen V2 del
ground truth, 90 tareas sin ejecutar y la protección contra llamadas
facturables. Se incorporaron estos ajustes en la rama de desarrollo:

- Mayor proporción de espacio para la navegación de las tres secciones,
  evitando en pantallas anchas que «Evaluación experimental» salte a
  una segunda línea.
- Con \`EXPERIMENT_EXECUTION_ENABLED=false\`, la casilla de autorización
  de pago no se muestra y el botón de inicio permanece deshabilitado.
- La API \`/experimental/overview\` incluye por tarea \`unit_progress\`
  con \`checkpoint_successful\`, \`checkpoint_failed\`, \`remaining\`
  y \`total\`. La API separa la huella de dataset, modelo, repetición,
  documento y hash del fragmento. No expone etiquetas humanas.
- Streamlit muestra una barra de progreso por unidad para la tarea
  seleccionada y, cuando exista, el estado independiente de su cola
  (\`queued\`, \`running\`, \`failed\`, \`completed\`).
- La barra de cláusulas **no sustituye** el estado de completitud formal
  del documento: ese estado exige informe completo, 21/21 u otras
  unidades correspondientes y persistencia del resultado.

Pruebas posteriores a la implementación:

\`\`\`powershell
git pull --ff-only origin experiment/binary-classification-ui-v2
$env:PYTHONPATH = (Resolve-Path ".\\backend").Path
python -m pytest tests/unit/test_experimental_ui_worker_flow.py -q
python -m pytest tests/unit -q
docker compose up -d --build backend frontend
docker compose ps
\`\`\`

Mantener el worker desactivado y nunca compartir las claves en las
capturas. Esta prueba de integración no sustituye una ejecución V2
real con LangGraph/MCP; solo verifica control y observabilidad local.


## Mejoras del acceso para la defensa — revisión de interfaz

En la revisión visual se observó que el investigador podía mostrar
accidentalmente la contraseña en una captura de pantalla. La nueva
implementación requiere un botón explícito **«Acceder al panel»**, borra
el contenido del campo al autenticar y **oculta el campo de contraseña
una vez iniciada la sesión**. Se muestra en su lugar **«Cerrar sesión»**.
No se persisten valores de contraseña en los archivos experimentales.

Si se compartió una captura donde se ve una contraseña real, debe
**cambiarse de inmediato** en el \`.env\` local y en cualquier otro
servicio donde se haya reutilizado, reiniciando solo los contenedores
que la consumen. Nunca usar esa contraseña para anexos académicos.

En «Evidencias» se incorporaron filtros de plataforma y tratamiento,
junto con traducción visual de los estados de tarea (por ejemplo,
\`pending\` → «Pendiente»). Los códigos internos se mantienen sin cambios
para conservar compatibilidad con el backend.

Comprobación visual, sin facturación:

\`\`\`powershell
git pull --ff-only origin experiment/binary-classification-ui-v2
$env:PYTHONPATH = (Resolve-Path ".\\backend").Path
python -m pytest tests/unit -q
docker compose up -d --build frontend
\`\`\`

Volver a entrar a \`http://localhost/experimental\`, seleccionar
«Acceder al panel», comprobar que la contraseña desaparece, probar
«Cerrar sesión», volver a entrar y revisar los filtros de «Evidencias».
Mantener \`EXPERIMENT_EXECUTION_ENABLED=false\` y el worker apagado.
