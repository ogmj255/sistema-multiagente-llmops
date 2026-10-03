import os
from datetime import datetime
from html import escape
from urllib.parse import urlparse
from uuid import UUID

import httpx
import pandas as pd
import streamlit as st

API_ANALYSIS_URL = os.getenv(
    "API_ANALYSIS_URL",
    "http://traefik/api/analisis",
)

API_BASE_URL = API_ANALYSIS_URL.rsplit("/", 1)[0]
API_REPORT_JSON_URL = f"{API_BASE_URL}/reportes/json"
API_REPORT_PDF_URL = f"{API_BASE_URL}/reportes/pdf"
API_LLMOPS_URL = f"{API_BASE_URL}/llmops"

CLASSIFICATION_LABELS = {
    "not_potentially_abusive": "No potencialmente abusiva",
    "potentially_abusive": "Potencialmente abusiva",
    "strong_indications_of_abusiveness": (
        "Indicios fuertes de abusividad"
    ),
}

EVIDENCE_LABELS = {
    "sufficient": "Suficiente",
    "partial": "Parcial",
    "insufficient": "Insuficiente",
}


def is_valid_url(value: str) -> bool:
    """Comprueba que la entrada sea una URL HTTP o HTTPS válida."""
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_valid_execution_id(value: str) -> bool:
    """Comprueba que el identificador tenga formato UUID."""

    try:
        UUID(value)
    except ValueError:
        return False

    return True


def render_plain_text(
    value: object,
    fallback: str = "No disponible.",
    css_class: str = "plain-contract-text",
) -> None:
    """Muestra texto sin interpretarlo como Markdown o LaTeX."""

    content = (
        str(value).strip()
        if value is not None
        else ""
    )

    if not content:
        content = fallback

    st.markdown(
        (
            f'<div class="{css_class}">'
            f"{escape(content)}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_legal_basis(
    legal_basis: list[dict[str, object]],
) -> None:
    """Muestra las fuentes jurídicas usadas por el analizador."""

    if not legal_basis:
        st.write("No se seleccionaron fundamentos jurídicos.")
        return

    for index, evidence in enumerate(
        legal_basis,
        start=1,
    ):
        title = evidence.get("title") or "Fuente jurídica"

        with st.expander(
            f"Fundamento jurídico {index}: {title}"
        ):
            citation = evidence.get("official_citation")
            issuing_body = evidence.get("issuing_body")
            jurisdiction = evidence.get("jurisdiction")
            document_type = evidence.get("document_type")
            binding_level = evidence.get("binding_level")
            status = evidence.get("status")
            content = evidence.get("content")
            source_url = evidence.get("source_url")

            if citation:
                st.write(
                    f"**Citación oficial:** {citation}"
                )

            if issuing_body:
                st.write(
                    f"**Organismo emisor:** {issuing_body}"
                )

            if jurisdiction:
                st.write(
                    f"**Jurisdicción:** {jurisdiction}"
                )

            if document_type:
                st.write(
                    f"**Tipo de documento:** {document_type}"
                )

            if binding_level:
                st.write(
                    f"**Nivel vinculante:** {binding_level}"
                )

            if status:
                st.write(
                    f"**Estado:** {status}"
                )

            if content:
                st.markdown("**Contenido recuperado:**")
                render_plain_text(content)

            if source_url:
                st.markdown(
                    f"[Consultar fuente]({source_url})"
                )


def render_clause(
    item: dict[str, object],
) -> None:
    """Muestra un resultado individual del analizador legal."""

    clause_order = item.get("clause_order", "-")
    response_status = item.get("status")

    if response_status != "success":
        with st.expander(
            f"Cláusula {clause_order} — Error de análisis"
        ):
            st.error(
                item.get("error")
                or "No fue posible analizar esta cláusula."
            )
        return

    assessment = item.get("result")

    if not isinstance(assessment, dict):
        return

    category = assessment.get("category")
    clause_type = assessment.get("clause_type")
    target = assessment.get("target")
    consequence = assessment.get("consequence")
    classification = assessment.get("classification")
    analysis_status = assessment.get("analysis_status")

    category_label = str(category or "Sin categoría")

    if analysis_status == "not_applicable":
        status_label = "No aplicable"
    else:
        status_label = CLASSIFICATION_LABELS.get(
            str(classification),
            str(classification),
        )

    status_key = (
        "not_applicable"
        if analysis_status == "not_applicable"
        else str(classification)
    )

    status_styles = {
        "not_potentially_abusive": (
            "#EAF7EE",
            "#A7D7B5",
            "#2F6B45",
        ),
        "potentially_abusive": (
            "#FFF6E5",
            "#E9D29B",
            "#7A5A12",
        ),
        "strong_indications_of_abusiveness": (
            "#FDECEC",
            "#E5B6B6",
            "#8A3D3D",
        ),
        "not_applicable": (
            "#F1F3F5",
            "#D5D9DE",
            "#5F6B76",
        ),
    }

    (
        status_background,
        status_border,
        status_text,
    ) = status_styles.get(
        status_key,
        status_styles["not_applicable"],
    )

    with st.expander(
        f"Cláusula {clause_order} — {category_label}"
    ):
        st.markdown(
            f"""
            <div style="
                display:flex;
                align-items:center;
                gap:0.55rem;
                background:{status_background};
                border-left:4px solid {status_border};
                border-radius:6px;
                padding:0.65rem 0.8rem;
                margin-bottom:0.9rem;
                color:{status_text};
                font-weight:600;
            ">
                <span style="
                    width:0.55rem;
                    height:0.55rem;
                    border-radius:50%;
                    background:{status_text};
                    display:inline-block;
                    flex-shrink:0;
                "></span>
                <span>{status_label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


        clause_type_text = escape(
            str(clause_type or "No determinado")
        )
        target_text = escape(
            str(target or "No determinado")
        )
        consequence_text = escape(
            str(consequence or "No especificada")
        )

        metadata_html = (
            '<div class="clause-metadata">'
            '<div class="metadata-item">'
            '<div class="metadata-label">Tipo contractual</div>'
            f'<div class="metadata-value">{clause_type_text}</div>'
            '</div>'
            '<div class="metadata-item">'
            '<div class="metadata-label">Dirigido a</div>'
            f'<div class="metadata-value">{target_text}</div>'
            '</div>'
            '<div class="metadata-item metadata-full">'
            '<div class="metadata-label">Consecuencia</div>'
            f'<div class="metadata-value">{consequence_text}</div>'
            '</div>'
            '</div>'
        )

        st.markdown(
            metadata_html,
            unsafe_allow_html=True,
        )

        st.markdown("#### Fragmento analizado")
        render_plain_text(
            assessment.get("relevant_fragment"),
            css_class=(
                "plain-contract-text "
                "contract-fragment"
            ),
        )

        st.markdown("#### Justificación")
        st.write(
            assessment.get("justification")
            or "No disponible."
        )

        recommendation = (
            assessment.get("recommendation")
            or "No disponible."
        )

        recommendation_text = escape(
            str(recommendation)
        )

        st.markdown(
            f"""
            <div class="recommendation-box">
                <div class="recommendation-title">
                    Recomendaci\u00f3n
                </div>
                <div>{recommendation_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        evidence = assessment.get(
            "evidence_sufficiency"
        )

        st.write(
            "**Suficiencia de evidencia jurídica:** "
            + EVIDENCE_LABELS.get(
                str(evidence),
                str(evidence),
            )
        )

        legal_basis = assessment.get(
            "legal_basis",
            [],
        )

        valid_legal_basis = (
            [
                item
                for item in legal_basis
                if isinstance(item, dict)
            ]
            if isinstance(legal_basis, list)
            else []
        )

        if valid_legal_basis:
            st.markdown(
                "#### Fundamento jur\u00eddico"
            )
            render_legal_basis(
                valid_legal_basis
            )
        else:
            st.markdown(
                (
                    '<div class="no-legal-basis">'
                    "Sin fundamento jur\u00eddico recuperado"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )


def prepare_report_downloads(
    report: dict[str, object],
) -> None:
    """Solicita al backend las exportaciones del informe."""

    try:
        json_response = httpx.post(
            API_REPORT_JSON_URL,
            json=report,
            timeout=30.0,
        )
        json_response.raise_for_status()

        pdf_response = httpx.post(
            API_REPORT_PDF_URL,
            json=report,
            timeout=30.0,
        )
        pdf_response.raise_for_status()

        st.session_state.report_json = (
            json_response.content
        )
        st.session_state.report_pdf = (
            pdf_response.content
        )

    except httpx.HTTPError:
        st.session_state.pop(
            "report_json",
            None,
        )
        st.session_state.pop(
            "report_pdf",
            None,
        )


def load_persisted_analysis(
    execution_id: str,
) -> bool:
    """Recupera del backend un análisis persistido."""

    try:
        response = httpx.get(
            f"{API_ANALYSIS_URL}/{execution_id}",
            timeout=30.0,
        )

        if response.status_code == 404:
            st.session_state.pop(
                "analysis_result",
                None,
            )
            st.session_state.pop(
                "report_json",
                None,
            )
            st.session_state.pop(
                "report_pdf",
                None,
            )
            st.error(
                "No se encontró un análisis asociado "
                "al identificador indicado."
            )
            return True

        response.raise_for_status()

        analysis_result = response.json()
        st.session_state.analysis_result = (
            analysis_result
        )

        report = analysis_result.get("report")

        if isinstance(report, dict):
            prepare_report_downloads(
                report
            )

        return True

    except httpx.HTTPStatusError as error:
        st.error(
            "El backend no pudo recuperar el análisis. "
            f"Código HTTP: {error.response.status_code}"
        )
        return True

    except httpx.RequestError:
        st.error(
            "No fue posible establecer comunicación "
            "para recuperar el análisis almacenado."
        )
        return False

def get_analysis_execution_detail(
    execution_id: str,
) -> dict[str, object] | None:
    """Recupera los datos contractuales de una ejecución."""

    try:
        response = httpx.get(
            f"{API_ANALYSIS_URL}/{execution_id}",
            timeout=10.0,
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()

        data = response.json()

        return (
            data
            if isinstance(data, dict)
            else None
        )

    except httpx.HTTPError:
        return None

def load_llmops_dashboard(
    limit: int = 50,
) -> dict[str, object] | None:
    """Recupera las métricas históricas del dashboard LLMOps."""

    try:
        response = httpx.get(
            API_LLMOPS_URL,
            params={
                "limit": limit,
            },
            timeout=10.0,
        )
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            return None

        return data

    except httpx.HTTPStatusError as error:
        st.error(
            "El backend no pudo recuperar las métricas LLMOps. "
            f"Código HTTP: {error.response.status_code}"
        )
        return None

    except httpx.RequestError:
        st.error(
            "No fue posible establecer comunicación "
            "con el servicio de monitoreo LLMOps."
        )
        return None


def render_analysis_results(
    data: dict[str, object],
) -> None:
    """Muestra el resumen y los resultados recibidos."""

    st.divider()
    st.subheader("Resultados del análisis")
    if data.get("reused_analysis") is True:
        execution_id = data.get("execution_id")
        reused_at = data.get("reused_analysis_at")

        message = (
            "Esta versión de los Términos de Servicio "
            "ya fue analizada anteriormente. "
            "Se muestran los resultados almacenados."
        )

        if isinstance(reused_at, str):
            try:
                reused_datetime = pd.to_datetime(
                    reused_at,
                    utc=True,
                )

                reused_datetime = reused_datetime.tz_convert(
                    "-05:00"
                )

                formatted_date = reused_datetime.strftime(
                    "%d/%m/%Y %H:%M:%S"
                )
            except ValueError:
                formatted_date = reused_at

            message += (
                f"\n\nFecha del análisis: "
                f"{formatted_date} UTC-5"
            )

        if execution_id:
            message += f"\n\nIdentificador: {execution_id}"

        st.info(message)

    platform = data.get("platform")
    source_url = data.get("source_url")

    platform_text = escape(
        str(platform or "No disponible")
    )
    source_url_text = escape(
        str(source_url or "No disponible")
    )
    source_url_href = escape(
        str(source_url or "#"),
        quote=True,
    )

    source_html = (
        '<div class="analysis-source-card">'
        '<div class="analysis-source-item">'
        '<div class="analysis-source-label">Plataforma</div>'
        f'<div class="analysis-source-value">{platform_text}</div>'
        '</div>'
        '<div class="analysis-source-item analysis-source-url">'
        '<div class="analysis-source-label">URL analizada</div>'
        f'<div class="analysis-source-value">'
        f'<a href="{source_url_href}" target="_blank">'
        f'{source_url_text}</a></div>'
        '</div>'
        '</div>'
    )

    st.markdown(
        source_html,
        unsafe_allow_html=True,
    )

    failed_count = data.get("failed_clauses", 0)

    metric_columns = st.columns(4)

    metric_cards = [
        (
            "Cláusulas",
            data.get("total_clauses", 0),
            "#F5F7FA",
            "#D9E0E7",
            "#475569",
        ),
        (
            "Analizadas",
            data.get("analyzed_clauses", 0),
            "#EEF5FB",
            "#C9DCEB",
            "#3E6685",
        ),
        (
            "Exitosas",
            data.get("successful_clauses", 0),
            "#EAF7EE",
            "#B8DEC3",
            "#2F6B45",
        ),
        (
            "Fallidas",
            failed_count,
            "#FDECEC" if failed_count else "#F5F7FA",
            "#E5B6B6" if failed_count else "#D9E0E7",
            "#8A3D3D" if failed_count else "#64748B",
        ),
    ]

    for column, card in zip(
        metric_columns,
        metric_cards,
        strict=True,
    ):
        (
            label,
            value,
            background,
            border,
            text_color,
        ) = card

        metric_html = (
            f'<div class="analysis-metric-card" '
            f'style="background:{background};'
            f'border-color:{border};">'
            f'<div class="analysis-metric-label" '
            f'style="color:{text_color};">{label}</div>'
            f'<div class="analysis-metric-value" '
            f'style="color:{text_color};">{value}</div>'
            '</div>'
        )

        column.markdown(
            metric_html,
            unsafe_allow_html=True,
        )

    report = data.get("report")

    if isinstance(report, dict):
        classification_summary = report.get(
            "classification_summary",
            {},
        )

        if isinstance(classification_summary, dict):
            st.markdown(
                '<div style="height:0.35rem"></div>',
                unsafe_allow_html=True,
            )
            st.markdown("### Resumen de clasificaciones")

            classification_columns = st.columns(4)

            classification_cards = [
                (
                    "not_potentially_abusive",
                    "No potencialmente abusivas",
                    "#EAF7EE",
                    "#A7D7B5",
                    "#2F6B45",
                ),
                (
                    "potentially_abusive",
                    "Potencialmente abusivas",
                    "#FFF6E5",
                    "#E9D29B",
                    "#7A5A12",
                ),
                (
                    "strong_indications_of_abusiveness",
                    "Indicios fuertes de abusividad",
                    "#FDECEC",
                    "#E5B6B6",
                    "#8A3D3D",
                ),
                (
                    "not_applicable",
                    "No aplicables",
                    "#F1F3F5",
                    "#D5D9DE",
                    "#5F6B76",
                ),
            ]

            for column, card in zip(
                classification_columns,
                classification_cards,
                strict=True,
            ):
                (
                    key,
                    label,
                    background,
                    border,
                    text_color,
                ) = card

                value = classification_summary.get(
                    key,
                    0,
                )

                column.markdown(
                    f"""
                    <div style="
                        background:{background};
                        border:1px solid {border};
                        border-radius:10px;
                        padding:1rem 0.9rem;
                        min-height:118px;
                        display:flex;
                        flex-direction:column;
                        justify-content:center;
                        align-items:center;
                        text-align:center;
                    ">
                        <div style="
                            font-size:1.85rem;
                            font-weight:700;
                            line-height:1;
                            color:{text_color};
                            margin-bottom:0.55rem;
                        ">{value}</div>
                        <div style="
                            font-size:0.9rem;
                            font-weight:600;
                            line-height:1.3;
                            color:{text_color};
                        ">{label}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        report_json = st.session_state.get(
            "report_json"
        )
        report_pdf = st.session_state.get(
            "report_pdf"
        )

        if (
            isinstance(report_json, bytes)
            and isinstance(report_pdf, bytes)
        ):
            st.markdown("### Descargar informe")

            download_columns = st.columns(2)

            download_columns[0].download_button(
                "Descargar JSON",
                data=report_json,
                file_name="informe_analisis.json",
                mime="application/json",
                use_container_width=True,
            )

            download_columns[1].download_button(
                "Descargar PDF",
                data=report_pdf,
                file_name="informe_analisis.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    results = data.get("results", [])

    if not isinstance(results, list):
        return

    st.markdown("### Cláusulas analizadas")

    if not results:
        st.info(
            "No se obtuvieron cláusulas para mostrar."
        )
        return

    for item in results:
        if isinstance(item, dict):
            render_clause(item)


def render_llmops_dashboard(
    data: dict[str, object],
) -> None:
    """Muestra el dashboard LLMOps organizado por vistas."""

    executions = data.get("executions", [])

    if not isinstance(executions, list):
        executions = []

    valid_executions = [
        execution
        for execution in executions
        if isinstance(execution, dict)
    ]

    if not valid_executions:
        st.info(
            "Todavía no existen ejecuciones persistidas "
            "para construir el dashboard."
        )
        return

    frame = pd.DataFrame(valid_executions)

    frame["created_at"] = (
        pd.to_datetime(
            frame["created_at"],
            errors="coerce",
            utc=True,
        )
        .dt.tz_convert("-05:00")
    )

    numeric_columns = (
        "execution_number",
        "duration_ms",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_usd",
        "error_count",
        "llm_invocation_count",
    )

    for column in numeric_columns:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

    frame["platform"] = (
        frame["platform"]
        .fillna("No disponible")
    )

    frame["source_url"] = (
        frame["source_url"]
        .fillna("")
    )
    frame["provider"] = (
        frame["provider"]
        .fillna("No disponible")
    )

    frame["model"] = (
        frame["model"]
        .fillna("No disponible")
    )

    frame["provider_display"] = (
        frame["provider"]
        .replace(
            {
                "openrouter": "OpenRouter",
            }
        )
    )

    frame["model_display"] = (
        frame["model"]
        .replace(
            {
                "not_recorded": "No registrado",
            }
        )
    )
    
    frame = frame.sort_values(
        "created_at"
    ).reset_index(drop=True)

    frame["execution_label"] = frame[
        "execution_number"
    ].apply(
        lambda value: (
            f"E{int(value)}"
            if pd.notna(value)
            else "E—"
        )
    )
    frame["latency_seconds"] = (
        frame["duration_ms"] / 1000
    )

    status_labels = {
        "success": "Exitosa",
        "partial": "Parcial",
        "error": "Error",
    }

    frame["status_label"] = (
        frame["status"]
        .map(status_labels)
        .fillna(frame["status"])
    )

    app_url = st.context.url

    # Estilos exclusivos del dashboard.
    st.markdown(
        """
        <style>
        .llmops-section {
            margin-top: 1.4rem;
            margin-bottom: 0.8rem;
        }

        .llmops-section-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: #252525;
        }

        .llmops-section-description {
            color: #64748B;
            font-size: 0.86rem;
            margin-top: 0.15rem;
        }

        .execution-info {
            background: #ffffff;
            border: 1px solid #E2E8F0;
            border-left: 4px solid #8f1d2c;
            border-radius: 8px;
            padding: 0.9rem 1rem;
            margin: 0.5rem 0 1rem 0;
        }

        .execution-info-platform {
            font-size: 1.1rem;
            font-weight: 700;
            color: #1F2937;
        }

        .execution-info-id {
            font-size: 0.78rem;
            color: #64748B;
            margin-top: 0.25rem;
            overflow-wrap: anywhere;
        }

        .history-wrapper {
            width: 100%;
            margin-top: 0.6rem;
        }

        .history-table {
            width: 100%;
            table-layout: fixed;
            border-collapse: collapse;
            background: #ffffff;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            overflow: hidden;
        }

        .history-table th {
            background: #F8FAFC;
            color: #475569;
            font-size: 0.76rem;
            font-weight: 700;
            text-align: left;
            padding: 0.7rem 0.55rem;
            border-bottom: 1px solid #E2E8F0;
        }

        .history-table td {
            color: #334155;
            font-size: 0.79rem;
            padding: 0.68rem 0.55rem;
            border-bottom: 1px solid #F1F5F9;
            vertical-align: middle;
            overflow-wrap: anywhere;
        }

        .history-table tr:last-child td {
            border-bottom: none;
        }

        .history-table a {
            color: #8f1d2c;
            font-weight: 600;
            text-decoration: none;
        }

        .history-table a:hover {
            text-decoration: underline;
        }

        .history-secondary {
            font-size: 0.72rem;
            color: #64748B;
            margin-top: 0.18rem;
            line-height: 1.25;
        }
        .status-badge {
            display: inline-block;
            border-radius: 999px;
            padding: 0.22rem 0.55rem;
            font-size: 0.72rem;
            font-weight: 700;
            white-space: nowrap;
        }

        .status-success {
            background: #ECFDF5;
            color: #047857;
        }

        .status-partial {
            background: #FFF7ED;
            color: #C2410C;
        }

        .status-error {
            background: #FEF2F2;
            color: #B91C1C;
        }

        .history-table th:nth-child(1),
        .history-table td:nth-child(1) {
            width: 18%;
        }

        .history-table th:nth-child(2),
        .history-table td:nth-child(2) {
            width: 17%;
        }

        .history-table th:nth-child(3),
        .history-table td:nth-child(3) {
            width: 11%;
        }

        .history-table th:nth-child(4),
        .history-table td:nth-child(4) {
            width: 11%;
        }

        .history-table th:nth-child(5),
        .history-table td:nth-child(5) {
            width: 11%;
        }

        .history-table th:nth-child(6),
        .history-table td:nth-child(6) {
            width: 12%;
        }

        .history-table th:nth-child(7),
        .history-table td:nth-child(7) {
            width: 10%;
        }

        .history-table th:nth-child(8),
        .history-table td:nth-child(8) {
            width: 10%;
        }

        .history-table th:nth-child(9),
        .history-table td:nth-child(9) {
            width: 10%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    summary_tab, history_tab, detail_tab = st.tabs(
        [
            "Resumen",
            "Historial",
            "Detalle de ejecución",
        ]
    )

    with summary_tab:
        st.markdown(
            """
            <div class="llmops-section">
                <div class="llmops-section-title">
                    Indicadores generales
                </div>
                <div class="llmops-section-description">
                    Estado acumulado de las ejecuciones registradas.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        total_executions = len(frame)

        average_latency = (
            frame["latency_seconds"]
            .fillna(0)
            .mean()
        )

        total_tokens = int(
            frame["total_tokens"]
            .fillna(0)
            .sum()
        )

        reported_costs = frame[
            "cost_usd"
        ].dropna()

        total_cost = (
            float(reported_costs.sum())
            if not reported_costs.empty
            else None
        )

        executions_with_errors = int(
            (
                frame["error_count"]
                .fillna(0)
                > 0
            ).sum()
        )

        error_rate = (
            executions_with_errors
            / total_executions
            * 100
            if total_executions
            else 0.0
        )

        metric_columns = st.columns(5)

        metric_columns[0].metric(
            "Ejecuciones",
            f"{total_executions:,}",
        )

        metric_columns[1].metric(
            "Latencia promedio",
            f"{average_latency:.2f} s",
        )

        metric_columns[2].metric(
            "Tokens totales",
            f"{total_tokens:,}",
        )

        metric_columns[3].metric(
            "Costo acumulado",
            (
                f"${total_cost:.6f}"
                if total_cost is not None
                else "No reportado"
            ),
        )

        metric_columns[4].metric(
            "Tasa de error",
            f"{error_rate:.2f} %",
        )

        st.markdown(
            """
            <div class="llmops-section">
                <div class="llmops-section-title">
                    Comportamiento de las ejecuciones
                </div>
                <div class="llmops-section-description">
                    Evolución de latencia, consumo, costo y estado.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        first_chart_row = st.columns(2)

        # -----------------------------------------------------
        # LATENCIA
        # -----------------------------------------------------

        with first_chart_row[0]:
            st.markdown("#### Latencia por ejecución")

            latency_chart = (
                frame[
                    [
                        "execution_label",
                        "latency_seconds",
                    ]
                ]
                .set_index("execution_label")
                .rename(
                    columns={
                        "latency_seconds": (
                            "Latencia (s)"
                        ),
                    }
                )
            )

            if len(frame) >= 3:
                st.line_chart(
                    latency_chart,
                    height=300,
                )
            else:
                st.bar_chart(
                    latency_chart,
                    height=300,
                )

            if len(frame) == 1:
                st.caption(
                    "Existe una sola ejecución; "
                    "se muestra como barra para evitar "
                    "una serie temporal sin trayectoria."
                )
            elif len(frame) == 2:
                st.caption(
                    "Con dos ejecuciones se utiliza "
                    "comparación mediante barras."
                )
            else:
                st.caption(
                    "La línea permite observar la "
                    "evolución de la latencia."
                )

        # -----------------------------------------------------
        # TOKENS
        # -----------------------------------------------------

        with first_chart_row[1]:
            st.markdown("#### Consumo de tokens")

            tokens_chart = (
                frame[
                    [
                        "execution_label",
                        "prompt_tokens",
                        "completion_tokens",
                    ]
                ]
                .set_index("execution_label")
                .rename(
                    columns={
                        "prompt_tokens": "Entrada",
                        "completion_tokens": "Salida",
                    }
                )
            )

            st.bar_chart(
                tokens_chart,
                stack=True,
                height=300,
            )

            st.caption(
                "Compara los tokens enviados al modelo "
                "con los tokens generados."
            )

        second_chart_row = st.columns(2)

        # -----------------------------------------------------
        # COSTO
        # -----------------------------------------------------

        with second_chart_row[0]:
            st.markdown("#### Costo por ejecución")

            cost_frame = frame[
                frame["cost_usd"].notna()
            ]

            if not cost_frame.empty:
                cost_chart = (
                    cost_frame[
                        [
                            "execution_label",
                            "cost_usd",
                        ]
                    ]
                    .set_index("execution_label")
                    .rename(
                        columns={
                            "cost_usd": "Costo USD",
                        }
                    )
                )

                st.bar_chart(
                    cost_chart,
                    height=300,
                )

                st.caption(
                    "Costo reportado para cada ejecución."
                )
            else:
                st.info(
                    "El proveedor no reportó costos "
                    "para las ejecuciones registradas."
                )

        # -----------------------------------------------------
        # ESTADO
        # -----------------------------------------------------

        with second_chart_row[1]:
            st.markdown("#### Estado de las ejecuciones")

            if len(frame) == 1:
                only_execution = frame.iloc[0]

                st.metric(
                    "Estado registrado",
                    str(
                        only_execution[
                            "status_label"
                        ]
                    ),
                )

                st.caption(
                    "Se mostrará una distribución "
                    "cuando existan varias ejecuciones."
                )

            else:
                status_chart = (
                    frame["status_label"]
                    .value_counts()
                    .rename_axis("Estado")
                    .reset_index(
                        name="Ejecuciones"
                    )
                )

                st.bar_chart(
                    status_chart,
                    x="Estado",
                    y="Ejecuciones",
                    horizontal=True,
                    height=300,
                )

                st.caption(
                    "Distribución de ejecuciones "
                    "exitosas, parciales y fallidas."
                )

    with history_tab:
        st.markdown(
            """
            <div class="llmops-section">
                <div class="llmops-section-title">
                    Historial de ejecuciones
                </div>
                <div class="llmops-section-description">
                    Consulte los análisis registrados sin
                    sobrecargar la vista principal.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        filter_columns = st.columns(2)

        platform_options = [
            "Todas"
        ] + sorted(
            str(platform)
            for platform in frame[
                "platform"
            ].dropna().unique()
        )

        selected_platform = (
            filter_columns[0].selectbox(
                "Plataforma",
                options=platform_options,
                key="history_platform_filter",
            )
        )

        status_options = [
            "Todos",
            "Exitosa",
            "Parcial",
            "Error",
        ]

        selected_status = (
            filter_columns[1].selectbox(
                "Estado",
                options=status_options,
                key="history_status_filter",
            )
        )

        history_frame = frame.copy()

        if selected_platform != "Todas":
            history_frame = history_frame[
                history_frame["platform"]
                == selected_platform
            ]

        if selected_status != "Todos":
            history_frame = history_frame[
                history_frame["status_label"]
                == selected_status
            ]

        history_frame = history_frame.sort_values(
            "created_at",
            ascending=False,
        ).reset_index(drop=True)

        if history_frame.empty:
            st.info(
                "No existen ejecuciones que coincidan "
                "con los filtros seleccionados."
            )

        else:
            PAGE_SIZE = 10

            total_rows = len(history_frame)

            total_pages = max(
                1,
                (
                    total_rows
                    + PAGE_SIZE
                    - 1
                )
                // PAGE_SIZE,
            )

            pagination_columns = st.columns(
                [3, 1]
            )

            pagination_columns[0].caption(
                (
                    "1 ejecución encontrada."
                    if total_rows == 1
                    else f"{total_rows} ejecuciones encontradas."
                )
            )

            if total_pages > 1:
                selected_page = (
                    pagination_columns[1]
                    .selectbox(
                        "Página",
                        options=list(
                            range(
                                1,
                                total_pages + 1,
                            )
                        ),
                        format_func=lambda page: (
                            f"{page} de {total_pages}"
                        ),
                        key="history_page",
                    )
                )
            else:
                selected_page = 1

            start = (
                selected_page - 1
            ) * PAGE_SIZE

            end = start + PAGE_SIZE

            visible_history = history_frame.iloc[
                start:end
            ]

            rows: list[str] = []

            for _, row in visible_history.iterrows():
                execution_id = str(
                    row["execution_id"]
                )

                created_at = row["created_at"]

                if pd.notna(created_at):
                    date_text = created_at.strftime(
                        "%d/%m/%Y %H:%M"
                    )
                else:
                    date_text = "No disponible"

                platform = escape(
                    str(row["platform"])
                )
                execution_number = row[
                    "execution_number"
                ]

                execution_number_text = (
                    str(int(execution_number))
                    if pd.notna(execution_number)
                    else "—"
                )

                model_display = str(
                    row["model_display"]
                )

                if "/" in model_display:
                    history_model = (
                        model_display.split("/")[-1]
                    )
                else:
                    history_model = model_display

                history_model = escape(
                    history_model
                )
                status = str(
                    row["status"]
                )

                status_text = escape(
                    str(row["status_label"])
                )

                status_class = {
                    "success": "status-success",
                    "partial": "status-partial",
                    "error": "status-error",
                }.get(
                    status,
                    "status-partial",
                )

                latency = row[
                    "latency_seconds"
                ]

                latency_text = (
                    f"{float(latency):.2f} s"
                    if pd.notna(latency)
                    else "—"
                )

                tokens = row[
                    "total_tokens"
                ]

                tokens_text = (
                    f"{int(tokens):,}"
                    if pd.notna(tokens)
                    else "—"
                )

                cost = row[
                    "cost_usd"
                ]

                cost_text = (
                    f"${float(cost):.6f}"
                    if pd.notna(cost)
                    else "—"
                )
                errors = row[
                    "error_count"
                ]

                errors_text = (
                    str(int(errors))
                    if pd.notna(errors)
                    else "—"
                )

                source_url = str(
                    row["source_url"]
                    or ""
                )

                analysis_url = (
                    f"{app_url}"
                    f"?execution="
                    f"{execution_id}"
                )

                if source_url:
                    source_link = (
                        '<a href="'
                        + escape(
                            source_url,
                            quote=True,
                        )
                        + '" target="_blank">'
                        + "Abrir"
                        + "</a>"
                    )
                else:
                    source_link = "—"

                analysis_link = (
                    '<a href="'
                    + escape(
                        analysis_url,
                        quote=True,
                    )
                    + '">'
                    + "Ver"
                    + "</a>"
                )

                rows.append(
                    "<tr>"
                    "<td>"
                    f"{date_text}"
                    '<div class="history-secondary">'
                    f"N.º {execution_number_text}"
                    "</div>"
                    "</td>"
                    "<td>"
                    f"{platform}"
                    '<div class="history-secondary">'
                    f"{history_model}"
                    "</div>"
                    "</td>"
                    "<td>"
                    f'<span class="status-badge {status_class}">'
                    f"{status_text}"
                    "</span>"
                    "</td>"
                    f"<td>{latency_text}</td>"
                    f"<td>{tokens_text}</td>"
                    f"<td>{cost_text}</td>"
                    f"<td>{errors_text}</td>"
                    f"<td>{source_link}</td>"
                    f"<td>{analysis_link}</td>"
                    "</tr>"
                )

            history_html = (
                '<div class="history-wrapper">'
                '<table class="history-table">'
                "<thead>"
                "<tr>"
                "<th>Fecha</th>"
                "<th>Plataforma</th>"
                "<th>Estado</th>"
                "<th>Latencia</th>"
                "<th>Tokens</th>"
                "<th>Costo</th>"
                "<th>Errores</th>"
                "<th>Fuente</th>"
                "<th>Análisis</th>"
                "</tr>"
                "</thead>"
                "<tbody>"
                f"{''.join(rows)}"
                "</tbody>"
                "</table>"
                "</div>"
            )

            st.html(
                history_html
            )

            if total_pages > 1:
                st.caption(
                    f"Mostrando registros "
                    f"{start + 1}–"
                    f"{min(end, total_rows)} "
                    f"de {total_rows}."
                )

    with detail_tab:
        st.markdown(
            """
            <div class="llmops-section">
                <div class="llmops-section-title">
                    Detalle de ejecución
                </div>
                <div class="llmops-section-description">
                    Consulte la telemetría completa de
                    una ejecución individual.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        detail_frame = frame.sort_values(
            "created_at",
            ascending=False,
        ).copy()

        detail_options: dict[str, str] = {}

        for _, row in detail_frame.iterrows():
            execution_id = str(
                row["execution_id"]
            )

            short_id = execution_id[:8]
            execution_number = row[
                "execution_number"
            ]

            execution_number_text = (
                str(int(execution_number))
                if pd.notna(execution_number)
                else "—"
            )
            created_at = row[
                "created_at"
            ]

            if pd.notna(created_at):
                date_text = (
                    created_at.strftime(
                        "%d/%m/%Y %H:%M"
                    )
                )
            else:
                date_text = (
                    "Fecha no disponible"
                )

            label = (
                f"N.º {execution_number_text} · "
                f"{row['platform']} · "
                f"{date_text} · "
                f"{short_id}"
            )

            detail_options[
                label
            ] = execution_id

        selected_label = st.selectbox(
            "Seleccionar ejecución",
            options=list(
                detail_options.keys()
            ),
            key="execution_detail_selector",
        )

        selected_execution_id = (
            detail_options[
                selected_label
            ]
        )

        selected_execution = (
            detail_frame[
                detail_frame[
                    "execution_id"
                ].astype(str)
                == selected_execution_id
            ]
            .iloc[0]
        )

        analysis_detail = get_analysis_execution_detail(
            selected_execution_id
        )

        selected_execution_number = (
            selected_execution[
                "execution_number"
            ]
        )

        selected_execution_number_text = (
            str(
                int(
                    selected_execution_number
                )
            )
            if pd.notna(
                selected_execution_number
            )
            else "—"
        )

        selected_provider = escape(
            str(
                selected_execution[
                    "provider_display"
                ]
            )
        )

        selected_model = escape(
            str(
                selected_execution[
                    "model_display"
                ]
            )
        )

        platform_detail = escape(
            str(
                selected_execution[
                    "platform"
                ]
            )
        )

        execution_info_html = (
            '<div class="execution-info">'
            '<div class="execution-info-platform">'
            f'{platform_detail}'
            '</div>'
            '<div class="execution-info-id">'
            'Ejecución N.º: '
            f'{selected_execution_number_text}'
            '&nbsp;&nbsp;·&nbsp;&nbsp;'
            'Proveedor: '
            f'{selected_provider}'
            '&nbsp;&nbsp;·&nbsp;&nbsp;'
            'Modelo: '
            f'{selected_model}'
            '</div>'
            '<div class="execution-info-id">'
            'ID: '
            f'{escape(selected_execution_id)}'
            '</div>'
            '</div>'
        )

        st.markdown(
            execution_info_html,
            unsafe_allow_html=True,
        )

        primary_detail = st.columns(4)

        primary_detail[0].metric(
            "Estado",
            str(
                selected_execution[
                    "status_label"
                ]
            ),
        )

        primary_detail[1].metric(
            "Latencia",
            (
                f"{float(selected_execution['latency_seconds']):.2f} s"
                if pd.notna(
                    selected_execution[
                        "latency_seconds"
                    ]
                )
                else "No disponible"
            ),
        )

        selected_cost = (
            selected_execution[
                "cost_usd"
            ]
        )

        primary_detail[2].metric(
            "Costo",
            (
                f"${float(selected_cost):.6f}"
                if pd.notna(
                    selected_cost
                )
                else "No reportado"
            ),
        )

        primary_detail[3].metric(
            "Errores",
            (
                f"{int(selected_execution['error_count'] or 0)}"
            ),
        )

        st.markdown("#### Consumo del modelo")

        token_columns = st.columns(4)

        token_columns[0].metric(
            "Tokens entrada",
            f"{int(selected_execution['prompt_tokens'] or 0):,}",
        )

        token_columns[1].metric(
            "Tokens salida",
            f"{int(selected_execution['completion_tokens'] or 0):,}",
        )

        token_columns[2].metric(
            "Tokens totales",
            f"{int(selected_execution['total_tokens'] or 0):,}",
        )

        token_columns[3].metric(
            "Invocaciones LLM",
            f"{int(selected_execution['llm_invocation_count'] or 0):,}",
        )

        st.markdown("#### Procesamiento contractual")

        if isinstance(
            analysis_detail,
            dict,
        ):
            total_clauses = int(
                analysis_detail.get(
                    "total_clauses",
                    0,
                )
                or 0
            )

            analyzed_clauses = int(
                analysis_detail.get(
                    "analyzed_clauses",
                    0,
                )
                or 0
            )

            successful_clauses = int(
                analysis_detail.get(
                    "successful_clauses",
                    0,
                )
                or 0
            )

            failed_clauses = int(
                analysis_detail.get(
                    "failed_clauses",
                    0,
                )
                or 0
            )

            failure_rate = (
                failed_clauses
                / analyzed_clauses
                * 100
                if analyzed_clauses > 0
                else None
            )

            clause_metrics = st.columns(5)

            clause_metrics[0].metric(
                "Cláusulas totales",
                f"{total_clauses:,}",
            )

            clause_metrics[1].metric(
                "Analizadas",
                f"{analyzed_clauses:,}",
            )

            clause_metrics[2].metric(
                "Exitosas",
                f"{successful_clauses:,}",
            )

            clause_metrics[3].metric(
                "Fallidas",
                f"{failed_clauses:,}",
            )

            clause_metrics[4].metric(
                "Tasa de fallo",
                (
                    f"{failure_rate:.2f} %"
                    if failure_rate is not None
                    else "No aplica"
                ),
                help=(
                    "Porcentaje de cláusulas cuyo análisis "
                    "no pudo completarse satisfactoriamente "
                    "respecto de las cláusulas analizadas."
                ),
            )

        else:
            st.info(
                "No existe un análisis contractual persistido "
                "para calcular las métricas por cláusula."
            )
        st.markdown("#### Información de origen")

        source_url = str(
            selected_execution[
                "source_url"
            ]
            or ""
        )

        detail_info = st.columns(
            [1, 2]
        )

        detail_info[0].markdown(
            "**Plataforma**"
        )

        detail_info[1].write(
            selected_execution[
                "platform"
            ]
        )

        detail_info = st.columns(
            [1, 2]
        )

        detail_info[0].markdown(
            "**Fecha**"
        )

        detail_created_at = (
            selected_execution[
                "created_at"
            ]
        )

        if pd.notna(
            detail_created_at
        ):
            detail_date = (
                detail_created_at.strftime(
                    "%d/%m/%Y %H:%M:%S "
                    "UTC-5"
                )
            )
        else:
            detail_date = (
                "No disponible"
            )

        detail_info[1].write(
            detail_date
        )

        detail_info = st.columns(
            [1, 2]
        )

        detail_info[0].markdown(
            "**URL fuente**"
        )

        if source_url:
            detail_info[1].markdown(
                f"[{source_url}]"
                f"({source_url})"
            )
        else:
            detail_info[1].write(
                "No disponible"
            )

        st.divider()

        analysis_url = (
            f"{app_url}"
            f"?execution="
            f"{selected_execution_id}"
        )

        st.link_button(
            "Abrir reporte completo",
            analysis_url,
            use_container_width=True,
        )

st.set_page_config(
    page_title="Análisis de Términos de Servicio",
    layout="wide",
)

st.markdown(
    """
    <style>
        .stApp {
            background-color: #f7f7f8;
        }

        /* Oculta elementos propios de Streamlit */
        header[data-testid="stHeader"] {
            display: none;
        }

        [data-testid="stToolbar"] {
            display: none;
        }

        [data-testid="stDecoration"] {
            display: none;
        }

        #MainMenu {
            visibility: hidden;
        }

        footer {
            visibility: hidden;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1.4rem;
            padding-bottom: 4rem;
        }

        .app-brand {
            padding-top: 0.25rem;
        }

        .app-brand-title {
            color: #252525;
            font-size: 1.15rem;
            font-weight: 700;
            line-height: 1.25;
        }

        .app-brand-subtitle {
            color: #64748B;
            font-size: 0.83rem;
            margin-top: 0.2rem;
        }

        .top-navigation-divider {
            height: 1px;
            background-color: #E5E7EB;
            margin-top: 0.65rem;
            margin-bottom: 1.6rem;
        }

        h1 {
            color: #8f1d2c;
            font-weight: 650;
        }

        h2, h3, h4 {
            color: #252525;
        }

        div[data-testid="stForm"] {
            background-color: #ffffff;
            border: 1px solid #dedede;
            border-top: 4px solid #8f1d2c;
            border-radius: 8px;
            padding: 1.25rem;
        }

        div[data-testid="stFormSubmitButton"] button {
            background-color: #8f1d2c;
            color: #ffffff;
            border-color: #8f1d2c;
            border-radius: 6px;
            font-weight: 600;
        }

        div[data-testid="stFormSubmitButton"] button:hover {
            background-color: #741724;
            color: #ffffff;
            border-color: #741724;
        }

        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #dddddd;
            border-radius: 7px;
            padding: 1rem;
        }

        div[data-testid="stExpander"] {
            background-color: #ffffff;
            border: 1px solid #dddddd;
            border-radius: 7px;
            margin-bottom: 0.55rem;
        }

        .plain-contract-text {
            font-family: inherit;
            font-size: 1rem;
            font-style: normal;
            line-height: 1.65;
            color: #252525;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            word-break: normal;
            margin-bottom: 1rem;
        }


        .contract-fragment {
            background-color: #F8FAFC;
            border-left: 4px solid #CBD5E1;
            border-radius: 6px;
            padding: 0.9rem 1rem;
            margin-top: 0.35rem;
            margin-bottom: 1.2rem;
            color: #374151;
            font-size: 0.95rem;
            line-height: 1.65;
        }


        .recommendation-box {
            background-color: #F3F7FB;
            border-left: 4px solid #B8C7D9;
            border-radius: 6px;
            padding: 0.85rem 1rem;
            margin-top: 1rem;
            margin-bottom: 1rem;
            color: #334155;
            line-height: 1.6;
        }

        .recommendation-title {
            font-weight: 700;
            color: #334155;
            margin-bottom: 0.35rem;
        }


        .clause-metadata {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 0.7rem;
            margin-top: 0.2rem;
            margin-bottom: 1.25rem;
        }

        .metadata-item {
            background-color: #FAFBFC;
            border: 1px solid #E5E7EB;
            border-radius: 6px;
            padding: 0.7rem 0.85rem;
        }

        .metadata-full {
            grid-column: 1 / -1;
        }

        .metadata-label {
            color: #64748B;
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.025em;
            margin-bottom: 0.2rem;
        }

        .metadata-value {
            color: #1F2937;
            font-size: 0.95rem;
            line-height: 1.45;
        }

        @media (max-width: 700px) {
            .clause-metadata {
                grid-template-columns: 1fr;
            }

            .metadata-full {
                grid-column: auto;
            }
        }


        .no-legal-basis {
            color: #64748B;
            font-size: 0.88rem;
            font-style: italic;
            margin-top: 0.45rem;
            margin-bottom: 0.4rem;
        }


        .analysis-source-card {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 1rem;
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 0.85rem 1rem;
            margin-bottom: 1rem;
        }

        .analysis-source-label {
            color: #64748B;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.025em;
            margin-bottom: 0.15rem;
        }

        .analysis-source-value {
            color: #1F2937;
            font-size: 0.95rem;
            line-height: 1.4;
            overflow-wrap: anywhere;
        }

        .analysis-source-value a {
            color: #426B8A;
            text-decoration: none;
        }

        .analysis-source-value a:hover {
            text-decoration: underline;
        }

        .analysis-metric-card {
            border: 1px solid;
            border-radius: 9px;
            padding: 0.75rem 0.9rem;
            min-height: 88px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .analysis-metric-label {
            font-size: 0.86rem;
            font-weight: 600;
            margin-bottom: 0.3rem;
        }

        .analysis-metric-value {
            font-size: 1.8rem;
            font-weight: 700;
            line-height: 1;
        }

        @media (max-width: 700px) {
            .analysis-source-card {
                grid-template-columns: 1fr;
            }
        }

        .dashboard-section-heading {
            margin-top: 2rem;
            margin-bottom: 1rem;
        }

        .dashboard-section-title {
            color: #252525;
            font-size: 1.25rem;
            font-weight: 700;
            line-height: 1.3;
        }

        .dashboard-section-description {
            color: #64748B;
            font-size: 0.88rem;
            margin-top: 0.2rem;
        }

        .dashboard-kpi-card {
            background-color: #ffffff;
            border: 1px solid #E2E8F0;
            border-top: 3px solid #8f1d2c;
            border-radius: 9px;
            padding: 0.9rem 1rem;
            min-height: 125px;
        }

        .dashboard-kpi-label {
            color: #64748B;
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }

        .dashboard-kpi-value {
            color: #1F2937;
            font-size: 1.7rem;
            font-weight: 700;
            line-height: 1.2;
            margin-top: 0.4rem;
        }

        .dashboard-kpi-description {
            color: #94A3B8;
            font-size: 0.75rem;
            line-height: 1.35;
            margin-top: 0.35rem;
        }

        .execution-detail-card {
            background-color: #ffffff;
            border: 1px solid #E2E8F0;
            border-left: 4px solid #8f1d2c;
            border-radius: 8px;
            padding: 0.8rem 1rem;
            margin-bottom: 1rem;
        }

        .execution-detail-platform {
            color: #1F2937;
            font-size: 1rem;
            font-weight: 700;
        }

        .execution-detail-id {
            color: #64748B;
            font-size: 0.78rem;
            margin-top: 0.2rem;
            overflow-wrap: anywhere;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

brand_column, navigation_column = st.columns(
    [1.6, 1]
)

with brand_column:
    st.markdown(
        """
        <div class="app-brand">
            <div class="app-brand-title">
                Sistema Multiagente LLMOps
            </div>
            <div class="app-brand-subtitle">
                Análisis automatizado de Términos de Servicio SaaS
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with navigation_column:
    if st.query_params.get("execution"):
        st.session_state["main_navigation"] = "Análisis"

    if "main_navigation" not in st.session_state:
        st.session_state["main_navigation"] = "Análisis"

    view = st.segmented_control(
        "Navegación principal",
        (
            "Análisis",
            "Dashboard LLMOps",
        ),
        key="main_navigation",
        label_visibility="collapsed",
    )

    if view is None:
        view = "Análisis"

    if view is None:
        view = "Análisis"

    st.markdown(
        '<div class="top-navigation-divider"></div>',
        unsafe_allow_html=True,
    )

if view == "Análisis":
    with st.form("analysis_form"):
        url = st.text_input(
            "URL de los Términos de Servicio",
            placeholder="https://ejemplo.com/terms",
        )

        submitted = st.form_submit_button(
            "Analizar términos"
        )


    if submitted:
        normalized_url = url.strip()

        if not is_valid_url(normalized_url):
            st.error(
                "Ingrese una URL válida que utilice HTTP o HTTPS."
            )
        else:
            with st.status(
                "Procesando los Términos de Servicio...",
                expanded=True,
            ) as processing_status:
                status_message = st.empty()

                status_message.write(
                    "El sistema está ejecutando el flujo multiagente. "
                    "Este proceso puede tardar algunos minutos."
                )

                try:
                    response = httpx.post(
                        API_ANALYSIS_URL,
                        json={
                            "url": normalized_url,
                        },
                        timeout=httpx.Timeout(
                            None,
                            connect=10.0,
                        ),
                    )

                    response.raise_for_status()

                    analysis_result = response.json()
                    st.session_state.analysis_result = analysis_result

                    report = analysis_result.get("report")

                    if isinstance(report, dict):
                        prepare_report_downloads(
                            report
                        )

                    pipeline_status = analysis_result.get("status")

                    execution_id = analysis_result.get(
                        "execution_id"
                    )

                    if (
                        pipeline_status in {"success", "partial"}
                        and isinstance(execution_id, str)
                        and execution_id
                    ):
                        st.query_params["execution"] = (
                            execution_id
                        )
                        st.session_state.loaded_execution_id = (
                            execution_id
                        )

                    if pipeline_status == "success":
                        status_message.write(
                            "El procesamiento multiagente "
                            "finalizó correctamente."
                        )
                        processing_status.update(
                            label="Análisis completado",
                            state="complete",
                            expanded=False,
                        )

                    elif pipeline_status == "partial":
                        status_message.write(
                            "El procesamiento finalizó con "
                            "resultados parciales."
                        )
                        processing_status.update(
                            label="Análisis completado parcialmente",
                            state="complete",
                            expanded=False,
                        )

                    elif pipeline_status == "error":
                        status_message.write(
                            "El procesamiento no pudo "
                            "completarse correctamente."
                        )
                        processing_status.update(
                            label="El análisis no pudo completarse",
                            state="error",
                            expanded=True,
                        )

                    else:
                        status_message.write(
                            "El backend devolvió un estado "
                            "final no esperado."
                        )
                        processing_status.update(
                            label="Estado del análisis no reconocido",
                            state="error",
                            expanded=True,
                        )

                except httpx.HTTPStatusError as error:
                    status_message.write(
                        "El procesamiento multiagente "
                        "se interrumpió."
                    )

                    processing_status.update(
                        label="El análisis no pudo completarse",
                        state="error",
                        expanded=True,
                    )

                    st.error(
                        "El backend rechazó la solicitud. "
                        f"Código HTTP: "
                        f"{error.response.status_code}"
                    )

                except httpx.RequestError:
                    status_message.write(
                        "No fue posible completar "
                        "el procesamiento."
                    )

                    processing_status.update(
                        label=(
                            "No fue posible completar "
                            "el análisis"
                        ),
                        state="error",
                        expanded=True,
                    )

                    st.error(
                        "No fue posible establecer comunicación "
                        "con el servicio de análisis."
                    )


    execution_query = st.query_params.get(
        "execution"
    )

    if (
        isinstance(execution_query, str)
        and execution_query
        and st.session_state.get(
            "loaded_execution_id"
        )
        != execution_query
    ):
        if not is_valid_execution_id(
            execution_query
        ):
            st.error(
                "El identificador de análisis de la URL "
                "no tiene un formato válido."
            )
            st.session_state.loaded_execution_id = (
                execution_query
            )
        elif load_persisted_analysis(
            execution_query
        ):
            st.session_state.loaded_execution_id = (
                execution_query
            )


    analysis_result = st.session_state.get(
        "analysis_result"
    )

    if isinstance(
        analysis_result,
        dict,
    ):
        render_analysis_results(
            analysis_result
        )

else:
    st.title("Dashboard LLMOps")
    st.write(
        "Monitoreo de latencia, costos, tokens y errores "
        "de las ejecuciones del sistema."
    )

    dashboard_data = load_llmops_dashboard(
        limit=200
    )

    if dashboard_data is None:
        st.info(
            "No fue posible cargar las métricas LLMOps."
        )
    else:
        render_llmops_dashboard(
            dashboard_data
        )
