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
                reused_datetime = datetime.fromisoformat(
                    reused_at.replace("Z", "+00:00")
                )
                formatted_date = reused_datetime.strftime(
                    "%d/%m/%Y %H:%M"
                )
            except ValueError:
                formatted_date = reused_at

            message += (
                f"\n\nFecha del análisis: {formatted_date}"
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
    """Muestra métricas históricas reales del sistema LLMOps."""

    executions = data.get("executions", [])

    if not isinstance(executions, list):
        executions = []

    valid_executions = [
        execution
        for execution in executions
        if isinstance(execution, dict)
    ]

    average_latency_ms = float(
        data.get("average_latency_ms", 0.0) or 0.0
    )

    total_cost_usd = data.get("total_cost_usd")

    cost_label = (
        f"${float(total_cost_usd):.6f}"
        if isinstance(total_cost_usd, (int, float))
        and not isinstance(total_cost_usd, bool)
        else "No reportado"
    )

    error_rate = float(
        data.get("error_rate_percent", 0.0) or 0.0
    )

    total_executions = int(
        data.get("total_executions", 0) or 0
    )

    prompt_tokens = sum(
        int(execution.get("prompt_tokens", 0) or 0)
        for execution in valid_executions
    )

    completion_tokens = sum(
        int(execution.get("completion_tokens", 0) or 0)
        for execution in valid_executions
    )

    invocation_count = sum(
        int(
            execution.get(
                "llm_invocation_count",
                0,
            )
            or 0
        )
        for execution in valid_executions
    )

    st.caption(
        "Indicadores calculados sobre las ejecuciones "
        "recientes persistidas en PostgreSQL."
    )

    st.subheader("Indicadores principales")

    primary_metrics = st.columns(3)

    primary_metrics[0].metric(
        "Latencia promedio",
        f"{average_latency_ms / 1000:.2f} s",
    )

    primary_metrics[1].metric(
        "Costo acumulado reportado",
        cost_label,
    )

    primary_metrics[2].metric(
        "Tasa de error",
        f"{error_rate:.2f} %",
        help=(
            "Porcentaje de ejecuciones de la ventana histórica "
            "que registraron al menos un error."
        ),
    )

    secondary_metrics = st.columns(4)

    secondary_metrics[0].metric(
        "Ejecuciones analizadas",
        total_executions,
    )

    secondary_metrics[1].metric(
        "Tokens de entrada",
        f"{prompt_tokens:,}",
    )

    secondary_metrics[2].metric(
        "Tokens de salida",
        f"{completion_tokens:,}",
    )

    secondary_metrics[3].metric(
        "Invocaciones LLM",
        f"{invocation_count:,}",
    )

    st.metric(
        "Tokens totales",
        f"{int(data.get('total_tokens', 0) or 0):,}",
    )

    if not valid_executions:
        st.info(
            "Todavía no existen ejecuciones persistidas "
            "para construir el histórico."
        )
        return

    frame = pd.DataFrame(valid_executions)

    frame["created_at"] = pd.to_datetime(
        frame["created_at"],
        errors="coerce",
        utc=True,
    )

    numeric_columns = (
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

    frame = frame.sort_values(
        "created_at",
    ).reset_index(drop=True)

    frame["execution"] = [
        f"Ejecución {index}"
        for index in range(
            1,
            len(frame) + 1,
        )
    ]

    frame["latency_seconds"] = (
        frame["duration_ms"] / 1000
    )

    st.divider()
    st.subheader("Evolución histórica")

    first_chart_row = st.columns(2)

    with first_chart_row[0]:
        st.markdown("#### Latencia por ejecución")

        latency_chart = (
            frame.set_index("execution")[
                ["latency_seconds"]
            ]
            .rename(
                columns={
                    "latency_seconds": "Latencia (s)",
                }
            )
        )

        st.line_chart(
            latency_chart,
        )

    with first_chart_row[1]:
        st.markdown("#### Costo por ejecución")

        if frame["cost_usd"].notna().any():
            cost_chart = (
                frame.set_index("execution")[
                    ["cost_usd"]
                ]
                .rename(
                    columns={
                        "cost_usd": "Costo USD",
                    }
                )
            )

            st.bar_chart(
                cost_chart,
            )
        else:
            st.info(
                "El proveedor no reportó costos "
                "para estas ejecuciones."
            )

    second_chart_row = st.columns(2)

    with second_chart_row[0]:
        st.markdown("#### Tokens por ejecución")

        tokens_chart = (
            frame.set_index("execution")[
                [
                    "prompt_tokens",
                    "completion_tokens",
                ]
            ]
            .rename(
                columns={
                    "prompt_tokens": "Entrada",
                    "completion_tokens": "Salida",
                }
            )
        )

        st.bar_chart(
            tokens_chart,
        )

    with second_chart_row[1]:
        st.markdown("#### Errores por ejecución")

        errors_chart = (
            frame.set_index("execution")[
                ["error_count"]
            ]
            .rename(
                columns={
                    "error_count": "Errores",
                }
            )
        )

        st.bar_chart(
            errors_chart,
        )

    st.divider()
    st.subheader("Ejecuciones recientes")

    status_labels = {
        "success": "Exitosa",
        "partial": "Parcial",
        "error": "Error",
    }

    table = frame.sort_values(
        "created_at",
        ascending=False,
    ).copy()

    table["Fecha"] = table["created_at"].dt.strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    table["Estado"] = table["status"].map(
        status_labels
    ).fillna(
        table["status"]
    )

    table["Latencia"] = table[
        "latency_seconds"
    ].map(
        lambda value: f"{value:.2f} s"
    )

    table["Costo USD"] = table[
        "cost_usd"
    ].map(
        lambda value: (
            f"${value:.6f}"
            if pd.notna(value)
            else "No reportado"
        )
    )

    table = table[
        [
            "execution_id",
            "Fecha",
            "Estado",
            "Latencia",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "Costo USD",
            "error_count",
            "llm_invocation_count",
        ]
    ].rename(
        columns={
            "execution_id": "Execution ID",
            "prompt_tokens": "Tokens entrada",
            "completion_tokens": "Tokens salida",
            "total_tokens": "Tokens totales",
            "error_count": "Errores",
            "llm_invocation_count": "Invocaciones LLM",
        }
    )

    st.dataframe(
        table,
        hide_index=True,
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

        .block-container {
            max-width: 1180px;
            padding-top: 2.5rem;
            padding-bottom: 4rem;
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

    </style>
    """,
    unsafe_allow_html=True,
)

view = st.sidebar.radio(
    "Navegación",
    (
        "Análisis",
        "Dashboard LLMOps",
    ),
)

if view == "Análisis":
    st.title("Análisis de Términos de Servicio")

    st.write(
        "Sistema multiagente para detectar cláusulas "
        "potencialmente abusivas en plataformas SaaS."
    )

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

    dashboard_data = load_llmops_dashboard()

    if dashboard_data is None:
        st.info(
            "No fue posible cargar las métricas LLMOps."
        )
    else:
        render_llmops_dashboard(
            dashboard_data
        )
