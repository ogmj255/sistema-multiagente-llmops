"""Panel experimental V2 dentro de la interfaz Streamlit existente.

No lanza el LLM directamente. Todas las operaciones pasan por FastAPI
autorizada y un worker dedicado con checkpoints de LangGraph/MCP.
"""

from __future__ import annotations

import hmac
import os

import httpx
import pandas as pd
import streamlit as st

API = os.getenv(
    "API_EXPERIMENT_URL", "http://traefik/api/experimental"
).rstrip("/")


def _headers() -> dict[str, str]:
    return {
        "X-Experiment-Token": os.getenv(
            "EXPERIMENT_ADMIN_TOKEN", ""
        )
    }


def _json_request(method: str, path: str, **kwargs):
    with httpx.Client(timeout=12.0) as client:
        response = client.request(
            method, f"{API}/{path}", headers=_headers(), **kwargs
        )
        response.raise_for_status()
        return response.json()


def _submit_operator_login(expected_password: str) -> None:
    """Valida el acceso al enviar el formulario y borra el texto ingresado.

    En Streamlit los callbacks se ejecutan antes de reconstruir widgets,
    por eso es seguro limpiar la clave del campo desde este callback.
    """
    submitted = st.session_state.get("experiment_operator_password", "")
    valid = (
        isinstance(submitted, str)
        and hmac.compare_digest(submitted, expected_password)
    )
    st.session_state["experiment_authenticated"] = valid
    st.session_state["experiment_login_error"] = not valid
    st.session_state["experiment_operator_password"] = ""


def _logout_operator() -> None:
    st.session_state["experiment_authenticated"] = False
    st.session_state["experiment_login_error"] = False
    st.session_state.pop("experiment_operator_password", None)


def render_experiment_page() -> None:
    st.title("Evaluación experimental")
    st.caption(
        "Protocolo NPA/PA V2 · LangGraph + MCP + RAG + OpenRouter + Langfuse"
    )
    st.info(
        "Este módulo evalúa las mismas unidades congeladas con tres modelos "
        "y tres repeticiones. NPA y PA son clases de riesgo; no aplicable "
        "se conserva como estado de aplicabilidad."
    )

    operator_password = os.getenv("EXPERIMENT_OPERATOR_PASSWORD", "")
    token = os.getenv("EXPERIMENT_ADMIN_TOKEN", "")
    if not operator_password or not token:
        st.warning(
            "Panel administrativo deshabilitado. Configure "
            "EXPERIMENT_OPERATOR_PASSWORD y EXPERIMENT_ADMIN_TOKEN "
            "en el entorno antes de acceder."
        )
        return

    if not st.session_state.get("experiment_authenticated", False):
        with st.form("experiment_operator_login"):
            st.text_input(
                "Contraseña del investigador",
                type="password",
                key="experiment_operator_password",
            )
            st.form_submit_button(
                "Acceder al panel",
                on_click=_submit_operator_login,
                args=(operator_password,),
            )
        if st.session_state.get("experiment_login_error", False):
            st.error("Contraseña incorrecta.")
        else:
            st.caption("Acceso restringido a la persona investigadora.")
        return

    # No mantener un campo con credenciales visibles al presentar
    # capturas o demostrar los resultados ante el tribunal.
    st.button("Cerrar sesión", on_click=_logout_operator)

    try:
        overview = _json_request("GET", "overview")
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as exc:
        st.error(
            "El servicio experimental no está disponible. "
            f"Detalle técnico: {type(exc).__name__}."
        )
        return

    manifest = overview["manifest"]
    progress = overview["progress"]
    counts = progress["counts"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tareas completadas", f"{counts['completed']}/90")
    col2.metric("Pendientes", counts["pending"])
    col3.metric("Fallidas", counts["failed"])
    col4.metric(
        "Costo reportado (USD)",
        f"{progress['reported_cost_usd']:.5f}",
    )
    st.progress(counts["completed"] / max(progress["tasks"], 1))
    st.caption(
        f"Huella de la referencia binaria V2: "
        f"{manifest['binary_v2_fingerprint']}"
    )

    tab_setup, tab_queue, tab_evidence = st.tabs([
        "Diseño experimental", "Ejecución y seguimiento", "Evidencias"
    ])
    with tab_setup:
        st.subheader("Configuración metodológica congelada")
        c1, c2, c3 = st.columns(3)
        c1.metric("Unidades contractuales", manifest["units"])
        c2.metric("NPA", manifest["classification_labels"]["NPA"])
        c3.metric("PA", manifest["classification_labels"]["PA"])
        st.caption(
            "Las 74 unidades no aplicables no pertenecen a NPA/PA. "
            "La versión V1 permanece archivada y no se suma a la campaña V2."
        )
        st.write(
            "10 documentos SaaS · 3 modelos de lenguaje · "
            "3 repeticiones por combinación · 90 tareas documentales."
        )
        st.warning(
            "En esta evaluación se emplean fragmentos congelados. "
            "El Web Scraper y el Preprocesador no se vuelven a ejecutar: "
            "los agentes jurídico, analizador e informes sí se invocan "
            "mediante el orquestador LangGraph y MCP."
        )

    with tab_queue:
        st.subheader("Seleccionar una ejecución")
        tasks = overview["tasks"]
        options = {
            (
                f"{t['task_id']} · {t['platform']} · "
                f"{t['treatment']} · R{t['repetition']} · "
                f"{t['unit_count']} unidades · {t['status']}"
            ): t for t in tasks
        }
        selected_text = st.selectbox(
            "Documento, tratamiento y repetición",
            list(options),
        )
        selected = options[selected_text]
        st.caption(
            f"Modelo: {selected['model']}. "
            "Cada combinación tiene una tarea independiente y "
            "no reutiliza predicciones de otros modelos o repeticiones."
        )
        unit_progress = selected.get("unit_progress") or {
            "total": selected["unit_count"],
            "checkpoint_successful": 0,
            "checkpoint_failed": 0,
            "remaining": selected["unit_count"],
        }
        recorded = unit_progress["checkpoint_successful"]
        total = unit_progress["total"]
        st.progress(
            recorded / max(total, 1),
            text=f"Cláusulas verificadas por checkpoint: {recorded}/{total}",
        )
        p1, p2, p3 = st.columns(3)
        p1.metric("Guardadas", recorded)
        p2.metric("Pendientes", unit_progress["remaining"])
        p3.metric("Errores registrados", unit_progress["checkpoint_failed"])
        job_status = selected.get("job_status")
        if job_status in {"queued", "running", "failed", "completed"}:
            st.caption(f"Estado del worker: {job_status}")
        else:
            st.caption("No hay una tarea del worker en curso.")

        enabled = overview.get("execution_enabled", False)
        if not enabled:
            st.info(
                "La ejecución de pago está deshabilitada. "
                "Se puede supervisar la campaña sin realizar "
                "llamadas a OpenRouter."
            )
        else:
            st.warning(
                "La facturación del proveedor no tiene un límite "
                "duro por documento. El costo dependerá del modelo, "
                "las cláusulas y los posibles reintentos."
            )

        # No solicitar consentimiento a un pago cuando el módulo
        # está expresamente deshabilitado por configuración.
        authorized = False
        if enabled:
            authorized = st.checkbox(
                "Autorizo expresamente el procesamiento completo "
                "de esta tarea y sus costos de OpenRouter.",
                key="experiment_paid_authorization",
                value=False,
            )
        else:
            st.caption(
                "Modo de consulta: no se solicitan autorizaciones "
                "ni se permiten inferencias con costo."
            )
        if st.button(
            "Iniciar tarea experimental",
            disabled=not enabled or not authorized
                or selected["status"] == "completed",
            type="primary",
        ):
            try:
                result = _json_request(
                    "POST", "jobs",
                    json={
                        "task_id": selected["task_id"],
                        "accept_paid_execution": True,
                    },
                )
                st.success(
                    f"Tarea {result['task_id']} añadida a la cola. "
                    "Se ejecutará en el worker experimental."
                )
                st.rerun()
            except httpx.HTTPStatusError as exc:
                st.error(
                    f"No se pudo programar la tarea "
                    f"(HTTP {exc.response.status_code}). "
                    "Revise que no exista una ejecución activa."
                )
            except httpx.RequestError:
                st.error("No se pudo contactar con el backend.")
        if st.button("Actualizar seguimiento"):
            st.rerun()

        jobs = overview.get("jobs", [])
        if jobs:
            st.subheader("Últimas tareas en la cola")
            st.dataframe(pd.DataFrame(jobs), hide_index=True)
        else:
            st.caption("Aún no existen tareas solicitadas desde la interfaz.")

    with tab_evidence:
        st.subheader("Trazabilidad de la evaluación")
        st.write(
            "Cada tarea conserva su ID, modelo, repetición, "
            "huella del corpus, unidades procesadas, checkpoints, "
            "costo reportado y trazas del flujo multiagente."
        )
        st.dataframe(
            pd.DataFrame([
                {
                    "Tarea": task["task_id"],
                    "Plataforma": task["platform"],
                    "Tratamiento": task["treatment"],
                    "Repetición": task["repetition"],
                    "Estado": task["status"],
                }
                for task in tasks
            ]),
            hide_index=True,
        )
        st.caption(
            "Las métricas de precisión, recall y F1 se calculan "
            "posteriormente a partir del ground truth. Nunca "
            "se incluyen etiquetas humanas en el prompt."
        )
        try:
            quality = _json_request("GET", "results")
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError):
            st.warning("No se pueden consultar las métricas experimentales.")
            return

        completed = [
            row for row in quality["documents"]
            if row["status"] == "completed"
        ]
        if completed:
            st.subheader("Calidad binaria por documento completado")
            st.dataframe(
                pd.DataFrame([
                    {
                        "Tarea": row["task_id"],
                        "Plataforma": row["platform"],
                        "Tratamiento": row["treatment"],
                        "Repetición": row["repetition"],
                        "Clasificadas": row["predictions_valid"],
                        "Exactitud NPA/PA": row["accuracy_evaluable_observed"],
                        "F1 macro NPA/PA": row["f1_macro_evaluable_observed"],
                        "Costo USD": row["cost_usd_reported"],
                    } for row in completed
                ]),
                hide_index=True,
            )
            chosen = st.selectbox(
                "Detalle de matriz de confusión",
                [r["task_id"] for r in completed],
            )
            entry = next(
                r for r in completed if r["task_id"] == chosen
            )
            matrix = entry.get("binary_confusion_matrix_on_observed")
            if matrix:
                st.dataframe(pd.DataFrame.from_dict(matrix, orient="index"))
            st.caption(
                "Los resultados del protocolo anterior (tres categorías) "
                "se conservan como históricos y NO se mezclan aquí."
            )
        else:
            st.info(
                "Aún no existen documentos completados en el protocolo "
                "binario V2. Las ejecuciones antiguas no se reutilizan."
            )

        st.subheader("Evolución por tratamiento y repetición")
        st.dataframe(pd.DataFrame([
            {
                "Modelo": row["treatment"],
                "Repetición": row["repetition"],
                "Documentos completos": row["documents_completed"],
                "Pendientes": row["documents_pending"],
                "Predicciones registradas": row["predictions_valid"],
                "Errores explícitos": row["explicit_unit_errors"],
                "F1 final": (
                    row["evaluable_units"]["f1_macro"]
                    if row["is_complete"] else None
                ),
            }
            for row in quality["repetitions"]
        ]), hide_index=True)
