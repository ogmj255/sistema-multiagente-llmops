"""Interfaz de evaluación experimental V2.

Consulta abierta del diseño, estado, resultados y evidencias.
Las ejecuciones pagadas requieren habilitación del servidor, confirmación
explícita y credenciales de operador verificadas por FastAPI.
Streamlit nunca llama a OpenRouter o MCP directamente.
"""

from __future__ import annotations

import json
import os

import httpx
import pandas as pd
import streamlit as st

API = os.getenv(
    "API_EXPERIMENT_URL", "http://traefik/api/experimental"
).rstrip("/")

STATUS_TEXT = {
    "pending": "Pendiente",
    "completed": "Completada",
    "failed": "Fallida",
    "queued": "En cola",
    "running": "En ejecución",
    "invalid": "Inválida",
}


def _request(method: str, path: str, **kwargs) -> dict:
    """Solo las escrituras llevan credenciales; la lectura es libre."""
    headers = kwargs.pop("headers", {})
    with httpx.Client(timeout=15.0) as client:
        response = client.request(
            method, f"{API}/{path}", headers=headers, **kwargs
        )
        response.raise_for_status()
        return response.json()


def _notice() -> None:
    message = st.session_state.pop("experiment_notice", None)
    if not message:
        return
    if message["type"] == "success":
        st.success(message["text"])
    else:
        st.error(message["text"])


def _enqueue_paid_task(task_id: str) -> None:
    """Callback: valida consentimiento y limpia la clave antes del rerender."""
    password = st.session_state.get("experiment_write_password", "")
    confirmed = st.session_state.get("experiment_paid_confirmed", False)
    st.session_state["experiment_write_password"] = ""
    st.session_state["experiment_paid_confirmed"] = False
    if not confirmed or not isinstance(password, str) or not password:
        st.session_state["experiment_notice"] = {
            "type": "error",
            "text": "Confirma el gasto e introduce la clave de autorización.",
        }
        return
    token = os.getenv("EXPERIMENT_ADMIN_TOKEN", "")
    if not token:
        st.session_state["experiment_notice"] = {
            "type": "error",
            "text": "La credencial interna de ejecución no está configurada.",
        }
        return
    try:
        result = _request(
            "POST", "jobs",
            headers={
                "X-Experiment-Token": token,
                "X-Experiment-Operator": password,
            },
            json={
                "task_id": task_id,
                "accept_paid_execution": True,
            },
        )
        st.session_state["experiment_notice"] = {
            "type": "success",
            "text": (
                f"{result['task_id']} añadida a la cola experimental. "
                "El worker la procesará al estar activo."
            ),
        }
    except httpx.HTTPStatusError as exc:
        st.session_state["experiment_notice"] = {
            "type": "error",
            "text": (
                f"Orden rechazada (HTTP {exc.response.status_code}). "
                "Verifica credenciales, límites y posibles tareas duplicadas."
            ),
        }
    except (httpx.RequestError, ValueError):
        st.session_state["experiment_notice"] = {
            "type": "error",
            "text": "No fue posible comunicar la solicitud al backend.",
        }


def _task_selector(tasks: list[dict], *, key: str) -> dict:
    task_ids = [task["task_id"] for task in tasks]
    chosen = st.selectbox(
        "Tarea experimental",
        task_ids,
        key=key,
        format_func=lambda value: next(
            (
                f"{t['task_id']} · {t['platform']} · "
                f"{t['treatment']} · R{t['repetition']} · "
                f"{STATUS_TEXT.get(t['status'], t['status'])}"
            )
            for t in tasks if t["task_id"] == value
        ),
    )
    return next(task for task in tasks if task["task_id"] == chosen)


def _design(overview: dict) -> None:
    manifest = overview["manifest"]
    tasks = overview["tasks"]
    st.subheader("Diseño y configuración metodológica")
    a, b, c, d = st.columns(4)
    a.metric("Unidades congeladas", manifest["units"])
    b.metric("NPA", manifest["classification_labels"]["NPA"])
    c.metric("PA", manifest["classification_labels"]["PA"])
    d.metric("No aplicables", manifest["applicability"]["not_applicable"])

    st.write(
        "Las **473 unidades evaluables** se clasifican en NPA/PA. "
        "La aplicabilidad se examina por separado. Los textos originales "
        "y las etiquetas humanas se mantienen en una referencia versionada."
    )
    st.write(
        "**Diseño formal:** 10 documentos × 3 LLM × 3 repeticiones "
        "= 90 tareas documentales y 4.923 decisiones esperadas."
    )
    models = {
        t["treatment"]: t["model"] for t in tasks
    }
    st.dataframe(
        pd.DataFrame([
            {"Tratamiento": code, "Modelo exacto": model}
            for code, model in sorted(models.items())
        ]),
        hide_index=True, use_container_width=True,
    )
    documents = {}
    for task in tasks:
        documents[task["document_id"]] = (
            task["platform"], task["unit_count"]
        )
    with st.expander("Ver los 10 documentos del corpus"):
        st.dataframe(
            pd.DataFrame([
                {"Documento": code, "Plataforma": value[0],
                 "Unidades": value[1]}
                for code, value in documents.items()
            ]),
            hide_index=True, use_container_width=True,
        )
    st.caption(
        "SHA-256 de la referencia binaria V2: "
        f"{manifest['binary_v2_fingerprint']}"
    )
    st.info(
        "Para comparar modelos se introducen los mismos fragmentos "
        "congelados mediante LangGraph y MCP. La extracción web y el "
        "preprocesamiento productivo no se repiten durante este experimento. "
        "La versión jurídica de ChromaDB y el commit deben auditarse "
        "antes de declarar la campaña formal."
    )


def _execution(overview: dict) -> None:
    st.subheader("Ejecución documental")
    tasks = overview["tasks"]
    documents = {}
    for task in tasks:
        documents[task["document_id"]] = task["platform"]
    models = {
        task["treatment"]: task["model"] for task in tasks
    }
    left, middle, right = st.columns(3)
    with left:
        document_id = st.selectbox(
            "Documento SaaS", list(documents),
            format_func=lambda code: f"{code} · {documents[code]}",
            key="exp_document",
        )
    with middle:
        treatment = st.selectbox(
            "Modelo LLM", list(models),
            format_func=lambda code: f"{code} · {models[code]}",
            key="exp_treatment",
        )
    with right:
        repetition = st.selectbox(
            "Repetición", [1, 2, 3],
            format_func=lambda num: f"R{num}",
            key="exp_repetition",
        )
    selected = next(
        task for task in tasks
        if task["document_id"] == document_id
        and task["treatment"] == treatment
        and task["repetition"] == repetition
    )
    st.session_state["exp_current_task_id"] = selected["task_id"]
    st.write(
        f"**{selected['task_id']}** · {selected['unit_count']} cláusulas · "
        f"{STATUS_TEXT.get(selected['status'], selected['status'])}"
    )
    st.caption(
        "Una tarea = todas las unidades de un documento, con un modelo "
        "y una repetición específica. Las otras repeticiones no reutilizan "
        "sus predicciones."
    )

    enabled = overview.get("execution_enabled", False)
    if not enabled:
        st.info(
            "Modo de consulta: la facturación está deshabilitada "
            "en el servidor. Se pueden revisar diseño, progreso, "
            "resultados y evidencias sin restricciones de acceso."
        )
    else:
        st.warning(
            "La tarea puede consumir créditos. No existe un límite duro "
            "de facturación para un documento en curso."
        )
        st.text_input(
            "Clave de autorización para iniciar una tarea con costo",
            type="password",
            key="experiment_write_password",
            help="Se solicita solo para una orden facturable, no para consultar.",
        )
        st.checkbox(
            "Confirmo que deseo ejecutar este documento completo "
            "y asumir su costo de OpenRouter.",
            value=False, key="experiment_paid_confirmed",
        )

    blocked = (
        not enabled
        or selected["status"] == "completed"
        or selected.get("job_status") in {"queued", "running", "completed"}
    )
    st.button(
        "Iniciar esta tarea documental",
        disabled=blocked,
        type="primary",
        on_click=_enqueue_paid_task,
        args=(selected["task_id"],),
    )
    _notice()
    if st.button("Actualizar estado de campaña", key="exp_reload_execution"):
        st.rerun()
    st.caption(
        "Prueba de una sola cláusula y lanzamiento masivo de 90 tareas: "
        "funcionalidades previstas para una fase posterior. "
        "Por ahora la ejecución autorizada es documental y secuencial."
    )


def _tracking(overview: dict) -> None:
    st.subheader("Seguimiento por cláusula")
    tasks = overview["tasks"]
    task_id = st.session_state.get("exp_current_task_id")
    if task_id not in {t["task_id"] for t in tasks}:
        task_id = tasks[0]["task_id"]
    index = next(
        i for i, task in enumerate(tasks) if task["task_id"] == task_id
    )
    chosen_id = st.selectbox(
        "Inspeccionar tarea", [t["task_id"] for t in tasks],
        index=index, key="exp_tracking_task",
    )
    task = next(t for t in tasks if t["task_id"] == chosen_id)
    progress = task["unit_progress"]
    completed = progress["checkpoint_successful"]
    total = progress["total"]
    st.progress(
        completed / max(total, 1),
        text=f"{completed} de {total} unidades guardadas en checkpoints",
    )
    a, b, c = st.columns(3)
    a.metric("Guardadas", completed)
    b.metric("Pendientes", progress["remaining"])
    c.metric("Fallos de unidades", progress["checkpoint_failed"])
    status = task.get("job_status") or task["status"]
    st.caption(
        f"Estado: {STATUS_TEXT.get(status, status)} · "
        f"Modelo: {task['model']}"
    )
    if st.button("Actualizar seguimiento", key="exp_reload_tracking"):
        st.rerun()
    try:
        details = _request("GET", f"tasks/{chosen_id}/units")
        st.dataframe(
            pd.DataFrame([
                {
                    "ID de unidad": row["id"],
                    "Estado": STATUS_TEXT.get(row["status"], row["status"]),
                }
                for row in details["units"]
            ]),
            hide_index=True, use_container_width=True,
        )
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
        st.warning("El detalle de unidades no está disponible.")
    jobs = [
        job for job in overview.get("jobs", [])
        if job.get("task_id") == chosen_id
    ]
    if jobs:
        job = jobs[0]
        st.caption(
            f"Worker: {STATUS_TEXT.get(job.get('status'), job.get('status'))} "
            f"· Ejecución: {job.get('execution_id') or 'sin ID todavía'}"
        )
        if job.get("status") == "failed":
            st.warning("El worker registró un fallo. Revise los registros del backend.")
    st.caption(
        "La barra representa clasificaciones exitosas persistidas. "
        "No sustituye el resultado completo del informe documental ni "
        "permite inferir la precisión jurídica."
    )


def _results(overview: dict, quality: dict | None) -> None:
    st.subheader("Resultados y comparación de modelos")
    if quality is None:
        st.warning("Las métricas todavía no pueden consultarse.")
        return
    completed = [
        row for row in quality["documents"]
        if row["status"] == "completed"
    ]
    if completed:
        st.dataframe(
            pd.DataFrame([
                {
                    "Tarea": row["task_id"],
                    "Plataforma": row["platform"],
                    "Modelo": row["treatment"],
                    "Repetición": row["repetition"],
                    "Exactitud NPA/PA": row["accuracy_evaluable_observed"],
                    "F1 macro NPA/PA": row["f1_macro_evaluable_observed"],
                    "Costo USD": row["cost_usd_reported"],
                }
                for row in completed
            ]),
            hide_index=True, use_container_width=True,
        )
        id_ = st.selectbox(
            "Matriz de confusión del documento",
            [row["task_id"] for row in completed],
            key="exp_result_detail",
        )
        current = next(row for row in completed if row["task_id"] == id_)
        matrix = current.get("binary_confusion_matrix_on_observed")
        if matrix:
            st.dataframe(
                pd.DataFrame.from_dict(matrix, orient="index"),
                use_container_width=True,
            )
    else:
        st.info(
            "Aún no se han completado tareas documentales del protocolo "
            "NPA/PA V2. Los resultados históricos V1 no se mezclan."
        )

    st.markdown("#### Comparación por modelo y repetición")
    st.dataframe(
        pd.DataFrame([
            {
                "Tratamiento": row["treatment"],
                "Repetición": row["repetition"],
                "Documentos": f"{row['documents_completed']}/10",
                "Cobertura": f"{row['predictions_valid']}/547",
                "Errores explícitos": row["explicit_unit_errors"],
                "F1 macro NPA/PA": (
                    row["evaluable_units"]["f1_macro"]
                    if row["is_complete"] else None
                ),
            }
            for row in quality["repetitions"]
        ]),
        hide_index=True, use_container_width=True,
    )
    st.caption(
        "F1, precisión y recall finales solo se presentan cuando la "
        "repetición está completa. No se imputan como errores las "
        "unidades de documentos que todavía no se ejecutaron."
    )


def _evidence(overview: dict, quality: dict | None) -> None:
    st.subheader("Evidencias y reproducibilidad")
    tasks = overview["tasks"]
    c1, c2 = st.columns(2)
    with c1:
        platform = st.selectbox(
            "Plataforma", ["Todas", *sorted({t["platform"] for t in tasks})],
            key="exp_evidence_platform",
        )
    with c2:
        treatment = st.selectbox(
            "Tratamiento", ["Todos", "T1", "T2", "T3"],
            key="exp_evidence_treatment",
        )
    subset = [
        row for row in tasks
        if (platform == "Todas" or row["platform"] == platform)
        and (treatment == "Todos" or row["treatment"] == treatment)
    ]
    table = pd.DataFrame([
        {
            "Tarea": row["task_id"],
            "Documento": row["platform"],
            "Modelo": row["model"],
            "Repetición": row["repetition"],
            "Estado": STATUS_TEXT.get(row["status"], row["status"]),
            "Checkpoints": row["unit_progress"]["checkpoint_successful"],
        }
        for row in subset
    ])
    st.caption(f"Mostrando {len(subset)} de las {len(tasks)} tareas V2.")
    st.dataframe(table, hide_index=True, use_container_width=True)

    st.download_button(
        "Descargar plan y estado CSV",
        data=table.to_csv(index=False).encode("utf-8-sig"),
        file_name="v2_estado_experimental.csv",
        mime="text/csv",
        disabled=table.empty,
    )
    st.download_button(
        "Descargar manifiesto JSON",
        data=json.dumps(
            overview["manifest"], ensure_ascii=False, indent=2
        ).encode("utf-8"),
        file_name="v2_manifiesto_groundtruth.json",
        mime="application/json",
    )
    if quality:
        st.download_button(
            "Descargar métricas y matrices JSON",
            data=json.dumps(
                quality, ensure_ascii=False, indent=2
            ).encode("utf-8"),
            file_name="v2_metricas_experimentales.json",
            mime="application/json",
        )
    st.caption(
        "Los archivos muestran el diseño, las métricas y la trazabilidad "
        "sin exponer etiquetas individuales del ground truth. "
        "Las trazas detalladas de agentes se consultan en Langfuse "
        "mediante el identificador de ejecución."
    )


def render_experiment_page() -> None:
    st.title("Evaluación experimental")
    st.caption(
        "Protocolo binario NPA/PA V2 · LangGraph + MCP + RAG "
        "+ OpenRouter + Langfuse"
    )
    try:
        overview = _request("GET", "overview")
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
        st.error(
            "No es posible consultar el backend experimental. "
            "Compruebe el estado de FastAPI y el corpus V2."
        )
        return

    summary = overview["progress"]
    counts = summary["counts"]
    a, b, c, d = st.columns(4)
    a.metric("Tareas completas", f"{counts['completed']}/{summary['tasks']}")
    b.metric("Pendientes", counts["pending"])
    c.metric("Fallidas", counts["failed"])
    d.metric("Costo reportado (USD)", f"{summary['reported_cost_usd']:.5f}")
    st.progress(
        counts["completed"] / max(summary["tasks"], 1),
        text="Avance formal de la campaña NPA/PA V2",
    )

    tabs = st.tabs([
        "Diseño", "Ejecución", "Seguimiento", "Resultados", "Evidencias"
    ])
    with tabs[0]:
        _design(overview)
    with tabs[1]:
        _execution(overview)
    with tabs[2]:
        _tracking(overview)
    quality = None
    try:
        quality = _request("GET", "results")
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
        pass
    with tabs[3]:
        _results(overview, quality)
    with tabs[4]:
        _evidence(overview, quality)
